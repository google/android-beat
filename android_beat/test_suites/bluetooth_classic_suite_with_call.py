"""Test suite for testing Bluetooth Classic with call."""

from mobly import base_suite
from mobly import config_parser
from mobly import suite_runner

from android_beat.tests import bluetooth_a2dp_with_call_test
from android_beat.tests import bluetooth_classic_call_control_test


class BluetoothClassicTestSuiteWithCall(base_suite.BaseSuite):
  """Test suite to run Bluetooth tests for Classic with call."""

  def setup_suite(self, config: config_parser.TestRunConfig):
    self.add_test_class(
        clazz=bluetooth_classic_call_control_test.BluetoothClassicCallControlTest
    )
    self.add_test_class(
        clazz=bluetooth_a2dp_with_call_test.BluetoothA2dpWithCallTest
    )


if __name__ == '__main__':
  suite_runner.run_suite_class()
