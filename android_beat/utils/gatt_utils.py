"""Utility functions related to Gatt operations."""

import datetime
import enum
from typing import Any
import uuid

from mobly import asserts
from mobly import utils
from mobly.controllers.android_device_lib import callback_handler_v2

_GATT_CONNECTION_TIMEOUT = datetime.timedelta(seconds=60)
_WAIT_EVENT_TIMEOUT = datetime.timedelta(seconds=30)

_SERVICE_TYPE_PRIMARY = 'SERVICE_TYPE_PRIMARY'
CUSTOM_BLE_SERVICE_UUID = '0000fe23-0000-1000-8000-00805f9b34fb'
CUSTOM_BLE_SERVICE_READ_CHARACTERISTIC_UUID = (
    '0000e634-0000-1000-8000-00805f9b34fb'
)
CUSTOM_BLE_DATA = 'testdata'
CUSTOM_BLE_SERVICE_WRITE_CHARACTERISTIC_UUID = (
    '0000e632-0000-1000-8000-00805f9b34fb'
)
CUSTOM_BLE_SERVICE_NOTIFY_CHARACTERISTIC_UUID = (
    '0000e636-0000-1000-8000-00805f9b34fb'
)


@enum.unique
class BluetoothGattCallback(enum.StrEnum):
  """Enum class for GATT callback public methods.

  https://developer.android.com/reference/android/bluetooth/BluetoothGattCallback
  """

  ON_CHARACTERISTIC_READ = 'onCharacteristicRead'
  ON_CHARACTERISTIC_WRITE = 'onCharacteristicWrite'
  ON_CONNECTION_STATE_CHANGE = 'onConnectionStateChange'
  ON_SERVICE_DISCOVERED = 'onServiceDiscovered'


@enum.unique
class BluetoothGattServerCallback(enum.StrEnum):
  """Enum class for GATT server callback public methods.

  https://developer.android.com/reference/android/bluetooth/BluetoothGattServerCallback
  """

  ON_CONNECTION_STATE_CHANGE = 'onConnectionStateChange'
  ON_CHARACTERISTIC_WRITE_REQUEST = 'onCharacteristicWriteRequest'
  ON_SERVICE_ADDED = 'onServiceAdded'


@enum.unique
class BluetoothProfileState(enum.StrEnum):
  """Enum class for BluetoothProfile profile State.

  https://developer.android.com/reference/android/bluetooth/BluetoothProfile
  """

  STATE_CONNECTED = 'STATE_CONNECTED'
  STATE_CONNECTING = 'STATE_CONNECTING'
  STATE_DISCONNECTED = 'STATE_DISCONNECTED'
  STATE_DISCONNECTING = 'STATE_DISCONNECTING'


@enum.unique
class GattProfileStatus(enum.StrEnum):
  """Enum class for GATT profile status.

  https://developer.android.com/reference/android/bluetooth/BluetoothGatt
  """

  GATT_SUCCESS = 'GATT_SUCCESS'
  GATT_CONNECTION_CONGESTED = 'GATT_CONNECTION_CONGESTED'
  GATT_CONNECTION_TIMEOUT = 'GATT_CONNECTION_TIMEOUT'
  GATT_INSUFFICIENT_AUTHENTICATION = 'GATT_INSUFFICIENT_AUTHENTICATION'
  GATT_FAILURE = 'GATT_FAILURE'


@enum.unique
class GattServicePropertyType(enum.StrEnum):
  """Enum class for GATT service property type.

  https://developer.android.com/reference/android/bluetooth/BluetoothGattCharacteristic
  """

  BROADCAST = 'PROPERTY_BROADCAST'
  READ = 'PROPERTY_READ'
  WRITE_NO_RESPONSE = 'PROPERTY_WRITE_NO_RESPONSE'
  WRITE = 'PROPERTY_WRITE'
  NOTIFY = 'PROPERTY_NOTIFY'
  INDICATE = 'PROPERTY_INDICATE'
  SIGNED_WRITE = 'PROPERTY_SIGNED_WRITE'
  EXTENDED_PROPS = 'PROPERTY_EXTENDED_PROPS'


