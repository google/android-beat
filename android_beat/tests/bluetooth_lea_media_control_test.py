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
import sys
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
_EVENT_WAIT_TIMEOUT = datetime.timedelta(seconds=15)
_STATE_SETTLE_TIME = datetime.timedelta(seconds=3)
_MEDIA_PLAY_TIME_WITH_RECORDING = datetime.timedelta(seconds=10)
_MEDIA_KEY_DEBOUNCE_TIME = datetime.timedelta(seconds=0.1)
_MEDIA_ACTION_WAIT_TIME = datetime.timedelta(seconds=1)
_ANDROID_VOLUME_LEVEL = 5
_BT_VOLUME_LEVEL = 51
_RECORDING_DURATION = datetime.timedelta(seconds=10)
_RECORDING_STATE_TIMEOUT = datetime.timedelta(seconds=30)


class BluetoothLeaMediaControlTest(base_test.BaseTestClass):
  """Test class for Bluetooth AVRC control from CT test."""

  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.SINGLE_DEVICE
  _BLUETOOTH_MODE = base_test.BluetoothMode.LEA
  _HAS_MEDIA = True

  def setup_test(self) -> None:
    super().setup_test()
    audio_utils.wait_and_assert_recording_has_ble_headset(self.ad)
    self.ad.log.info('BLE headset is ready for recording.')

  def teardown_test(self):
    if self.ad.bt_snippet.mediaIsRecording():
      self.ad.bt_snippet.mediaStopRecording()
    # Clean up the file.
    self.ad.adb.shell(['rm', '-f', recording_utils.RECORDING_FILE_PATH])
    super().teardown_test()

  def test_46_1_and_46_2_media_control_play_pause(self):
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
  def test_46_3_media_control_prev_next(self):
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
    self.ad.log.info('Setting playlist with: ', self._MEDIA_PLAYLIST_PATHS)
    for file_path in self._MEDIA_PLAYLIST_PATHS:
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

  def test_47_3_lea_volume_control_from_android_device(self):
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
    self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_PLAYLIST_PATHS[0])
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

  def test_47_1_lea_volume_control_from_bt_device(self):
    """Test for LEA volume control from Bluetooth device.

    Precondition:
      1. Android device and Bluetooth reference device paired.
      2. Bluetooth LE Audio is active.
      3. Media file is pushed to Android device.

    Test Steps:
      1. Start local file playback on Android device.
      2. Verify media is playing on Android device and streaming on BT device.
      3. Set volume to 5 on BT device.
      4. Verify volume is set to 5 on Android device.
      5. Volume up from BT device.
      6. Verify volume is set to 6 on Android device.
      7. Volume down from BT device.
      8. Verify volume is set to 5 on Android device.

    Expected Results:
      1. Volume is adjusted correctly on Android device.
    """
    self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_PLAYLIST_PATHS[0])
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device',
        timeout=_MEDIA_PLAY_TIME,
    )

    volume_level = _ANDROID_VOLUME_LEVEL
    # self.ad.bt_snippet.setMusicVolume(volume_level)
    self.bt_device.set_volume(_BT_VOLUME_LEVEL)
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

  def test_47_2_lea_volume_control_to_min_max_from_bt_device(self):
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
      self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_PLAYLIST_PATHS[0])
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

  def test_50_1_and_50_2_start_stop_recording(self):
    """Tests starting and stopping media recording.

    Objective:
    To make sure the bluetooth device can start and stop recording correctly.

    Precondition:
    - DUT is paired with the primary BT device.
    - DUT is in LE Audio media mode.
    - DUT has a media file to play.
    - DUT has a BLE headset connected.

    Procedure:
    1. Start recording.
    2. Wait for the recording to finish.
    3. Stop recording.

    Verification:
    1. The recording file is saved to the expected path.
    2. The recording file is pulled to the host machine.
    """
    self.ad.log.info(
        'Starting recording, saving to %s', recording_utils.RECORDING_FILE_NAME
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
      self.ad.log.info(
          'Recording device info: %s',
          self.ad.bt_snippet.mediaGetRecordingBleDeviceInfo(),
      )
    pull_path = os.path.join(
        self.current_test_info.output_path, recording_utils.RECORDING_FILE_NAME
    )
    self.ad.adb.pull([recording_utils.RECORDING_FILE_PATH, pull_path])

  def _start_audio_recording(self) -> None:
    """Starts audio recording if the platform is Linux."""
    if sys.platform == 'linux':
      self.bt_device.start_audio_recording()

  def _stop_audio_recording(self) -> None:
    """Stops audio recording if the platform is Linux."""
    if sys.platform == 'linux':
      self.bt_device.stop_audio_recording(self.current_test_info.output_path)

  def test_45_1_streaming(self):
    """Validate LE Audio media streaming functionality.

    Objective:
      To validate the Device Under Test (DUT) can successfully play media and
      route to the connected Bluetooth device via LE Audio.

    Test Preconditions:
      1. Device: 1 Android device and 1 Bluetooth reference device.

    Test Steps:
      1. Play local media on DUT and routes to the connected device.
      2. Verify the media routes to BT device continuously for 1 minute.
      3. Stop the media on DUT.

    Pass criteria:
      1. DUT can play media and routes to the connected device without breaks.
    """
    try:
      self._start_audio_recording()
      self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_PLAYLIST_PATHS[0])
      test_utils.wait_until_or_assert(
          lambda: bluetooth_utils.is_le_audio_streaming_active(
              self.ad, self.bt_device.bluetooth_address_primary
          ),
          error_msg=f'{self.ad} Timed out waiting for LE Audio media streaming',
          timeout=_MEDIA_PLAY_TIME,
      )
    finally:
      self.ad.bt_snippet.media3Stop()
      assert self.current_test_info is not None
      self._stop_audio_recording()


if __name__ == '__main__':
  test_runner.main()
