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

"""Bluetooth call utils."""

import enum
import time

from mobly import asserts
from mobly.controllers import android_device


@enum.unique
class CallState(enum.IntEnum):
  """Enum class for call state.

  https://developer.android.com/reference/android/telephony/TelephonyManager
  """

  CALL_STATE_IDLE = 0
  CALL_STATE_RINGING = 1
  CALL_STATE_OFFHOOK = 2


def place_call(ad: android_device.AndroidDevice, call_number: str) -> None:
  """Places a call from ad to specific number."""
  ad.adb.shell(f'am start -a android.intent.action.CALL -d tel:{call_number}')


def answer_call(ad: android_device.AndroidDevice) -> None:
  """Answers a call on ad."""
  # A short delay to ensure that the CALL_STATE_RINGING event is received and
  # phone is ready to answer the incoming call.
  time.sleep(3)
  ad.adb.shell('input keyevent KEYCODE_CALL')


def get_call_state(ad: android_device.AndroidDevice) -> int:
  """Gets the telephony call state of ad."""
  return ad.bt_snippet.getTelephonyCallState()


def end_call(ad: android_device.AndroidDevice) -> None:
  """Ends a call on ad."""
  ad.adb.shell('input keyevent KEYCODE_ENDCALL')


def get_phone_number(ad: android_device.AndroidDevice) -> str:
  """Gets the phone number of ad."""
  phone_number = ad.bt_snippet.getLine1Number()
  if not phone_number:
    ad.log.info(
        'Phone number is not written to the SIM card, trying to get from'
        ' dimensions'
    )
    asserts.assert_in(
        'phone_number', ad.dimensions, 'Phone number is not set in dimensions'
    )
    phone_number = ad.dimensions['phone_number']
  return phone_number
