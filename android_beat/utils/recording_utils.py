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

"""Utility functions for audio recording."""

from collections.abc import Iterator
import contextlib

from mobly import asserts
from mobly.controllers import android_device


RECORDING_FILE_NAME = 'test_recording.mp4'
RECORDING_FILE_PATH = '/storage/emulated/0/Android/data/com.google.snippet.bluetooth/cache/test_recording.mp4'


@contextlib.contextmanager
def record_audio_context(ad: android_device.AndroidDevice) -> Iterator[None]:
  """Context manager to start and stop audio recording."""
  ad.log.info('Starting VBC test: Activating microphone recording.')
  try:
    ad.bt_snippet.mediaStartRecording(RECORDING_FILE_NAME)
    ad.log.info(
        'Audio input devices: %s',
        ad.bt_snippet.mediaGetActiveMicrophones(),
    )
    yield
  finally:
    output_path = ad.bt_snippet.mediaStopRecording()
    asserts.assert_equal(
        output_path,
        RECORDING_FILE_PATH,
        f'Expected path {RECORDING_FILE_PATH}, got {output_path}',
    )
    ad.log.info('Stopped recording.')
