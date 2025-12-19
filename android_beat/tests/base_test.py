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

"""Base test for Bluetooth."""

import datetime
import enum
import time

from mobly import asserts
from mobly import base_test
from mobly import records
from mobly import utils as mobly_utils
from mobly.controllers import android_device
from mobly.controllers.android_device_lib import apk_utils

from android_beat.platforms.bluetooth import bluetooth_reference_device
from android_beat.platforms.bluetooth import tws_device
from android_beat.utils import bluetooth_utils

_DELAY_BETWEEN_BLUETOOTH_STATE_CHANGE = datetime.timedelta(seconds=5)

_BLUETOOTH_SNIPPETS_PACKAGE = 'com.google.snippet.bluetooth'


@enum.unique
class BluetoothMode(enum.Enum):
  """The high-level operational modes for Bluetooth audio.

  Attributes:
    NONE: No active Bluetooth audio mode. This state requires the user to
      explicitly select a mode; otherwise, an error will occur.
    CLASSIC: Classic Bluetooth Audio. This mode includes standard profiles like
      HFP (Hands-Free Profile) and A2DP (Advanced Audio Distribution Profile).
    LEA: LE Audio (Low Energy Audio). This mode utilizes the Bluetooth Low
      Energy specification for audio transmission.
  """

  NONE = enum.auto()
  CLASSIC = enum.auto()
  LEA = enum.auto()


@enum.unique
class AndroidDeviceAmount(enum.IntEnum):
  """The required quantity of Android devices for a given test execution."""

  SINGLE_DEVICE = 1
  TWO_DEVICES = 2
  THREE_DEVICES = 3


class BaseTestClass(base_test.BaseTestClass):
  """Mobly Base test class for Bluetooth.

  Attributes:
    ad: The primary Android Device Under Test (DUT).
    ads: A list of Android devices used for testing.
    bt_device: The primary Bluetooth device under test.
    bt_devices: A list of Bluetooth devices used for testing.
    file_tag: The file tag used to get the file path from user params.
  """

  _ANDROID_DEVICE_AMOUNT = AndroidDeviceAmount.SINGLE_DEVICE
  _BLUETOOTH_MODE = BluetoothMode.NONE

  ad: android_device.AndroidDevice
  ads: list[android_device.AndroidDevice]
  bt_device: tws_device.TwsDevice
  bt_devices: list[tws_device.TwsDevice]
  file_tag: str

  def _setup_android_device(self, ad: android_device.AndroidDevice) -> None:
    """Sets up the Android device."""
    # Skip the setup wizard if exists.
    try:
      ad.adb.shell('am start -a com.android.setupwizard.EXIT')
    except android_device.adb.AdbError:
      ad.log.exception('Fail to exit the setup wizard, skipping...')

    # Enable Bluetooth HCI snoop log.
    try:
      ad.adb.shell('setprop persist.bluetooth.btsnooplogmode full')
      ad.adb.shell('setprop persist.bluetooth.btsnoopsize 0xfffffffffffffff')
    except android_device.adb.AdbError:
      ad.log.exception(
          'Fail to enable Bluetooth HCI snoop log, skipping...'
      )

    # Update LE audio connection policy.
    enable_le_audio = (
        'true' if self._BLUETOOTH_MODE == BluetoothMode.LEA else 'false'
    )
    try:
      ad.adb.shell(
          'setprop persist.bluetooth.leaudio.bypass_allow_list'
          f' {enable_le_audio}'
      )
    except android_device.adb.AdbError:
      ad.log.exception('Fail to update LE audio connection policy, skipping...')

    # Reboot the device to ensure the device is in the clean state.
    ad.reboot()

    # Install and load Bluetooth snippet apk.
    apk_path = "android_beat/snippet/bluetooth_snippets.apk"
    apk_utils.install(ad, apk_path)
    ad.load_snippet('bt_snippet', _BLUETOOTH_SNIPPETS_PACKAGE)

    # Clear saved devices before test starts
    bluetooth_utils.clear_saved_devices(ad)

    # Disable and enable Bluetooth to ensure it is in the clean state.
    ad.adb.shell('svc bluetooth disable')
    time.sleep(_DELAY_BETWEEN_BLUETOOTH_STATE_CHANGE.total_seconds())
    ad.adb.shell('svc bluetooth enable')
    time.sleep(_DELAY_BETWEEN_BLUETOOTH_STATE_CHANGE.total_seconds())

  def setup_class(self) -> None:
    asserts.abort_class_if(
        self._BLUETOOTH_MODE == BluetoothMode.NONE,
        'Please set the Bluetooth mode explicitly.',
    )

    self.file_tag = 'files' if 'files' in self.user_params else 'mh_files'

    self.ads = self.register_controller(
        android_device, min_number=self._ANDROID_DEVICE_AMOUNT
    )
    mobly_utils.concurrent_exec(
        self._setup_android_device,
        [[ad] for ad in self.ads],
        raise_on_exception=True,
    )
    self.ad = self.ads[0]

    self.bt_devices = self.register_controller(bluetooth_reference_device)
    mobly_utils.concurrent_exec(
        lambda d: d.factory_reset(),
        ([bt_device] for bt_device in self.bt_devices),
        raise_on_exception=True,
    )
    mobly_utils.concurrent_exec(
        lambda d: d.set_component_number(2),
        ([bt_device] for bt_device in self.bt_devices),
        raise_on_exception=True,
    )
    self.bt_device = self.bt_devices[0]

  def teardown_test(self) -> None:
    mobly_utils.concurrent_exec(
        lambda d: d.services.create_output_excerpts_all(self.current_test_info),
        [[ad] for ad in self.ads],
        raise_on_exception=True,
    )
    mobly_utils.concurrent_exec(
        lambda d: d.create_output_excerpts(self.current_test_info),
        [[bt_device] for bt_device in self.bt_devices],
        raise_on_exception=True,
    )

  def on_fail(self, record: records.TestResultRecord) -> None:
    android_device.take_bug_reports(
        self.ads, destination=self.current_test_info.output_path
    )

  def teardown_class(self):
    bluetooth_utils.clear_saved_devices(self.ad)
    mobly_utils.concurrent_exec(
        lambda d: d.factory_reset(),
        ([bt_device] for bt_device in self.bt_devices),
        raise_on_exception=True,
    )
