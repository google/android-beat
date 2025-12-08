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

"""Utility functions related to Audio operations."""

import datetime
import enum

from mobly.controllers import android_device

from bluetooth import test_utils

_AUDIO_CONNECTION_TIMEOUT = datetime.timedelta(seconds=30)
_VOLUME_SETTLE_TIME = datetime.timedelta(seconds=45)
_RECORDING_STATE_TIMEOUT = datetime.timedelta(seconds=30)


@enum.unique
class AudioDeviceType(enum.IntEnum):
  """Type of audio output/input device.

  https://developer.android.com/reference/android/media/AudioDeviceInfo

  Attributes:
    TYPE_BLUETOOTH_SCO: A device type describing a Bluetooth device typically
      used for telephony.
    TYPE_BLUETOOTH_A2DP: A device type describing a Bluetooth device supporting
      the A2DP profile.
    TYPE_BLE_HEADSET: A device type describing a Bluetooth Low Energy (BLE)
      audio headset or headphones. Headphones are grouped with headsets when the
      device is a sink: the features of headsets and headphones with regard to
      playback are the same.
  """

  TYPE_BLUETOOTH_SCO = 7
  TYPE_BLUETOOTH_A2DP = 8
  TYPE_BLE_HEADSET = 26


def wait_and_assert_audio_device_type(
    ad: android_device.AndroidDevice,
    expect_audio_device_type: AudioDeviceType,
    expect_active: bool,
    timeout: datetime.timedelta = _AUDIO_CONNECTION_TIMEOUT,
) -> None:
  """Waits for and asserts audio device type supported on Android device.

  This method waits until the expected audio device type supported on the
  Android device is either active or inactive, matching the value of
  `expect_active`.

  Args:
    ad: The Android device used to check the audio device type.
    expect_audio_device_type: The expected audio device type.
    expect_active: The expected state of the audio device type.
      * True: Expects the audio device type to be active (connected).
      * False: Expects the audio device type to be inactive (disconnected).
    timeout: The maximum time to wait for the audio device type to reach the
      expected state.

  Raises:
    signals.TestFailure: If the audio device type does not match
      `expect_active` within the specified timeout.
  """
  test_utils.wait_until_or_assert(
      condition=lambda: (
          expect_audio_device_type in ad.bt_snippet.getAudioDeviceTypes()
      )
      == expect_active,
      error_msg=(
          f'{ad} Timed out waiting for {expect_audio_device_type.name} to reach'
          f' the {"active" if expect_active else "inactive"} state'
      ),
      timeout=timeout,
  )
