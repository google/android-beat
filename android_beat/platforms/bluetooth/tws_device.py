"""Mobly controller module for a True Wireless Stereo (TWS) device."""

from __future__ import annotations

from collections.abc import Sequence
import dataclasses
import datetime
import logging
import pathlib
from typing import Any

import immutabledict
from mobly import runtime_test_info
from mobly import signals
from mobly import utils

from android_beat.platforms.bluetooth import bes_device
from android_beat.platforms.bluetooth import bluetooth_reference_device_base
from android_beat.platforms.bluetooth import tws_device_config
from android_beat.platforms.bluetooth.lib import bes_constants


# This is used in the config file located in the test lab's home directory.
MOBLY_CONTROLLER_CONFIG_NAME = 'TwsDevice'

# The supported underlying controller class list.
_SUPPORTED_DEVICE_CLASSES = immutabledict.immutabledict({
    bes_device.MOBLY_CONTROLLER_CONFIG_NAME: bes_device,
})

# Error messages used in this module.
_DEVICE_CONFIG_ERROR_MSG = (
    'Failed to parse device configs when creating TWS devices: '
)
_INVALID_BLUETOOTH_ADDRESS_MESSAGE = (
    'Invalid primary Bluetooth address. The Bluetooth address should be one of'
    ' the valid addresses in go/bes-board-bt-address.'
)


class TwsDeviceError(signals.ControllerError):
  """Raised for errors related to the TwsDevice controller module."""


def create(configs: Sequence[dict[str, Any]]) -> list[TwsDevice]:
  """Creates TwsDevice controller objects.

  Mobly uses this to instantiate TwsDevice controller objects from configs.
  The configs come from Mobly configs that look like:

    ```config.yaml
    TestBeds:
    - Name: SampleTestBed
      Controllers:
        TwsDevice:
        - controller_type: 'BesDevice'
          primary_ear: 'RIGHT'
          left_config:
            remote_mode: false
            serial_port: '/dev/ttyUSB1'
            bluetooth_address: '11:22:33:44:55:66'
          right_config:
            remote_mode: false
            serial_port: '/dev/ttyUSB0'
            bluetooth_address: '22:33:44:55:66:77'
    ```

  Each config should have required key-value pair 'controller_type',
  'left_config' and 'right_config'.

  Args:
    configs: a list of dicts, each representing a configuration for a TWS
      device.

  Returns:
    A list of TwsDevice objects.

  Raises:
    errors.BtReferenceError: Invalid controller configs are given.
  """
  try:
    device_configs = tws_device_config.from_dicts(configs)
  except Exception as e:
    raise TwsDeviceError(_DEVICE_CONFIG_ERROR_MSG, e) from e

  devices = []
  for config in device_configs:
    logging.debug(
        'Creating TWS device with base controller type %s',
        config.controller_type,
    )
    try:
      devices.append(TwsDevice(config))
    except Exception:  # pylint: disable=broad-except
      utils.concurrent_exec(
          lambda d: d.destroy(),
          param_list=[[d] for d in devices],
          raise_on_exception=True,
      )
      raise

  return devices


def destroy(devices: Sequence[TwsDevice]) -> None:
  """Destroys TwsDevice objects.

  Mobly uses this to destroy TwsDevice objects created by `create`.

  Args:
    devices: list of TwsDevice.
  """
  for device in devices:
    try:
      device.destroy()
    except Exception:  # pylint: disable=broad-except
      logging.exception('Failed to clean up device properly: %s', repr(device))


