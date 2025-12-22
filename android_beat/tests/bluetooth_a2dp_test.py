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

"""Bluetooth A2DP test."""

import datetime
import os
import time

from mobly import asserts
from mobly import test_runner

from android_beat.tests import base_test
from android_beat.utils import audio_utils
from android_beat.utils import bluetooth_utils
from android_beat.utils import test_utils

_MEDIA_PLAY_TIME = datetime.timedelta(seconds=30)


class BluetoothA2dpTest(base_test.BaseTestClass):
  """Test class for Bluetooth A2DP test."""

  _BLUETOOTH_MODE = base_test.BluetoothMode.CLASSIC
  _ANDROID_DEVICE_AMOUNT = base_test.AndroidDeviceAmount.SINGLE_DEVICE
  _MEDIA_FILES_NAMES = ('sine_tone_0.wav',)
  _MEDIA_FILES_PATHS = (
      '/sdcard/Download/sine_tone_0.wav',
  )

  def _pair_bluetooth_device(self) -> None:
    """Pairs the Android device with the Bluetooth device."""
    bluetooth_utils.pair_bluetooth_device(self.ad, self.bt_device)
    bluetooth_utils.wait_and_assert_a2dp_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
    )
    audio_utils.wait_and_assert_audio_device_type(
        self.ad,
        audio_utils.AudioDeviceType.TYPE_BLUETOOTH_A2DP,
        expect_active=True,
    )

  def setup_class(self) -> None:
    super().setup_class()
    # Mute the notification sound.
    self.ad.adb.shell('cmd media_session volume --stream 5 --set 0')
    self._pair_bluetooth_device()

    audio_utils.generate_and_push_audio_files(
        self.ad,
        self._MEDIA_FILES_NAMES,
        self.current_test_info.output_path,
    )
    self.generate_audio_file_paths = [
        os.path.join(self.current_test_info.output_path, file_name)
        for file_name in self._MEDIA_FILES_NAMES
    ]

  def setup_test(self) -> None:
    super().setup_test()
    # Check if A2DP is still connected. If not, factory reset the Bluetooth
    # device and repair it.
    if not self.ad.bt_snippet.btIsA2dpConnected(
        self.bt_device.bluetooth_address_primary
    ):
      bluetooth_utils.clear_saved_devices(self.ad)
      self.bt_device.factory_reset()
      self._pair_bluetooth_device()
    self.ad.bt_snippet.media3Stop()

  def teardown_test(self) -> None:
    self.ad.bt_snippet.media3Stop()
    super().teardown_test()

  def test_a2dp_stream(self):
    """A2DP stream.

    Objective:
      To validate the Device Under Test (DUT) can successfully play media and
      route to the connected device.

    Test Preconditions:
      1. Device: 1 Android device and 1 Bluetooth reference device.
      2. Sine_tone audio generated on the host and pushed to the device.

    Test Steps:
      1. Start audio recording.
      2. Play local media on DUT and routes to the connected device.
      3. Verify the media routes to BT device.
      4. Stop the media on DUT
      5. Verify the media stops streaming to the BT device from DUT.
      6. Stop audio recording.
      7. Detect the target audio and srouce audio start time.

    Pass criteria:
      1. DUT can play media and routes to the connected device.
    """
    with audio_utils.assert_a2dp_playback_stopped(self.ad, self.bt_device):
      # Play sine_tone audio.
      self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_FILES_PATHS[0])
      audio_utils.start_audio_recording(self.bt_device)

      bluetooth_utils.wait_and_assert_a2dp_playback_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
      )

      # Verify the media routes to BT device.
      test_utils.wait_until_or_assert(
          condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
              self.bt_device.bluetooth_address_primary
          ),
          error_msg='Failed to continue streaming audio to bt device',
          timeout=_MEDIA_PLAY_TIME,
      )

      time.sleep(_MEDIA_PLAY_TIME.total_seconds())
      recorded_audio_files_on_host = audio_utils.stop_audio_recording(
          self.bt_device, self.current_test_info.output_path
      )
      audio_utils.assert_has_audio_start_time(
          self.generate_audio_file_paths[0],
          recorded_audio_files_on_host,
      )

  def test_a2dp_stream_connect_from_snk(self):
    """Music stream routes to BT device when BT devices turned it back on.

    Objective:
      To validate the Device Under Test (DUT) can successfully connect to the
      Bluetooth device and stream media routes to BT device with A2DP profile
      when it is turned on.

    Test Preconditions:
      1. Device: 1 Android device and 1 Bluetooth reference device.
      2. Sine_tone audio generated on the host and pushed to the device.

    Test Steps:
      1. Turn off the BT device.
      2. Verify the BT device is still in paired status.
      3. Start audio recording.
      4. Play local media on DUT and routes to the connected device.
      5. Turn on the BT device.
      6. Verify the media routes quickly to BT device.
      7. Stop the media on DUT.
      8. Verify the media stops streaming to the BT device from DUT.
      9. Stop audio recording.
      10. Detect the target audio and srouce audio start time.

    Pass Criteria:
      1. Audio gets routed to BT device when BT devices turned it back on.
    """
    try:
      # Turn off the BT device.
      self.bt_device.close_box()

      # Verify the A2DP profile is disconnected.
      bluetooth_utils.wait_and_assert_a2dp_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=False
      )

      # Verify the BT device is still in paired status.
      asserts.assert_true(
          bluetooth_utils.is_bt_device_in_saved_devices(
              self.ad, self.bt_device.bluetooth_address_primary
          ),
          msg=(
              'Failed to keep pair status with Bluetooth device after turning'
              ' offBT device'
          ),
      )
    except Exception:
      self.bt_device.open_box()
      raise

    with audio_utils.assert_a2dp_playback_stopped(self.ad, self.bt_device):
      # Play sine_tone audio.
      self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_FILES_PATHS[0])

      # Turn on the BT device.
      self.bt_device.open_box()

      # Start audio recording on the BT device.
      audio_utils.start_audio_recording(self.bt_device)

      # Verify the A2DP profile is reconnected.
      bluetooth_utils.wait_and_assert_a2dp_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
      )
      # Verify the HFP profile is reconnected.
      bluetooth_utils.wait_and_assert_hfp_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
      )

      # Verify the media routes quickly to BT device.
      bluetooth_utils.wait_and_assert_a2dp_playback_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
      )

      test_utils.wait_until_or_assert(
          condition=lambda: self.ad.bt_snippet.btIsA2dpPlaying(
              self.bt_device.bluetooth_address_primary
          ),
          error_msg='Failed to continue streaming audio to bt device',
          timeout=_MEDIA_PLAY_TIME,
      )

      time.sleep(_MEDIA_PLAY_TIME.total_seconds())
      recorded_audio_files_on_host = audio_utils.stop_audio_recording(
          self.bt_device, self.current_test_info.output_path
      )
      audio_utils.assert_has_audio_start_time(
          self.generate_audio_file_paths[0],
          recorded_audio_files_on_host,
      )

  def test_a2dp_stream_reconnect_from_src(self):
    """A2DP stream routes to BT device when dut reconnects to BT device.

    Objective:
      To validate the Device Under Test (DUT) can successfully reconnect to the
      Bluetooth device and Stream media routes to BT device with A2DP profile.

    Test Preconditions:
      1. Device: 1 Android device and 1 Bluetooth reference device.
      2. Sine_tone audio generated on the host and pushed to the device.

    Test Steps:
      1. Disconnect A2DP and HFP profiles with the BT device from DUT.
      2. Verify the BT device is still in paired status.
      3. Start audio recording.
      4. Play local media on DUT and routes to the connected device.
      5. Reconnect A2DP profile with the BT device from DUT.
      6. Verify A2DP and HFP profiles are connected.
      7. Verify the media routes quickly to BT device.
      8. Stop the media on DUT
      9. Verify the media stops streaming to the BT device from DUT.
      10. Stop audio recording.
      11. Detect the target audio and srouce audio start time.

    Pass Criteria:
      1. Audio gets routed to BT device when DUT reconnects to BT device.
    """
    # Disconnects the A2DP and HFP profiles from DUT
    self.ad.bt_snippet.btA2dpDisconnect(
        self.bt_device.bluetooth_address_primary
    )
    self.ad.bt_snippet.btHfpDisconnect(self.bt_device.bluetooth_address_primary)

    # Verify the A2dp and HFP profiles are disconnected.
    bluetooth_utils.wait_and_assert_a2dp_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=False
    )
    bluetooth_utils.wait_and_assert_hfp_state(
        self.ad, self.bt_device.bluetooth_address_primary, expect_active=False
    )

    # Verify the BT device is still in paired status.
    asserts.assert_true(
        bluetooth_utils.is_bt_device_in_saved_devices(
            self.ad, self.bt_device.bluetooth_address_primary
        ),
        msg=(
            'Failed to keep pair status with Bluetooth device after turning off'
            'BT device'
        ),
    )

    with audio_utils.assert_a2dp_playback_stopped(self.ad, self.bt_device):
      # Play sine_tone audio.
      self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_FILES_PATHS[0])

      # Reconnect A2DP and HFP profiles with the BT device from DUT.
      self.ad.bt_snippet.btA2dpConnect(self.bt_device.bluetooth_address_primary)
      self.ad.bt_snippet.btHfpConnect(self.bt_device.bluetooth_address_primary)

      # Start audio recording on the BT device.
      audio_utils.start_audio_recording(self.bt_device)

      # Verify the A2DP and HFP profiles are connected.
      bluetooth_utils.wait_and_assert_a2dp_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
      )
      bluetooth_utils.wait_and_assert_hfp_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
      )

      # Verify the media routes quickly to BT device.
      bluetooth_utils.wait_and_assert_a2dp_playback_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
      )
      time.sleep(_MEDIA_PLAY_TIME.total_seconds())
      recorded_audio_files_on_host = audio_utils.stop_audio_recording(
          self.bt_device, self.current_test_info.output_path
      )
      audio_utils.assert_has_audio_start_time(
          self.generate_audio_file_paths[0],
          recorded_audio_files_on_host,
      )

  def test_a2dp_suspend_streaming_from_src(self):
    """DUT stop streaming to BT device when dut stops the music.

    Objective:
      To validate the Device Under Test (DUT) can successfully reconnect to the
      Bluetooth device and stop streaming media to BT device when DUT stops the
      music.

    Test Preconditions:
      1. Device: 1 Android device and 1 Bluetooth reference device.
      2. Sine_tone audio generated on the host and pushed to the device.

    Test Steps:
      1. Start audio recording.
      2. Play local media on DUT and routes to the connected device.
      3. Verify the media routes to BT device.
      4. Stop the media on DUT.
      5. Verify DUT stop streaming to BT device.
      6. Stop the media on DUT
      7. Verify the media stops streaming to the BT device from DUT.
      8. Stop audio recording.
      9. Detect the target audio and srouce audio start time.

    Pass Criteria:
      1. DUT should stop streaming to BT device when DUT stops the music.
    """
    with audio_utils.assert_a2dp_playback_stopped(self.ad, self.bt_device):
      # Play sine_tone audio.
      self.ad.bt_snippet.media3StartLocalFile(self._MEDIA_FILES_PATHS[0])

      # Start audio recording on the BT device.
      audio_utils.start_audio_recording(self.bt_device)

      # Verify the media is playing on the BT device.
      bluetooth_utils.wait_and_assert_a2dp_playback_state(
          self.ad, self.bt_device.bluetooth_address_primary, expect_active=True
      )
      time.sleep(_MEDIA_PLAY_TIME.total_seconds())
      recorded_audio_files_on_host = audio_utils.stop_audio_recording(
          self.bt_device, self.current_test_info.output_path
      )
      audio_utils.assert_has_audio_start_time(
          self.generate_audio_file_paths[0],
          recorded_audio_files_on_host,
      )


if __name__ == '__main__':
  test_runner.main()
