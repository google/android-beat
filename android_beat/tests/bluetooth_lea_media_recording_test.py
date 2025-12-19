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

"""Mobly test for LEA media recording."""

import datetime
import os
import time

from mobly import asserts
from mobly import test_runner

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import recording_utils
from android_beat.utils import test_utils

_MEDIA_FILES_BASENAMES = ('sine_tone_0.wav',)

_RECORDING_DURATION = datetime.timedelta(seconds=10)
_RECORDING_STATE_TIMEOUT = datetime.timedelta(seconds=30)


class BluetoothLeaMediaRecordingTest(base_test.BaseTestClass):
  """Mobly test for LEA media recording using MediaRecordingSnippet."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.LEA
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.SINGLE_DEVICE

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
    self.bt_device.factory_reset()
    audio_utils.generate_and_push_audio_files(
        self.ad,
        _MEDIA_FILES_BASENAMES,
        self.current_test_info.output_path,
    )
    self.real_generate_file_path = os.path.join(
        self.current_test_info.output_path, _MEDIA_FILES_BASENAMES[0]
    )
    self._pair_bluetooth_lea_device()

  def setup_test(self) -> None:
    asserts.skip_if(
        not self.ad.bt_snippet.btIsLeAudioSupported(),
        f'{self.ad} LE Audio is not supported',
    )
    if not self.ad.bt_snippet.btIsLeAudioConnected(
        self.bt_device.bluetooth_address_primary
    ):
      bluetooth_utils.clear_saved_devices(self.ad)
      self.bt_device.factory_reset()
      self._pair_bluetooth_lea_device()
    audio_utils.wait_and_assert_recording_has_ble_headset(self.ad)
    self.ad.bt_snippet.mediaStopRecording()
    self.ad.log.info('BLE headset is ready for recording.')

  def teardown_test(self):
    if self.ad.bt_snippet.mediaIsRecording():
      self.ad.bt_snippet.mediaStopRecording()
    # Clean up the file.
    self.ad.adb.shell(['rm', '-f', recording_utils.RECORDING_FILE_PATH])
    super().teardown_test()

  def test_start_stop_recording(self):
    """Tests starting and stopping media recording.

    Objective:
    To make sure the bluetooth device can start and stop recording correctly.

    Precondition:
    - DUT is paired with the primary BT device.
    - DUT is in LE Audio media mode.
    - DUT has a media file to play.
    - DUT has a BLE headset connected.

    Procedure:
    1. Start recording.
    2. Wait for the recording to finish.
    3. Stop recording.

    Verification:
    1. The recording file is saved to the expected path.
    2. The recording file is pulled to the host machine.
    """
    self.ad.log.info(
        'Starting recording, saving to %s', recording_utils.RECORDING_FILE_NAME
    )
    with recording_utils.record_audio_context(self.ad):
      time.sleep(_RECORDING_DURATION.total_seconds())  # Record for 10 seconds
      test_utils.wait_until_or_assert(
          condition=self.ad.bt_snippet.mediaIsRecording,
          error_msg='Media is not recording',
          timeout=_RECORDING_STATE_TIMEOUT,
      )
      test_utils.wait_until_or_assert(
          condition=lambda: self.ad.bt_snippet.mediaGetRecordingBleDeviceInfo()
          == self.bt_device.bluetooth_address_primary,
          error_msg='Recording device is not the primary BT device',
          timeout=_RECORDING_STATE_TIMEOUT,
      )
      self.ad.log.info(
          'Recording device info: %s',
          self.ad.bt_snippet.mediaGetRecordingBleDeviceInfo(),
      )
    pull_path = os.path.join(
        self.current_test_info.output_path, recording_utils.RECORDING_FILE_NAME
    )
    self.ad.adb.pull([recording_utils.RECORDING_FILE_PATH, pull_path])

if __name__ == '__main__':
  test_runner.main()
