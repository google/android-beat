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

"""Bluetooth A2DP with call test."""

import contextlib
import datetime
import os
import time

from mobly import test_runner
from mobly import records
from mobly.controllers import android_device

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import call_utils
from android_beat.utils import media_utils
from android_beat.utils import test_utils

_AUDIO_CONNECTION_TIMEOUT = datetime.timedelta(seconds=15)
_MAKE_CALL_TIMEOUT = datetime.timedelta(seconds=30)
_GET_CALL_STATE_TIMEOUT = datetime.timedelta(seconds=30)
_END_CALL_TIMEOUT = datetime.timedelta(seconds=30)
_MEDIA_PLAY_TIME = datetime.timedelta(seconds=30)


class BluetoothA2dpWithCallTest(base_test.BaseTestClass):
  """Test class for Bluetooth A2DP with call test."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.CLASSIC
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.TWO_DEVICES
  _MEDIA_FILES_NAMES = ('sine_tone_0.wav',)
  _MEDIA_FILES_PATHS = ('/sdcard/Download/sine_tone_0.wav',)
  ad_ref: android_device.AndroidDevice
  generate_audio_file_path: str

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
    self.ad_ref = self.ads[1]
    audio_utils.generate_and_push_audio_files(
        self.ad,
        self._MEDIA_FILES_NAMES,
        self.current_test_info.output_path,
    )
    self.generate_audio_file_path = os.path.join(
        self.current_test_info.output_path, self._MEDIA_FILES_NAMES[0]
    )

  @contextlib.contextmanager
  def _media_playback_context(self, file_path: str):
    """Context manager for playing local media."""
    try:
      self.ad.bt_snippet.media3StartLocalFile(file_path)
      test_utils.wait_until_or_assert(
          condition=self.ad.bt_snippet.media3IsPlayerPlaying,
          error_msg='Failed to start media playback on the DUT',
          timeout=_AUDIO_CONNECTION_TIMEOUT,
      )
      yield
    finally:
      # Stop the media.
      self.ad.bt_snippet.media3Stop()
      # Verify the media stops streaming to the BT device from DUT.
      bluetooth_utils.wait_and_assert_a2dp_playback_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=False
      )

  @contextlib.contextmanager
  def _bt_audio_recording_context(self, target_audio_file: str):
    """Context manager for recording audio on the BT device."""
    audio_utils.start_audio_recording(self.bt_device)
    try:
      yield
    finally:
      recorded_audio_files_on_host = audio_utils.stop_audio_recording(
          self.bt_device, self.current_test_info.output_path
      )
      audio_utils.assert_has_audio_start_time(
          target_audio_file,
          recorded_audio_files_on_host,
      )

  @contextlib.contextmanager
  def _phone_call_context(self):
    """Context manager for handling a phone call between two Android devices."""
    ad_ref_number = call_utils.get_phone_number(self.ad_ref)
    call_utils.place_call(self.ad, ad_ref_number)
    try:
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad_ref)
          == call_utils.CallState.CALL_STATE_RINGING,
          error_msg='Failed to make an outgoing call to the reference device',
          timeout=_MAKE_CALL_TIMEOUT,
      )
      call_utils.answer_call(self.ad_ref)
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad)
          == call_utils.CallState.CALL_STATE_OFFHOOK
          and call_utils.get_call_state(self.ad_ref)
          == call_utils.CallState.CALL_STATE_OFFHOOK,
          error_msg='Failed to establish a voice call between devices',
          timeout=_GET_CALL_STATE_TIMEOUT,
      )
      yield
    finally:
      call_utils.end_call(self.ad)
      call_utils.end_call(self.ad_ref)
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad)
          == call_utils.CallState.CALL_STATE_IDLE
          and call_utils.get_call_state(self.ad_ref)
          == call_utils.CallState.CALL_STATE_IDLE,
          error_msg='Failed to end the voice call on both devices',
          timeout=_END_CALL_TIMEOUT,
      )

  @records.uid('b4bd5d0c-30b7-4555-ab17-1ba16b660221')
  def test_a2dp_stream_resume_back_after_call_end_with_bt_device(self):
    """A2DP stream resume back after call end with BT device.

    Objective:
      To validate the Device Under Test (DUT) can successfully resume the A2DP
      stream back to the BT device after the call is ended with the Bluetooth
      device.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Sine_tone audio generated on the host and pushed to the device.

    Test Steps:
      1. Start audio recording.
      2. DUT plays local music, and verify it routes to BT device.
      3. DUT make a call to Android Reference device.
      4. Verify the music is paused and call audio routes to BT device.
      5. End the call on both Android devices.
      6. Verify the music is resumed back on the BT device.
      7. Stop the media on DUT
      8. Verify the media stops streaming to the BT device from DUT.
      9. Stop audio recording.
      10. Detect the target audio and srouce audio start time.

    Pass Criteria:
      1. DUT can reconnect back to BT HS after BT HS is turned on.
      2. BT HS receive phone audio with HFP profile successfully.
    """
    # Set the media volume to maximum.
    # This is for achieving optimal sound clarity in audio recordings.
    max_music_volume = self.ad.bt_snippet.getMusicMaxVolume()
    self.ad.bt_snippet.setMusicVolume(max_music_volume)

    with self._media_playback_context(self._MEDIA_FILES_PATHS[0]):
      # Step 1 & 2: Start audio recording & Verify DUT plays local music to BT.
      with self._bt_audio_recording_context(self.generate_audio_file_path):
        # Verify the media is playing on the BT device.
        bluetooth_utils.wait_and_assert_a2dp_playback_state(
            self.ad,
            self.bt_device.bluetooth_address_primary,
            expect_active=True,
        )
        time.sleep(_MEDIA_PLAY_TIME.total_seconds())

      # Step 3 & 4: Make a call.
      with self._phone_call_context():
        # Verify the call audio routes to BT device.
        media_utils.wait_for_expected_media_router_type(
            self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
        )

      # Step 5 & 6: After call end, start recording again and verify media
      # resumes.
      with self._bt_audio_recording_context(self.generate_audio_file_path):
        # Verify the media is playing on the BT device.
        bluetooth_utils.wait_and_assert_a2dp_playback_state(
            self.ad,
            self.bt_device.bluetooth_address_primary,
            expect_active=True,
            timeout=_AUDIO_CONNECTION_TIMEOUT,
        )
        # Ensure media continues playing for some duration to be recorded.
        time.sleep(_MEDIA_PLAY_TIME.total_seconds())


if __name__ == '__main__':
  test_runner.main()
