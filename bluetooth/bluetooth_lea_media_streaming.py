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

"""Bluetooth LE Audio unicast - media streaming test."""

import datetime

from mobly import asserts
from mobly import test_runner
from mobly import records

from bluetooth import audio_utils
from bluetooth import base_test
from bluetooth import bluetooth_utils
from bluetooth import test_utils

_MEDIA_FILE_PATH = '/sdcard/Download/pixel_ringtone.wav'
_MEDIA_PLAY_TIME = datetime.timedelta(seconds=15)


class BluetoothLeaMediaStreamingTest(base_test.BaseTestClass):
  """Media streaming tests for Bluetooth LE Audio."""

  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.SINGLE_DEVICE
  _BLUETOOTH_MODE = base_test.BluetoothMode.LEA

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
    asserts.abort_class_if(
        not self.ad.bt_snippet.btIsLeAudioSupported(),
        f'{self.ad} LE Audio is not supported',
    )

    self._pair_bluetooth_lea_device()

    self.ad.adb.push(
        [self.user_params[self.file_tag]['media_files'][0], _MEDIA_FILE_PATH]
    )

  def setup_test(self) -> None:
    # Check if LEA is still connected. If not, factory reset the Bluetooth
    # device and repair it.
    if not self.ad.bt_snippet.btIsLeAudioConnected(
        self.bt_device.bluetooth_address_primary
    ):
      bluetooth_utils.clear_saved_devices(self.ad)
      self.bt_device.factory_reset()
      self._pair_bluetooth_lea_device()

  @records.uid('7094b686-e5b4-4f7f-bb71-42e58800fece')
  def test_streaming(self):
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
      self.bt_device.start_audio_recording()
      self.ad.bt_snippet.media3StartLocalFile(_MEDIA_FILE_PATH)
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
      self.bt_device.stop_audio_recording(self.current_test_info.output_path)


if __name__ == '__main__':
  test_runner.main()
