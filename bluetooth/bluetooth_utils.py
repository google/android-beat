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

"""Utility functions related to Bluetooth operations."""

from collections.abc import Sequence
import datetime
import logging
import time
from typing import Any

from mobly import asserts
from mobly.controllers import android_device
import tenacity

from bluetooth import test_utils
from bluetooth import tws_device

_CSIP_CONNECTED_EVENT = 'Enter Connected\\({address}\\): STACK_EVENT'
_CSIP_COORDINATOR_STATE_MACHINE_TAG = 'CsipSetCoordinatorStateMachine'
_CSIP_CONNECTION_LEVEL = 'I'

# The unpairing process needs to wait more than 3 seconds to ensure completion.
_DELAY_BETWEEN_BLUETOOTH_UNPAIR = datetime.timedelta(seconds=3)

_AUDIO_CONNECTION_TIMEOUT = datetime.timedelta(seconds=10)
_BLUETOOTH_DISCOVERY_TIMEOUT = datetime.timedelta(seconds=120)
_BLUETOOTH_PAIRING_TIMEOUT = datetime.timedelta(seconds=60)
_BLUETOOTH_PROFILE_CONNECTION_TIMEOUT = datetime.timedelta(seconds=30)
_CSIP_GROUP_SET_TIMEOUT = datetime.timedelta(seconds=120)


def clear_saved_devices(
    ad: android_device.AndroidDevice,
    bt_devices_addresses: Sequence[str] = (),
) -> None:
  """Clears the saved Bluetooth devices on the Android device.

  This function unpairs Bluetooth devices from the given Android device.
  If `bt_devices_addresses` is provided and the device is paired, it will unpair
  the devices with the given addresses. Then it will unpair all other paired 
  Bluetooth devices.

  Args:
    ad: The Android device.
    bt_devices_addresses: A sequence of Bluetooth addresses to unpair.
  """
  for device in ad.bt_snippet.btGetPairedDevices():
    if device['Address'] in bt_devices_addresses:
      ad.bt_snippet.btUnpairDevice(device['Address'])
      time.sleep(_DELAY_BETWEEN_BLUETOOTH_UNPAIR.total_seconds())
  while devices := ad.bt_snippet.btGetPairedDevices():
    ad.bt_snippet.btUnpairDevice(devices[0]['Address'])
    time.sleep(_DELAY_BETWEEN_BLUETOOTH_UNPAIR.total_seconds())


def start_pairing_mode(
    bt_device: android_device.AndroidDevice | tws_device.TwsDevice,
    timeout: datetime.timedelta = _BLUETOOTH_DISCOVERY_TIMEOUT,
) -> None:
  """Starts pairing mode on the Bluetooth device."""
  if isinstance(bt_device, android_device.AndroidDevice):
    bt_device.bt_snippet.btBecomeDiscoverable(timeout.total_seconds())
    bt_device.bt_snippet.btStartAutoAcceptIncomingPairRequest()
  else:
    bt_device.start_pairing_mode()


def _is_bluetooth_address_and_name_match(
    bluetooth_device: dict[str, Any],
    expected_address: str,
    expected_name: str | None = None,
) -> bool:
  """Returns True if Bluetooth address and name match, False otherwise."""
  if bluetooth_device['Address'].lower() == expected_address.lower():
    if expected_name is None or bluetooth_device['Name'] == expected_name:
      return True
  return False


def is_bt_device_discovered(
    ad: android_device.AndroidDevice,
    bluetooth_address: str,
    bluetooth_name: str | None = None,
) -> bool:
  """Returns True if Android discovered Bluetooth device, False otherwise."""
  for device in ad.bt_snippet.btDiscoverAndGetResults():
    if _is_bluetooth_address_and_name_match(
        device, bluetooth_address, bluetooth_name
    ):
      return True
  return False


def is_bt_device_in_saved_devices(
    ad: android_device.AndroidDevice,
    bluetooth_address: str,
    bluetooth_name: str | None = None,
) -> bool:
  """Returns True if Android paired with Bluetooth device, False otherwise."""
  for device in ad.bt_snippet.btGetPairedDevices():
    if _is_bluetooth_address_and_name_match(
        device, bluetooth_address, bluetooth_name
    ):
      return True
  return False


