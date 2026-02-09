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

import enum

from mobly import asserts
from mobly import base_test
from mobly import records
from mobly import utils as mobly_utils
from mobly.controllers import android_device

from android_beat.platforms.bluetooth import bluetooth_reference_device
from android_beat.platforms.bluetooth import tws_device
from android_beat.utils import android_setup_utils
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import call_utils


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
  """

  _ANDROID_DEVICE_AMOUNT = AndroidDeviceAmount.SINGLE_DEVICE
  _BLUETOOTH_MODE = BluetoothMode.NONE
  _HAS_MEDIA = False
  _WITHOUT_BT_DEVICE = False
  _HAS_CALL = False

  _MEDIA_PLAYLIST_FILES = ('sine_tone_0.wav', 'sine_tone_1.wav')
  _MEDIA_PLAYLIST_PATHS = (
      '/sdcard/Download/sine_tone_0.wav',
      '/sdcard/Download/sine_tone_1.wav',
  )

  ad: android_device.AndroidDevice
  ad_ref: android_device.AndroidDevice | None
  ad_ter: android_device.AndroidDevice | None
  ads: list[android_device.AndroidDevice]
  bt_device: tws_device.TwsDevice
  bt_devices: list[tws_device.TwsDevice]
  generate_audio_file_paths: list[str]

  def _setup_android_device(self, ad: android_device.AndroidDevice) -> None:
    """Sets up the Android device."""
    android_setup_utils.skip_setup_wizard(ad)
    android_setup_utils.enable_bluetooth_hci_snoop_log(ad)
    android_setup_utils.update_le_audio_connection_policy(
        ad, is_lea_enabled=self._BLUETOOTH_MODE == BluetoothMode.LEA
    )
    android_setup_utils.install_and_load_bluetooth_snippet(
        ad,
        "android_beat/snippet/bluetooth_snippets.apk",
    )
    call_utils.get_phone_number_if_need_call(ad, self._HAS_CALL)

    bluetooth_utils.clear_saved_devices(ad)
    bluetooth_utils.reset_android_bluetooth_state(ad)
    bluetooth_utils.get_devices_bluetooth_address(ad)

  def setup_class(self) -> None:
    # if abort class, please check the Bluetooth mode is set explicitly.
    asserts.abort_class_if(
        self._BLUETOOTH_MODE == BluetoothMode.NONE,
        'Please set the Bluetooth mode explicitly.',
    )

    # Initialize and register Android devices.
    self.ads = self.register_controller(
        android_device, min_number=self._ANDROID_DEVICE_AMOUNT
    )
    mobly_utils.concurrent_exec(
        self._setup_android_device,
        [[ad] for ad in self.ads],
        raise_on_exception=True,
    )
    self.ad, self.ad_ref, self.ad_ter = android_setup_utils.get_android_devices(
        self.ads, self._ANDROID_DEVICE_AMOUNT
    )

    # Initialize and register Bluetooth devices.
    if self._WITHOUT_BT_DEVICE:
      self.bt_devices = []
    else:
      self.bt_devices = self.register_controller(bluetooth_reference_device)
      self.bt_device = bluetooth_utils.reset_bluetooth_devices(self.bt_devices)
      bluetooth_utils.pair_and_assert_bluetooth_state(
          self.ad, [self.bt_device], self._BLUETOOTH_MODE == BluetoothMode.LEA
      )

    self.generate_audio_file_paths = (
        audio_utils.generate_and_push_audio_files_to_device(
            self.ad,
            self._MEDIA_PLAYLIST_FILES,
            self.current_test_info.output_path,
            has_media=self._HAS_MEDIA,
        )
    )

  def setup_test(self) -> None:
    if self._WITHOUT_BT_DEVICE:
      return

    android_setup_utils.check_connection_and_reconnect(
        self.ad,
        self.bt_device,
        self._BLUETOOTH_MODE == BluetoothMode.LEA,
    )
    android_setup_utils.stop_media_on_android_device_if_has_media(
        self.ad, self._HAS_MEDIA
    )

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
    mobly_utils.concurrent_exec(
        call_utils.end_call_and_check_idle,
        [
            [self.ad, self._HAS_CALL],
            [self.ad_ref, self._HAS_CALL],
            [self.ad_ter, self._HAS_CALL],
        ],
        raise_on_exception=True,
    )
    android_setup_utils.stop_media_on_android_device_if_has_media(
        self.ad, self._HAS_MEDIA
    )

  def on_fail(self, record: records.TestResultRecord) -> None:
    android_device.take_bug_reports(
        self.ads, destination=self.current_test_info.output_path
    )

  def teardown_class(self):
    if self._WITHOUT_BT_DEVICE:
      bluetooth_utils.clear_saved_devices(self.ad, self.ad_ref.bt_address)
    else:
      bluetooth_utils.clear_saved_devices(
          self.ad, [self.bt_device.bluetooth_address_primary]
      )
    mobly_utils.concurrent_exec(
        lambda d: d.factory_reset(),
        ([bt_device] for bt_device in self.bt_devices),
        raise_on_exception=True,
    )
