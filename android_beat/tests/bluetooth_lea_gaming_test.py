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
# pylint: disable=attribute-error
import datetime
import time

from mobly import test_runner

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import media_utils
from android_beat.utils import recording_utils
from android_beat.utils import test_utils

_MEDIA_PLAY_TIME = datetime.timedelta(seconds=15)
_MEDIA_DEVICE_TYPE_TIMEOUT = datetime.timedelta(seconds=30)
_MEDIA_STATE_TIMEOUT = datetime.timedelta(seconds=30)
_RECORDING_DURATION = datetime.timedelta(seconds=10)
_RECORDING_STATE_TIMEOUT = datetime.timedelta(seconds=30)


class BluetoothLeaGamingTest(base_test.BaseTestClass):
  """Test class for Bluetooth LEA gaming streaming test."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.LEA
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.SINGLE_DEVICE
  _HAS_MEDIA = True

  def setup_test(self) -> None:
    super().setup_test()
    audio_utils.wait_and_assert_recording_has_ble_headset(self.ad)
    self.ad.bt_snippet.mediaStopRecording()
    self.ad.log.info('BLE headset is ready for recording.')

  def teardown_test(self):
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
    self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_PLAYLIST_PATHS[0])
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
    self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_PLAYLIST_PATHS[0])

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

    with recording_utils.record_audio_context(self.ad):
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


if __name__ == '__main__':
  test_runner.main()
