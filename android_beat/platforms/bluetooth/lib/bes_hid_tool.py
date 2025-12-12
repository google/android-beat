"""HID tool for BES boards."""

import datetime
import logging
import pathlib
import re
import time

from mobly import utils as mobly_utils

from android_beat.platforms.cros.lib import ssh as ssh_lib
import resources


# The command to install the hidapi library
_HIDAPI_PKG_NAME = 'libhidapi-dev'
_HIDLIB_LIST_COMMAND = f'apt list --installed | grep {_HIDAPI_PKG_NAME}'
_HIDLIB_INSTALL_COMMAND_REMOTE = (
    'echo {password} | sudo -S apt-get --allow-releaseinfo-change update &&'
    f' sudo apt-get -y install {_HIDAPI_PKG_NAME}'
)
_HIDLIB_INSTALL_COMMAND_LOCAL = (
    f'sudo apt-get update && sudo apt-get -y install {_HIDAPI_PKG_NAME}'
)
_UNUSED_APT_CONFIG_FILE = '/etc/apt/apt.conf.d/99defaultrelease'
_REMOVE_APT_CONFIG_COMMAND = 'echo {password} | sudo -S rm {config_file}'

# The file path of the HID tool script in google3
_HID_TOOL_CODE_PATH = (
    'google3/devtools/bettertogether/feature/bluetooth/git/platforms/bluetooth/tools/hidtool.c'
)

# The directory path pattern to save cache files on Raspberry Pi
_REMOTE_CACHE_DIR_PATH = '/home/{username}/.cache'
_LOCAL_CACHE_DIR_PATH = '/tmp'

_DEFAULT_HIDTOOL_SOURCE_NAME = 'hidtool.c'
_DEFAULT_HIDTOOL_NAME = 'hidtool.o'

_HIDTOOL_COMPILE_COMMAND = 'gcc -o {output_path} {source_path} -lhidapi-hidraw'
_HIDTOOL_RUN_COMMAND_ON_HOST = 'sudo {tool_path} {command}'
_HIDTOOL_RUN_COMMAND_ON_RPI = 'echo {password} | sudo -S {tool_path} {command}'

_MCU_VERSION_REGEX = r'V\d\.\d\.\d'
_STABLE_MCU_VERSION = 'V1.0.3'

# Timeouts for waiting for the BES boards to be ready
_SHORT_TIMEOUT = datetime.timedelta(seconds=10)
_LONG_TIMEOUT = datetime.timedelta(seconds=30)


def _install_hidapi_lib_local() -> None:
  """Installs hidapi library on Mobly host."""
  _, stdout, _ = mobly_utils.run_command(_HIDLIB_LIST_COMMAND, shell=True)
  if stdout:
    logging.info('HID library is already installed.')
    return

  mobly_utils.run_command(_HIDLIB_INSTALL_COMMAND_LOCAL, shell=True)

  _, stdout, _ = mobly_utils.run_command(_HIDLIB_LIST_COMMAND, shell=True)
  if _HIDAPI_PKG_NAME.encode() not in stdout:
    raise RuntimeError('Failed to install HID library on host.')


def _install_hidapi_lib_remote(
    ssh: ssh_lib.SSHProxy,
    password: str,
) -> None:
  """Installs the hidapi library on Raspberry Pi."""
  try:
    ssh.execute_command(_HIDLIB_LIST_COMMAND)
    logging.info('HID library is already installed.')
    return
  except Exception:  # pylint: disable=broad-except
    pass

  if ssh.is_file(_UNUSED_APT_CONFIG_FILE):
    ssh.execute_command(
        _REMOVE_APT_CONFIG_COMMAND.format(
            config_file=_UNUSED_APT_CONFIG_FILE,
            password=password,
        )
    )
  ssh.execute_command(_HIDLIB_INSTALL_COMMAND_REMOTE.format(password=password))


def _push_code_file_to_remote(ssh: ssh_lib.SSHProxy, username: str) -> None:
  """Pushes the HID tool source code to Raspberry Pi."""
  remote_hid_code_path = str(
      pathlib.PurePosixPath(
          _REMOTE_CACHE_DIR_PATH.format(username=username),
          _DEFAULT_HIDTOOL_SOURCE_NAME,
      )
  )
  local_hid_code_path = resources.GetResourceFilename(_HID_TOOL_CODE_PATH)
  if ssh.is_file(remote_hid_code_path):
    try:
      ssh.rm_file(remote_hid_code_path)
    except IOError:
      return

  ssh.push(
      local_src_filename=local_hid_code_path,
      remote_dest_filename=remote_hid_code_path,
      change_permission=True,
  )


def _compile_hidtool_local() -> None:
  """Compiles HID tool source code to a binary on Mobly host."""
  local_hid_code_path = resources.GetResourceFilename(_HID_TOOL_CODE_PATH)
  output_file_path = pathlib.Path(
      _LOCAL_CACHE_DIR_PATH,
      _DEFAULT_HIDTOOL_NAME,
  )
  mobly_utils.run_command(
      cmd=_HIDTOOL_COMPILE_COMMAND.format(
          output_path=output_file_path,
          source_path=local_hid_code_path,
      ),
      shell=True,
  )
  if not output_file_path.is_file():
    raise FileNotFoundError('Failed to compile HID tool')
  logging.info('HID tool compiled as %s', output_file_path)