def wait_and_assert_a2dp_state(
    ad: android_device.AndroidDevice,
    bluetooth_address: str,
    expect_active: bool,
    timeout: datetime.timedelta = _BLUETOOTH_PROFILE_CONNECTION_TIMEOUT,
) -> None:
  """Waits for and asserts A2DP connection state with a Bluetooth device.

  This method waits until the Advanced Audio Distribution Profile (A2DP)
  connection to the specified Bluetooth device is either active or inactive,
  matching the value of `expect_active`.

  Args:
    ad: The Android device used to check the A2DP connection state.
    bluetooth_address: The MAC address of the target Bluetooth device.
    expect_active: The expected state of the A2DP connection.
      * True: Expects the A2DP connection to be active (connected).
      * False: Expects the A2DP connection to be inactive (disconnected).
    timeout: The maximum time to wait for the A2DP connection to reach the
      expected state.

  Raises:
    signals.TestFailure: If the A2DP connection state does not match
      `expect_active` within the specified timeout.
  """
  test_utils.wait_until_or_assert(
      condition=lambda: ad.bt_snippet.btIsA2dpConnected(bluetooth_address)
      == expect_active,
      error_msg=(
          f'{ad} Timed out waiting for A2DP connection to reach the'
          f' {"active" if expect_active else "inactive"} state'
      ),
      timeout=timeout,
  )


def wait_and_assert_a2dp_playback_state(
    ad: android_device.AndroidDevice,
    bluetooth_address: str,
    expect_active: bool,
    timeout: datetime.timedelta = _AUDIO_CONNECTION_TIMEOUT,
) -> None:
  """Waits for and asserts A2DP playback state with a Bluetooth device."""
  test_utils.wait_until_or_assert(
      condition=lambda: ad.bt_snippet.btIsA2dpPlaying(bluetooth_address)
      == expect_active,
      error_msg=(
          f'{ad} Timed out waiting for A2DP playback to reach the'
          f' {"active" if expect_active else "inactive"} state'
      ),
      timeout=timeout,
  )


def wait_and_assert_hfp_state(
    ad: android_device.AndroidDevice,
    bluetooth_address: str,
    expect_active: bool,
    timeout: datetime.timedelta = _BLUETOOTH_PROFILE_CONNECTION_TIMEOUT,
) -> None:
  """Waits for and asserts HFP connection state with a Bluetooth device.

  This method waits until the Hands Free Profile (HFP) connection to the
  specified Bluetooth device is either active or inactive, matching the value of
  `expect_active`.

  Args:
    ad: The Android device used to check the HFP connection state.
    bluetooth_address: The MAC address of the target Bluetooth device.
    expect_active: The expected state of the HFP connection.
      * True: Expects the HFP connection to be active (connected).
      * False: Expects the HFP connection to be inactive (disconnected).
    timeout: The maximum time to wait for the HFP connection to reach the
      expected state.

  Raises:
    signals.TestFailure: If the HFP connection state does not match
      `expect_active` within the specified timeout.
  """
  test_utils.wait_until_or_assert(
      condition=lambda: ad.bt_snippet.btIsHfpConnected(bluetooth_address)
      == expect_active,
      error_msg=(
          f'{ad} Timed out waiting for HFP connection to reach the'
          f' {"active" if expect_active else "inactive"} state'
      ),
      timeout=timeout,
  )


def wait_and_assert_lea_state(
    ad: android_device.AndroidDevice,
    bluetooth_address: str,
    expect_active: bool,
    timeout: datetime.timedelta = _BLUETOOTH_PROFILE_CONNECTION_TIMEOUT,
) -> None:
  """Waits for and asserts LEA connection state with a Bluetooth device.

  This method waits until the Low Energy Audio (LEA) connection to the specified
  Bluetooth device is either active or inactive, matching the value of
  `expect_active`.

  Args:
    ad: The Android device used to check the LEA connection state.
    bluetooth_address: The MAC address of the target Bluetooth device.
    expect_active: The expected state of the LEA connection.
      * True: Expects the LEA connection to be active (connected).
      * False: Expects the LEA connection to be inactive (disconnected).
    timeout: The maximum time to wait for the LEA connection to reach the
      expected state.

  Raises:
    signals.TestFailure: If the LEA connection state does not match
      `expect_active` within the specified timeout.
  """
  test_utils.wait_until_or_assert(
      condition=lambda: ad.bt_snippet.btIsLeAudioConnected(bluetooth_address)
      == expect_active,
      error_msg=(
          f'{ad} Timed out waiting for LEA connection to reach the'
          f' {"active" if expect_active else "inactive"} state'
      ),
      timeout=timeout,
  )


