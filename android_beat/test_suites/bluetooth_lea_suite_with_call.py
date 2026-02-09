"""Test suite for testing Bluetooth LE Audio with call."""

from mobly import base_suite
from mobly import config_parser
from mobly import suite_runner

from android_beat.tests import bluetooth_lea_call_control_test


class BluetoothLeaTestSuiteWithCall(base_suite.BaseSuite):
  """Test suite to run Bluetooth tests for LE Audio with call."""

  def setup_suite(self, config: config_parser.TestRunConfig):
    self.add_test_class(
        clazz=bluetooth_lea_call_control_test.BluetoothLeaCallControlTest
    )


if __name__ == '__main__':
  suite_runner.run_suite_class()
