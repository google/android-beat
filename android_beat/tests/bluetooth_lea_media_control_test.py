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

"""Bluetooth LE Audio media control test."""

import datetime
import os
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
_EVENT_WAIT_TIMEOUT = datetime.timedelta(seconds=15)
_STATE_SETTLE_TIME = datetime.timedelta(seconds=3)
_MEDIA_PLAY_TIME_WITH_RECORDING = datetime.timedelta(seconds=10)
_MEDIA_KEY_DEBOUNCE_TIME = datetime.timedelta(seconds=0.1)
_MEDIA_ACTION_WAIT_TIME = datetime.timedelta(seconds=1)


class BluetoothLeaMediaControlTest(base_test.BaseTestClass):
  """Test class for Bluetooth AVRC control from CT test."""

  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.SINGLE_DEVICE
  _BLUETOOTH_MODE = base_test.BluetoothMode.LEA

  _MEDIA_FILES_BASENAMES = ['sine_tone_0.wav', 'sine_tone_1.wav']
  _MEDIA_FILES_PATHS = [
      '/sdcard/Download/sine_tone_0.wav',
      '/sdcard/Download/sine_tone_1.wav',
  ]

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

  def setup_class(self) -> None:
    super().setup_class()
    asserts.abort_class_if(
        not self.ad.bt_snippet.btIsLeAudioSupported(),
        f'{self.ad} LE Audio is not supported',
    )

    self._pair_bluetooth_lea_device()

    audio_utils.generate_and_push_audio_files(
        self.ad,
        self._MEDIA_FILES_BASENAMES,
        self.current_test_info.output_path,
    )
    self.generate_audio_file_paths = [
        os.path.join(self.current_test_info.output_path, file_name)
        for file_name in self._MEDIA_FILES_BASENAMES
    ]
    self.ad.bt_snippet.media3Stop()

  def setup_test(self) -> None:
    # Check if LEA is still connected. If not, factory reset the Bluetooth
    # device and repair it.
    if not self.ad.bt_snippet.btIsLeAudioConnected(
        self.bt_device.bluetooth_address_primary
    ):
      bluetooth_utils.clear_saved_devices(self.ad)
      self.bt_device.factory_reset()
      self._pair_bluetooth_lea_device()

  def teardown_test(self) -> None:
    self.ad.bt_snippet.media3Stop()
    self.ad.bt_snippet.media3ClearPlaylist()

  def test_media_control_play_pause(self):
    """Test for Bluetooth LE Audio media control from CT test.

    Precondition:
      1. Android device and Bluetooth reference device paired.
      2. Bluetooth LE Audio is active.
      3. Media file is pushed to Android device.

    Test Steps:
      1. Start local file playback on Android device.
      2. Verify media is playing on Android device and streaming on BT device.
      3. Pause media playback from BT device.
      4. Verify media is paused on Android device and not streaming on BT
      device.
      5. Play media playback from BT device.
      6. Verify media is playing on Android device and streaming on BT device.

    Expected Results:
      1. Media is playing on Android device and streaming on BT device.
      2. Media is paused on Android device.
      3. Media is playing on Android device and streaming on BT device.
    """
    self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_FILES_PATHS[0])
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

    self.bt_device.media_pause()
    test_utils.wait_until_or_assert(
        condition=lambda: not self.ad.bt_snippet.media3IsPlayerPlaying(),
        error_msg='Failed to pause media on Android device',
        timeout=_MEDIA_PLAY_TIME,
    )

    self.bt_device.media_play()
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
  def test_media_control_prev_next(self):
    """Test for Bluetooth LE Audio media control from CT test.

    Precondition:
      1. Android device and Bluetooth reference device paired.
      2. Bluetooth LE Audio is active.
      3. Media file is pushed to Android device.

    Test Steps:
      1. Start playlist playback on Android device.
      2. Verify media is playing on Android device and streaming on BT device.
      3. Send NEXT from BT device.
      4. Verify media is playing on Android device and streaming on BT device.
      5. Send NEXT from BT device.
      6. Verify media is playing on Android device and streaming on BT device.
      7. Send PREVIOUS from BT device.
      8. Verify media is playing on Android device and streaming on BT device.
      9. Send PREVIOUS from BT device.
      10. Verify media is playing on Android device and streaming on BT device.

    Expected Results:
      1. Media is playing on Android device and streaming on BT device with
      correct track index.
    """
    self.ad.log.info('Setting playlist with: ', self._MEDIA_FILES_PATHS)
    for file_path in self._MEDIA_FILES_PATHS:
      self.ad.log.info(f'Adding {file_path} to playlist')
      self.ad.bt_snippet.media3AddToPlaylist(file_path)

    self.ad.log.info('Starting playlist at index 0.')
    self.ad.bt_snippet.media3StartPlaylistWithIndex(0)
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to play media on LE Audio',
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 0,
        error_msg='Failed to start playlist at index 0.',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    self.ad.log.info('Playlist started, track index 0.')

    self.ad.log.info('Sending NEXT from BT device (to index 1)...')
    self.bt_device.media_next()
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 1,
        error_msg='Failed to advance to track index 1.',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to play media on LE Audio',
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[1],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index is updated to 1.')

    self.ad.log.info('Sending NEXT from BT device (to index 1)...')

    self.bt_device.media_next()
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 1,
        error_msg='Index changed from last track.',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to play media on LE Audio',
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[1],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index is remains 1.')

    self.ad.log.info('Sending PREVIOUS from BT device (to index 0)...')

    self.bt_device.media_prev()
    time.sleep(_MEDIA_KEY_DEBOUNCE_TIME.total_seconds())
    self.bt_device.media_prev()
    time.sleep(_STATE_SETTLE_TIME.total_seconds())
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 0,
        error_msg='Failed to go back to track index 0.',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to play media on LE Audio',
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[0],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index is updated to 0.')

    self.ad.log.info('Sending PREVIOUS from BT device (at first track)...')

    self.bt_device.media_prev()
    time.sleep(_MEDIA_KEY_DEBOUNCE_TIME.total_seconds())
    self.bt_device.media_prev()
    time.sleep(_STATE_SETTLE_TIME.total_seconds())
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 0,
        error_msg='Index changed from first track.',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_le_audio_streaming_active(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to play media on LE Audio',
        timeout=_MEDIA_DEVICE_TYPE_TIMEOUT,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[0],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index is remains 0.')

  def test_lea_volume_control_from_android_device(self):
    """Test for LEA volume control from Android device.

    Precondition:
      1. Android device and Bluetooth reference device paired.
      2. Bluetooth LE Audio is active.
      3. Media file is pushed to Android device.

    Test Steps:
      1. Start local file playback on Android device.
      2. Verify media is playing on Android device and streaming on BT device.
      3. Set volume to 5 on Android device.
      4. Verify volume is set to 5 on Android device.
      5. Adjust volume to 6 on Android device.
      6. Verify volume is set to 6 on Android device.
      7. Adjust volume to 5 on Android device.
      8. Verify volume is set to 5 on Android device.

    Expected Results:
      1. Volume is adjusted correctly on Android device.
    """
    self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_FILES_PATHS[0])
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_MEDIA_PLAY_TIME,
    )
    self.ad.log.info('Setting volume to 5')
    self.ad.bt_snippet.setMusicVolume(5)
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.getMusicVolume() == 5,
        error_msg='Failed to set volume to 5',
        timeout=_STATE_SETTLE_TIME,
    )
    self.ad.log.info('Volume is now 50%.')

    self.ad.bt_snippet.media3AdjustVolume(
        media_utils.VolumeDirection.ADJUST_RAISE
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.getMusicVolume() == 6,
        error_msg='Failed to adjust volume to 6',
        timeout=_STATE_SETTLE_TIME,
    )
    self.ad.log.info('Volume is now 60%.')

    self.ad.bt_snippet.media3AdjustVolume(
        media_utils.VolumeDirection.ADJUST_LOWER
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.getMusicVolume() == 5,
        error_msg='Failed to adjust volume to 5',
        timeout=_STATE_SETTLE_TIME,
    )
    self.ad.log.info('Volume is now 50%.')

  def test_lea_volume_control_from_bt_device(self):
    """Test for LEA volume control from Bluetooth device.

    Precondition:
      1. Android device and Bluetooth reference device paired.
      2. Bluetooth LE Audio is active.
      3. Media file is pushed to Android device.

    Test Steps:
      1. Start local file playback on Android device.
      2. Verify media is playing on Android device and streaming on BT device.
      3. Set volume to 5 on Android device.
      4. Verify volume is set to 5 on Android device.
      5. Volume up from BT device.
      6. Verify volume is set to 6 on Android device.
      7. Volume down from BT device.
      8. Verify volume is set to 5 on Android device.

    Expected Results:
      1. Volume is adjusted correctly on Android device.
    """
    self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_FILES_PATHS[0])
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_MEDIA_PLAY_TIME,
    )
    volume_level = 5
    self.ad.bt_snippet.setMusicVolume(volume_level)
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.getMusicVolume() == volume_level,
        error_msg=f'Failed to set volume to {volume_level}',
        timeout=_STATE_SETTLE_TIME,
    )
    self.ad.log.info('Volume is now %s', volume_level)

    self.bt_device.volume_up()
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.getMusicVolume() > volume_level,
        error_msg=(
            'Failed to increase volume, current volume:'
            f' {self.ad.bt_snippet.getMusicVolume()}'
        ),
        timeout=_STATE_SETTLE_TIME,
    )
    self.ad.log.info(
        'Volume is now up to%s', self.ad.bt_snippet.getMusicVolume()
    )

    volume_level = self.ad.bt_snippet.getMusicVolume()
    self.bt_device.volume_down()
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.getMusicVolume() < volume_level,
        error_msg=(
            'Failed to decrease volume, current volume:'
            f' {self.ad.bt_snippet.getMusicVolume()}'
        ),
        timeout=_STATE_SETTLE_TIME,
    )
    self.ad.log.info(
        'Volume is now down to %s', self.ad.bt_snippet.getMusicVolume()
    )

  def test_lea_volume_control_to_min_max_from_bt_device(self):
    """Test for LEA volume control to min/max from Bluetooth device.

    Precondition:
      1. Android device and Bluetooth reference device paired.
      2. Bluetooth LE Audio is active.
      3. Media file is pushed to Android device.

    Test Steps:
      1. Start local file playback on Android device.
      2. Verify media is playing on Android device and streaming on BT device.
      3. Set volume to a middle level on Android device.
      4. Repeatedly press volume up on BT device.
      5. Verify volume is set to max on Android device.
      6. Repeatedly press volume down on BT device.
      7. Verify volume is set to min on Android device.

    Expected Results:
      1. Volume is adjusted to max and min correctly on Android device.
    """
    try:
      self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_FILES_PATHS[0])
      test_utils.wait_until_or_assert(
          condition=self.ad.bt_snippet.media3IsPlayerPlaying,
          error_msg='Failed to play media on Android device',
          timeout=_MEDIA_PLAY_TIME,
      )

      mid_volume = self.ad.bt_snippet.getMusicMaxVolume() // 2
      self.ad.bt_snippet.setMusicVolume(
          mid_volume
      )
      test_utils.wait_until_or_assert(
          condition=lambda: self.ad.bt_snippet.getMusicVolume() == mid_volume,
          error_msg=f'Failed to set volume to {mid_volume}',
          timeout=_STATE_SETTLE_TIME,
      )

      self.ad.log.info('Max volume: %d', self.ad.bt_snippet.getMusicMaxVolume())
      self.ad.log.info('Increasing volume to max from BT device...')
      audio_utils.wait_and_assert_volume_up_to_max(self.ad, self.bt_device)

      self.ad.log.info(
          'Volume reached max: %d', self.ad.bt_snippet.getMusicVolume()
      )

      self.ad.log.info('Decreasing volume to min from BT device...')
      audio_utils.wait_and_assert_volume_down_to_min(self.ad, self.bt_device)

      self.ad.log.info('Volume reached min: 0')
    finally:
      self.ad.bt_snippet.setMusicVolume(
          self.ad.bt_snippet.getMusicMaxVolume() // 2
      )

if __name__ == '__main__':
  test_runner.main()
