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

import datetime
import enum
import time

from mobly import asserts
from mobly.controllers import android_device

from android_beat.utils import test_utils


_CALL_STATE_TIMEOUT = datetime.timedelta(seconds=10)

# Delay to ensure the call state is updated when call is answered or ended.
# A short waiting period allows Android devices and Bluetooth devices to
# properly release resources.
BEFORE_ANSWER_CALL_DELAY = datetime.timedelta(seconds=4)
AFTER_ANSWER_CALL_DELAY = datetime.timedelta(seconds=8)
IN_CALL_PROCESS_DELAY = datetime.timedelta(seconds=3)
END_CALL_DELAY = datetime.timedelta(seconds=3)


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


def get_phone_number_if_need_call(
    ad: android_device.AndroidDevice,
    has_call: bool,
) -> None:
  """Gets the phone number of ad."""
  if not has_call:
    return
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
  ad.phone_number = phone_number


def end_call_and_check_idle(
    ad: android_device.AndroidDevice | None,
    has_call: bool,
    timeout: datetime.timedelta = _CALL_STATE_TIMEOUT,
) -> None:
  """Ends a call on ad and checks if the call state is idle."""
  if ad is None or not has_call:
    return
  end_call(ad)
  test_utils.wait_until_or_assert(
      condition=lambda: get_call_state(ad) == CallState.CALL_STATE_IDLE,
      error_msg='Failed to end the voice call',
      timeout=timeout,
  )
  time.sleep(END_CALL_DELAY.total_seconds())

