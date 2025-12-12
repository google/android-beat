"""The module to manage audio recording on the local device or remote Raspberry Pi.

For local audio recording, the audio recorder will be started on the local host.

.. code-block:: python

  recorder = audio_recorder.AudioRecorder()
  recorder.start(
      prefix='audio_recording',
      sample_rate=8000,
      sample_format='S16_LE',
      capture_device_name='hw:0,1',
      log_dir='local_log_dir',
  )
  ...
  recorder.stop()
  recording_file = recorder.recording_filename

For remote audio recording, user should provide a SSH connection instance, and
the audio recorder will be started on the remote host via SSH.

.. code-block:: python
  recorder = audio_recorder.AudioRecorder(ssh_connection)
  recorder.start(
      prefix='audio_recording',
      sample_rate=8000,
      sample_format='S16_LE',
      capture_device_name='hw:0,1',
  )
  ...
  recorder.stop()
  # Pulls the recording file from the remote host to the local host.
  ssh_connection.pull(recorder.recording_filename, local_path)
"""

import dataclasses
import logging
import pathlib
import re
import shlex
import subprocess
import tempfile
import time
from typing import Any

from mobly import logger as mobly_logger
from mobly import utils

from android_beat.platforms.cros.lib import ssh as ssh_lib


# Error messages used in this module.
_START_RECORDER_IS_RUNNIN_MSG = (
    'Cannot start audio recording because recorder is running'
)
_RECORDER_STARTUP_TIMEOUT_MSG = (
    'Timeout expired when waiting on the output of the audio recorder startup'
    ' process.'
)
_RECORDER_DIES_DURING_STARTUP_MSG = (
    'The audio recorder crashed during startup. Check the log of the recorder.'
)
_RECORDER_NOT_STARTED_MSG = (
    'Audio recorder has not been started. Please call `start()` first.'
)
_RECORDER_NO_DURATION_MSG = (
    'Audio recorder has not been started with a duration and is running'
    ' indefinitely. Please use `stop()` to stop the recorder.'
)

# The pattern used to filter the audio interface information
_CAPTURE_HARDWARE_DEVICE_PATTERN = re.compile(
    'card (?P<card_num>[0-9]+): (?P<card_name>.+), '
    'device (?P<device_num>[0-9]+): (?P<device_name>.+)'
)

# The file path pattern of the audio recording in test device
_RECORDING_FILENAME_PATTERN = '{prefix},{capture_device},{timestamp}.wav'
_RECORDING_REMOTE_DIRCTORY = '/tmp'

# The pattern used to filter the log indicating that the recorder has started
_WAIT_FOR_RECORDING_PATTERN = 'Recording WAVE'

# Maximum time to wait for the audio recorder to be ready
_RECORDER_STARTUP_TIMEOUT_SEC = 60

_DEFAULT_CAPTURE_DEVICE_NAME = 'default'
_DEFAULT_RECORDING_CHANNEL = 1


class AudioRecorderBaseError(Exception):
  """Base error class for audio_recorder module."""


class AudioRecorderStartupError(AudioRecorderBaseError):
  """The audio recorder encounters error during startup."""


class AudioRecorderRuntimeError(AudioRecorderBaseError):
  """The audio recorder encounters error during runtime."""


class AudioDeviceNotAvailableError(AudioRecorderBaseError):
  """The audio device is not available."""


@dataclasses.dataclass
class CaptureDevice:
  """A container to collect capture hardware device information.

  Attributes:
    card_num: The card number of the PCM device.
    card_name: The card name of the PCM device.
    device_num: The device number of the PCM device.
    device_name: The device name of the PCM device.
  """

  card_num: int
  card_name: str
  device_num: int
  device_name: str

  def is_valid_pcm_name(self, pcm_name: str) -> bool:
    """Returns if the PCM name is a valid name of the capture device."""
    return pcm_name == self.hw_name or pcm_name == self.plughw_name

  @property
  def hw_name(self) -> str:
    """Returns the hw name of the capture device.

    The ALSA hw device description uses the hw plugin, which is a raw
    communication without any conversions.
    https://www.alsa-project.org/alsa-doc/alsa-lib/pcm.html

    Returns:
      The hw name of the capture device.
    """
    return f'hw:{self.card_num},{self.device_num}'

  @property
  def plughw_name(self) -> str:
    """Returns the plughw name of the capture device.

    The plughw device description uses the plug plugin and hw plugin as slave.
    Plug plugin is an automatic conversion plugin, which converts channels, rate
    and format on request.
    https://www.alsa-project.org/alsa-doc/alsa-lib/pcm.html
    https://www.alsa-project.org/alsa-doc/alsa-lib/pcm_plugins.html

    Returns:
      The plughw name of the capture device.
    """
    return f'plughw:{self.card_num},{self.device_num}'

  @property
  def detail(self) -> str:
    """Returns the detailed information of the capture device."""
    return (
        f'card {self.card_num}: {self.card_name}, '
        f'device {self.device_num}: {self.device_name}'
    )


