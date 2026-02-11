# Android BEAT (Bluetooth End-to-end Automation Test)

## What is Android BEAT?

Android BEAT (Bluetooth End-to-end Automation Test) is a test suite for
validating Bluetooth functionality by executing critical user journeys (CUJs).

The primary goal of this project is to provide a comprehensive, automated
testing solution that ensures Bluetooth features are robust and reliable across
a wide range of Android devices.

This is not an officially supported Google product. This project is not eligible
for the [Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).

## What is Tested?

The test suite covers key Bluetooth Classic and LE Audio features, ranging from
device connection and media streaming to call control and BLE coexistence. The
following sections provide a detailed breakdown of the features under test for
each category.

### Bluetooth Classic

* **Connection**:
    * Discover and pair with Classic Bluetooth devices.
* **A2DP (Advanced Audio Distribution Profile)**:
    * Stream media to Classic Bluetooth audio devices.
    * Auto-Reconnect: Verify headset automatically reconnects and resumes playback when powered on.
    * Suspend: Verify link enters suspend state when media playback is stopped.
* **AVRCP (Audio/Video Remote Control Profile)**:
    * Control media playback (Play/Pause/Next/Previous) from both the phone and headset.
    * Control and synchronize volume from both phone and headset.
* **HFP (Hands-Free Profile)**:
    * Make, answer, reject, and end calls from both phone and headset.
    * Transfer call audio between the phone and headset during an active call.
    * Reliability: Verify connection stability and audio routing when headset or phone Bluetooth is turned off/on during an active call.
* **OPP (Object Push Profile)**:
    * Send and receive files via Bluetooth.
* **BLE (Bluetooth Low Energy)**:
    * GATT: Connect to BLE peripherals, discover GATT services.
    * Coexistence: Verify BLE GATT connection is maintained during A2DP streaming.

### Bluetooth LE Audio (LEA)

* **Connection**:
    * Discover, pair, and unpair LE Audio devices.
* **Media Streaming**:
    * Stream media via LE Audio Unicast.
    * Automatically switch to low-latency gaming mode for games, and verify microphone back-channel (VBC) works simultaneously with game audio.
* **Media Control**:
    * Control media playback (Play/Pause/Next/Previous) from the headset.
    * Control and synchronize absolute volume between the phone and headset.
* **Call Control**:
    * Call Interruption: Ensure media streaming pauses when a call is active and resumes after the call ends.
    * Audio Routing: If the headset powers off during a call, ensure call audio correctly routes back to the phone.

## Hardware Requirements

To run the tests, you will need the following hardware:

* **Mobly Host**: A Linux desktop computer.
* **Android Devices**: **Two** Android devices.
   - One device serves as the **Device Under Test (DUT)**, whose Bluetooth
     functionality is being evaluated. The second device serves as a **Reference
     Phone (REF)**, which is used to interact with the DUT in certain test
     cases. For example, the REF phone is needed to place calls to or receive
     calls from the DUT when testing Hands-Free Profile (HFP) or LE Audio (LEA)
     call capabilities, and to send or receive files when testing Object Push
     Profile (OPP).
   - **[Important Note] Build Type**: A `userdebug` build on the DUT is
     recommended for full automation. `userdebug` builds allow tests to
     automatically switch between LE Audio and Classic profiles during a test
     run. If you require this level of automation, a `userdebug` build is
     necessary. If you are using a `user` build, you need to manually set the
     profile before testing: enable LE Audio in Developer Options to run
     LEA tests, or disable it to run Classic tests. Note: This manual
     toggle option may not be available on all devices (e.g., Samsung).
* **[Strong Recommended] SIM Card**: **Two** SIM cards are required for testing
  HFP and LEA call-related features. If either or both phones lack an active SIM
  card, call-related tests will be skipped.
