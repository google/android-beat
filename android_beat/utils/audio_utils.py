# Copyright 2025 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility functions related to Audio operations."""

from collections.abc import Sequence
import datetime
import enum
import logging
import math
import os
import pathlib
import sys
import time

import librosa
from mobly import asserts
from mobly.controllers import android_device
import numpy
import scipy

from android_beat.platforms.bluetooth import tws_device
from android_beat.utils import test_utils


_AUDIO_CONNECTION_TIMEOUT = datetime.timedelta(seconds=30)
_VOLUME_SETTLE_TIME = datetime.timedelta(seconds=60)
_RECORDING_STATE_TIMEOUT = datetime.timedelta(seconds=30)
_FREQUENCY = 1000.0
_MEDIA_LOCAL_PARENT_PATH = '/sdcard/Download'
_MEDIA_MUSIC_LENGTH = datetime.timedelta(seconds=15)
_VOLUME_DELAY_TIME = datetime.timedelta(seconds=0.3)


@enum.unique
class AudioDeviceType(enum.IntEnum):
  """Type of audio output/input device.

  https://developer.android.com/reference/android/media/AudioDeviceInfo

  Attributes:
    TYPE_BLUETOOTH_SCO: A device type describing a Bluetooth device typically
      used for telephony.
    TYPE_BLUETOOTH_A2DP: A device type describing a Bluetooth device supporting
      the A2DP profile.
    TYPE_BLE_HEADSET: A device type describing a Bluetooth Low Energy (BLE)
      audio headset or headphones. Headphones are grouped with headsets when the
      device is a sink: the features of headsets and headphones with regard to
      playback are the same.
  """

  TYPE_BLUETOOTH_SCO = 7
  TYPE_BLUETOOTH_A2DP = 8
  TYPE_BLE_HEADSET = 26


def wait_and_assert_audio_device_type(
    ad: android_device.AndroidDevice,
    expect_audio_device_type: AudioDeviceType,
    expect_active: bool,
    timeout: datetime.timedelta = _AUDIO_CONNECTION_TIMEOUT,
) -> None:
  """Waits for and asserts audio device type supported on Android device.

  This method waits until the expected audio device type supported on the
  Android device is either active or inactive, matching the value of
  `expect_active`.

  Args:
    ad: The Android device used to check the audio device type.
    expect_audio_device_type: The expected audio device type.
    expect_active: The expected state of the audio device type.
      * True: Expects the audio device type to be active (connected).
      * False: Expects the audio device type to be inactive (disconnected).
    timeout: The maximum time to wait for the audio device type to reach the
      expected state.

  Raises:
    signals.TestFailure: If the audio device type does not match
      `expect_active` within the specified timeout.
  """
  test_utils.wait_until_or_assert(
      condition=lambda: (
          expect_audio_device_type in ad.bt_snippet.getAudioDeviceTypes()
      )
      == expect_active,
      error_msg=(
          f'{ad} Timed out waiting for {expect_audio_device_type.name} to reach'
          f' the {"active" if expect_active else "inactive"} state'
      ),
      timeout=timeout,
  )


def generate_and_push_audio_files(
    ad: android_device.AndroidDevice,
    playlist_files: Sequence[str],
    local_source_audio_path: str,
) -> None:
  """Generates audio files and pushes to the device.

  Args:
    ad: The Android device that needs to push audio files.
    playlist_files: A list of audio file names that need to be generated.
    local_source_audio_path: The path of the local audio file.
  """
  ad.adb.shell(['rm', '-rf', f'{_MEDIA_LOCAL_PARENT_PATH}/*'])
  frequency = _FREQUENCY
  for file_name in playlist_files:
    local_source_audio_path_with_file_name = os.path.join(
        local_source_audio_path, file_name
    )
    ad.log.info(
        'Generating %s with frequency %s',
        local_source_audio_path_with_file_name,
        frequency,
    )
    generate_sine_tone_file(
        frequency,
        magnitude=0.5,
        duration=_MEDIA_MUSIC_LENGTH,
        filename=local_source_audio_path_with_file_name,
    )
    frequency += 500.0
    ad.log.info(
        'Pushing %s to %s',
        local_source_audio_path_with_file_name,
        _MEDIA_LOCAL_PARENT_PATH,
    )
    ad.adb.push(
        [local_source_audio_path_with_file_name, _MEDIA_LOCAL_PARENT_PATH]
    )
    ad.log.info('Pushed %s to %s', file_name, _MEDIA_LOCAL_PARENT_PATH)


