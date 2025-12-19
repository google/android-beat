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

"""Bluetooth AVRCP control test."""

import datetime
import os
import time

from mobly import test_runner

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import media_utils
from android_beat.utils import test_utils

_MEDIA_PLAY_TIME = datetime.timedelta(seconds=15)
_STATE_SETTLE_TIME = datetime.timedelta(seconds=5)
_EVENT_WAIT_TIMEOUT = datetime.timedelta(seconds=15)
_MEDIA_PLAY_TIME_WITH_RECORDING = datetime.timedelta(seconds=10)
_MEDIA_ACTION_WAIT_TIME = datetime.timedelta(seconds=1)

_PLAYLIST_FILES = ('sine_tone_0.wav', 'sine_tone_1.wav')
_PLAYLIST_PATHS = (
    '/sdcard/Download/sine_tone_0.wav',
    '/sdcard/Download/sine_tone_1.wav',
)


class BluetoothAvrcpTest(base_test.BaseTestClass):
  """Test class for Bluetooth AVRCP control test."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.CLASSIC
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.SINGLE_DEVICE
  _MEDIA_FILES_BASENAMES = ('sine_tone_0.wav', 'sine_tone_1.wav')
  _MEDIA_FILES_PATHS = (
      '/sdcard/Download/sine_tone_0.wav',
      '/sdcard/Download/sine_tone_1.wav',
  )

  def _pair_bluetooth_device(self) -> None:
    """Pairs the Android device with the Bluetooth device."""
    bluetooth_utils.pair_bluetooth_device(self.ad, self.bt_device)
    bluetooth_utils.wait_and_assert_hfp_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
    )
    audio_utils.wait_and_assert_audio_device_type(
        self.ad,
        audio_utils.AudioDeviceType.TYPE_BLUETOOTH_SCO,
        expect_active=True,
    )

  def setup_class(self) -> None:
    super().setup_class()
    self._pair_bluetooth_device()

    audio_utils.generate_and_push_audio_files(
        self.ad,
        self._MEDIA_FILES_BASENAMES,
        self.current_test_info.output_path,
    )
    self.generate_audio_file_paths = [
        os.path.join(self.current_test_info.output_path, file_name)
        for file_name in self._MEDIA_FILES_BASENAMES
    ]

  def setup_test(self) -> None:
    super().setup_test()
    # Check if HFP is still connected. If not, factory reset the Bluetooth
    # device and repair it.
    if not self.ad.bt_snippet.btIsHfpConnected(
        self.bt_device.bluetooth_address_primary
    ):
      bluetooth_utils.clear_saved_devices(self.ad)
      self.bt_device.factory_reset()
      self._pair_bluetooth_device()
    self.ad.bt_snippet.media3Stop()
    self.ad.bt_snippet.media3ClearPlaylist()

  def teardown_test(self) -> None:
    self.ad.bt_snippet.media3Stop()
    self.ad.bt_snippet.media3ClearPlaylist()
    super().teardown_test()

  def test_avrcp_play_pause_from_android(self):
    """Test for play/pause audio in AVRCP control from Android device.

    Precondition:
      1. Pair the Android device and Bluetooth reference device.
      2. Connect to the Bluetooth reference device.

    Test Steps:
      1. Play audio from Android device.
      2. Verify the audio is playing on Android device and streaming to
      Bluetooth reference device.
      3. Pause audio from Android device.
      4. Verify the audio is paused on Android device and streaming to Bluetooth
      reference device.
      5. Resume audio from Android device.
      6. Verify the audio is playing on Android device and streaming to
      Bluetooth reference device.

    Expected Results:
      1. Verify the audio is playing on Android device and streaming to
      Bluetooth reference device.
      2. Verify the audio is paused on Android device and streaming to Bluetooth
      reference device.
      3. Verify the audio is resumed on Android device and streaming to
      Bluetooth reference device.
    """
    # Play sine_tone audio.
    self.ad.bt_snippet.media3StartLocalFile(_PLAYLIST_PATHS[0])
    self.ad.log.info('Start playing audio...')
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to start playing media on Android device',
        timeout=_MEDIA_PLAY_TIME,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when Android device starts'
            ' playing'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )

    self.ad.log.info('Pausing audio on Android device...')
    self.ad.bt_snippet.media3Pause()
    test_utils.wait_until_or_assert(
        condition=lambda: not self.ad.bt_snippet.media3IsPlayerPlaying(),
        error_msg='Failed to pause playing media on Android device',
        timeout=_MEDIA_PLAY_TIME,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: not self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to pause stream media to BT device when Android device'
            ' pauses'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )

    self.ad.log.info('Resuming audio on Android device...')
    self.ad.bt_snippet.media3Play()
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to resume playing media on Android device',
        timeout=_MEDIA_PLAY_TIME,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to resume streaming media to BT device when Android'
            ' device resumes playing'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )

  def test_avrcp_next_prev_from_android(self):
    """Test for next/prev track in AVRCP control from Android device.

    Objective:
      To validate the Device Under Test (DUT) can successfully play media list
      and route to the connected device. Make sure the next/prev control works
      as expected.

    Test Preconditions:
      1. Device: 1 Android device and 1 Bluetooth reference device.
      2. Audio generated on the host and pushed to the device.
      3. Android device is paired with Bluetooth reference device.

    Test Steps:
      1. Play audio from Android device.
      2. Verify the audio is playing on Android device, streaming to
      Bluetooth reference device and the track index is 0.
      3. Send next from Android device.
      4. Verify the audio is playing on Android device, streaming to
      Bluetooth reference device and the track index is 1.
      5. Send next from Android device.
      6. Verify the audio is playing on Android device, streaming to
      Bluetooth reference device and the track index is 1.
      7. Send previous from Android device.
      8. Verify the audio is playing on Android device, streaming to
      Bluetooth reference device and the track index is 0.
      9. Send previous from Android device.
      10. Verify the audio is playing on Android device, streaming to
      Bluetooth reference device and the track index is 0.

    Expected Results:
      1. Verify the audio is playing on Android device.
      2. Verify the audio is streaming to Bluetooth reference device.
      3. Verify the track index is correct.
      4. Verify the audio recording is correct when playing next/prev track.
    """
    self.ad.log.info('Setting playlist with: %s', _PLAYLIST_PATHS)
    for file_path in _PLAYLIST_PATHS:
      self.ad.log.info('Adding %s to playlist', file_path)
      self.ad.bt_snippet.media3AddToPlaylist(file_path)

    self.ad.log.info('Starting playlist at index 0 on Android device.')
    self.ad.bt_snippet.media3StartPlaylistWithIndex(0)
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 0,
        error_msg='Failed to start play the first track. Track index is not 0.',
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to start playing playlist on Android device. Track index'
            ' is 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when Android device starts'
            ' playing. Track index is 0.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    self.ad.log.info('Playlist started, track index 0.')

    self.ad.log.info('Sending next command from BT device (to index 1)...')
    self.ad.bt_snippet.media3PlayNext()
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 1,
        error_msg=(
            'Failed to play the next track on Android device when Android'
            ' device plays next. Track index is not 1.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to keep playing on Android device when Android device plays'
            ' next. Track index is 1'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when Android device plays'
            ' next. Track index is 1'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[1],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index is now 1.')

    self.ad.log.info(
        'Sending next command from BT device (remain at index 1)...'
    )
    self.ad.bt_snippet.media3PlayNext()
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 1,
        error_msg=(
            'Failed to remain on the current track as the end of the playlist'
            ' when Android device plays next. Track index is not 1.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to keep playing on Android device when Android device plays'
            ' next. Track index is 1'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when Android device plays'
            ' next. Track index is 1'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[1],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index remains 1 (last track).')

    self.ad.log.info('Sending previous from BT device (to index 0)...')
    self.ad.bt_snippet.media3PlayPrevious()
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 0,
        error_msg=(
            'Failed to play the previous track on Android device when Android'
            ' device plays previous. Track index is not 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to keep playing on Android device when Android device plays'
            ' previous. Track index is 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when Android device plays'
            ' previous. Track index is 0'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[0],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index is now 0.')

    self.ad.log.info('Sending previous from Android device (to index 0)...')
    self.ad.bt_snippet.media3PlayPrevious()
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 0,
        error_msg=(
            'Failed to remain on the current track as the start of the playlist'
            ' when Android device plays previous. Track index is not 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to keep playing track on Android device when Android device'
            ' plays previous. Track index is 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media on BT device when Android device plays'
            ' previous. Track index is 0'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[0],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index remains 0 (first track).')

  def test_avrcp_play_pause_from_bt_device(self):
    """Test for play/pause audio in AVRCP control from BT device.

    Precondition:
      1. Pair the Android device and Bluetooth reference device.
      2. Connect to the Bluetooth reference device.

    Test Steps:
      1. Play audio from Android device.
      2. Verify the audio is playing on Android device and Bluetooth
      reference device.
      3. Pause audio from Bluetooth device.
      4. Verify the audio is paused on Android device and Bluetooth
      reference device.
      5. Resume audio from Bluetooth device.
      6. Verify the audio is playing on Android device and Bluetooth
      reference device.

    Expected Results:
      1. Verify the audio is playing on Android device
      2. Verify the audio is streaming to Bluetooth
    """
    # Play sine_tone audio.
    self.ad.bt_snippet.media3StartLocalFile(_PLAYLIST_PATHS[0])
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to start play media on Android device.',
        timeout=_MEDIA_PLAY_TIME,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when Android device starts'
            ' playing.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )

    self.bt_device.media_pause()
    test_utils.wait_until_or_assert(
        condition=lambda: not self.ad.bt_snippet.media3IsPlayerPlaying(),
        error_msg=(
            'Failed to pause media on Android device when BT device sends pause'
            ' command.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: not self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to pause stream media to BT device when BT device sends'
            ' pause command.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )

    self.bt_device.media_play()
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to resume media on Android device when BT device sends play'
            ' command.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when BT device sends play'
            ' command.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )

  def test_avrcp_next_prev_from_bt_device(self):
    """Test for next/prev track in AVRCP control from BT device.

    Precondition:
      1. Pair the Android device and Bluetooth reference device.
      2. Connect to the Bluetooth reference device.
      3. Set playlist with 3 sine_tone audio files.

    Test Steps:
      1. Start playlist from Android device.
      2. Verify the playlist is playing on Android device and Bluetooth
      reference device and the track index is 0.
      3. Send NEXT from BT device.
      4. Verify the audio is playing on Android device, streaming to
      Bluetooth reference device and the track index is 1.
      5. Send NEXT from BT device.
      6. Verify the audio is playing on Android device, streaming to
      Bluetooth reference device and the track index is 1.
      7. Send PREVIOUS from BT device.
      8. Verify the audio is playing on Android device, streaming to
      Bluetooth reference device and the track index is 0.
      9. Send PREVIOUS from BT device.
      10. Verify the audio is playing on Android device, streaming to
      Bluetooth reference device and the track index is 0.

    Expected Results:
      1. Verify the playlist is playing on Android device and Bluetooth
      reference device.
      2. Verify the initial track index is correct.
      3. Verify the audio recording is correct when playing next/prev track.
    """
    self.ad.log.info('Setting playlist with: %s', _PLAYLIST_PATHS)
    for file_path in _PLAYLIST_PATHS:
      self.ad.log.info('Adding %s to playlist', file_path)
      self.ad.bt_snippet.media3AddToPlaylist(file_path)

    self.ad.log.info('Starting playlist at index 0.')
    self.ad.bt_snippet.media3StartPlaylistWithIndex(0)
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 0,
        error_msg=(
            'Failed to play the first track on Android device. Track index is'
            ' not 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to keep playing on Android device when Android device'
            ' starts playing playlist. Track index is 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when Android device starts'
            ' playing playlist. Track index is 0.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )

    self.ad.log.info('Playlist started, track index 0.')

    self.ad.log.info('Sending next from BT device (to index 1)...')
    self.bt_device.media_next()
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 1,
        error_msg=(
            'Failed to play the next track on Android device when BT device'
            ' sends next command. Track index is not 1.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to keep playing track by pressing next on BT device when BT'
            ' device sends next command. Track index is 1.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when BT device sends next'
            ' command. Track index is 1.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[1],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index is now 1.')

    # For here and all the following tests about keep index.
    self.ad.log.info('Sending next from BT device (remain at index 1)...')
    self.bt_device.media_next()
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 1,
        error_msg=(
            'Failed to remain on the current track as the end of the playlist'
            ' when BT device sends next command. Track index is not 1.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to keep playing when BT device sends next command. Track'
            ' index is 1.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when BT device sends next'
            ' command. Track index is 1.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[1],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index remains 1 (last track).')

    self.ad.log.info('Sending previous from BT device (to index 0)...')
    self.bt_device.media_prev()
    time.sleep(0.1)
    self.bt_device.media_prev()
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 0,
        error_msg=(
            'Failed to keep playing on Android device when BT device sends'
            ' previous command. Track index is not 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to play previous track when BT device sends previous'
            ' command. Track index is 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when BT device sends previous'
            ' command. Track index is 0.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[0],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index is now 0.')

    # For here and all the following tests about keep index.
    self.ad.log.info('Sending previous from BT device (remain at index 0)...')
    self.bt_device.media_prev()
    time.sleep(0.1)
    self.bt_device.media_prev()
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.media3GetCurrentTrackIndex() == 0,
        error_msg=(
            'Failed to play the previous track on Android device when BT device'
            ' sends next command. Track index is not 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    time.sleep(_MEDIA_ACTION_WAIT_TIME.total_seconds())
    audio_utils.start_audio_recording(self.bt_device)
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg=(
            'Failed to play previous track when BT device sends previous'
            ' command. Track index is 0.'
        ),
        timeout=_EVENT_WAIT_TIMEOUT,
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
            self.bt_device.bluetooth_address_primary
        ),
        error_msg=(
            'Failed to stream media to BT device when BT device sends previous'
            ' command. Track index is 0.'
        ),
        timeout=_MEDIA_PLAY_TIME,
    )
    time.sleep(_MEDIA_PLAY_TIME_WITH_RECORDING.total_seconds())
    recorded_audio_files_on_host = audio_utils.stop_audio_recording(
        self.bt_device, self.current_test_info.output_path
    )
    audio_utils.assert_has_audio_start_time(
        self.generate_audio_file_paths[0],
        recorded_audio_files_on_host,
    )
    self.ad.log.info('Track index remains 0 (first track).')

  def test_avrcp_volume_control_from_android(self):
    """Test for AVRCP volume control from Android device.

    Precondition:
    1. Pair the Android device and Bluetooth reference device.
    2. Connect to the Bluetooth reference device.

    Test Steps:
    1. Play audio from Android device.
    2. Verify the audio is playing on Android device and Bluetooth
    reference device.
    3. Raise the volume on Android device.
    4. Verify the volume is adjusted on Android device and Bluetooth
    reference device.
    5. Lower the volume on Android device.
    6. Verify the volume is adjusted on Android device and Bluetooth
    reference device.

    Expected Results:
    1. Verify the audio is playing on Android device and Bluetooth
    reference device.
    2. Verify the volume is adjusted on Android device and Bluetooth
    reference device.
    """
    self.ad.bt_snippet.media3StartLocalFile(_PLAYLIST_PATHS[0])
    test_utils.wait_until_or_assert(
        condition=self.ad.bt_snippet.media3IsPlayerPlaying,
        error_msg='Failed to play media on Android device.',
        timeout=_MEDIA_PLAY_TIME,
    )
    self.ad.log.info('Setting volume to 5')
    self.ad.bt_snippet.setMusicVolume(5)
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.getMusicVolume() == 5,
        error_msg='Failed to set volume to 5 on Android device.',
        timeout=_STATE_SETTLE_TIME,
    )
    self.ad.log.info('Volume is now 50%.')

    self.ad.bt_snippet.media3AdjustVolume(
        media_utils.VolumeDirection.ADJUST_RAISE
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.getMusicVolume() == 6,
        error_msg='Failed to increase volume to 6 on Android device.',
        timeout=_STATE_SETTLE_TIME,
    )
    self.ad.log.info('Volume is now 60%.')

    self.ad.bt_snippet.media3AdjustVolume(
        media_utils.VolumeDirection.ADJUST_LOWER
    )
    test_utils.wait_until_or_assert(
        condition=lambda: self.ad.bt_snippet.getMusicVolume() == 5,
        error_msg='Failed to decrease volume to 5 on Android device.',
        timeout=_STATE_SETTLE_TIME,
    )
    self.ad.log.info('Volume is now 50%.')


if __name__ == '__main__':
  test_runner.main()