@dataclasses.dataclass
class AudioRecorderConfig:
  """The configuration of the audio recorder."""

  prefix: str
  capture_device: str
  channels: int
  duration: float | None
  sample_rate: int
  sample_format: str


class AudioRecorder:
  """The module to record the audio output of the device.

  This module records the audio output from the local or remote host in a WAV
  file.

  This module uses `arecord`, a command-line sound recorder for Advanced Linux
  Sound Architecture(ALSA) soundcard driver like PulseAudio and Pipewire. Can
  also use a hardware capture device as audio input, eg. a USB sound card. The
  audio capture device can be specified by `capture_device_name` param in
  `start()`.

  Make sure the audio capture device is available. Run the following commands
  to grant the current user permission to access the audio device.
  .. code-block:: shell

   sudo usermod -a -G adm $USER
   sudo chmod a+rw /dev/snd/*
   sudo chmod a+rw /dev/snd/control*

  Attributes:
    is_alive: True if the audio recorder is running; False otherwise.
    recording_filename: The filename of the sudio recording.
    recorder_log_filename: The filename of the recorder log.
  """

  _ssh: ssh_lib.SSHProxy | None = None
  _recorder_process: ssh_lib.RemotePopen | subprocess.Popen[Any] | None = None
  _config: AudioRecorderConfig | None = None

  recording_filename: pathlib.Path | None = None
  recorder_log_filename: pathlib.Path | None = None

  def __init__(self, ssh: ssh_lib.SSHProxy | None = None) -> None:
    """Initializes the AudioRecorder instance.

    Args:
      ssh: The ssh connection to the remote host. If None, the audio recorder
        will be started on the local host.
    """
    self._ssh = ssh

  @property
  def is_alive(self) -> bool:
    """True if the audio recorder is running; False otherwise."""
    return (
        self._recorder_process is not None
        and self._recorder_process.poll() is None
    )

  def start(
      self,
      prefix: str = 'audio',
      capture_device_name: str = _DEFAULT_CAPTURE_DEVICE_NAME,
      channels: int = _DEFAULT_RECORDING_CHANNEL,
      duration: float | None = None,
      sample_rate: int = 44100,
      sample_format: str = 'S16_LE',
      log_dir: str = '',
  ) -> None:
    """Starts audio recording on the test device.

    Args:
      prefix: Prefix of the file name of the recording.
      capture_device_name: The card name or PCM name of hardware capture device
        as audio input.
      channels: The number of channels of the recording.
      duration: The duration of the recording, in seconds. If not None, the
        recording will be stopped autometically after the duration. If None, the
        recording will be stopped by calling `stop()`.
      sample_rate: The sample rate, in Hertz.
      sample_format: The sample format of the recording.
      log_dir: The directory to store the recorder log file on the local host.
        If empty, the recorder log file will be stored in the temp directory.

    Raises:
      AudioRecorderStartupError: Raised when the recorder has been started.
      AudioDeviceNotAvailableError: Raised when the specified audio
        capture device is not available.
    """
    if self.is_alive:
      raise AudioRecorderStartupError(_START_RECORDER_IS_RUNNIN_MSG)

    capture_device = get_capture_device(capture_device_name, self._ssh)
    self._config = AudioRecorderConfig(
        prefix=prefix,
        capture_device=capture_device,
        channels=channels,
        duration=duration,
        sample_rate=sample_rate,
        sample_format=sample_format,
    )

    # From `arecord -h`: A value of zero means infinity.
    duration = duration or 0

    timestamp = mobly_logger.get_log_file_timestamp()
    self.recorder_log_filename = pathlib.Path(
        tempfile.gettempdir() if not log_dir else log_dir,
        f'audio_log_{timestamp}.txt',
    )

    if self._ssh is None:
      # Recording file is saved in the same directory as the recorder log file
      # on the local host if the audio recorder is started locally.
      recording_log_dir = log_dir if log_dir else tempfile.gettempdir()
    else:
      # Recording file is saved to `/tmp` directory on the remote host if the
      # audio recorder is started remotely.
      recording_log_dir = _RECORDING_REMOTE_DIRCTORY
    self.recording_filename = pathlib.Path(
        recording_log_dir,
        _RECORDING_FILENAME_PATTERN.format(
            prefix=prefix,
            capture_device=capture_device,
            timestamp=timestamp,
        ),
    )

    cmd = (
        f'arecord -f {shlex.quote(sample_format)} -r {sample_rate}'
        f' -c {channels} -d {duration} -D {shlex.quote(capture_device)}'
        f' {shlex.quote(str(self.recording_filename))}'
    )

    logging.debug('Start audio recorder')
    if self._ssh is None:
      cmd = f'{cmd} > {shlex.quote(str(self.recorder_log_filename))} 2>&1'
      self._recorder_process = utils.start_standing_subprocess(cmd, shell=True)
    else:
      self._recorder_process = self._ssh.start_remote_process(
          cmd, get_pty=True, output_file_path=str(self.recorder_log_filename)
      )

    self._wait_for_recorder_start(self.recorder_log_filename)
    logging.debug('Audio recorder started')

  def _wait_for_recorder_start(self, host_log_path: pathlib.Path) -> None:
    """Waits for the audio recorder log.

    Args:
      host_log_path: The path of the recorder log file on the host.

    Raises:
      AudioRecorderStartupError: Raised if failed to start the audio recorder.
    """
    deadline_time = time.perf_counter() + _RECORDER_STARTUP_TIMEOUT_SEC
    while deadline_time > time.perf_counter():
      if not self.is_alive:
        self.stop()
        raise AudioRecorderStartupError(_RECORDER_DIES_DURING_STARTUP_MSG)
      try:
        match = re.search(
            _WAIT_FOR_RECORDING_PATTERN,
            open(host_log_path, 'r').read(),
        )
        if match is not None:
          return
      except OSError:
        logging.error('Failed to open the recorder log file. Trying again.')

      logging.debug('Wait 0.5s for recorder startup log file.')
      time.sleep(0.5)

    self.stop()
    raise AudioRecorderStartupError(_RECORDER_STARTUP_TIMEOUT_MSG)

  def stop(self) -> None:
    """Stops the audio recorder."""
    if self.is_alive:
      assert self._recorder_process  # Checked by is_alive.
      logging.debug('Stop audio recorder')
      if self._ssh is None:
        utils.stop_standing_subprocess(self._recorder_process)
      else:
        self._recorder_process.kill()
      logging.debug('Audio recorder stopped')

    self._recorder_process = None

  def wait(self) -> None:
    """Waits for the audio recorder to finish if it is started with a duration."""
    if self._config is None:
      raise AudioRecorderRuntimeError(_RECORDER_NOT_STARTED_MSG)
    if self._config.duration is None:
      raise AudioRecorderRuntimeError(_RECORDER_NO_DURATION_MSG)
    if not self.is_alive:
      return
    assert self._recorder_process  # Checked by is_alive.

    logging.debug('Wait for audio recorder to finish')
    if self._ssh is None:
      utils.wait_for_standing_subprocess(self._recorder_process)
    else:
      self._recorder_process.wait()
    logging.debug('Audio recorder finished')


