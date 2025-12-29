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

"""Bluetooth Classic call control test."""

import datetime
import os

from mobly import asserts
from mobly import test_runner
from mobly.controllers import android_device

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import call_utils
from android_beat.utils import media_utils
from android_beat.utils import test_utils

_BLUETOOTH_DISCOVERY_TIMEOUT = datetime.timedelta(seconds=120)
_BLUETOOTH_PAIRING_TIMEOUT = datetime.timedelta(seconds=60)
_MAKE_CALL_TIMEOUT = datetime.timedelta(seconds=60)
_GET_CALL_STATE_TIMEOUT = datetime.timedelta(seconds=30)
_END_CALL_TIMEOUT = datetime.timedelta(seconds=30)

_DEFAULT_MUSIC_VOLUME = 80
_MEDIA_FILES_NAMES = ("sine_tone_0.wav",)
_MEDIA_FILES_PATHS = ("/sdcard/Download/sine_tone_0.wav",)


class BluetoothClassicCallControlTest(base_test.BaseTestClass):
  """Test class for Call control test."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.CLASSIC
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.TWO_DEVICES
  ad_ref: android_device.AndroidDevice

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
    self.ad_ref = self.ads[1]
    self._pair_bluetooth_device()
    audio_utils.generate_and_push_audio_files(
        self.ad,
        _MEDIA_FILES_NAMES,
        self.current_test_info.output_path,
    )
    self.generate_audio_file_path = os.path.join(
        self.current_test_info.output_path, _MEDIA_FILES_NAMES[0]
    )
    self.ad_ref.phone_number = call_utils.get_phone_number(self.ad_ref)
    self.ad.phone_number = call_utils.get_phone_number(self.ad)

  def setup_test(self) -> None:
    super().setup_test()
    if not self.ad.bt_snippet.btIsHfpConnected(
        self.bt_device.bluetooth_address_primary
    ):
      self.bt_device.factory_reset()
      bluetooth_utils.clear_saved_devices(self.ad)
      self._pair_bluetooth_device()

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
        error_msg="Failed to end the voice call on both devices",
        timeout=_END_CALL_TIMEOUT,
    )

  def test_disconnect_turn_off_bt_device(self):
    """Tests Bluetooth disconnect - turn off BT device.

    Objective:
      To validate the Device Under Test (DUT) can successfully disconnect from
      a remote Bluetooth device (BT device) when the BT device is turned off.

    Test Preconditions:
      Device: 1 Android device and 1 Bluetooth Reference Device.

    Test Steps:
      1. BT device turns off.
      2. Verify the A2DP and HEADSET profiles are disconnected.
      3. Verify the BT device is still in saved devices.
    Pass Criteria:
      1. DUT should disconnect A2DP/HFP (Classic) connection.
    """
    try:
      # Turn off the BT device
      self.bt_device.power_off()

      # Verify A2DP and HEADSET profiles are successfully unlinked and Android
      # system recognizes the correct audio device type.
      bluetooth_utils.wait_and_assert_a2dp_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=False
      )
      bluetooth_utils.wait_and_assert_hfp_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=False
      )
      audio_utils.wait_and_assert_audio_device_type(
          self.ad,
          audio_utils.AudioDeviceType.TYPE_BLUETOOTH_A2DP,
          expect_active=False,
      )
      audio_utils.wait_and_assert_audio_device_type(
          self.ad,
          audio_utils.AudioDeviceType.TYPE_BLUETOOTH_SCO,
          expect_active=False,
      )

      # Verify the BT device is still in saved devices.
      test_utils.wait_until_or_assert(
          condition=lambda: bluetooth_utils.is_bt_device_in_saved_devices(
              self.ad, self.bt_device.bluetooth_address_primary
          ),
          error_msg=(
              "Failed to keep pair status with Bluetooth device after turning"
              " off Bluetooth device"
          ),
          timeout=_BLUETOOTH_PAIRING_TIMEOUT,
      )
    finally:
      self.bt_device.power_on()

  def test_auto_connect_turn_on_bt_device(self) -> None:
    """Tests Bluetooth Hands-Free Profile connection when turn on headset.

    Objective:
      To validate the Device Under Test (DUT) can successfully reconnect to a
      remote Bluetooth device (BT device) when the paired BT device is turned
      on and call audio is routed to the BT device via the Hands-Free Profile.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Env: Live cellular network.

    Test Steps:
      1. Turn off the BT device.
      2. Verify the BT device is still in paired status.
      3. Turn on the BT device.
      4. Verify the BT profile is recognized and reconnected.
      5. Make a call and check phone audio.

    Pass Criteria:
      1. DUT can reconnect back to BT HS after BT HS is turned on.
      2. BT HS receive phone audio with HFP profile successfully.
    """

    try:
      # Turn off the BT device
      self.bt_device.power_off()

      # Verify HEADSET profile is successfully unlinked and Android system
      # recognizes the correct audio device type.
      bluetooth_utils.wait_and_assert_hfp_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=False
      )
      audio_utils.wait_and_assert_audio_device_type(
          self.ad,
          audio_utils.AudioDeviceType.TYPE_BLUETOOTH_SCO,
          expect_active=False,
      )

      # Verify the BT device is still in paired status
      asserts.assert_true(
          bluetooth_utils.is_bt_device_in_saved_devices(
              self.ad, self.bt_device.bluetooth_address_primary
          ),
          msg=(
              "Failed to keep pair status with Bluetooth device after turning"
              " off Bluetooth device"
          ),
      )
    finally:
      # Turn on the BT device
      self.bt_device.power_on()

    # Verify HEADSET profile is successfully linked and Android system
    # recognizes the correct audio device type.
    bluetooth_utils.wait_and_assert_hfp_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
    )
    audio_utils.wait_and_assert_audio_device_type(
        self.ad,
        audio_utils.AudioDeviceType.TYPE_BLUETOOTH_SCO,
        expect_active=True,
    )

    # Make a call from DUT to Android Reference device
    call_utils.place_call(self.ad, self.ad_ref.phone_number)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_RINGING,
        error_msg="Failed to make an outgoing call to the reference device",
        timeout=_MAKE_CALL_TIMEOUT,
    )
    call_utils.answer_call(self.ad_ref)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_OFFHOOK
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_OFFHOOK,
        error_msg="Failed to establish a voice call between devices",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

    # Verify the call audio routes to BT device.
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

  def test_answer_and_end_call_from_android(self) -> None:
    """Tests Bluetooth HFP connection when Android answer and end call.

    Objective:
      To validate the Device Under Test (DUT) pair and connect with Bluetooth
      device (BT device) and Android device successfully answer and end a
      call via the Hands-Free Profile.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Env: Live cellular network.

    Test Steps:
      1. Verify the HFP profile is recognizesd and connected.
      2. Make a call from Android Reference device to DUT.
      3. Answer the call from Android device.
      4. Verify the call audio routes to BT device.
      5. End the call from Android device.
      6. Verify the call ended and call audio stop routing to BT device.

    Pass Criteria:
      1. Call ring routes to BT device.
      2. Call should be answered by Android device and audio routs to BT device.
      4. Call audio should be clear and audible on the both BT device end.
      3. Call should be correctly ended by Android device.
    """

    # Make a call from Android Reference device to DUT.
    call_utils.place_call(self.ad_ref, self.ad.phone_number)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_RINGING,
        error_msg="Failed to make an outgoing call to the reference device",
        timeout=_MAKE_CALL_TIMEOUT,
    )

    # Answer the call from Android device.
    call_utils.answer_call(self.ad)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_OFFHOOK
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_OFFHOOK,
        error_msg="Failed to answer the call from Android device",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

    # Verify the call audio routes to BT device.
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    # End the call from Android device.
    call_utils.end_call(self.ad)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_IDLE
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_IDLE,
        error_msg="Failed to end the call from Android device",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

  def test_answer_and_end_call_from_bt_device(self) -> None:
    """Tests Bluetooth HFP connection when BT device answer and end call.

    Objective:
      To validate the Device Under Test (DUT) pair and connect with Bluetooth
      device (BT device) and bt_device successfully answer and end a call
      via the Hands-Free Profile.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Env: Live cellular network.

    Test Steps:
      1. Verify the HFP profile is recognizesd and connected.
      2. Make a call from Android Reference device to DUT.
      3. Answer the call from BT device.
      4. Verify the call audio routes to BT device.
      5. End the call from BT device.
      6. Verify the call ended.

    Pass Criteria:
      1. Call ring routes to BT device.
      2. Call should be answered by BT device and audio routs to BT device.
      3. Call should be correctly ended by BT device.
    """

    # Make a call from Android Reference device to DUT.
    call_utils.place_call(self.ad_ref, self.ad.phone_number)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_RINGING,
        error_msg="Failed to make an outgoing call to the reference device",
        timeout=_MAKE_CALL_TIMEOUT,
    )

    # Answer the call from BT device.
    self.bt_device.call_accept()
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_OFFHOOK
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_OFFHOOK,
        error_msg="Failed to answer the call from BT device",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

    # Verify the call audio routes to BT device.
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    # End the call from BT device.
    self.bt_device.call_decline()
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_IDLE
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_IDLE,
        error_msg="Failed to end the call from BT device",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

  def test_answer_call_from_bt_device_and_end_call_from_android(
      self,
  ) -> None:
    """Tests Bluetooth HFP connection when answer and end call.

    Objective:
      To validate the Device Under Test (DUT) pair and connect with Bluetooth
      device (BT device) and BT device successfully answer call and end a
      call on Android device via the Hands-Free Profile.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Env: Live cellular network.

    Test Steps:
      1. Verify the HFP profile is recognizesd and connected.
      2. Make a call from Android Reference device to DUT.
      3. Answer the call from BT device.
      4. Verify the call audio routes to BT device.
      5. End the call from Android device.

    Pass Criteria:
      1. Call ring routes to BT device.
      2. Call should be answered by BT device and audio routs to BT device.
      3. Call audio should be clear audible both BT device end.
      3. Call should be correctly ended by Android device.
    """

    # Make a call from Android Reference device to DUT.
    call_utils.place_call(self.ad_ref, self.ad.phone_number)

    # Answer the call from BT device.
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_RINGING,
        error_msg="Failed to make an outgoing call to the reference device",
        timeout=_MAKE_CALL_TIMEOUT,
    )
    self.bt_device.call_accept()
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_OFFHOOK
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_OFFHOOK,
        error_msg="Failed to answer the call from BT device",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

    # Verify the call audio routes to BT device.
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    # End the call from Android device.
    call_utils.end_call(self.ad)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_IDLE
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_IDLE,
        error_msg="Failed to end the call from Android device",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

  def test_reject_incoming_call_from_bt_device(self) -> None:
    """Tests Bluetooth HFP connection when rejecting call from BT device.

    Objective:
      To validate the Device Under Test (DUT) pair and connect with Bluetooth
      device (BT device) and make a call from Android reference device to DUT.
      Then BT device successfully reject incoming call.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Env: Live cellular network.

    Test Steps:

      1. Verify the HFP profile is recognizesd and connected.
      2. Make a call from Android Reference device to DUT.
      3. Reject the call from BT device.
      4. Verify the call state becomes idle on both Android device.

    Pass Criteria:
      1. Call ring routes to BT device.
      2. Call should be correctly ended by BT device.
    """

    # Make a call from Android Reference device to DUT.
    call_utils.place_call(self.ad_ref, self.ad.phone_number)

    # Reject the call from BT device.
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_RINGING,
        error_msg="Failed to make an outgoing call to the reference device",
        timeout=_MAKE_CALL_TIMEOUT,
    )
    self.bt_device.call_decline()

    # Veiry the call state becomes idle on both Android device.
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_IDLE
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_IDLE,
        error_msg="Failed to get IDLE state when BT device rejecting the call.",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

  def test_make_and_end_call_from_android(self) -> None:
    """Tests Bluetooth HFP connection outgoing and termating call from Android.

    Objective:
      To validate the Device Under Test (DUT) pair and connect with Bluetooth
      device (BT device) and make an outgoing call from DUT to Android reference
      device. Then DUT successfully end the call.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Env: Live cellular network.

    Test Steps:
      1. Verify the HFP profile is recognizesd and connected.
      2. Make a call from DUT to Android Reference device.
      3. Verify the BT device could hear the outgoing call ringing audio.
      4. Verify the call state becomes offhook on both Android device.
      5. Verify the call audio routes to BT device.
      5. End the call from Android device.
      6. Verify the call state becomes idle on both Android device.

    Pass Criteria:
      1. BT device should be able to hear the ring for outgoing call.
      2. Call audio should be hear clearly on both BT device end.
      2. Call should be ended by correctly by DUT.
    """

    # Make a call from DUT to Android Reference device.
    call_utils.place_call(self.ad, self.ad_ref.phone_number)

    # Verify the Android reference device is in ringing state.
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_RINGING,
        error_msg="Failed to make an outgoing call to the reference device",
        timeout=_MAKE_CALL_TIMEOUT,
    )

    # Answer the call from Android reference device.
    call_utils.answer_call(self.ad_ref)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_OFFHOOK
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_OFFHOOK,
        error_msg="Failed to establish a voice call between devices",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

    # Verify the call audio routs to BT device
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    # End the call from Android device.
    call_utils.end_call(self.ad)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_IDLE
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_IDLE,
        error_msg=(
            "Failed to get IDLE state when Android device rejecting the call."
        ),
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

  def test_make_call_from_android_and_end_call_from_bt_device(self) -> None:
    """Tests Bluetooth HFP connection make an outgoing call and terminate it.

    Objective:
      To validate the Device Under Test (DUT) pair and connect with Bluetooth
      device (BT device) and make an outgoing call from DUT to Android reference
      device. Then successfully end the call from BT device.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Env: Live cellular network.

    Test Steps:
      1. Verify the HFP profile is recognizesd and connected.
      2. Make a call from DUT to Android Reference device.
      3. Verify the BT device could hear the outgoing call ringing audio.
      4. Verify the call state becomes offhook on both Android device.
      5. Verify the call audio routes to BT device.
      6. End the call from BT device.
      7. Verify the call state becomes idle on both Android device.

    Pass Criteria:
      1. BT device should be able to hear the ring for outgoing call.
      2. Call audio should be hear clearly on both BT device end.
      2. Call should be ended by correctly by DUT.
    """

    # Make a call from DUT to Android Reference device.
    call_utils.place_call(self.ad, self.ad_ref.phone_number)

    # Verify the Android reference device is in ringing state.
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_RINGING,
        error_msg="Failed to make an outgoing call to the reference device",
        timeout=_MAKE_CALL_TIMEOUT,
    )

    # Answer the call from Android reference device.
    call_utils.answer_call(self.ad_ref)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_OFFHOOK
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_OFFHOOK,
        error_msg="Failed to establish a voice call between Android devices",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

    # Verify the call audio routs to BT device
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    # End the call from Android device.
    self.bt_device.call_decline()
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_IDLE
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_IDLE,
        error_msg="Failed to get IDLE state when BT device rejecting the call.",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

  def test_audio_transfer_during_call_bt_device_to_and_from_android(
      self,
  ) -> None:
    """Tests audio transfer between Android and BT device during a call.

    Objective:
      To validate the Device Under Test (DUT) pair and connect with Bluetooth
      device (BT device) and make an outgoing call to Android reference from
      Android device and verify audio transfer between Android and BT device.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Env: Live cellular network.

    Test Steps:
      1. BT device starts pairing mode.
      2. DUT initiates Bluetooth discovery.
      3. DUT pairs with the BT device and verify the pairing is successful.
      4. Verify the HFP profile is recognizesd and connected.
      5. Make a call from DUT to Android Reference device.
      6. Verify the call state becomes offhook on both Android device.
      7. Verify the call audio routes to BT device.
      8. Disconnect a2dp and HFP to transfer audio to Android device.
      9. Reconnect a2dp and HFP to transfer audio to BT device.
      10. Verify the call audio routes to BT device.

    Pass Criteria:
      1. Call audio should be correctly transferred between Android and BT
      device.
      2. Call audio should be hear clearly on both BT device end.
      2. Call quality should not get affected.
    """

    # Make a call from DUT to Android Reference device.
    call_utils.place_call(self.ad, self.ad_ref.phone_number)

    # Verify the Android reference device is in ringing state.
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_RINGING,
        error_msg="Failed to make an outgoing call to the reference device",
        timeout=_MAKE_CALL_TIMEOUT,
    )

    # Answer the call from Android reference device.
    call_utils.answer_call(self.ad_ref)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_OFFHOOK
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_OFFHOOK,
        error_msg="Failed to establish a voice call between Android devices",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

    # Verify the call audio routes to BT device
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    # Disconnect HFP to transfer audio to Android device.
    self.ad.bt_snippet.btA2dpDisconnect(
        self.bt_device.bluetooth_address_primary
    )
    self.ad.bt_snippet.btHfpDisconnect(self.bt_device.bluetooth_address_primary)

    # Verify the call audio routes to Android device
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_UNKNOWN
    )

    # Reconnect HFP to transfer audio to BT device.
    self.ad.bt_snippet.btA2dpConnect(self.bt_device.bluetooth_address_primary)
    self.ad.bt_snippet.btHfpConnect(self.bt_device.bluetooth_address_primary)

    # Verify the call audio routes to BT device
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )
    # call audio quality when transferring audio between devices.

  def test_turn_on_hf_during_active_call_from_bt_device(self) -> None:
    """Tests Bluetooth Hands-Free Profile connection when turn on headset.

    Objective:
      To validate the Device Under Test (DUT) can successfully reconnect to a
      remote Bluetooth device (BT device) when the BT device is turned on, and
      call audio is routed to the BT device via the Hands-Free Profile during a
      call.

    Test Preconditions:
      1. Device: 2 Android device with SIM and 1 Bluetooth reference device.
      2. Env: Live cellular network.

    Test Steps:
      1. Turn off the BT device.
      2. Verify the BT device is still in paired status.
      3. Make a call from DUT to BT device.
      4. Turn on the BT device.
      5. BT profile is recognizesd and reconnected.
      6. Verify the call audio routes to BT device.

    Pass Criteria:
      1. Call gets routed to HF when AG gets connected.
      2. Call should be audible both way.
    """

    try:
      # Turn off the BT device
      self.bt_device.power_off()

      # Verify HEADSET profile is successfully unlinked and Android system
      # recognizes the correct audio device type.
      bluetooth_utils.wait_and_assert_hfp_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=False
      )
      audio_utils.wait_and_assert_audio_device_type(
          self.ad,
          audio_utils.AudioDeviceType.TYPE_BLUETOOTH_SCO,
          expect_active=False,
      )

      # Verify the BT device is still in paired status
      asserts.assert_true(
          bluetooth_utils.is_bt_device_in_saved_devices(
              self.ad, self.bt_device.bluetooth_address_primary
          ),
          msg=(
              "Failed to keep pair status with Bluetooth device after turning"
              " offBT device"
          ),
      )

      # Make a call from DUT to Android Reference device
      call_utils.place_call(self.ad, self.ad_ref.phone_number)
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad_ref)
          == call_utils.CallState.CALL_STATE_RINGING,
          error_msg="Failed to make an outgoing call to the reference device",
          timeout=_MAKE_CALL_TIMEOUT,
      )
      call_utils.answer_call(self.ad_ref)
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad)
          == call_utils.CallState.CALL_STATE_OFFHOOK
          and call_utils.get_call_state(self.ad_ref)
          == call_utils.CallState.CALL_STATE_OFFHOOK,
          error_msg="Failed to establish a voice call between devices",
          timeout=_GET_CALL_STATE_TIMEOUT,
      )
    finally:
      # Turn on the BT device
      self.bt_device.power_on()

    # Verify HEADSET profile is successfully linked and Android system
    # recognizes the correct audio device type.
    bluetooth_utils.wait_and_assert_hfp_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
    )
    audio_utils.wait_and_assert_audio_device_type(
        self.ad,
        audio_utils.AudioDeviceType.TYPE_BLUETOOTH_SCO,
        expect_active=True,
    )

    # Verify call is still ongoing
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_OFFHOOK
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_OFFHOOK,
        error_msg="Failed to keep the voice call after reconnect HFP profile",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

    # Verify the call audio routes to BT device.
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
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
      1. Verify the BT profile is recognizesd and connected.
      2. Make a call from DUT to Android Reference device.
      3. Verify the call audio routes to BT device.
      4. Turn off the BT device.
      5. Verify the call audio stop routing to BT device.

    Pass Criteria:
      1. Call gets routed to BT device when it gets connected.
      2. Call should be audible both way.
    """

    # Make a call from DUT to Android Reference device
    call_utils.place_call(self.ad, self.ad_ref.phone_number)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_RINGING,
        error_msg="Failed to make an outgoing call to the reference device",
        timeout=_MAKE_CALL_TIMEOUT,
    )
    call_utils.answer_call(self.ad_ref)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_OFFHOOK
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_OFFHOOK,
        error_msg="Failed to establish a voice call between devices",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

    # Verify the call audio routes to BT device.
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    try:
      # Turn off the BT device
      self.bt_device.power_off()

      # Verify HEADSET profile is successfully unlinked and Android system
      # recognizes the correct audio device type.
      bluetooth_utils.wait_and_assert_hfp_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=False
      )
      audio_utils.wait_and_assert_audio_device_type(
          self.ad,
          audio_utils.AudioDeviceType.TYPE_BLUETOOTH_SCO,
          expect_active=False,
      )

      # Verify call is still ongoing
      test_utils.wait_until_or_assert(
          condition=lambda: call_utils.get_call_state(self.ad)
          == call_utils.CallState.CALL_STATE_OFFHOOK
          and call_utils.get_call_state(self.ad_ref)
          == call_utils.CallState.CALL_STATE_OFFHOOK,
          error_msg=(
              "Failed to keep the voice call after disconnect HFP profile"
          ),
          timeout=_GET_CALL_STATE_TIMEOUT,
      )

      # Verify the call audio stop routes to BT device.
      media_utils.wait_for_expected_media_router_type(
          self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
      )
    finally:
      self.bt_device.power_on()
  # Notes: this bug will cause BES board crash and affects others tests.
  def _test_media_stream_call_turn_off_active_call_from_bt_device(self) -> None:
    """Tests Bluetooth media stream - call - turn off active call.

    Objective:
      1. Device: 2 Android device with SIM connecting to WiFi and 1 Bluetooth
      reference device.
      2. Env: Live cellular network.
      3. Network: WiFi.

    Test Steps:
      1. DUT pair and connect with LE Audio headset.
      2. DUT set volume level to 80% and stream media.
      3. Verify the media routes to BT device.
      4. DUT make a call to another Android device.
      5. Turn off BT on DUT.
      6. Verify call routs to DUT.
      7. Turn on BT on DUT.
      8. Verify BT devices reconnects to DUT and call routs to BT device.

    Pass Criteria:
      1. DUT pair and connect with HFP profile when disabled LE Audio.
      2. DUT pair and connect with LE Audio headset when enabled LE Audio.
      3. When DUT turn off BT, call should be routed to DUT.
      4. When DUT turn on BT, call should be routed back to BT device.
      5. Call audio volume should be the same level, which was set before
      disconnect, when re-renabing BT.
    """

    # Play media on DUT
    self.ad.bt_snippet.media3StartLocalFile(_MEDIA_FILES_PATHS[0])

    # Verify the media is playing on the BT device.
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    # DUT set call volume level to 80%.
    self.ad.bt_snippet.setVoiceCallVolume(_DEFAULT_MUSIC_VOLUME)

    # Make a call from DUT to Android Reference device
    call_utils.place_call(self.ad, self.ad_ref.phone_number)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_RINGING,
        error_msg="Failed to make an outgoing call to the reference device",
        timeout=_MAKE_CALL_TIMEOUT,
    )
    call_utils.answer_call(self.ad_ref)
    test_utils.wait_until_or_assert(
        condition=lambda: call_utils.get_call_state(self.ad)
        == call_utils.CallState.CALL_STATE_OFFHOOK
        and call_utils.get_call_state(self.ad_ref)
        == call_utils.CallState.CALL_STATE_OFFHOOK,
        error_msg="Failed to establish a voice call between devices",
        timeout=_GET_CALL_STATE_TIMEOUT,
    )

    # Verify the call audio routes to BT device.
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    # Turn off the BT device on DUT.
    self.ad.bt_snippet.btDisable()
    # media stream to speaker.
    # Verify the call audio routes to DUT.
    media_utils.wait_for_expected_media_router_type(
        self.ad, media_utils.MediaRouterType.DEVICE_TYPE_BLUETOOTH
    )

    # Turn on the BT device on DUT.
    self.ad.bt_snippet.btEnable()
    # Verify the BT device is still in paired status
    asserts.assert_true(
        bluetooth_utils.is_bt_device_in_saved_devices(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        msg=(
            "Failed to keep pair status with Bluetooth device after turning off"
            " Bluetooth device"
        ),
    )

    # Verify HEADSET profile is successfully linked and Android system
    # recognizes the correct audio device type.
    bluetooth_utils.wait_and_assert_hfp_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
    )
    audio_utils.wait_and_assert_audio_device_type(
        self.ad,
        audio_utils.AudioDeviceType.TYPE_BLUETOOTH_SCO,
        expect_active=True,
    )

    # Verify DUT's call volume level is same as 80%.
    asserts.assert_equal(
        self.ad.bt_snippet.getVoiceCallVolume(_DEFAULT_MUSIC_VOLUME),
        _DEFAULT_MUSIC_VOLUME,
        msg="Failed to set call volume level to {_DEFAULT_MUSIC_VOLUME}",
    )


if __name__ == "__main__":
  test_runner.main()
