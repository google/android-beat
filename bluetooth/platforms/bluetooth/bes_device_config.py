"""Controller configurations for the BES controller module."""

from __future__ import annotations

from collections.abc import Sequence
import dataclasses
import json
import logging
from typing import Any

import dacite

from bluetooth.platforms.bluetooth.lib import utils

# Error messages used in this module.
_DEVICE_EMPTY_CONFIG_MSG = 'Configuration is empty, abort!'
_CONFIG_MISSING_REQUIRED_KEY_MSG = 'Missing required key in config'
_CONFIG_INVALID_VALUE_MSG = 'Invalid value in config'
_INVALID_BLUETOOTH_ADDRESS_MSG = 'Invalid Bluetooth address'


class ConfigError(Exception):
  """The BES controller configs encounter error."""


def from_dicts(configs: Sequence[dict[str, Any]]) -> list[DeviceConfig]:
  """Create DeviceConfig objects from a list of dict configs.

  Args:
    configs: A list of dicts each representing the configuration of one
      Bluetooth reference device.

  Returns:
    A list of DeviceConfig.

  Raises:
    errors.ConfigError: Invalid controller config is given.
  """
  device_configs = []
  if not configs:
    raise ConfigError(_DEVICE_EMPTY_CONFIG_MSG)

  for config in configs:
    logging.debug('Parsing BES config: %s', config)
    device_configs.append(DeviceConfig.from_dict(config))

  return device_configs