def start_audio_recording(
    bt_device: tws_device.TwsDevice,
) -> None:
  """Starts audio recording on the Bluetooth device if the platform is Linux."""
  if sys.platform != 'linux':
    return
  bt_device.start_audio_recording()


def stop_audio_recording(
    bt_device: tws_device.TwsDevice,
    output_path: pathlib.Path,
) -> list[pathlib.Path] | None:
  """Stops audio recording and associates the recorded files retrieved.

  Args:
    bt_device: The Bluetooth device used for recording.
    output_path: The host path to save the recorded audio files.

  Returns:
    A list of paths to the recorded audio files on the host, or None if not on
    Linux.

  Raises:
    signals.TestFailure: If no audio files were recorded.
  """
  if sys.platform != 'linux':
    return None

  recorded_audio_files_on_host = bt_device.stop_audio_recording(
      output_path
  )
  asserts.assert_true(
      recorded_audio_files_on_host,
      'recorded_audio_files_on_host should not be empty. please check the'
      ' audio recording.',
  )
  return recorded_audio_files_on_host


def is_volume_max_after_volume_up(
    ad: android_device.AndroidDevice,
    bt_device: tws_device.TwsDevice,
) -> bool:
  """Waits for volume to be updated to the specified level."""
  bt_device.volume_up()
  time.sleep(_VOLUME_DELAY_TIME.total_seconds())
  return ad.bt_snippet.getMusicVolume() == ad.bt_snippet.getMusicMaxVolume()


def wait_and_assert_volume_up_to_max(
    ad: android_device.AndroidDevice,
    bt_device: tws_device.TwsDevice,
) -> None:
  """Waits for volume to be updated to max."""
  test_utils.wait_until_or_assert(
      condition=lambda: is_volume_max_after_volume_up(ad, bt_device),
      error_msg=(
          'Failed to set volume to max. Current volume:'
          f' {ad.bt_snippet.getMusicVolume()}'
      ),
      timeout=_VOLUME_SETTLE_TIME,
  )


def is_volume_min_after_volume_down(
    ad: android_device.AndroidDevice,
    bt_device: tws_device.TwsDevice,
) -> bool:
  """Waits for volume to be updated to the specified level."""
  bt_device.volume_down()
  time.sleep(_VOLUME_DELAY_TIME.total_seconds())
  return ad.bt_snippet.getMusicVolume() == 0


def wait_and_assert_volume_down_to_min(
    ad: android_device.AndroidDevice,
    bt_device: tws_device.TwsDevice,
) -> None:
  """Waits for volume to be updated to min."""
  test_utils.wait_until_or_assert(
      condition=lambda: is_volume_min_after_volume_down(ad, bt_device),
      error_msg=(
          'Failed to set volume to min. Current volume:'
          f' {ad.bt_snippet.getMusicVolume()}'
      ),
      timeout=_VOLUME_SETTLE_TIME,
  )

SAMPLE_RATE = 44100  # Default audio sample rate.
CROSS_CORRELATION_THRESHOLD = 0.9
SILENCE_THRESHOLD = 0.01  # Amplitude threshold to detect non-silent audio.


def generate_sine_tone_file(
    frequency: float,
    magnitude: float,
    duration: datetime.timedelta,
    filename: str | pathlib.Path,
    sample_rate: int = SAMPLE_RATE,
) -> None:
  """Generates a sinusoidal tone audio file of the given frequency and duration.

  The generated sine tone is a pure sine wave with the given frequency,
  magnitude and duration. This file can be used as a target sound for audio
  detection.

  Args:
    frequency: The frequency of the tone.
    magnitude: The magnitude of the tone.
    duration: Length of the audio to generate, in seconds.
    filename: The file path to save the generated tone file.
    sample_rate: Optional sample rate of the tone.
  """
  samples = int(duration.total_seconds() * sample_rate)
  audio_data = [
      magnitude * math.sin(2 * math.pi * frequency / sample_rate * i)
      for i in range(samples)
  ]
  audio_data_np = numpy.array(audio_data, dtype=numpy.float32)
  scipy.io.wavfile.write(str(filename), sample_rate, audio_data_np)