def list_capture_devices(
    ssh: ssh_lib.SSHProxy | None = None,
) -> list[CaptureDevice]:
  """Lists the capture hardware devices on the local or remote host.

  There can be multiple audio inputs on the Linux-based host, such as built-in
  audio server and external soundcards. https://linux.die.net/man/1/arecord
  To query the audio capture hardware device list, run command `arecord -l`
  on the host.

  Audio recorder supports recording from different sound input by setting
  `capture_device` param in `start()`.
  This method lists all *hardware* devices that can be captured on the local or
  remote host.

  Args:
    ssh: The ssh connection to the remote host. If None, the local host will be
      used.

  Returns:
    A list of CaptureDevice instances of available capture hardware devices.
  """
  if ssh is None:
    _, raw_output, _ = utils.run_command(
        'arecord -l', shell=True, universal_newlines=True
    )
  else:
    try:
      raw_output = ssh.execute_command('arecord -l')
    except ssh_lib.ExecuteCommandError:
      raw_output = ''
      logging.exception('Failed to list capture hardware devices.')

  capture_devices = []
  for matched in _CAPTURE_HARDWARE_DEVICE_PATTERN.finditer(raw_output):
    capture_devices.append(
        CaptureDevice(
            int(matched['card_num']),
            matched['card_name'],
            int(matched['device_num']),
            matched['device_name'],
        )
    )
  return capture_devices


def get_capture_device(
    capture_device_name: str,
    ssh: ssh_lib.SSHProxy | None = None,
) -> str:
  """Returns the given capture device, or raise an error if not found."""
  if capture_device_name == _DEFAULT_CAPTURE_DEVICE_NAME:
    return _DEFAULT_CAPTURE_DEVICE_NAME
  for device in list_capture_devices(ssh):
    if device.is_valid_pcm_name(capture_device_name):
      return capture_device_name
    if device.card_name == capture_device_name:
      return device.hw_name
  raise AudioDeviceNotAvailableError(
      'Failed to record because audio capture hardware device'
      f' is not available: {capture_device_name}'
  )
