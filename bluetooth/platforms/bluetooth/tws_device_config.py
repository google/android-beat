"""Controller configurations for the TWS controller module."""

from __future__ import annotations

from collections.abc import Sequence
import dataclasses
import enum
import json
import logging
from typing import Any

import dacite

from bluetooth.platforms.bluetooth import bes_device

# Supported controller class names as the value of `controller_type`.
_SUPPORTED_CONTROLLER_TYPES = (bes_device.MOBLY_CONTROLLER_CONFIG_NAME,)

# Error messages used in this module.
_DEVICE_EMPTY_CONFIG_MSG = 'Configuration is empty, abort!'
_CONFIG_MISSING_REQUIRED_KEY_MSG = 'Missing required key in config'
_CONFIG_WRONG_TYPE_MSG = 'Wrong type in config'
_CONFIG_INVALID_VALUE_MSG = 'Invalid value in config'


class ConfigError(Exception):
  """The TWS controller configs encounter error."""

  def __init__(
      self, message: str, config: dict[str, Any] | None = None
  ) -> None:
    if config is not None:
      message = f'{message}: {config}'
    super().__init__(message)


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
    logging.debug('Parsing TWS device config: %s', config)
    device_configs.append(DeviceConfig.from_dict(config))

  return device_configs


@enum.unique
class EarType(enum.StrEnum):
  """The type of the ear in a TWS device."""

  LEFT = 'LEFT'
  RIGHT = 'RIGHT'

  @classmethod
  def from_string(cls, ear_type: str) -> EarType:
    """Converts the ear type string to the corresponding EarType."""
    if ear_type.upper() in (cls.LEFT.value, cls.LEFT.value.lower()):
      return cls.LEFT
    elif ear_type.upper() in (cls.RIGHT.value, cls.RIGHT.value.lower()):
      return cls.RIGHT
    else:
      raise ValueError(f'Unsupported ear type: {ear_type}')


@dataclasses.dataclass
class DeviceConfig:
  """Provides configs and default values for TwsDevice.

  TWS stands for True Wireless Stereo. In this context, it refers to a
  Bluetooth device that consists of: left earbud, right earbud, and (optionally)
  case. The components of the TWS device are paired with each other during
  initialization, communicate with each other over Bluetooth, and work as one
  device in the test.

  Attributes:
    controller_type: The controller type of the components of the TWS device.
      The two earbuds are considered as two components, but should be of the
      same controller type.
    left_config: The config of the left earbud. The config format should be
      aligned with the config of the controller type.
    right_config: The config of the right earbud. The config format should be
      aligned with the config of the controller type.
    case_config: The config of the case. The case config is optional depending
      on the controller type. The config format should be aligned with the
      config of the controller type.
    primary_ear: The primary ear of the TWS device which advertises data and
      initiates bonding with the DUT. It can be either left ('LEFT', 'left',
      'Left', 'L', 'l') or right ('RIGHT', 'right', 'Right', 'R', 'r') depending
      on the underlying controller type.
  """

  controller_type: str
  left_config: dict[str, Any]
  right_config: dict[str, Any]
  case_config: dict[str, Any] | None = None
  primary_ear: EarType = EarType.RIGHT

  def __post_init__(self):
    if self.controller_type not in _SUPPORTED_CONTROLLER_TYPES:
      raise ConfigError(f'Unsupported controller type: {self.controller_type}')

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

    # Callable used in dacite.Config.type_hooks to transform the input data
    def _convert_to_dict_if_json(data: Any) -> Any:
      """Converts the input data to a dict if the it is valid JSON string."""
      if isinstance(data, str):
        try:
          return json.loads(data)
        except json.decoder.JSONDecodeError:
          pass
      return data

    type_converters = {
        # Convert JSON strings to dict.
        dict[str, Any]: _convert_to_dict_if_json,
        EarType: EarType.from_string,
    }
    try:
      config = dacite.from_dict(
          data_class=DeviceConfig,
          data=config,
          config=dacite.Config(type_hooks=type_converters),
      )
    except dacite.exceptions.MissingValueError as err:
      raise ConfigError(_CONFIG_MISSING_REQUIRED_KEY_MSG, config) from err
    except dacite.exceptions.WrongTypeError as err:
      raise ConfigError(_CONFIG_WRONG_TYPE_MSG, config) from err
    except ValueError as err:
      raise ConfigError(_CONFIG_INVALID_VALUE_MSG, config) from err

    return config