def detect_audio_start_time(
    target_audio_path: str | pathlib.Path,
    source_audio_path: str | pathlib.Path,
    threshold: float = CROSS_CORRELATION_THRESHOLD,
    window_duration: datetime.timedelta = datetime.timedelta(seconds=3),
) -> datetime.timedelta | None:
  """Detects the start time of a target audio within a source audio.

  This method uses matched filtering to find if the target audio is found in the
  source audio, and outputs the start time.

  Args:
    target_audio_path: Path to the audio file containing the target sound.
    source_audio_path: Path to the audio file to be searched.
    threshold: The threshold value for detection.
    window_duration: The duration of the window to be used for detection.

  Returns:
    The start time of the target audio within the source audio, or None if not
    found.
  """
  # Load the audio files
  target_audio, soundrate = librosa.load(target_audio_path, sr=None)
  source_audio, soundrate_source = librosa.load(source_audio_path, sr=None)

  # Resample the source audio to ensure both audios have the same sample rate
  if soundrate_source != soundrate:
    logging.debug(
        'Resampling the source audio. Target soundrate: %d. Source'
        ' soundrate: %d',
        soundrate,
        soundrate_source,
    )
    source_audio = librosa.resample(
        source_audio, orig_sr=soundrate_source, target_sr=soundrate
    )

  target_len = len(target_audio)
  source_len = len(source_audio)

  if target_len == 0 or source_len == 0:
    logging.error('Target or source audio is empty.')
    return None

  # Trim leading and trailing silence from the target audio
  target_audio_trimmed, index = librosa.effects.trim(target_audio)
  if target_audio_trimmed.size == 0:
    logging.warning('Target audio is completely silent.')
    return None

  logging.info(
      'Target audio trimmed from %d to %d samples. Non-silent interval: %s',
      target_len,
      len(target_audio_trimmed),
      index,
  )
  target_trimmed_len = len(target_audio_trimmed)

  filter_audio = target_audio_trimmed
  filter_len = int(
      min(
          target_trimmed_len,
          source_len,
          soundrate * window_duration.total_seconds(),
      )
  )
  if target_trimmed_len > filter_len:
    logging.info(
        'Trimmed target audio is longer than the window duration (%d seconds).'
        ' Using the first %d samples of trimmed target audio as the filter.',
        window_duration.total_seconds(),
        filter_len,
    )
    filter_audio = target_audio_trimmed[:filter_len]

  # Time-reverse the target audio to create the matched filter
  matched_filter = numpy.flip(filter_audio)

  # Apply the matched filter to source audio use convolution
  response = scipy.signal.convolve(source_audio, matched_filter, mode='valid')
  if response.size == 0:
    logging.error('Convolution result is empty.')
    return None

  # Normalize the response
  max_abs_response = numpy.max(numpy.abs(response))
  if max_abs_response == 0:
    logging.error('Max absolute response is zero, cannot normalize.')
    return None
  normalized_response = response / max_abs_response

  # Check if any value in the response exceeds the threshold
  for i, value in enumerate(normalized_response):
    if value > threshold:
      logging.info('value: %s, threshold: %s', value, threshold)
      logging.info('Found target audio at %d seconds.', i / soundrate)
      return datetime.timedelta(seconds=i / soundrate)
  return None


