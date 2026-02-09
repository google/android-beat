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

"""Send file and receive file over RFCOMM."""

import datetime

from mobly import test_runner
from mobly import utils as mobly_utils

from android_beat.tests import base_test
from android_beat.utils import bluetooth_utils
from android_beat.utils import opp_utils
from android_beat.utils import test_utils


_BLUETOOTH_DISCOVERY_TIMEOUT = datetime.timedelta(seconds=120)
_BLUETOOTH_PAIRING_TIMEOUT = datetime.timedelta(seconds=120)
_DEFAULT_FILE_PATH = "/sdcard/Download"
_SECURE_TRANS_FILE_LIST = (
    "sine_tone_0.wav",
    "sine_tone_1.wav",
)
_INSECURE_TRANS_FILE_LIST = (
    "sine_tone_2.wav",
    "sine_tone_3.wav",
)
_ALL_TRANS_FILE_LIST = (
    "sine_tone_0.wav",
    "sine_tone_1.wav",
    "sine_tone_2.wav",
    "sine_tone_3.wav",
)


class BluetoothOppTest(base_test.BaseTestClass):
  """Send file and receive file over RFCOMM."""

  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.TWO_DEVICES
  _BLUETOOTH_MODE = base_test.BluetoothMode.CLASSIC
  _HAS_MEDIA = True
  _MEDIA_PLAYLIST_FILES = _ALL_TRANS_FILE_LIST
  _WITHOUT_BT_DEVICE = True

  def teardown_test(self) -> None:
    mobly_utils.concurrent_exec(
        bluetooth_utils.clear_saved_devices,
        [[self.ad], [self.ad_ref]],
        max_workers=2,
        raise_on_exception=True,
    )
    super().teardown_test()

  def test_bt_transfer_file_over_secure_rfcomme(self):
    """Test for sending file and receiving file over secure RFCOMM.

    Objective:
      To validate the Device Under Test (DUT) can successfully transfer files
      over a secure RFCOMM channel to a paired remote Bluetooth device (BT
      device).

    Test Preconditions:
      Device: 2 Android device.

    Steps:
      1. BT device starts pairing mode.
      2. DUT initiates Bluetooth discovery and verify the BT device is
      discovered.
      3. DUT pairs with the BT device and verify the pairing is successful.
      4. DUT sends file to the BT device and verify the file is received.

    Pass Criteria:
      1. DUT should pair with the BT device.
      2. DUT can send files through a secure API and Bt device can receive
         files normally
      3. The file size and md5 are the same.
    """
    if self.ad_ref is None:
      raise ValueError("Android reference device is not provided.")

    # BT device starts pairing mode.
    bluetooth_utils.start_pairing_mode(self.ad_ref)
    # DUT initiates Bluetooth discovery and verify the BT device is discovered.
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_discovered(
            self.ad, self.ad_ref.bt_address
        ),
        error_msg="Failed to discover Bluetooth device",
        timeout=_BLUETOOTH_DISCOVERY_TIMEOUT,
    )
    # DUT pairs with the BT device and verify the pairing is successful.
    bluetooth_utils.start_pairing_with_retry(self.ad, self.ad_ref.bt_address)
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_in_saved_devices(
            self.ad, self.ad_ref.bt_address
        ),
        error_msg="Failed to pair with Bluetooth device",
        timeout=_BLUETOOTH_PAIRING_TIMEOUT,
    )

    for file_name in _SECURE_TRANS_FILE_LIST:
      opp_utils.bt_send_file(
          self.ad,
          self.ad_ref,
          self.ad_ref.bt_address,
          send_file_path=f"{_DEFAULT_FILE_PATH}/{file_name}",
          received_file_path=f"{_DEFAULT_FILE_PATH}/receive_{file_name}",
          is_secure=True,
      )

  def test_bt_transfer_file_over_insecure_rfcomme(self):
    """Test for sending file and receiving file over insecure RFCOMM.

    Objective:
      To validate the Device Under Test (DUT) can successfully transfer files
      over an insecure RFCOMM channel to an unpaired remote Bluetooth device (BT
      device).

    Test Preconditions:
      Device: 2 Android device.

    Steps:
      1. DUT sends file to the BT device and verify the file is received.

    Pass Criteria:
      1. DUT can send files through an insecure API and Bt device can receive
         files normally
      2. The file size and md5 are the same.
    """
    if self.ad_ref is None:
      raise ValueError("Android reference device is not provided.")

    for file_name in _INSECURE_TRANS_FILE_LIST:
      opp_utils.bt_send_file(
          self.ad,
          self.ad_ref,
          self.ad_ref.bt_address,
          send_file_path=f"{_DEFAULT_FILE_PATH}/{file_name}",
          received_file_path=f"{_DEFAULT_FILE_PATH}/receive_{file_name}",
          is_secure=False,
      )


if __name__ == "__main__":
  test_runner.main()
