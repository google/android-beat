"""Utils for setting up Android devices."""

import datetime
import time

from typing import Any

from mobly.controllers import android_device
from mobly.controllers.android_device_lib import apk_utils

from android_beat.platforms.bluetooth import tws_device
from android_beat.utils import bluetooth_utils


_BLUETOOTH_SNIPPET_PACKAGE = 'com.google.snippet.bluetooth'
_BLUETOOTH_SNIPPET_NAME = 'bt_snippet'
_SHORT_DELAY_TIME = datetime.timedelta(seconds=3)


def skip_setup_wizard(ad: android_device.AndroidDevice) -> None:
  """Skips the setup wizard if exists.

  Args:
    ad: The Android device to skip the setup wizard.
  """
  try:
    ad.adb.shell('am start -a com.android.setupwizard.EXIT')
  except android_device.adb.AdbError:
    ad.log.exception('Fail to exit the setup wizard, skipping...')


def enable_bluetooth_hci_snoop_log(ad: android_device.AndroidDevice) -> None:
  """Enables Bluetooth HCI snoop log.

  Args:
    ad: The Android device to enable Bluetooth HCI snoop log.
  """
  try:
    ad.adb.shell('setprop persist.bluetooth.btsnooplogmode full')
    ad.adb.shell('setprop persist.bluetooth.btsnoopsize 0xfffffffffffffff')
  except android_device.adb.AdbError:
    ad.log.exception(
        'Fail to enable Bluetooth HCI snoop log, skipping...'
    )


def update_le_audio_connection_policy(
    ad: android_device.AndroidDevice,
    is_lea_enabled: bool = False,
) -> None:
  """Updates LE audio connection policy.

  Args:
    ad: The Android device to update LE audio connection policy.
    is_lea_enabled: Whether to enable LE audio connection policy.
  """
  try:
    ad.adb.shell(
        'setprop persist.bluetooth.leaudio.bypass_allow_list'
        f' {str(is_lea_enabled).lower()}'
    )
  except android_device.adb.AdbError:
    ad.log.exception('Fail to update LE audio connection policy, skipping...')
  finally:
    ad.reboot()


def install_and_load_bluetooth_snippet(
    ad: android_device.AndroidDevice,
    apk_path: str,
    snippet_package: str = _BLUETOOTH_SNIPPET_PACKAGE,
    snippet_name: str = _BLUETOOTH_SNIPPET_NAME,
) -> None:
  """Installs custom snippet apk and loads the snippet service.

  Args:
    ad: The Android device.
    apk_path: The path of the custom snippet apk.
    snippet_package: The package name of the custom snippet apk.
    snippet_name: The attribute name to which to attach the snippet client.
  """
  apk_utils.install(ad, apk_path)
  ad.load_snippet(snippet_name, snippet_package)


def get_android_devices(
    ads: list[android_device.AndroidDevice],
    android_device_amount: int,
) -> tuple[
    android_device.AndroidDevice,
    android_device.AndroidDevice | None,
    android_device.AndroidDevice | None,
]:
  """Gets the Android devices based on the required quantity.

  Args:
    ads: The Android devices.
    android_device_amount: The required quantity of Android devices.

  Returns:
    A tuple containing up to three AndroidDevice instances. The first element
    is always the primary device. The second and third elements are None if
    fewer than 2 or 3 devices are requested, respectively.

  Raises:
    ValueError: If `android_device_amount` is not 1, 2, or 3, or if
      `ads` contains fewer devices than specified by `android_device_amount`.
  """
  try:
    if android_device_amount == 1:
      return ads[0], None, None
    elif android_device_amount == 2:
      return ads[0], ads[1], None
    elif android_device_amount == 3:
      return ads[0], ads[1], ads[2]
    else:
      raise ValueError(
          f'Unsupported Android device amount: {android_device_amount}'
      )
  except IndexError as e:
    raise ValueError(
        f'Insufficient Android devices: {android_device_amount} provided.'
    ) from e


def check_connection_and_reconnect(
    ad: android_device.AndroidDevice,
    bt_device: tws_device.TwsDevice,
    is_lea_enabled: bool,
) -> None:
  """Checks the connection and reconnect if needed."""
  if ad.bt_snippet.btIsA2dpConnected(
      bt_device.bluetooth_address_primary
  ) == ad.bt_snippet.btIsLeAudioConnected(bt_device.bluetooth_address_primary):
    bluetooth_utils.clear_saved_devices(ad)
    bt_device.factory_reset()
    bluetooth_utils.pair_and_assert_bluetooth_state(
        ad,
        [bt_device],
        is_lea_enabled,
    )


def stop_media_on_android_device_if_has_media(
    ad: android_device.AndroidDevice,
    has_media: bool,
) -> None:
  """Stops media on Android device if has media."""
  if has_media:
    ad.bt_snippet.media3Stop()
    time.sleep(_SHORT_DELAY_TIME.total_seconds())
    ad.bt_snippet.media3ClearPlaylist()

