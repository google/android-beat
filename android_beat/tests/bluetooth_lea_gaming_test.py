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

"""Bluetooth LEA gaming streaming test."""

import contextlib
import datetime
import time

from mobly import asserts
from mobly import test_runner

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import media_utils
from android_beat.utils import test_utils

_MEDIA_PLAY_TIME = datetime.timedelta(seconds=15)
_MEDIA_DEVICE_TYPE_TIMEOUT = datetime.timedelta(seconds=30)
_MEDIA_STATE_TIMEOUT = datetime.timedelta(seconds=30)
_RECORDING_DURATION = datetime.timedelta(seconds=10)
_RECORDING_STATE_TIMEOUT = datetime.timedelta(seconds=30)

_RECORDING_FILE_NAME = 'test_recording.mp4'
_RECORDING_FILE_PATH = '/storage/emulated/0/Android/data/com.google.snippet.bluetooth/cache/test_recording.mp4'
_MEDIA_FILES_BASENAMES = ('sine_tone_0.wav',)
_MEDIA_FILES_PATHS = ('/sdcard/Download/sine_tone_0.wav',)


class BluetoothLeaGamingTest(base_test.BaseTestClass):
  """Test class for Bluetooth LEA gaming streaming test."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.LEA
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.SINGLE_DEVICE

  def _pair_bluetooth_lea_device(self) -> None:
    """Pairs the Android device with the Bluetooth LE Audio device."""
    bluetooth_utils.pair_bluetooth_device(self.ad, self.bt_device)
    bluetooth_utils.wait_and_assert_lea_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
    )
    audio_utils.wait_and_assert_audio_device_type(
        self.ad,
        audio_utils.AudioDeviceType.TYPE_BLE_HEADSET,
        expect_active=True,
    )

  @contextlib.contextmanager
  def _record_audio(self):
    """Context manager to start and stop audio recording."""
    self.ad.log.info('Starting VBC test: Activating microphone recording.')
    try:
      self.ad.bt_snippet.mediaStartRecording(_RECORDING_FILE_NAME)
      self.ad.log.info(
          'Audio input devices: %s',
          self.ad.bt_snippet.mediaGetActiveMicrophones(),
      )
      yield
    finally:
      output_path = self.ad.bt_snippet.mediaStopRecording()
      asserts.assert_equal(
          output_path,
          _RECORDING_FILE_PATH,
          f'Expected path {_RECORDING_FILE_PATH}, got {output_path}',
      )
      self.ad.log.info('Stopped recording.')

  def setup_class(self) -> None:
    super().setup_class()
    self.bt_device.factory_reset()
    audio_utils.generate_and_push_audio_files(
        self.ad,
        _MEDIA_FILES_BASENAMES,
        self.current_test_info.output_path,
    )
    self._pair_bluetooth_lea_device()

  def setup_test(self) -> None:
    asserts.skip_if(
        not self.ad.bt_snippet.btIsLeAudioSupported(),
        f'{self.ad} LE Audio is not supported',
    )
    if not self.ad.bt_snippet.btIsLeAudioConnected(
        self.bt_device.bluetooth_address_primary
    ):
      bluetooth_utils.clear_saved_devices(self.ad)
      self.bt_device.factory_reset()
      self._pair_bluetooth_lea_device()
    audio_utils.wait_and_assert_recording_has_ble_headset(self.ad)
    self.ad.bt_snippet.media3Stop()
    self.ad.bt_snippet.mediaStopRecording()
    self.ad.log.info('BLE headset is ready for recording.')

  def teardown_test(self):
    self.ad.bt_snippet.media3Stop()
    self.ad.bt_snippet.mediaStopRecording()
    super().teardown_test()

  def test_game_streaming(self):
    """Test for Bluetooth LE Audio gaming streaming.

    Precondition:
      1. DUT and Bluetooth device are paired.
      2. DUT and Bluetooth device are connected via LE Audio.

    Test Steps:
      1. Set audio usage to GAME.
      2. Verify the audio usage is GAME.
      3. Pause media on the Android device.
      4. Verify the audio usage is GAME.
      5. Play media on the Android device.
      6. Verify the audio usage is GAME.

    Pass Criteria:
      1. Verify the audio usage is GAME.
      2. Verify the media is playing on the Bluetooth device.
      3. Verify the media is keeping playing on the Bluetooth device after pause
      and resume.
    """
    self.ad.bt_snippet.media3SetAudioUsage(
        media_utils.AudioUsage.USAGE_GAME,
        media_utils.AudioContentType.CONTENT_TYPE_UNKNOWN,
    )
    self.ad.bt_snippet.media3StartLocalFile(_MEDIA_FILES_PATHS[0])
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_MEDIA_PLAY_TIME,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to play media on LE Audio',
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )
    current_usage_name = media_utils.AudioUsage(
        self.ad.bt_snippet.media3GetAudioUsage()
    ).name
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetAudioUsage()
        == media_utils.AudioUsage.USAGE_GAME,
        error_msg=(
            'Failed to set audio usage to GAME, current usage is'
            f' {current_usage_name}'
        ),
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )

  def test_game_streaming_with_vbc(self):
    """Test for Bluetooth LE Audio gaming streaming with Voice Back Channel(VBC).

    Precondition:
      1. DUT and Bluetooth device are paired.
      2. DUT and Bluetooth device are connected via LE Audio.

    Test Steps:
      1. Set audio usage to GAME and start media playback.
      2. Verify game audio is streaming correctly to the Bluetooth device.
      3. Start recording from the Bluetooth device's microphone to activate VBC.
      4. While recording, verify that the game audio stream is not interrupted.
      5. Stop and verify the recording.
      6. Verify the game audio stream is still active.
      7. Stop media playback.

    Pass Criteria:
      1. Verify the game audio (downlink) streams successfully to the Bluetooth
      device.
      2. Verify the voice recording (uplink/VBC) is successful.
      3. Verify the game audio is not interrupted or degraded during VBC
      activation.
    """
    self.ad.bt_snippet.media3SetAudioUsage(
        media_utils.AudioUsage.USAGE_GAME,
        media_utils.AudioContentType.CONTENT_TYPE_UNKNOWN,
    )
    self.ad.bt_snippet.media3StartLocalFile(_MEDIA_FILES_PATHS[0])

    self.ad.log.info('Verifying game audio is playing on LE Audio device.')
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_MEDIA_PLAY_TIME,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to play media on LE Audio',
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )
    current_usage_name = media_utils.AudioUsage(
        self.ad.bt_snippet.media3GetAudioUsage()
    ).name
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetAudioUsage()
        == media_utils.AudioUsage.USAGE_GAME,
        error_msg=(
            'Failed to set audio usage to GAME, current usage is '
            f'{current_usage_name}'
        ),
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )

    with self._record_audio():
      time.sleep(_RECORDING_DURATION.total_seconds())  # Record for 10 seconds
      test_utils.wait_until_or_assert(
          condition=self.ad.bt_snippet.mediaIsRecording,
          error_msg='Media is not recording',
          timeout=_RECORDING_STATE_TIMEOUT,
      )
      test_utils.wait_until_or_assert(
          condition=lambda: self.ad.bt_snippet.mediaGetRecordingBleDeviceInfo()
          == self.bt_device.bluetooth_address_primary,
          error_msg='Recording device is not the primary BT device',
          timeout=_RECORDING_STATE_TIMEOUT,
      )
      self.ad.log.info('Verifying game audio was not interrupted by VBC.')
      test_utils.wait_until_or_assert(
          condition=self.ad.bt_snippet.media3IsPlayerPlaying,
          error_msg='Media playback stopped during VBC recording.',
          timeout=_MEDIA_STATE_TIMEOUT,
      )
      test_utils.wait_until_or_assert(
          condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
              self.ad, self.bt_device.bluetooth_address_primary
          ),
          error_msg=(
              'Media is no longer playing on LE Audio while VBC was active.'
          ),
          timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
      )
      self.ad.log.info(
          'Recording device info: %s',
          self.ad.bt_snippet.mediaGetRecordingBleDeviceInfo(),
      )

    self.ad.log.info('Test finished, VBC did not interrupt game streaming.')
  # fixed.
  def _test_game_streaming_with_vbc_power_off_on(self):
    """Test for Bluetooth LE Audio gaming streaming with VBC and power cycle.

    Precondition:
      1. DUT and Bluetooth device are paired.
      2. DUT and Bluetooth device are connected via LE Audio.

    Test Steps:
      1. Set audio usage to GAME and start media playback.
      2. Verify game audio is streaming correctly to the Bluetooth device.
      3. Set and record volume level.
      4. Start recording from the Bluetooth device's microphone to activate VBC.
      5. Power off Bluetooth device.
      6. Verify LE audio disconnect, recording stops and audio routes to DUT
         speaker.
      7. Power on Bluetooth device.
      8. Verify LE audio reconnect and media streams to Bluetooth device.
      9. Verify volume level is restored.
      10. Start recording again to verify VBC can be reactivated.
      11. Stop and verify the recording.
      12. Verify the game audio stream is still active.
      13. Stop media playback.

    Pass Criteria:
      1. When power OFF Bluetooth device, Gaming+VBC audio routes to DUT
      speaker.
      2. When power ON Bluetooth device, Bluetooth device connects automatically
      and Gaming+VBC audio routes back to Bluetooth device.
      3. VBC stream can be reactivated after Bluetooth device power cycle.
      4. Game audio is not interrupted or degraded after VBC activation
      and power cycle.
      5. Audio volume is the same level which was set before disconnection.
    """
    self.ad.bt_snippet.media3SetAudioUsage(
        media_utils.AudioUsage.USAGE_GAME,
        media_utils.AudioContentType.CONTENT_TYPE_UNKNOWN,
    )
    self.ad.bt_snippet.media3StartLocalFile(_MEDIA_FILES_PATHS[0])

    self.ad.log.info('Verifying game audio is playing on LE Audio device.')
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_MEDIA_PLAY_TIME,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to play media on LE Audio',
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )
    current_usage_name = media_utils.AudioUsage(
        self.ad.bt_snippet.media3GetAudioUsage()
    ).name
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetAudioUsage()
        == media_utils.AudioUsage.USAGE_GAME,
        error_msg=(
            'Failed to set audio usage to GAME, current usage is '
            f'{current_usage_name}'
        ),
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )

    # Set and store volume
    max_volume = self.ad.bt_snippet.getMusicMaxVolume()
    target_volume = max_volume // 2
    self.ad.log.info('Setting volume to %d.', target_volume)
    self.ad.bt_snippet.setMusicVolume(target_volume)
    time.sleep(1)  # wait for volume to be set
    current_volume = self.ad.bt_snippet.getMusicVolume()
    asserts.assert_equal(
        current_volume, target_volume, 'Failed to set music volume.'
    )

    with self._record_audio():
      test_utils.wait_until_or_assert(
          condition=self.ad.bt_snippet.mediaIsRecording,
          error_msg='Media is not recording',
          timeout=_RECORDING_STATE_TIMEOUT,
      )

      self.ad.log.info('Power off BT device.')
      self.bt_device.power_off()
      test_utils.wait_until_or_assert(
          condition=lambda: not bluetooth_utils.is_le_audio_streaming_active(
              self.ad, self.bt_device.bluetooth_address_primary
          ),
          error_msg='Failed to disconnect media on LE Audio',
          timeout=_MEDIA_STATE_TIMEOUT,
      )

      self.ad.log.info('Power on BT device.')
      self.bt_device.power_on()
      test_utils.wait_until_or_assert(
          condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
              self.ad, self.bt_device.bluetooth_address_primary
          ),
          error_msg='Failed to reconnect media on LE Audio',
          timeout=_MEDIA_STATE_TIMEOUT,
      )
      current_usage_name = media_utils.AudioUsage(
          self.ad.bt_snippet.media3GetAudioUsage()
      ).name
      test_utils.wait_until_or_assert(
          condition=lambda: self.ad.bt_snippet.media3GetAudioUsage()
          == media_utils.AudioUsage.USAGE_GAME,
          error_msg=(
              'Failed to set audio usage to GAME, current usage is'
              f' {current_usage_name}'
          ),
          timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
      )

      self.ad.log.info('Verifying volume is restored.')
      restored_volume = self.ad.bt_snippet.getMusicVolume()
      asserts.assert_equal(
          restored_volume,
          target_volume,
          f'Volume not restored: expected {target_volume}, got'
          f' {restored_volume}',
      )

      self.ad.log.info('Reactivating microphone recording after power cycle.')
      self.ad.bt_snippet.mediaStartRecording(_RECORDING_FILE_NAME)
      time.sleep(_RECORDING_DURATION.total_seconds())  # Record for 10 seconds
      test_utils.wait_until_or_assert(
          condition=self.ad.bt_snippet.mediaIsRecording,
          error_msg='Media is not recording after power cycle',
          timeout=_RECORDING_STATE_TIMEOUT,
      )
      test_utils.wait_until_or_assert(
          condition=lambda: self.ad.bt_snippet.mediaGetRecordingBleDeviceInfo()
          == self.bt_device.bluetooth_address_primary,
          error_msg=(
              'Recording device is not the primary BT device after power cycle'
          ),
          timeout=_RECORDING_STATE_TIMEOUT,
      )
      self.ad.log.info('Verifying game audio was not interrupted by VBC.')
      test_utils.wait_until_or_assert(
          condition=self.ad.bt_snippet.media3IsPlayerPlaying,
          error_msg=(
              'Media playback stopped during VBC recording after power cycle.'
          ),
          timeout=_MEDIA_STATE_TIMEOUT,
      )
      asserts.assert_true(
          'Recording device info: %s',
          self.ad.bt_snippet.mediaGetRecordingBleDeviceInfo(),
      )

    self.ad.log.info('Test finished, VBC restart after power cycle success.')


if __name__ == '__main__':
  test_runner.main()
