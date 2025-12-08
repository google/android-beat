# Copyright 2025 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility functions for general test related operations."""

from collections.abc import Callable
import datetime
import time

from mobly import asserts

_SHORT_DELAY_TIME_BETWEEN_ACTIONS = datetime.timedelta(seconds=1)


def wait_until_or_assert(
    condition: Callable[[], bool],
    error_msg: str,
    timeout: datetime.timedelta,
) -> None:
  """Waits until the condition is met, or asserts if timeout.

  Args:
    condition: Represents the condition to wait for.
    error_msg: The error message to be included in the assertion failure.
    timeout: The maximum time to wait for the condition to be met.

  Raises:
    mobly.signals.TestFailure: When the condition is not met within the timeout.
  """
  end_time = time.monotonic() + timeout.total_seconds()
  while time.monotonic() < end_time:
    if condition():
      return
    time.sleep(_SHORT_DELAY_TIME_BETWEEN_ACTIONS.total_seconds())
  asserts.fail(f'{error_msg} within {timeout.total_seconds()} seconds')