def _compile_hidtool_remote(ssh: ssh_lib.SSHProxy, username: str) -> None:
  """Compiles the HID tool source code to a binary on Raspberry Pi."""
  remote_cache_dir_path = _REMOTE_CACHE_DIR_PATH.format(username=username)
  remote_hid_code_path = str(
      pathlib.PurePosixPath(remote_cache_dir_path, _DEFAULT_HIDTOOL_SOURCE_NAME)
  )
  output_file_path = str(
      pathlib.PurePosixPath(remote_cache_dir_path, _DEFAULT_HIDTOOL_NAME)
  )
  if not ssh.is_file(remote_hid_code_path):
    raise RuntimeError('HID tool source file not found.')

  ssh.execute_command(
      command=_HIDTOOL_COMPILE_COMMAND.format(
          output_path=output_file_path,
          source_path=remote_hid_code_path,
      ),
  )
  logging.info('HID tool compiled as %s', output_file_path)


def _run_hidtool_local(action_command: str) -> str:
  """Runs HID tool on Mobly host."""
  tool_path = pathlib.Path(
      _LOCAL_CACHE_DIR_PATH,
      _DEFAULT_HIDTOOL_NAME,
  )
  logging.info('HID run command: %s', action_command)
  return mobly_utils.run_command(
      _HIDTOOL_RUN_COMMAND_ON_HOST.format(
          tool_path=tool_path, command=action_command
      ),
      shell=True,
      universal_newlines=True,
  )[1]


def _run_hidtool_remote(
    action_command: str,
    ssh: ssh_lib.SSHProxy,
    username: str,
    password: str,
) -> str:
  """Runs the HID tool on Raspberry Pi and sends a command to BES boards."""
  tool_path = pathlib.PurePosixPath(
      _REMOTE_CACHE_DIR_PATH.format(username=username),
      _DEFAULT_HIDTOOL_NAME,
  )
  cmd = _HIDTOOL_RUN_COMMAND_ON_RPI.format(
      password=password,
      tool_path=tool_path,
      command=action_command,
  )

  logging.info('HID run command: %s', action_command)
  return ssh.execute_command(cmd)


def _check_mcu_version_local() -> None:
  """Checks if the MCU version is a stable version on Mobly host.

  BES v2 board has 2 USB ports, 1 for remote control and 1 for data streaming.
  Each port requires a different firmware. The MCU firmware controls button
  press and the BT firmware controls data streaming and other BT features.

  The MCU firmware can only be flashed manually. So we need to check if
  the current MCU version is a stable version. If not, please file a ticket to
  the lab team to flash the MCU firmware.

  Raises:
    RuntimeError: If the MCU version is not a stable version.
  """
  version_result = _run_hidtool_local('WLTVER?')
  for matched in re.findall(_MCU_VERSION_REGEX, version_result):
    if matched != _STABLE_MCU_VERSION:
      raise RuntimeError(
          f'Current MCU version {matched} is not a stable version.'
          ' Please flash the MCU firmware to the stable version'
          f' {_STABLE_MCU_VERSION}.'
      )


def _check_mcu_version_remote(
    ssh: ssh_lib.SSHProxy, username: str, password: str
) -> None:
  """Checks if the MCU version is a stable version.

  BES v2 board has 2 USB ports, 1 for remote control and 1 for data streaming.
  Each port requires a different firmware. The MCU firmware controls button
  press and the BT firmware controls data streaming and other BT features.

  The MCU firmware can only be flashed manually. So we need to check if
  the current MCU version is a stable version. If not, please file a ticket to
  the lab team to flash the MCU firmware.

  Args:
    ssh: The SSH proxy to the Raspberry Pi.
    username: The username of the Raspberry Pi.
    password: The password of the Raspberry Pi.

  Raises:
    RuntimeError: If the MCU version is not a stable version.
  """
  version_result = _run_hidtool_remote('WLTVER?', ssh, username, password)
  for matched in re.findall(_MCU_VERSION_REGEX, version_result):
    if matched != _STABLE_MCU_VERSION:
      raise RuntimeError(
          f'Current MCU version {matched} is not a stable version.'
          ' Please flash the MCU firmware to the stable version'
          f' {_STABLE_MCU_VERSION}.'
      )


def power_on_remote(
    ssh: ssh_lib.SSHProxy,
    username: str,
    password: str,
) -> None:
  """Powers on the BES boards connected to Raspberry Pi."""
  # 1. Install required libraries on Raspberry Pi.
  _install_hidapi_lib_remote(ssh, password)

  # 2. Push and compile the HID tool on Raspberry Pi.
  _push_code_file_to_remote(ssh, username)
  _compile_hidtool_remote(ssh, username)

  # 3. Check the MCU version.
  _check_mcu_version_remote(ssh, username, password)
  time.sleep(_SHORT_TIMEOUT.total_seconds())

  # 4. Run power on and reboot commands one by one to recover the BES boards.
  _run_hidtool_remote('mobly_test:power_on', ssh, username, password)
  time.sleep(_LONG_TIMEOUT.total_seconds())
  _run_hidtool_remote('mobly_test:reboot', ssh, username, password)
  time.sleep(_LONG_TIMEOUT.total_seconds())


def power_on_local() -> None:
  """Powers on the BES boards connected to Mobly host."""
  # 1. Install required libraries on host.
  _install_hidapi_lib_local()

  # 2. Compile the HID tool on host.
  _compile_hidtool_local()

  # 3. Check the MCU version.
  _check_mcu_version_local()
  time.sleep(_SHORT_TIMEOUT.total_seconds())

  # 4. Run power on and reboot commands one by one to recover the BES boards.
  _run_hidtool_local('mobly_test:power_on')
  time.sleep(_LONG_TIMEOUT.total_seconds())
  _run_hidtool_local('mobly_test:reboot')
  time.sleep(_LONG_TIMEOUT.total_seconds())