def find_audio_segment_with_chroma(
    target_audio_path: str | pathlib.Path,
    source_audio_path: str | pathlib.Path,
    threshold: float = 0.8,
) -> datetime.timedelta | None:
  """Finds the start time of a target audio segment within a source audio using chroma features.

  This function compares the chroma features of a target audio against a source
  audio to find potential matches. It uses cross-correlation on the chroma
  features to identify the most similar segment.

  Args:
    target_audio_path: Path to the audio file containing the target sound.
    source_audio_path: Path to the audio file to be searched.
    threshold: The correlation threshold to consider a match valid.

  Returns:
    The start time of the best-matching segment in the source audio as a
    datetime.timedelta, or None if no match is found above the threshold.
  """
  # Load audio files
  y_target, sr_target = librosa.load(target_audio_path, sr=None)
  y_source, sr_source = librosa.load(source_audio_path, sr=None)

  # Ensure sample rates are consistent
  if sr_target != sr_source:
    y_target = librosa.resample(
        y_target, orig_sr=sr_target, target_sr=sr_source
    )
  sr = sr_source

  if y_target.size == 0:
    logging.error('The target audio file is empty.')
    return None
  if y_source.size == 0:
    logging.error('The source audio file is empty.')
    return None

  # Using a larger FFT window helps in better frequency differentiation.
  n_fft = 4096
  hop_length = int(n_fft / 4)

  # Create chroma features for both audio files
  logging.info('y_target.shape: %s', y_target.shape)
  logging.info('y_source.shape: %s', y_source.shape)
  chroma_target = librosa.feature.chroma_stft(
      y=y_target, sr=sr, n_fft=n_fft, hop_length=hop_length
  )
  chroma_source = librosa.feature.chroma_stft(
      y=y_source, sr=sr, n_fft=n_fft, hop_length=hop_length
  )

  logging.info('chroma_target.shape: %s', chroma_target.shape)
  logging.info('chroma_source.shape: %s', chroma_source.shape)
  if chroma_target.shape[1] > chroma_source.shape[1]:
    logging.error('Target chroma is longer than source chroma.')
    return None

  result_len = chroma_source.shape[1] - chroma_target.shape[1] + 1
  correlation = numpy.zeros(result_len)
  for i in range(chroma_target.shape[0]):
    correlation += scipy.signal.correlate(
        chroma_source[i], chroma_target[i], mode='valid', method='fft'
    )

  # Find the best match point
  best_match_frame = numpy.argmax(correlation)
  max_corr_value = correlation[best_match_frame]

  # Normalize the correlation score. This is a simplified normalization that
  # scales the score by the maximum value found in the source chroma features.
  # It helps make the matching less sensitive to the overall signal energy.
  max_abs_response = numpy.max(numpy.abs(chroma_source))
  if max_abs_response == 0:
    logging.error('Max absolute response is zero, cannot normalize.')
    return None
  normalized_response = max_corr_value / max_abs_response

  logging.info('Best feature match score: %.4f', normalized_response)

  if normalized_response > threshold:
    match_time_sec = librosa.frames_to_time(
        best_match_frame, sr=sr, hop_length=hop_length
    )
    return datetime.timedelta(seconds=match_time_sec)
  return None


def assert_has_audio_start_time(
    original_audio_file_on_host: str | pathlib.Path,
    recorded_audio_files_on_host: list[pathlib.Path] | None,
) -> None:
  """Detects the start time of the target audio file in the recorded audio files."""
  if recorded_audio_files_on_host is None:
    return
  asserts.assert_is_not_none(
      detect_audio_start_time(
          recorded_audio_files_on_host[0],
          original_audio_file_on_host,
      ),
      msg=(
          'The audio comparison by frequency is incorrect, possibly because the'
          ' audio did not switch to the corresponding index, or the recording'
          ' on the BES device failed.'
      ),
  )
  asserts.assert_is_not_none(
      find_audio_segment_with_chroma(
          recorded_audio_files_on_host[0],
          original_audio_file_on_host,
      ),
      msg=(
          'The audio comparison by chroma is incorrect, possibly because the'
          ' audio did not switch to the corresponding index, or the recording'
          ' on the BES device failed.'
      ),
  )


def wait_and_assert_recording_has_ble_headset(
    ad: android_device.AndroidDevice,
) -> None:
  """Waits for and asserts BLE headset is ready for recording."""
  test_utils.wait_until_or_assert(
      condition=ad.bt_snippet.mediaHasBleHeadset,
      error_msg='Failed to detect BLE headset.',
      timeout=_RECORDING_STATE_TIMEOUT,
  )