* **BES Boards**: Two BES boards
  BES board is a reference device from the [mobly-bluetooth-ref-validation](https://github.com/google/mobly-bluetooth-ref-validation) project.

### Test Environment

It is strongly recommended to use an RF shielding box or room for setting up
the test environment to minimize wireless signal interference and ensure test
stability and result reliability.

For test suites involving phone calls (e.g. bluetooth_classic_suite_with_call),
both Android devices must be equipped with active SIM cards and ensure both
phones have stable cellular signal.

### Host Prerequisites

Ensure the host machine has the following software installed:

* `arecord`
    * You can use install `arecord` on the desktop if you haven't. You can use
    `sudo apt-get install alsa-utils` to install it on Debian/Ubuntu.
* [Android Debug Bridge (adb)](https://developer.android.com/tools/adb) (1.0.40+ recommended)
* python3.11+

### Phone Setup Instructions

**Enable Developer Options on Android Devices**:

  - On each Android device, enable [developer options](https://developer.android.com/studio/debug/dev-options) and turn on **USB debugging**.
  - Connect the devices to the host machine via USB and authorize the connection.
  - Verify the devices are connected by running `adb devices`.

### Prepare BES Device

If you use the BES Bluetooth dev board as the reference device, please follow
these steps:

1.  Prepare *one* pair for TWS tests.
2.  Connect the `USB-UART` port of the board with your PC/workstation with USB
    cable.
3.  Press `PWR` button on the board if needed.
4.  Take down the serial port of the BES board. We'll need it for the configuration file.

#### How to Get Serial Port of the BES Board

For Linux, the serial port is something like `/dev/ttyUSB0`.
Command to list the available ports:

```bash
ls /dev/ttyUSB*
```

## Configure Testbed

1.  Modify the Mobly device config YAML file `BluetoothLocalTestbed.yaml` to match your setup.
2.  Update the `serial` under `AndroidDevice` with your device's serial number obtained from `adb devices`.
3.  Update `serial_port` and `bluetooth_address` for the `BluetoothReferenceDevice` section based on your BES device setup.

    When setting up, you need to identify the `serial_port` and `pcm_name` for
    each board. To do this correctly, connect only one BES board to the host
    machine at a time:
    *   To find its serial port, run `ls /dev/ttyUSB*`.
    *   To find its `pcm_name` for `audio_configs`, run `arecord -l`. This
        lists audio capture devices. Find the line for the BES device and note
        card number `X` and device `Y` from `card X: ..., device Y: ...`.
        The `pcm_name` is `plughw:X,Y`.

    Note down the values for the first board, then disconnect it and repeat
    the process for the second board. This ensures you can distinguish between
    boards and correctly fill in the `serial_port` and `pcm_name` for
    `left_config` and `right_config`.

  Example `BluetoothLocalTestbed.yaml`:

  ```yaml
  TestBeds:
  - Name: BluetoothLocalTestbed
    Controllers:
      AndroidDevice:
        - serial: 'YOUR_DUT_SERIAL'
      AndroidDevice:
        - serial: 'YOUR_REF_SERIAL'
      BluetoothReferenceDevice:
        - controller_name: 'TwsDevice'
          controller_type: 'BesDevice'
          primary_ear: 'RIGHT'
          left_config:
            remote_mode: false
            serial_port: 'YOUR_LEFT_BES_PORT' # e.g. /dev/ttyUSB0
            bluetooth_address: '11:11:22:33:33:50'
            audio_configs:
              pcm_name: 'hw:0,0' # See above for how to query pcm name
              sample_rate: 8000
              sample_format: 'S16_LE'
              channels: 2
          right_config:
            remote_mode: false
            serial_port: 'YOUR_RIGHT_BES_PORT' # e.g. /dev/ttyUSB1
            bluetooth_address: '11:11:22:33:33:51'
            audio_configs:
              pcm_name: 'hw:1,0' # See above for how to query pcm name
              sample_rate: 8000
              sample_format: 'S16_LE'
              channels: 2
  MoblyParams:
    LogPath: '/tmp/mobly_logs'
  ```

## Run Tests

This section explains how to set up the environment and run Bluetooth end-to-end
tests.

### Install Dependencies

Run the following commands on your desktop computer to prepare Python
environment:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip3 install -r requirements.txt
  ```

### Run Whole Test Suites
<style>
  table {
    width: 100%;
    max-width: 1200px;
    border-collapse: collapse;
  }
  th, td {
    border: 1px solid #ddd;
    padding: 12px;
    text-align: left;
  }
</style>
| Profile \ Features | Standard (No SIM) | With Calls (SIM Required) |
| :--- | :--- | :--- |
| **LE Audio** | LE Audio test suite | LE Audio with call test suite |
| **Classic** | Classic test suite | Classic with call test suite |

Run the Bluetooth **LE Audio test suite**:

```bash
python3 -m android_beat.test_suites.bluetooth_lea_suite -c android_beat/BluetoothLocalTestbed.yaml
```

Run the Bluetooth **LE Audio with calls test suite** if SIM cards are installed.
This covers additional features on top of the suite above.

```bash
python3 -m android_beat.test_suites.bluetooth_lea_suite_with_call -c android_beat/BluetoothLocalTestbed.yaml
```

Run the Bluetooth **Classic test suite**:

```bash
python3 -m android_beat.test_suites.bluetooth_classic_suite -c android_beat/BluetoothLocalTestbed.yaml
```

Run the Bluetooth **Classic with calls test suite** if SIM cards are installed.
This covers additional features on top of the suite above.

```bash
python3 -m android_beat.test_suites.bluetooth_classic_with_call_suite -c android_beat/BluetoothLocalTestbed.yaml
```

#### Run Specific Test Cases / Classes

Running the whole test suite could be time consuming. For debugging purposes,
you can run a single test case / class or a subset of the test suite by adding
`--tests` flag.

+   To run a specific test case, add `--tests TestClass.test_method` to the
    execution command. For example:

  ```bash
  python3 -m android_beat.tests.bluetooth_lea_connection_test -c android_beat/BluetoothLocalTestbed.yaml --tests BluetoothLeaConnectionTest.test_pairing
  ```

+   To run all tests in a specific test class, add `--tests TestClass` to the
    execution command. For example:

  ```bash
  python3 -m android_beat.tests.bluetooth_lea_connection_test -c android_beat/BluetoothLocalTestbed.yaml --tests BluetoothLeaConnectionTest
  ```

## View Results and Debug

You could upload the results to Google’s test result store, this bring 2 benefits:

 - Easily analyze the test results with the BTX viewer.
 - Easily share test results via a single URL link.

### Manually upload results

1. If it's your first time using the result uploader,

  * Follow the [Mobly Result Uploader README](https://github.com/android/mobly-android-partner-tools#first-time-setup) for first-time setup.

  * Run `python3 -m pip install mobly-android-partner-tools` to install the
  result uploader.

2. At the end of a completed test run, you'll see the final lines on the console
   output as follows. Record the folder path in the line starting with
   "Artifacts are saved in".

  ```
  Total time elapsed 961.7551812920001s
  Artifacts are saved in "/tmp/logs/mobly/BluetoothLocalTestbed/10-23-2023_10-30-50-685"
  Test summary saved in "/tmp/logs/mobly/BluetoothLocalTestbed/10-23-2023_10-30-50-685/test_summary.yaml"
  Test results: Error 0, Executed 12, Failed 0, Passed 12, Requested 0, Skipped 0
  ```

3. Run the uploader command, setting the `artifacts_folder` as the path recorded
   in the previous step.

    ```bash
    results_uploader <artifacts_folder>
    ```

4. If successful, at the end of the upload process you will get a link beginning
   with http://btx.cloud.google.com.
   You may view your results and share this link to others who wish to view your
   test results.
   * If you do not see a link, consult the [Troubleshooting](https://github.com/android/mobly-android-partner-tools#troubleshooting)
     section.

### View your results in BTX

When you open a BTX link, you should see the following dashboard.

![target](btx_target.png)

1. Use this checkbox to show/hide test cases based on status (e.g. Failed,
   Passed, Skipped).
2. A list of test cases along with their results:
   Green (passed), Red (failed), Grey (skipped). Click on the test case name to
   display the details for that test.
3. Click to open the Mobly Inspector debugging UI. See more details below.
4. A list of test artifacts (log files, bugreports, videos) recorded from the
   test case. Click to view/download the file contents.
5. The test failure stacktrace, if the test failed.
6. The test properties.

See [Troubleshooting](https://github.com/android/mobly-android-partner-tools?tab=readme-ov-file#view-your-results-in-btx) if you do not see the above elements or need more details.
