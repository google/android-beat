"""Test suite for testing Bluetooth Classic."""

from mobly import base_suite
from mobly import config_parser
from mobly import suite_runner

from android_beat.tests import bluetooth_a2dp_test
from android_beat.tests import bluetooth_avrcp_test
from android_beat.tests import bluetooth_ble_test
from android_beat.tests import bluetooth_classic_connection_test
from android_beat.tests import bluetooth_opp_test


class BluetoothClassicTestSuite(base_suite.BaseSuite):
  """Test suite to run Bluetooth tests for Classic."""

  def setup_suite(self, config: config_parser.TestRunConfig):
    self.add_test_class(
        clazz=bluetooth_classic_connection_test.BluetoothClassicConnectionTest
    )
    self.add_test_class(clazz=bluetooth_a2dp_test.BluetoothA2dpTest)
    self.add_test_class(clazz=bluetooth_avrcp_test.BluetoothAvrcpTest)
    self.add_test_class(clazz=bluetooth_ble_test.BluetoothBleTest)
    self.add_test_class(clazz=bluetooth_opp_test.BluetoothOppTest)


if __name__ == '__main__':
  suite_runner.run_suite_class()