class TwsDevice(bluetooth_reference_device_base.BluetoothReferenceDeviceBase):
  """Mobly controller for a TWS device.

  TWS stands for True Wireless Stereo. In this context, it refers to a
  Bluetooth device that consists of: left earbud, right earbud, and (optionally)
  case. The components of the TWS device are paired with each other during
  initialization, communicate with each other over Bluetooth, and work as one
  device in the test.

  Each object of this class represents a set of TWS device (earbuds and case) in
  Mobly.

  This class is a wrapper of the base controller type specified in the config.
  The base controller type should be one of the supported controller types in
  `tws_device_config`.

  Attributes:
    bluetooth_address_primary: The unique BRE/DR address (classic Bluetooth
      address) of the primary board.
    bluetooth_address_secondary: The unique BRE/DR address (classic Bluetooth
      address) of the secondary board.
    version: The version of the firmware on the TWS device.
    config: The configurations for the device.
    log: A logger adapted from root logger with an added prefix
      '[TwsDevice|<bluetooth_address_primary>] 'specific to a test device.
  """

  _primary_device: bluetooth_reference_device_base.BluetoothReferenceDeviceBase
  _secondary_device: (
      bluetooth_reference_device_base.BluetoothReferenceDeviceBase
  )
  _left_device: bluetooth_reference_device_base.BluetoothReferenceDeviceBase
  _right_device: bluetooth_reference_device_base.BluetoothReferenceDeviceBase
  _case_device: (
      bluetooth_reference_device_base.BluetoothReferenceDeviceBase | None
  )
  _is_stereo_recording: bool

  bluetooth_address_primary: str
  bluetooth_address_secondary: str

  def __init__(self, config: tws_device_config.DeviceConfig) -> None:
    self.config = config

    if config.controller_type not in _SUPPORTED_DEVICE_CLASSES:
      raise TwsDeviceError(
          f'Unsupported controller type: {config.controller_type}'
      )

    self._create_device_instance(config)

    if config.primary_ear == tws_device_config.EarType.LEFT:
      self._primary_device = self._left_device
      self._secondary_device = self._right_device
    else:
      self._primary_device = self._right_device
      self._secondary_device = self._left_device

    self.bluetooth_address_primary = self._primary_device.bluetooth_address
    self.bluetooth_address_secondary = self._secondary_device.bluetooth_address
    self._is_stereo_recording = False

  def _create_device_instance(
      self, config: tws_device_config.DeviceConfig
  ) -> None:
    """Creates device instances of the underlying controller type."""
    underlying_device_class = _SUPPORTED_DEVICE_CLASSES[config.controller_type]
    if config.case_config is not None:
      self._left_device, self._right_device, self._case_device, *_ = (
          underlying_device_class.create(
              [config.left_config, config.right_config, config.case_config]
          )
      )
    else:
      self._left_device, self._right_device, *_ = (
          underlying_device_class.create(
              [config.left_config, config.right_config]
          )
      )
      self._case_device = None

  @property
  def is_alive(self) -> bool:
    """True if the underlying devices are alive; False otherwise."""
    return self._primary_device.is_alive or self._secondary_device.is_alive

  @property
  def version(self) -> str:
    """The version of the BES devboards."""
    if self.is_alive:
      return f'L: {self._left_device.version}, R: {self._right_device.version}'
    else:
      return 'unknown'

  @property
  def primary_ear(self) -> str:
    """The primary ear of the TWS device."""
    return str(self.config.primary_ear)

  @property
  def bluetooth_address(self) -> str:
    """The classic Bluetooth address of the TWS device."""
    return self.bluetooth_address_primary

  def __repr__(self) -> str:
    return f'<TwsDevice|{self._primary_device}|{self._secondary_device}>'

  def __del__(self) -> None:
    self.destroy()

  def destroy(self) -> None:
    """Tears TwsDevice object down."""
    self._left_device.destroy()
    self._right_device.destroy()
    if self._case_device is not None:
      self._case_device.destroy()

  def get_info(self) -> dict[str, Any]:
    """Gets the build information of the TWS board."""
    return {
        'primary_ear': self.primary_ear,
        'primary_ear_info': dataclasses.asdict(self.get_device_info('primary')),
        'secondary_ear_info': dataclasses.asdict(
            self.get_device_info('secondary')
        ),
        'case': (
            dataclasses.asdict(self.get_device_info('case'))
            if self._case_device is not None
            else None
        ),
        'version': self.version,
    }

  def create_output_excerpts(
      self, test_info: runtime_test_info.RuntimeTestInfo
  ) -> list[Any]:
    """Creates excerpts for specified logs and returns the excerpt paths.

    Args:
      test_info: `self.current_test_info` in a Mobly test.

    Returns:
      The list of absolute paths to excerpt files.
    """
    if not self.is_alive:
      return []

    return self._primary_device.create_output_excerpts(
        test_info
    ) + self._secondary_device.create_output_excerpts(test_info)

  def _pair_tws_after_reboot(self) -> None:
    """Pairs the two BES devboards as a pair of TWS earbuds after reboot."""
    utils.concurrent_exec(
        lambda d: d.enable_tws(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )
    utils.concurrent_exec(
        lambda d: d.pair_tws(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def reboot(self) -> None:
    """Soft reboots the device."""
    utils.concurrent_exec(
        lambda d: d.reboot(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )
    self._pair_tws_after_reboot()

  def factory_reset(self) -> None:
    """Factory resets the BES devboard."""
    utils.concurrent_exec(
        lambda d, wait_for_access: d.factory_reset(wait_for_access),
        param_list=[
            [self._primary_device, True],
            [self._secondary_device, False],
        ],
        raise_on_exception=True,
    )
    self._pair_tws_after_reboot()

  def power_on(self) -> None:
    """Soft powers on the device."""
    utils.concurrent_exec(
        lambda d: d.power_on(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def power_off(self) -> None:
    """Soft powers off the device."""
    utils.concurrent_exec(
        lambda d: d.power_off(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def get_device_info(
      self, target: str = 'primary'
  ) -> bluetooth_reference_device_base.BluetoothInfo:
    """Gets the general information of the device.

    Args:
      target: The target board to get the device information of, can be
        'primary', 'secondary', 'left', 'right', or 'case'.

    Returns:
      A BluetoothInfo object that contains the Bluetooth address and name
      information of the Bluetooth device.

    Raises:
      ValueError: If the value of `target` is invalid.
    """
    device = getattr(self, f'_{target.lower()}_device', None)
    if device is None:
      raise ValueError(f'Unknown target: {target}')
    return device.get_device_info()

  def set_address(self, address: str) -> None:
    """Sets the Bluetooth address of the device.

    This command will reboot the device for the new address to take effect.

    Args:
      address: The new primary Bluetooth address to be set on the BES board. The
        secondary Bluetooth address will be automatically generated based on the
        primary Bluetooth address.

    Raises:
      NotImplementedError: If the controller type does not support this method.
      ValueError: If the given address is invalid.
    """
    if self.config.controller_type != bes_device.MOBLY_CONTROLLER_CONFIG_NAME:
      raise NotImplementedError(
          'TwsDevice does not support set_address for this controller type.'
          ' Please configure the address in the testbed config.'
      )

    if address not in bes_constants.VALID_BLUETOOTH_ADDRESS_ALL:
      raise ValueError(_INVALID_BLUETOOTH_ADDRESS_MESSAGE)

    self._primary_device.set_address(address)
    self.bluetooth_address_primary = address

    secondary_address = f'{address[:-2]}{(int(address[-2:], 16) - 1):x}'
    self._secondary_device.set_address(secondary_address)
    self.bluetooth_address_secondary = secondary_address

  def set_name(self, bluetooth_name: str, ble_name: str) -> None:
    """Sets the classic Bluetooth name and BLE name of the device.

    This command will reboot the device for the new names to take effect.

    Args:
      bluetooth_name: The new classic Bluetooth name of the device.
      ble_name: The new BLE name of the device.
    """
    self._primary_device.set_name(bluetooth_name, ble_name)

  def get_fast_pair_support(self) -> bool:
    """Checks if the device supports Google Fast Pair."""
    return self._primary_device.get_fast_pair_support()

  def enable_fast_pair(self) -> None:
    """Enables Google Fast Pair on the device."""
    self._primary_device.enable_fast_pair()

  def disable_fast_pair(self) -> None:
    """Disables Google Fast Pair on the device."""
    self._primary_device.disable_fast_pair()

  def get_fp_params(self) -> tuple[str, str]:
    """Gets the Fast Pair parameters of the device."""
    return self._primary_device.get_fp_params()

  def set_fp_params(self, model_id: str, private_key: str) -> None:
    """Sets the Fast Pair parameters of the device.

    This command will reboot the device for the new parameters to take effect.

    Args:
      model_id: Google Fast Pair model ID (format XXXXXX or 0xXXXXXX).
      private_key: Google Fast Pair anti-spoofing key (base64, uncompressed).
    """
    self._primary_device.set_fp_params(model_id, private_key)

  def set_name_and_fp_params(
      self,
      bluetooth_name: str,
      ble_name: str,
      model_id: str,
      private_key: str,
  ) -> None:
    """Sets the Bluetooth name and Fast Pair parameters of the device.

    This command will reboot the device for the settings to take effect.

    Args:
      bluetooth_name: The new classic Bluetooth name of the device.
      ble_name: The new BLE name of the device.
      model_id: Google Fast Pair model ID (format XXXXXX or 0xXXXXXX).
      private_key: Google Fast Pair anti-spoofing key (base64, uncompressed).
    """
    self._primary_device.set_name_and_fp_params(
        bluetooth_name, ble_name, model_id, private_key
    )

  def get_sass_support(self) -> bool:
    """Checks if the device supports Fast Pair Audio Switch (SASS) feature."""
    return self._primary_device.get_sass_support()

  def enable_sass(self) -> None:
    """Enables Fast Pair Audio Switch (SASS) feature on the device."""
    self._primary_device.enable_sass()

  def disable_sass(self) -> None:
    """Disables Fast Pair Audio Switch (SASS) feature on the device."""
    self._primary_device.disable_sass()

  def get_lea_support(self) -> bool:
    """Checks if the device supports LE Audio."""
    return self._primary_device.get_lea_support()

  def enable_lea(self) -> None:
    """Enables LE Audio on the device."""
    self._primary_device.enable_lea()

  def disable_lea(self) -> None:
    """Disables LE Audio on the device."""
    self._primary_device.disable_lea()

  def set_single_point(self) -> None:
    """Sets the device to single point mode."""
    self._primary_device.set_single_point()

  def set_multi_point(self) -> None:
    """Sets the device to multi point mode."""
    self._primary_device.set_multi_point()

  def start_pairing_mode(
      self, timeout: datetime.timedelta | None = None
  ) -> None:
    """Puts the devboard into pairing mode.

    Args:
      timeout: The optional timeout to stop pairing mode. The device will exit
        the pairing mode after this timeout has elapsed. If None, the device
        will keep staying in pairing mode.
    """
    self._primary_device.start_pairing_mode(timeout)

  def stop_pairing_mode(self) -> None:
    """Exits the pairing mode."""
    self._primary_device.stop_pairing_mode()

  def connect(self, address: str) -> None:
    """Connects the BES devboard to the given address.

    Args:
      address: The target classic Bluetooth address to connect to.
    """
    self._primary_device.connect(address)

  def disconnect(self, address: str) -> None:
    """Disconnects from a given address.

    Args:
      address: The target classic Bluetooth address to disconnect from.
    """
    self._primary_device.disconnect(address)

  def clear_paired_devices(self) -> None:
    """Clears all of the paired devices.

    This method disconnects and unpairs all the paired devices.
    """
    self._primary_device.clear_paired_devices()

  def enable_tws(self):
    """Enables the TWS mode."""
    utils.concurrent_exec(
        lambda d: d.enable_tws(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def disable_tws(self) -> None:
    """Disables the TWS mode."""
    raise NotImplementedError('This is a TWS device, can not disable TWS mode.')

  def get_component_number(self) -> int:
    """Gets the number of components of the device."""
    return self._primary_device.get_component_number()

  def set_component_number(self, number: int) -> None:
    """Sets the number of components of the device.

    Component number refers to the device number in the CSIP
    (https://www.bluetooth.com/specifications/specs/csip-1-0-1/) Coordinated
    Set. If 1, the device has a single component. It shows 1 address on Android
    after pairing. If 2, the device has two components, one CSIP Set Coordinator
    (primary earbud), one CSIP Set Member (secondary earbud). And shows 2
    addresses on Android after pairing.

    Args:
      number: The target number of components.
    """
    self._primary_device.set_component_number(number)

  def pair_tws(self) -> None:
    """Pairs the two BES devboards as a pair of TWS earbuds."""
    utils.concurrent_exec(
        lambda d: d.pair_tws(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def get_in_box_state(self) -> bool:
    """Gets if the TWS earpods are in the box."""
    return self._primary_device.get_in_box_state()

  def set_in_box_state(self, in_box: bool) -> None:
    """Sets the box state of the TWS earpods."""
    utils.concurrent_exec(
        lambda d: d.set_in_box_state(in_box),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def get_on_head_state(self) -> bool:
    """Gets if the TWS earpods are on head."""
    return self._primary_device.get_on_head_state()

  def set_on_head_state(self, on_head: bool) -> None:
    """Sets the on head status of the TWS earpods."""
    utils.concurrent_exec(
        lambda d: d.set_on_head_state(on_head),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def open_box(self) -> None:
    """Opens the charging box."""
    utils.concurrent_exec(
        lambda d: d.open_box(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def fetch_out(self) -> None:
    """Fetches the TWS earpods out of the charging box."""
    utils.concurrent_exec(
        lambda d: d.fetch_out(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def wear_up(self) -> None:
    """Puts the TWS earpods on head."""
    utils.concurrent_exec(
        lambda d: d.wear_up(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def wear_down(self) -> None:
    """Takes the TWS earpods off head."""
    utils.concurrent_exec(
        lambda d: d.wear_down(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def put_in(self) -> None:
    """Puts the TWS earpods into the charging box."""
    utils.concurrent_exec(
        lambda d: d.put_in(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def close_box(self) -> None:
    """Closes the charging box."""
    utils.concurrent_exec(
        lambda d: d.close_box(),
        param_list=[[self._primary_device], [self._secondary_device]],
        raise_on_exception=True,
    )

  def start_audio_recording(
      self,
      stereo: bool = False,
      channels: bes_device.AudioChannelMode | None = None,
      sample_rate: int | None = None,
  ) -> None:
    """Starts the audio recorder to record audio output of the TWS device.

    Args:
      stereo: If True, record audio from both boards to form a stereo recording.
        Otherwise, record from the primary device only.
      channels: The number of channels of the recording. If None, use the
        default value.
      sample_rate: The sample rate, in Hertz. If None, use the default value.
    """
    self._is_stereo_recording = stereo
    if stereo:
      utils.concurrent_exec(
          lambda d: d.start_audio_recording(
              channels=channels,
              sample_rate=sample_rate,
          ),
          param_list=[[self._primary_device], [self._secondary_device]],
          raise_on_exception=True,
      )
    else:
      self._primary_device.start_audio_recording(
          channels=channels, sample_rate=sample_rate
      )

  def stop_audio_recording(
      self, output_directory: pathlib.Path
  ) -> list[pathlib.Path]:
    """Stops the audio recorder and moves the recording file to the output directory.

    Args:
      output_directory: The directory to move the recording file to.

    Returns:
      A list of paths to the recording files.
    """
    if self._is_stereo_recording:
      return utils.concurrent_exec(  # pytype: disable=bad-return-type
          lambda d: d.stop_audio_recording(output_directory),
          param_list=[[self._primary_device], [self._secondary_device]],
          raise_on_exception=True,
      )
    else:
      return [self._primary_device.stop_audio_recording(output_directory)]

  def set_battery_level(
      self,
      left_level: int,
      right_level: int,
      case_level: int | None = None,
  ) -> None:
    """Sets the fake battery level of the device.

    Args:
      left_level: The fake battery level of the left earbud, in the range of
        0-100. `level=80` represents that the battery is 80% full.
      right_level: The fake battery level of the right earbud, in the range of
        0-100. `level=80` represents that the battery is 80% full.
      case_level: The fake battery level of the case, in the range of 0-100. If
        None, there will be no case level set.
    """
    self._primary_device.set_battery_level_tws(
        left_level, right_level, case_level
    )

  def get_battery_level(self) -> tuple[int, int, int | None]:  # pytype: disable=signature-mismatch
    """Gets the fake battery level of the device.

    Returns:
      The fake battery level of the (left, right, case), in the range of 0-100.
      `level=80` represents that the battery is 80% full.
    """
    try:
      # Supported only on BES v2 and above.
      return self._primary_device.get_battery_level_tws()
    except (bes_device.BesDeviceError, bes_device.BesRuntimeError):
      pass

    return (
        self._left_device.get_battery_level(),
        self._right_device.get_battery_level(),
        None,
    )

  def get_paired_devices(self) -> list[dict[str, str]]:
    """Gets the list of paired devices information.

    Returns:
      A list of dicts containing the paired device name and address. The keys in
      the result dict are aligned with the Android `btGetPairedDevices` result.
      Example:
      [
        {'Name': 'Phone A', 'Address': '00:11:22:33:44:55'},
        {'Name': 'Phone B', 'Address': '66:77:88:99:AA:BB'},
      ]
    """
    return self._primary_device.get_paired_devices()

  def media_play(self) -> None:
    """Plays the media stream."""
    self._primary_device.media_play()

  def media_pause(self) -> None:
    """Pauses the media stream."""
    self._primary_device.media_pause()

  def media_next(self) -> None:
    """Jumps to the next media track."""
    self._primary_device.media_next()

  def media_prev(self) -> None:
    """Jumps to the previous media track."""
    self._primary_device.media_prev()

  def volume_up(self, level: int = 1) -> None:
    """Increases the device volume.

    This method simulates a press on the `Vol+` button. Each simulated press on
    the button will increase the volume by `level` unit.

    Args:
      level: The number of volume levels to increase.
    """
    self._primary_device.volume_up(level)

  def volume_down(self, level: int = 1) -> None:
    """Increases the device volume.

    This method simulates a press on the `Vol-` button. Each simulated press on
    the button will decrease the volume by `level` unit.

    Args:
      level: The number of volume levels to decrease.
    """
    self._primary_device.volume_down(level)

  def set_volume(self, level: int) -> None:
    """Sets the volume of the device to a given level.

    Args:
      level: The target volume level, in the range of [0, 127].
    """
    self._primary_device.set_volume(level)

  def get_volume(self) -> int:
    """Gets the volume of the device.

    Returns:
      The volume level of the device.
    """
    return self._primary_device.get_volume()

  def call_accept(self) -> None:
    """Accepts a phone call."""
    self._primary_device.call_accept()

  def call_decline(self) -> None:
    """Declines a phone call or hangs up on a current phone call."""
    self._primary_device.call_decline()

  def call_hold(self) -> None:
    """Holds the current call."""
    self._primary_device.call_hold()

  def call_redial(self) -> None:
    """Redials the last phone call."""
    self._primary_device.call_redial()

  def get_anc_support(self) -> bool:
    """Checks if the device supports Active Noise Cancellation (ANC)."""
    return self._primary_device.get_anc_support()

  def enable_anc(self) -> None:
    """Enables Active Noise Cancellation (ANC) on the device."""
    self._primary_device.enable_anc()

  def disable_anc(self) -> None:
    """Disables Active Noise Cancellation (ANC) on the device."""
    self._primary_device.disable_anc()

  def get_anc_mode(self) -> bluetooth_reference_device_base.AncMode:
    """Gets the ANC mode of the device."""
    return self._primary_device.get_anc_mode()

  def set_anc_mode(
      self, mode: str | bluetooth_reference_device_base.AncMode
  ) -> None:
    """Sets the ANC mode of the device."""
    self._primary_device.set_anc_mode(mode)

  def get_spatial_audio_support(self) -> bool:
    """Checks if the device supports Spatial Audio."""
    return self._primary_device.get_spatial_audio_support()

  def enable_spatial_audio(self) -> None:
    """Enables Spatial Audio on the device."""
    self._primary_device.enable_spatial_audio()

  def disable_spatial_audio(self) -> None:
    """Disables Spatial Audio on the device."""
    self._primary_device.disable_spatial_audio()
