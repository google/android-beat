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

"""Bluetooth LE Audio call control test."""

import datetime

from mobly import test_runner
from mobly.controllers import android_device

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import call_utils
from android_beat.utils import media_utils
from android_beat.utils import test_utils

_MAKE_CALL_TIMEOUT = datetime.timedelta(seconds=60)
_GET_CALL_STATE_TIMEOUT = datetime.timedelta(seconds=30)
_END_CALL_TIMEOUT = datetime.timedelta(seconds=30)


class BluetoothLeaCallControlTest(base_test.BaseTestClass):
  """Test class for LE Audio Call control test."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.LEA
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.TWO_DEVICES
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
    self.ad.phone_number = call_utils.get_phone_number(self.ad)
    self.ad_ref.phone_number = call_utils.get_phone_number(self.ad_ref)

  def setup_test(self) -> None:
    super().setup_test()
    if not self.ad.bt_snippet.btIsLeAudioConnected(
        self.bt_device.bluetooth_address_primary
    ):
      self.bt_device.factory_reset()
      bluetooth_utils.clear_saved_devices(self.ad)
      self._pair_bluetooth_lea_device()

  def teardown_test(self) -> None:
    super().teardown_test()
    # End the call on both devices
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

  def test_turn_off_hf_during_active_call_from_bt_device(self) -> None:
    """Tests Bluetooth Hands-Free Profile connection when turn off headset.

    Objective:
      To validate the Device Under Test (DUT) can successfully disconnect to a
      remote Bluetooth device (BT device) depends on the BT device is turned off
      and call audio stop routing to the BT device via the Hands-Free Profile.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Env: Live cellular network.

    Test Steps:
      1. Make a call from DUT to Android Reference device.
      2. Verify the call audio routes to BT device.
      3. Turn off the BT device.
      4. Verify the call audio stop routing to BT device.

    Pass Criteria:
      1. Call gets routed to BT device when it gets connected.
      2. Call should be audible both way.
    """

    # Make a call from DUT to Android Reference device
    call_utils.place_call(self.ad, self.ad_ref.phone_number)
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

    # Verify the call audio routes to BT device.
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    try:
      # Turn off the BT device
      self.bt_device.power_off()

      # Verify LE Audio profile is successfully unlinked and Android system
      # recognizes the correct audio device type.
      bluetooth_utils.wait_and_assert_lea_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=False
      )
      audio_utils.wait_and_assert_audio_device_type(
          self.ad,
          audio_utils.AudioDeviceType.TYPE_BLE_HEADSET,
          expect_active=False,
      )

      # Verify call is still ongoing
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad)
          == call_utils.CallState.CALL_STATE_OFFHOOK
          and call_utils.get_call_state(self.ad_ref)
          == call_utils.CallState.CALL_STATE_OFFHOOK,
          error_msg=(
              'Failed to keep the voice call after disconnect HFP profile'
          ),
          timeout=_GET_CALL_STATE_TIMEOUT,
      )

      # Verify the call audio stop routes to BT device.
      media_utils.wait_for_expected_media_router_type(
          self.ad, media_utils.MediaRouterType.DEVICE_TYPE_UNKNOWN
      )
    finally:
      self.bt_device.power_on()

  def test_incoming_call_answer_from_android_device(self):
    """Test answer incoming call from Android device.

    Objective:
      To validate the Device Under Test (DUT) can successfully answer an
      incoming call from Android device.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.

    Predictions:
      1. BT device is paired with DUT.
      2. LE Audio profile is connected.

    Test Steps:
      1. DUT pair and connect with LE Audio headset.
      2. DUT make a call to Android Reference device.
      3. Verify the call state is ringing on both android devices.
      4. DUT answer the call.
      5. Verify the call state is offhook on both android devices.
      6. DUT end the call.
      7. Verify the call state is idle on both android devices.

    Pass Criteria:
      1. DUT can successfully answer an incoming call from Android device.
      2. DUT can successfully end the call.
    """
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

    call_utils.end_call(self.ad)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_IDLE,
        error_msg='Failed to end the voice call',
        timeout=_GET_CALL_STATE_TIMEOUT,
    )


if __name__ == '__main__':
  test_runner.main()