@dataclasses.dataclass
class DeviceConfig:
  """Provides configs and default values for BesDevice.

  Attributes:
    serial_port: The serial port of the BES dev board connected to the Mobly
      host or the Raspberry Pi.
    bluetooth_address: The Bluetooth MAC address of the BES dev board connected
      to the Mobly host or the Raspberry Pi.
    remote_mode: Whether the BES dev board is connected to a remote Linux-based
      devive such as Raspberry Pi. If True, the serial connection will be built
      over SSH.
    hostname: The IP address or hostname of the device that the BES dev board is
      connected to (if applicable).
    ssh_port: The SSH port of the device that the BES dev board is connected to
      (if applicable).
    username: Username to log in the device that the BES dev board is connected
      to (if applicable).
    password: Password to log in the device that the BES dev board is connected
      to (if applicable).
    keyfile: The local file path to the SSH key file on the Mobly test host
      machine.
    proxy_command: The SSH proxy command to use. For example, to access a device
      on the test network from a Cloudtop, set "proxy_command='corp-ssh-helper
      --dst_username=<name> <IP> <port>'". Note that placeholders within the SSH
      command, such as '%h' and '%p', will not be substituted with the hostname
      and port when a proxy command is used.
    audio_configs: The configuration for audio recording from the BES dev board.
    dimensions: The field for user to pass MH dimensions or custom configs of
      the BES device.
  """

  # BES configs.
  serial_port: str
  bluetooth_address: str

  # SSH configs. If the BES dev board is connected to a remote device (eg.
  # Raspberry Pi), the `hostname` field needs to be specified. If `hostname` is
  # not specified, BES controller will build serial connection locally.
  remote_mode: bool = False
  hostname: str | None = None
  ssh_port: int = 22
  username: str = 'pi'
  password: str = 'raspberry'
  keyfile: str | None = None
  proxy_command: str | None = None

  @dataclasses.dataclass
  class AudioConfig:
    # To query the pcm name, run command `arecord -l` on the test machine.
    # Example command output to device name conversion:
    # Command output "card 0: PCH [HDA Intel PCH], device 0: ALC662 rev3 Analog"
    # The pcm name of the above capture device is `hw:0,0` or `plughw:0,0`.
    pcm_name: str
    sample_rate: int = 8000
    sample_format: str = 'S16_LE'
    channels: int = 1

  # Audio configs for recording sounds from the BES dev board.
  # If None, BES conntroller cannot record sounds from the BES dev board.
  audio_configs: AudioConfig | None = None

  # MH dimensions of this testbed. The dimensions can then be used to filter
  # devices in the test. Dimensions can also be set in local testbeds.
  #
  # Example testbed:
  #   ```config.yaml
  #   BesDevice:
  #   - serial_port: '/dev/ttyUSB0'
  #     bluetooth_address: '11:22:33:44:55:66'
  #     dimensions:
  #       mode: 'headset'
  #   ```
  dimensions: dict[str, Any] = dataclasses.field(default_factory=dict)

  def __post_init__(self):
    if not utils.is_valid_address(self.bluetooth_address):
      raise ConfigError(
          f'{_INVALID_BLUETOOTH_ADDRESS_MSG}: {self.bluetooth_address}'
      )
    if self.remote_mode and self.hostname is None:
      raise ConfigError(
          f'{_CONFIG_MISSING_REQUIRED_KEY_MSG}: hostname is required if remote'
          ' mode is enabled.'
      )

  def get(self, key: str, default_value: Any = None) -> Any:
    """Gets the value of the key in device config or its dimensions.

    This method first tries to get the value of the key from DeviceConfig
    attributes. If the key is not in the attributes, it will try to get the
    value from `dimensions` dict.

    Args:
      key: The key to find.
      default_value: The value to return if cannot find target key.

    Returns:
      The value of the key if the key is in DeviceConfig attributes or
      dimensions. Otherwise, returns `default_value`.
    """
    if hasattr(self, key):
      return getattr(self, key)
    if key in self.dimensions:
      return self.dimensions[key]
    return default_value

  @classmethod
  def from_dict(cls, config: dict[str, Any]) -> DeviceConfig:
    """Parses controller configs from Mobly runner to DeviceConfig.

    Args:
      config: A dictionary of string parameters.

    Returns:
      DeviceConfig data class.

    Raises:
      ConfigError: Invalid controller config is given.
    """
    def _bool_converter(value: Any) -> bool:
      """Converts the input data to a boolean if it is string."""
      if isinstance(value, bool):
        return value
      if isinstance(value, str) and value.lower() == 'true':
        return True
      if isinstance(value, str) and value.lower() == 'false':
        return False
      raise ValueError(f'Invalid value for bool: {value}')

    def _audio_config_converter(
        data: str | dict[str, Any],
    ) -> DeviceConfig.AudioConfig:
      r"""Converts the input data to an AudioConfig.

      When MobileHarness pass the config to Mobly, the `MoblyConfigGenerator`
      will set a dictionary property to a JSON string if it failed to set the
      property as is.
      (http://google3/java/com/google/devtools/mobileharness/platform/testbed/mobly/util/MoblyConfigGenerator.java;l=182-192;rcl=584762789)
      So `audio_configs` may receive JSON string inputs. For example,
      ```config.yaml
         BesDevice:
         - serial_port: '/dev/ttyUSB0'
           bluetooth_address: '11:22:33:44:55:66'
           audio_configs: "{\"pcm_name\": \"hw:0,0\", \"sample_rate\": 8000}"
      ```

      Args:
        data: The input data to convert. It can be a JSON string or a dict.

      Returns:
        AudioConfig data class.
      """
      if isinstance(data, str):
        data = json.loads(data)
      return dacite.from_dict(
          data_class=DeviceConfig.AudioConfig,
          data=data,
          config=dacite.Config(type_hooks={int: int}),
      )

    type_converters = {
        # Integer converter: any integer value in string
        # simply cast it to integer.
        int: int,
        bool: _bool_converter,
        DeviceConfig.AudioConfig: _audio_config_converter,
    }
    try:
      config = dacite.from_dict(
          data_class=DeviceConfig,
          data=config,
          config=dacite.Config(type_hooks=type_converters))
    except dacite.exceptions.MissingValueError as err:
      raise ConfigError(
          f'{_CONFIG_MISSING_REQUIRED_KEY_MSG}: {config}') from err
    except ValueError as err:
      raise ConfigError(
          f'{_CONFIG_INVALID_VALUE_MSG}: {config}') from err

    return config