def get_custom_service_and_characteristics() -> list[dict[str, Any]]:
  return [{
      'UUID': CUSTOM_BLE_SERVICE_UUID,
      'Type': _SERVICE_TYPE_PRIMARY,
      'Characteristics': [
          {
              'UUID': CUSTOM_BLE_SERVICE_WRITE_CHARACTERISTIC_UUID,
              'Properties': 'PROPERTY_WRITE',
              'Permissions': 'PERMISSION_WRITE',
          },
          {
              'UUID': '0000e633-0000-1000-8000-00805f9b34fb',
              'Properties': 'PROPERTY_WRITE',
              'Permissions': 'PERMISSION_WRITE',
          },
          {
              'UUID': CUSTOM_BLE_SERVICE_READ_CHARACTERISTIC_UUID,
              'Properties': 'PROPERTY_READ',
              'Permissions': 'PERMISSION_READ',
              'Data': CUSTOM_BLE_DATA,
          },
          {
              'UUID': '0000e635-0000-1000-8000-00805f9b34fb',
              'Properties': 'PROPERTY_READ',
              'Permissions': 'PERMISSION_READ',
              'Data': utils.rand_ascii_str(8),
          },
          {
              'UUID': '0000e636-0000-1000-8000-00805f9b34fb',
              'Properties': 'PROPERTY_READ',
              'Permissions': 'PERMISSION_READ',
              'Data': utils.rand_ascii_str(8),
          },
          {
              'UUID': CUSTOM_BLE_SERVICE_NOTIFY_CHARACTERISTIC_UUID,
              'Properties': 'PROPERTY_NOTIFY',
              'Permissions': 'PERMISSION_READ',
          },
      ],
  }]


def generate_callback_id(request_type: str) -> str:
  """Generates a callback id for the given request type."""
  return f'{request_type}_{uuid.uuid4()}'


def assert_event_success(
    callback_handler: callback_handler_v2.CallbackHandlerV2,
    event_name: BluetoothGattCallback | BluetoothGattServerCallback,
    expected_data: str | None = None,
) -> None:
  """Asserts the event is successful."""
  event = callback_handler.waitAndGet(
      event_name=event_name,
      timeout=_WAIT_EVENT_TIMEOUT.total_seconds(),
  )
  if 'status' in event.data:
    asserts.assert_equal(
        event.data['status'],
        GattProfileStatus.GATT_SUCCESS,
        msg=f'Failed to complete GATT operation "{event_name}".',
    )
  if expected_data is not None:
    asserts.assert_in(
        'Data',
        event.data,
        msg=f'Failed to get the key "Data" from the {event_name}. callback.',
    )
    asserts.assert_true(
        event.data['Data'],
        expected_data,
        'Failed to verify the data equals to the expected data.',
    )


def assert_gatt_client_connected(
    client_callback_handler: callback_handler_v2.CallbackHandlerV2,
) -> None:
  """Asserts GATT client is connected."""
  connect_event = client_callback_handler.waitAndGet(
      event_name=BluetoothGattCallback.ON_CONNECTION_STATE_CHANGE,
      timeout=_GATT_CONNECTION_TIMEOUT.total_seconds(),
  )
  asserts.assert_equal(
      connect_event.data['status'],
      GattProfileStatus.GATT_SUCCESS,
      msg='Failed to execute GATT operation "Client Connect".',
  )
  asserts.assert_equal(
      connect_event.data['newState'],
      BluetoothProfileState.STATE_CONNECTED,
      msg='Failed to connect to the reference device.',
  )


