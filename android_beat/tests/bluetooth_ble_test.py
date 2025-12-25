"""Bluetooth ble test."""

import datetime
import time

from mobly import asserts
from mobly import test_runner
from mobly import records
from mobly import utils

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import gatt_utils
from android_beat.utils import test_utils

_AUDIO_CONNECTION_TIMEOUT = datetime.timedelta(seconds=10)
_BLUETOOTH_DISCOVERY_TIMEOUT = datetime.timedelta(seconds=120)
_BLUETOOTH_PAIRING_TIMEOUT = datetime.timedelta(seconds=60)
_BLUETOOTH_PROFILE_CONNECTION_TIMEOUT = datetime.timedelta(seconds=60)

_MEDIA_MUSIC_LENGTH = datetime.timedelta(minutes=5)


class BluetoothBleTest(base_test.BaseTestClass):
  """Test class for Bluetooth BLE test."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.CLASSIC
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.TWO_DEVICES
  _MEDIA_FILES_BASENAMES = ('sine_tone_0.wav',)
  _MEDIA_FILES_PATHS = ('/sdcard/Download/sine_tone_0.wav',)

  def setup_class(self) -> None:
    super().setup_class()
    self.ad_ref = self.ads[1]
    self.ad_ref_address = self.ad_ref.bt_snippet.btGetAddress()
    audio_utils.generate_and_push_audio_files(
        self.ad,
        self._MEDIA_FILES_BASENAMES,
        self.current_test_info.output_path,
    )

  def setup_test(self) -> None:
    self.bt_device.factory_reset()
    utils.concurrent_exec(
        bluetooth_utils.clear_saved_devices,
        [[self.ad], [self.ad_ref]],
    )

  def teardown_test(self) -> None:
    utils.concurrent_exec(
        bluetooth_utils.clear_saved_devices,
        [[self.ad], [self.ad_ref]],
    )
    super().teardown_test()

  @records.uid('cfc57da9-6385-4860-9c49-fa4c3709d7f6')
  def test_ble_pair_and_connect(self):
    """Test for connecting to BLE accessories and syncing data.

    Objective:
      To Validate the Device Under Test (DUT) can successfully pair and connect
      to two remote Peripheral devices (BLE device and Android reference
      device). And the DUT can sync data from the connected device.

    Test Preconditions:
      1. Device: 2 Android device and 1 BLE device.
      2. Settings: Bluetooth LE Audio is enabled.

    Steps:
      1. BLE device starts pairing mode.
      2. DUT initiates Bluetooth discovery and discover the BLE device
      3. DUT pairs with the BLE device and verify the pairing is successful.
      4. BLE device broadcast GATT Server automatically.
      5. DUT starts GATT Client.
      6. DUT discovers BLE services and get the first service and characteristic
      UUID to ensure the service and characteristic are supported.
      7. Sync data from BLE device to DUT.
      8. DUT stops GATT Client.
      9. Verify the GATT connection closed in Client.
      10. Android reference device start pairing mode.
      11. DUT discovers the Android reference device.
      12. Android reference device starts GATT Server.
      13. DUT starts GATT Client.
      14. DUT discovers GATT services.
      15. Sync data from Android reference device to DUT.
      16. DUT stops GATT Client.
      17. Veryfy the GATT connection closed in Client.
      18. Android reference device stops GATT Server.
      19. Veryfy the GATT connection closed in Server.


    Pass Criteria:
      1. DUT can connect with the BLE device and Android reference device.
      2. DUT can sync data from the connected devices.
    """
    # BLE device starts pairing mode.
    bluetooth_utils.start_pairing_mode(
        self.bt_device, timeout=_BLUETOOTH_DISCOVERY_TIMEOUT
    )

    # DUT initiates Bluetooth discovery and verify the BLE device is discovered.
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_discovered(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to discover BLE device',
        timeout=_BLUETOOTH_DISCOVERY_TIMEOUT,
    )

    # DUT pairs with the BLE device and verify the pairing is successful.
    bluetooth_utils.start_pairing_with_retry(
        self.ad, self.bt_device.bluetooth_address_primary
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_in_saved_devices(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to pair with BLE device',
        timeout=_BLUETOOTH_PAIRING_TIMEOUT,
    )

    client_callback_ble_device = None
    try:
      # DUT connects to BLE device with GATT.
      self.ad.log.info('Waiting 5s for bluetooth to stabilize...')
      time.sleep(5)
      client_callback_ble_device = self.ad.bt_snippet.bleConnectGatt(
          self.bt_device.bluetooth_address_primary
      )
      gatt_utils.assert_gatt_client_connected(client_callback_ble_device)
      # DUT check what GATT services the BLE device provides.
      self.ad.bt_snippet.bleDiscoverServices()
      services_data_bt_device = gatt_utils.discovered_gatt_services(
          client_callback_ble_device
      )
      # Get the first readable service and characteristic UUID from BLE device.
      first_readable_service_uuid, first_readable_characteristic_uuid = (
          gatt_utils.get_first_readable_service_and_characteristic_uuid(
              services_data_bt_device
          )
      )

      # READ / WRITE sync data.
      asserts.assert_true(
          self.ad.bt_snippet.bleReadOperation(
              first_readable_service_uuid,
              first_readable_characteristic_uuid,
          ),
          msg=(
              'Failed to initiate BLE read for characteristic'
              f' {first_readable_characteristic_uuid} in'
              f' {first_readable_service_uuid}'
          ),
      )

    finally:
      if client_callback_ble_device is not None:
        self.ad.bt_snippet.bleDisconnect()
        gatt_utils.assert_gatt_client_disconnected(client_callback_ble_device)

    # Android reference device starts pairing mode.
    bluetooth_utils.start_pairing_mode(
        self.ad_ref, timeout=_BLUETOOTH_DISCOVERY_TIMEOUT
    )

    # DUT initiates Bluetooth discovery and verify the Android reference device
    # is discovered.
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_discovered(
            self.ad, self.ad_ref_address
        ),
        error_msg='Failed to discover Android reference device',
        timeout=_BLUETOOTH_DISCOVERY_TIMEOUT,
    )
    # When Android device acts as a GATT server, Bluetooth pairing will conflict
    # with BLE Gatt. So here ad_ref just advertising but not pair.

    server_callback_ad_ref = None
    client_callback_ad_ref = None
    try:
      # ad_ref adds services and starts GATT server.
      server_callback_ad_ref = self.ad_ref.bt_snippet.bleStartServer(
          gatt_utils.get_custom_service_and_characteristics(),
      )
      gatt_utils.assert_gatt_server_services_added(server_callback_ad_ref)
      # DUT connects to Android reference device GATT.
      client_callback_ad_ref = self.ad.bt_snippet.bleConnectGatt(
          self.ad_ref_address
      )
      gatt_utils.assert_gatt_client_connected(client_callback_ad_ref)
      # DUT check what GATT services the Android reference device provides.
      self.ad.bt_snippet.bleDiscoverServices()
      services_data_ad_ref = gatt_utils.discovered_gatt_services(
          client_callback_ad_ref
      )
      # Assert the specific service and characteristic are supported.
      gatt_utils.assert_specific_service_supported(
          services_data_ad_ref,
          gatt_utils.CUSTOM_BLE_SERVICE_UUID,
          gatt_utils.CUSTOM_BLE_SERVICE_READ_CHARACTERISTIC_UUID,
      )
      # READ / WRITE sync data.
      asserts.assert_true(
          self.ad.bt_snippet.bleReadOperation(
              gatt_utils.CUSTOM_BLE_SERVICE_UUID,
              gatt_utils.CUSTOM_BLE_SERVICE_READ_CHARACTERISTIC_UUID,
          ),
          msg=(
              'Failed to initiate BLE read for characteristic'
              f' {gatt_utils.CUSTOM_BLE_SERVICE_READ_CHARACTERISTIC_UUID} in'
              f' service {gatt_utils.CUSTOM_BLE_SERVICE_UUID}'
          ),
      )
    finally:
      self.ad_ref.bt_snippet.bleCancelConnectionByAddress(self.ad_address)
      if client_callback_ad_ref is not None:
        self.ad.bt_snippet.bleDisconnect()
        gatt_utils.assert_gatt_client_disconnected(client_callback_ad_ref)
      if server_callback_ad_ref is not None:
        self.ad_ref.bt_snippet.bleStopServer()
        gatt_utils.assert_gatt_server_disconnected(server_callback_ad_ref)

  def test_ble_a2dp_playing(self):
    """Test for BLE accessory connect - A2DP playing.

    Objective:
      To Validate the Device Under Test (DUT) can successfully pair and connect
      to a Peripheral device (BLE device). DUT can play media and routes to the
      connected device. And DUT can sync data from the connected device during
      playing.

    Test Preconditions:
      1. Device: 1 Android device and 1 BLE device.
      2. Resource: a audio/media file transferred to the DUT.

    Test Steps:
      1. BLE device starts pairing mode.
      2. DUT initiates Bluetooth discovery and discover the BLE device.
      3. DUT pairs with the BLE device and verify the pairing is successful.
      4. Verify the A2DP profiles and A2DP headset are successfully linked.
      5. Play local media on DUT and routes to the connected device.
      6. Start GATT connection from DUT to BLE device.
      7. DUT check what GATT services the BLE device provides.
      8. DUT discovers BLE services and get the first service and characteristic
      UUID to ensure the service and characteristic are supported.
      9. Sync data from BLE device to DUT.
      10. DUT stops GATT Client.
      11. Verify the GATT connection closed in Client.

    Pass criteria:
      1. Meida routes to BLE devices corretly with smooth and good quality.
      2. DUT can sync data from BLE devices when media is playing.
      3. GATT Connection is stable
    """
    # BLE device starts pairing mode.
    bluetooth_utils.start_pairing_mode(
        self.bt_device, timeout=_BLUETOOTH_DISCOVERY_TIMEOUT
    )

    # DUT initiates Bluetooth discovery and verify the BLE device is discovered.
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_discovered(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to discover BLE device',
        timeout=_BLUETOOTH_DISCOVERY_TIMEOUT,
    )

    # DUT pairs with the BLE device and verify the pairing is successful.
    bluetooth_utils.start_pairing_with_retry(
        self.ad, self.bt_device.bluetooth_address_primary
    )
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_in_saved_devices(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        error_msg='Failed to pair with BLE device',
        timeout=_BLUETOOTH_PAIRING_TIMEOUT,
    )

    # Verify the A2dp profile is successfully linked and Android system
    # recognizes the correct audio device type.
    bluetooth_utils.wait_and_assert_a2dp_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
    )
    audio_utils.wait_and_assert_audio_device_type(
        self.ad,
        audio_utils.AudioDeviceType.TYPE_BLUETOOTH_A2DP,
        expect_active=True,
    )

    # Play local media on DUT.
    self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_FILES_PATHS[0])

    # Verify the media is playing and routed to the connected device.
    bluetooth_utils.wait_and_assert_a2dp_playback_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
    )
    client_callback_ble_device = None
    try:
      # DUT connects to BLE device with GATT.
      self.ad.log.info('Waiting 5s for bluetooth to stabilize...')
      time.sleep(5)
      client_callback_ble_device = self.ad.bt_snippet.bleConnectGatt(
          self.bt_device.bluetooth_address_primary
      )
      gatt_utils.assert_gatt_client_connected(client_callback_ble_device)

      # DUT check what GATT services the BLE device provides.
      self.ad.bt_snippet.bleDiscoverServices()
      services_data_bt_device = gatt_utils.discovered_gatt_services(
          client_callback_ble_device
      )

      # Get the first readable service and characteristic UUID from BLE device.
      first_readable_service_uuid, first_readable_characteristic_uuid = (
          gatt_utils.get_first_readable_service_and_characteristic_uuid(
              services_data_bt_device
          )
      )

      # READ / WRITE sync data.
      asserts.assert_true(
          self.ad.bt_snippet.bleReadOperation(
              first_readable_service_uuid,
              first_readable_characteristic_uuid,
          ),
          msg=(
              'Failed to initiate BLE read for characteristic'
              f' {first_readable_characteristic_uuid} in'
              f' {first_readable_service_uuid}'
          ),
      )

    finally:
      self.ad.bt_snippet.media3Stop()
      if client_callback_ble_device is not None:
        self.ad.bt_snippet.bleDisconnect()
        gatt_utils.assert_gatt_client_disconnected(client_callback_ble_device)

  def test_gatt_server_read_characteristic_request(self):
    """Test for GATT server handle service read characteristic request.

    Objective:
      To validate the Android reference device can successfully pair and connect
      to a Peripheral device (DUT: Device Under Test). DUT supports to read
      services data from Client and sync data to Server.

    Test Preconditions:
      1. Device: 2 Android devices.

    Test Steps:
      1. DUT start advertising.
      2. Android reference device initiates Bluetooth discovery and discover the
      DUT.
      4. DUT add services and starts GATT server.
      5. Android reference device connects to DUT with GATT Client.
      6. Android reference device discovers GATT services.
      7. Android reference device checks the added services is supported to
      read.
      8. Android reference device reads data from DUT.
      9. DUT stops GATT server.
      10. Android reference device stops GATT client.
      11. Verify the GATT connection closed both in Client and Server.

    Pass criteria:
      1. Android reference device can connect with DUT
      2. Android reference device can read data from the DUT.
      3. GATT Connection is stable.
    """
    # DUT starts pairing mode.
    bluetooth_utils.start_pairing_mode(
        self.ad, timeout=_BLUETOOTH_DISCOVERY_TIMEOUT
    )

    # Android reference device initiates Bluetooth discovery and verify the DUT
    # is discovered.
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_discovered(
            self.ad_ref, self.ad_address
        ),
        error_msg='Failed to discover Android reference device',
        timeout=_BLUETOOTH_DISCOVERY_TIMEOUT,
    )
    # When Android device acts as a GATT server, Bluetooth pairing will conflict
    # with BLE Gatt. So DUT just advertising and been discovered but not pair.

    server_callback = None
    client_callback = None
    try:
      # ad adds services and starts GATT server.
      server_callback = self.ad.bt_snippet.bleStartServer(
          gatt_utils.get_custom_service_and_characteristics(),
      )
      gatt_utils.assert_gatt_server_services_added(server_callback)

      # Android reference device connects to DUT with GATT client.
      client_callback = self.ad_ref.bt_snippet.bleConnectGatt(self.ad_address)
      gatt_utils.assert_gatt_client_connected(client_callback)

      # Android reference device check what GATT services the DUT provides.
      self.ad_ref.bt_snippet.bleDiscoverServices()
      services_data_ad = gatt_utils.discovered_gatt_services(client_callback)

      # Assert the specific service and characteristic are supported.
      gatt_utils.assert_specific_service_supported(
          services_data_ad,
          gatt_utils.CUSTOM_BLE_SERVICE_UUID,
          gatt_utils.CUSTOM_BLE_SERVICE_READ_CHARACTERISTIC_UUID,
      )

      # READ data from DUT to Android reference device.
      asserts.assert_true(
          self.ad_ref.bt_snippet.bleReadOperation(
              gatt_utils.CUSTOM_BLE_SERVICE_UUID,
              gatt_utils.CUSTOM_BLE_SERVICE_READ_CHARACTERISTIC_UUID,
          ),
          msg=(
              'Failed to initiate BLE read for characteristic'
              f' {gatt_utils.CUSTOM_BLE_SERVICE_READ_CHARACTERISTIC_UUID} in'
              f' service {gatt_utils.CUSTOM_BLE_SERVICE_UUID}'
          ),
      )

      # Asserts the read operation is completed and the read data equals to
      # the expected data.
      gatt_utils.assert_event_success(
          client_callback,
          gatt_utils.BluetoothGattCallback.ON_CHARACTERISTIC_READ,
          gatt_utils.CUSTOM_BLE_DATA,
      )

    finally:
      self.ad.bt_snippet.bleCancelConnectionByAddress(self.ad_ref_address)
      if client_callback is not None:
        self.ad_ref.bt_snippet.bleDisconnect()
        gatt_utils.assert_gatt_client_disconnected(client_callback)
      if server_callback is not None:
        self.ad.bt_snippet.bleStopServer()
        gatt_utils.assert_gatt_server_disconnected(server_callback)

  def test_gatt_server_write_characteristic_request(self):
    """Test for GATT server handle service write characteristic request.

    Objective:
      To validate the Android reference device can successfully pair and connect
      to a Peripheral device (DUT: Device Under Test). DUT supports to write
      services from Client and sync data to Server.

    Test Preconditions:
      1. Device: 2 Android devices.

    Test Steps:
      1. DUT start advertising.
      2. Android reference device initiates Bluetooth discovery and discover the
      DUT.
      4. DUT add services and starts GATT server.
      5. Android reference device connects to DUT with GATT Client.
      6. Android reference device discovers GATT services.
      7. Android reference device checks the added services is supported to
      read.
      8. Android reference device writes data to DUT.
      9. Android reference device stops GATT client.
      10. DUT stops GATT server.
      11. Verify the GATT connection closed both in Client and Server.

    Pass criteria:
      1. Android reference device can connect with DUT.
      2. Android reference device can write data to the DUT.
      3. GATT Connection is stable.
    """
    # DUT starts pairing mode.
    bluetooth_utils.start_pairing_mode(
        self.ad, timeout=_BLUETOOTH_DISCOVERY_TIMEOUT
    )

    # Android reference device initiates Bluetooth discovery and verify the DUT
    # is discovered.
    test_utils.wait_until_or_assert(
        condition=lambda: bluetooth_utils.is_bt_device_discovered(
            self.ad_ref, self.ad_address
        ),
        error_msg='Failed to discover Android reference device',
        timeout=_BLUETOOTH_DISCOVERY_TIMEOUT,
    )
    # When Android device acts as a GATT server, Bluetooth pairing will conflict
    # with BLE Gatt. So here ad just advertising but not pair.

    server_callback = None
    client_callback = None
    try:
      # ad adds services and starts GATT server.
      server_callback = self.ad.bt_snippet.bleStartServer(
          gatt_utils.get_custom_service_and_characteristics(),
      )
      gatt_utils.assert_gatt_server_services_added(server_callback)

      # Android reference device connects to DUT with GATT Client.
      client_callback = self.ad_ref.bt_snippet.bleConnectGatt(self.ad_address)
      gatt_utils.assert_gatt_client_connected(client_callback)

      # DUT check what GATT services the DUT provides.
      self.ad_ref.bt_snippet.bleDiscoverServices()
      services_data_ad = gatt_utils.discovered_gatt_services(client_callback)

      # Assert the specific service and characteristic are supported.
      gatt_utils.assert_specific_service_supported(
          services_data_ad,
          gatt_utils.CUSTOM_BLE_SERVICE_UUID,
          gatt_utils.CUSTOM_BLE_SERVICE_WRITE_CHARACTERISTIC_UUID,
      )

      # Write data from Android reference device to DUT with GATT.
      asserts.assert_true(
          self.ad_ref.bt_snippet.bleWriteOperation(
              gatt_utils.CUSTOM_BLE_SERVICE_UUID,
              gatt_utils.CUSTOM_BLE_SERVICE_WRITE_CHARACTERISTIC_UUID,
              gatt_utils.CUSTOM_BLE_DATA,
          ),
          msg=(
              'Failed to initiate BLE write for characteristic'
              f' {gatt_utils.CUSTOM_BLE_SERVICE_WRITE_CHARACTERISTIC_UUID} in'
              f' service {gatt_utils.CUSTOM_BLE_SERVICE_UUID}'
          ),
      )

      # Verify the Server received the write request and the write data value
      # is correct on the Server.
      gatt_utils.assert_event_success(
          server_callback,
          gatt_utils.BluetoothGattServerCallback.ON_CHARACTERISTIC_WRITE_REQUEST,
          gatt_utils.CUSTOM_BLE_DATA,
      )

      # Verify the write operation is completed.
      gatt_utils.assert_event_success(
          client_callback,
          gatt_utils.BluetoothGattCallback.ON_CHARACTERISTIC_WRITE,
      )

    finally:
      self.ad.bt_snippet.bleCancelConnectionByAddress(self.ad_ref_address)
      if client_callback is not None:
        self.ad_ref.bt_snippet.bleDisconnect()
        gatt_utils.assert_gatt_client_disconnected(client_callback)
      if server_callback is not None:
        self.ad.bt_snippet.bleStopServer()
        gatt_utils.assert_gatt_server_disconnected(server_callback)


if __name__ == '__main__':
  test_runner.main()
