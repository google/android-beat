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

"""Bluetooth LE Audio unicast - media streaming test with call."""

import datetime

from mobly import test_runner
from mobly.controllers import android_device

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import call_utils
from android_beat.utils import media_utils
from android_beat.utils import test_utils

_AUDIO_CONNECTION_TIMEOUT = datetime.timedelta(seconds=20)
_MEDIA_PLAY_TIME = datetime.timedelta(seconds=15)
_END_CALL_TIMEOUT = datetime.timedelta(seconds=10)
_MAKE_CALL_TIMEOUT = datetime.timedelta(seconds=30)
_GET_CALL_STATE_TIMEOUT = datetime.timedelta(seconds=30)


class BluetoothLeaMediaStreamingWithCallTest(base_test.BaseTestClass):
  """Media streaming with call tests for Bluetooth LE Audio."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.LEA
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.TWO_DEVICES
  _MEDIA_FILES_NAMES = ('sine_tone_0.wav',)
  _MEDIA_FILES_PATHS = ('/sdcard/Download/sine_tone_0.wav',)
  ad_ref: android_device.AndroidDevice

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
    self.ad_ref = self.ads[1]
    self._pair_bluetooth_lea_device()
    audio_utils.generate_and_push_audio_files(
        self.ad,
        self._MEDIA_FILES_NAMES,
        self.current_test_info.output_path,
    )
    self.ad.phone_number = call_utils.get_phone_number(self.ad)
    self.ad_ref.phone_number = call_utils.get_phone_number(self.ad_ref)

  def test_call_interrupt_media_streaming(self):
    """Call interrupt when media streaming.

    Obejctive:
      To validate the Device Under Test (DUT) can successfully make a call and
      interrupt the media streaming via LE Audio.

    Test Preconditions:
      1. Device: 2 Android devices and 1 Bluetooth reference device.

    Test Steps:
      1. Play local media on DUT and routes to the connected device.
      2. Verify the media routes to BT device continuously for 1 minute.
      3. REF make a voice call to DUT, and DUT answer the call.
      4. Verify the media is paused and call audio is routed to BT device when
      DUT answer the call.
      5. Verify the media is resumed when DUT end the call.

    Pass Criteria:
      1. DUT can play media and routes to the connected device without breaks.
    """
    # Play local media on DUT and routes to the connected device.
    try:
      self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_FILES_PATHS[0])
      test_utils.wait_until_or_assert(
          condition=self.ad.bt_snippet.media3IsPlayerPlaying,
          error_msg='Failed to play media on bt device via LE Audio',
          timeout=_AUDIO_CONNECTION_TIMEOUT,
      )
      test_utils.wait_until_or_assert(
          condition=lambda: media_utils.get_media_router_type(self.ad)
          == media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH,
          error_msg='Failed to play media on bt device via LE Audio',
          timeout=_AUDIO_CONNECTION_TIMEOUT,
      )
      # Make a call to DUT.
      call_utils.place_call(self.ad_ref, self.ad.phone_number)
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad)
          == call_utils.CallState.CALL_STATE_RINGING,
          error_msg='Failed to make an outgoing call to the reference device',
          timeout=_MAKE_CALL_TIMEOUT,
      )
      call_utils.answer_call(self.ad)
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad)
          == call_utils.CallState.CALL_STATE_OFFHOOK
          and call_utils.get_call_state(self.ad_ref)
          == call_utils.CallState.CALL_STATE_OFFHOOK,
          error_msg='Failed to establish a voice call between devices',
          timeout=_GET_CALL_STATE_TIMEOUT,
      )

      test_utils.wait_until_or_assert(
          lambda: bluetooth_utils.is_le_audio_streaming_active(
              self.ad, self.bt_device.bluetooth_address_primary
          ),
          error_msg='failed to stream media on bt device via LE Audio',
          timeout=_MEDIA_PLAY_TIME,
      )
      test_utils.wait_until_or_assert(
          condition=lambda: not self.ad.bt_snippet.media3IsPlayerPlaying(),
          error_msg=(
              'should to pause media because of incoming call, but failed'
          ),
          timeout=_AUDIO_CONNECTION_TIMEOUT,
      )
      call_utils.end_call(self.ad)
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad)
          == call_utils.CallState.CALL_STATE_IDLE,
          error_msg='Failed to end the voice call on DUT',
          timeout=_END_CALL_TIMEOUT,
      )
      test_utils.wait_until_or_assert(
          condition=self.ad.bt_snippet.media3IsPlayerPlaying,
          error_msg='Failed to resume media to BT device after call end',
          timeout=_AUDIO_CONNECTION_TIMEOUT,
      )
    finally:
      call_utils.end_call(self.ad_ref)
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad_ref)
          == call_utils.CallState.CALL_STATE_IDLE,
          error_msg='Failed to end the voice call on reference device',
          timeout=_END_CALL_TIMEOUT,
      )
      self.ad.bt_snippet.media3Stop()


if __name__ == '__main__':
  test_runner.main()