def assert_gatt_client_disconnected(
    client_callback_handler: callback_handler_v2.CallbackHandlerV2,
) -> None:
  """Asserts GATT client is disconnected."""
  disconnect_event = client_callback_handler.waitAndGet(
      event_name=BluetoothGattCallback.ON_CONNECTION_STATE_CHANGE,
      timeout=_GATT_CONNECTION_TIMEOUT.total_seconds(),
  )
  asserts.assert_equal(
      disconnect_event.data['status'],
      GattProfileStatus.GATT_SUCCESS,
      msg='Failed to execute GATT operation. "Client Disconnect"',
  )
  asserts.assert_equal(
      disconnect_event.data['newState'],
      BluetoothProfileState.STATE_DISCONNECTED,
      msg='Failed to disconnect from the reference device.',
  )


def discovered_gatt_services(
    client_callback_handler: callback_handler_v2.CallbackHandlerV2,
) -> list[dict[str, Any]]:
  """Discovers services from the BLE device."""
  discovery_event = client_callback_handler.waitAndGet(
      event_name=BluetoothGattCallback.ON_SERVICE_DISCOVERED,
      timeout=_WAIT_EVENT_TIMEOUT.total_seconds(),
  )
  if (
      discovery_event.data['status'] == GattProfileStatus.GATT_SUCCESS
      and discovery_event.data['gatt']['Services'] is not None
  ):
    return discovery_event.data['gatt']['Services']
  asserts.fail('Failed to discover services from the BLE device.')


def assert_specific_service_supported(
    services: list[dict[str, Any]],
    service_uuid: str,
    characteristics_uuid: str,
) -> None:
  """Asserts the service property is expected."""
  for service in services:
    if service['UUID'] == service_uuid:
      for characteristic in service['Characteristics']:
        if characteristic['UUID'] == characteristics_uuid:
          return
  asserts.fail(
      'Failed to find the specific service or characteristic with GATT.'
  )


def get_first_readable_service_and_characteristic_uuid(
    services: list[dict[str, Any]],
) -> tuple[str, str]:
  """Gets the first characteristic and service UUID with discovered services."""
  if services is None:
    asserts.fail('Failed to get the discovered services. It is None.')
  for service in services:
    characteristics = service.get('Characteristics')
    for characteristic in characteristics:
      if characteristic.get('Property') == GattServicePropertyType.READ:
        first_readable_service_uuid = service['UUID']
        first_readable_characteristic_uuid = characteristic['UUID']
        return first_readable_service_uuid, first_readable_characteristic_uuid
  asserts.fail('Failed to get a not None readable service and characteristic.')


def assert_gatt_server_services_added(
    server_callback_handler: callback_handler_v2.CallbackHandlerV2,
) -> None:
  """Asserts GATT server services are added."""
  connect_event = server_callback_handler.waitAndGet(
      event_name=BluetoothGattServerCallback.ON_SERVICE_ADDED,
      timeout=_GATT_CONNECTION_TIMEOUT.total_seconds(),
  )
  asserts.assert_equal(
      connect_event.data['status'],
      GattProfileStatus.GATT_SUCCESS,
      msg='Failed to execute GATT operation "services added".',
  )


def assert_gatt_server_disconnected(
    server_callback_handler: callback_handler_v2.CallbackHandlerV2,
) -> None:
  """Asserts if GATT server is disconnected."""
  disconnect_event = server_callback_handler.waitAndGet(
      event_name=BluetoothGattServerCallback.ON_CONNECTION_STATE_CHANGE,
      timeout=_GATT_CONNECTION_TIMEOUT.total_seconds(),
  )
  asserts.assert_equal(
      disconnect_event.data['status'],
      GattProfileStatus.GATT_SUCCESS,
      msg='Failed to execute GATT operation "Server Disconnect".',
  )
  # When server starts, the callbackhandler gets newState 'connected'. But there
  # is no callback with startGattServer to check event 'onConnectionStateChange'
  # . So the newState will be keeped for next call. if we check newState here.
  # It will be connected, which keeps the change last time.
