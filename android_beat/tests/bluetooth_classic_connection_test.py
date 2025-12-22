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

"""Bluetooth Classic connection test."""

import datetime

from mobly import test_runner

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import test_utils

_BLUETOOTH_DISCOVERY_TIMEOUT = datetime.timedelta(seconds=120)
_BLUETOOTH_PAIRING_TIMEOUT = datetime.timedelta(seconds=60)


class BluetoothClassicConnectionTest(base_test.BaseTestClass):
  """Connection tests for Bluetooth Classic."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.CLASSIC
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.SINGLE_DEVICE

  def setup_test(self) -> None:
    """Sets up the test."""
    bluetooth_utils.clear_saved_devices(self.ad)
    self.bt_device.factory_reset()

  def teardown_test(self) -> None:
    """Tears down the test."""
    super().teardown_test()
    bluetooth_utils.clear_saved_devices(self.ad)

  def test_discovery(self):
    """Tests Bluetooth discovery.

    Objective:
      To validate the Device Under Test (DUT) can successfully discover a
      remote Bluetooth device (BT device).

    Test Preconditions:
      Device: 1 Android device and 1 Bluetooth Reference Device.

    Test Steps:
      1. BT device starts pairing mode.
      2. DUT initiates Bluetooth discovery.

    Pass Criteria:
      1. DUT should discover the BT device.
    """
    # BT device starts pairing mode.
    bluetooth_utils.start_pairing_mode(
        self.bt_device, timeout=_BLUETOOTH_DISCOVERY_TIMEOUT
    )

    # DUT initiates Bluetooth discovery and verify the BT device is discovered.
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_discovered(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to discover Bluetooth device',
        timeout=_BLUETOOTH_DISCOVERY_TIMEOUT,
    )

  def test_pairing(self):
    """Tests Bluetooth pairing.

    Objective:
      To validate the Device Under Test (DUT) can successfully establish a
      pairing link with a remote Bluetooth device (BT device).

    Test Preconditions:
      Device: 1 Android device and 1 Bluetooth Reference Device.

    Test Steps:
      1. BT device starts pairing mode.
      2. DUT initiates Bluetooth discovery.
      3. DUT pairs with the BT device.

    Pass Criteria:
      1. DUT should pair with the BT device.
      2. DUT should establish A2DP/HFP (Classic) or LE Audio connection.
    """
    # BT device starts pairing mode.
    bluetooth_utils.start_pairing_mode(
        self.bt_device, timeout=_BLUETOOTH_DISCOVERY_TIMEOUT
    )

    # DUT initiates Bluetooth discovery and verify the BT device is discovered.
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_discovered(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to discover Bluetooth device',
        timeout=_BLUETOOTH_DISCOVERY_TIMEOUT,
    )

    # DUT pairs with the BT device and verify the pairing is successful.
    bluetooth_utils.start_pairing_with_retry(
        self.ad, self.bt_device.bluetooth_address_primary
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_in_saved_devices(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to pair with Bluetooth device',
        timeout=_BLUETOOTH_PAIRING_TIMEOUT,
    )

    # Verify A2DP and HEADSET profiles are successfully linked and Android
    # system recognizes the correct audio device type.
    bluetooth_utils.wait_and_assert_a2dp_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
    )
    bluetooth_utils.wait_and_assert_hfp_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
    )
    audio_utils.wait_and_assert_audio_device_type(
        self.ad,
        audio_utils.AudioDeviceType.TYPE_BLUETOOTH_A2DP,
        expect_active=True,
    )
    audio_utils.wait_and_assert_audio_device_type(
        self.ad,
        audio_utils.AudioDeviceType.TYPE_BLUETOOTH_SCO,
        expect_active=True,
    )


if __name__ == '__main__':
  test_runner.main()