def is_le_audio_streaming_active(
    ad: android_device.AndroidDevice, bluetooth_address: str
) -> bool:
  """Returns True if active audio stream is playing via LEA, False otherwise."""
  return (
      ad.bt_snippet.media3IsLeaStreamActive()
      and ad.bt_snippet.btIsLeAudioConnected(bluetooth_address)
  )


def _convert_to_anonymous_address(bluetooth_address: str) -> str:
  """Converts the Bluetooth address to anonymous address in Android logcat."""
  return f'XX:XX:XX:XX:{bluetooth_address[-5:]}'


@tenacity.retry(
    stop=tenacity.stop_after_attempt(4),
    wait=tenacity.wait_exponential(multiplier=1, max=10),
    before_sleep=tenacity.before_sleep_log(
        logging.getLogger(__name__), logging.INFO
    ),
)
def start_pairing_with_retry(
    ad: android_device.AndroidDevice,
    primary_bluetooth_address: str,
    secondary_bluetooth_address: str | None = None,
)-> None:
  """Initiates pairing with a Bluetooth device and retries on failure.

  Args:
    ad: The Android device.
    primary_bluetooth_address: The MAC address of the target Bluetooth device.
    secondary_bluetooth_address: The MAC address of the secondary Bluetooth
      device. This argument is used internally to ensure the CSIP group is
      correctly set for both the primary and secondary devices; however, the
      actual Bluetooth pairing connection is only established with the primary
      address.

  Raises:
    signals.TestFailure: If the CSIP group is not set for primary or secondary
      ear within timeout.
  """
  if (
      not hasattr(ad.services, 'logcat_pubsub')
      or secondary_bluetooth_address is None
  ):
    ad.bt_snippet.btPairDevice(primary_bluetooth_address)
    return

  anonymous_address = _convert_to_anonymous_address(primary_bluetooth_address)
  anonymous_address_secondary = _convert_to_anonymous_address(
      secondary_bluetooth_address
  )
  with ad.services.logcat_pubsub.event(
      pattern=_CSIP_CONNECTED_EVENT.format(address=anonymous_address),
      tag=_CSIP_COORDINATOR_STATE_MACHINE_TAG,
      level=_CSIP_CONNECTION_LEVEL,
  ) as primary_ear_paired_event:
    with ad.services.logcat_pubsub.event(
        pattern=_CSIP_CONNECTED_EVENT.format(
            address=anonymous_address_secondary
        ),
        tag=_CSIP_COORDINATOR_STATE_MACHINE_TAG,
        level=_CSIP_CONNECTION_LEVEL,
    ) as secondary_ear_paired_event:
      start_time = time.monotonic()
      ad.bt_snippet.btPairDevice(primary_bluetooth_address)
      asserts.assert_true(
          primary_ear_paired_event.wait(_CSIP_GROUP_SET_TIMEOUT),
          'Failed to set CSIP group for primary ear within'
          f' {_CSIP_GROUP_SET_TIMEOUT.total_seconds()} seconds',
      )
      remaining_time = _CSIP_GROUP_SET_TIMEOUT.total_seconds() - (
          time.monotonic() - start_time
      )
      asserts.assert_true(
          secondary_ear_paired_event.wait(remaining_time),
          'Failed to set CSIP group for secondary ear within'
          f' {remaining_time} seconds',
      )


def pair_bluetooth_device(
    ad: android_device.AndroidDevice,
    bt_device: tws_device.TwsDevice,
) -> None:
  """Initiates and completes the Bluetooth pairing process.

  This method handles enabling pairing mode on the Bluetooth device and waiting
  for the successful pairing confirmation on the Android device.

  Args:
    ad: The Android device that will perform the pairing
    bt_device: The Bluetooth device to put into pairing mode.
  """
  bluetooth_address = bt_device.bluetooth_address_primary
  start_pairing_mode(bt_device, timeout=_BLUETOOTH_DISCOVERY_TIMEOUT)
  test_utils.wait_until_or_assert(
      condition=lambda: is_bt_device_discovered(ad, bluetooth_address),
      error_msg=f'{ad} Timed out waiting for Bluetooth device to be discovered',
      timeout=_BLUETOOTH_DISCOVERY_TIMEOUT,
  )
  start_pairing_with_retry(ad, bluetooth_address)
  test_utils.wait_until_or_assert(
      condition=lambda: is_bt_device_in_saved_devices(ad, bluetooth_address),
      error_msg=f'{ad} Timed out waiting for Bluetooth device to be paired',
      timeout=_BLUETOOTH_PAIRING_TIMEOUT,
  )
