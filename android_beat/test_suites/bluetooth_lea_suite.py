"""Test suite for testing Bluetooth LE Audio."""

from mobly import base_suite
from mobly import config_parser
from mobly import test_runner_suite

from android_beat.tests import bluetooth_lea_connection_test
from android_beat.tests import bluetooth_lea_gaming_test
from android_beat.tests import bluetooth_lea_media_control_test


class BluetoothLeaTestSuite(base_suite.BaseSuite):
  """Test suite to run Bluetooth tests for LE Audio."""

  def setup_suite(self, config: config_parser.TestRunConfig):
    self.add_test_class(
        clazz=bluetooth_lea_connection_test.BluetoothLeaConnectionTest
    )
    self.add_test_class(clazz=bluetooth_lea_gaming_test.BluetoothLeaGamingTest)
    self.add_test_class(
        clazz=bluetooth_lea_media_control_test.BluetoothLeaMediaControlTest
    )


if __name__ == '__main__':
  test_runner_suite.main()
