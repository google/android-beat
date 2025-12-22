# Android BEAT (Bluetooth End-to-end Automation Test)

## What is Android BEAT?

Android BEAT (Bluetooth End-to-end Automation Test) is a test suite based on the
[Mobly framework](https://github.com/google/mobly). It is designed to validate
Bluetooth functionality by executing critical user journeys (CUJs).

The primary goal of this project is to provide a comprehensive, automated
testing solution that ensures Bluetooth features are robust and reliable across
a wide range of Android devices.

This is not an officially supported Google product. This project is not eligible
for the [Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).

## Hardware Requirements

To run the tests, you will need the following hardware:

* **Android Devices**: Two Android devices with SIM cards - One to serve as the
device under test (DUT) and one as the reference (REF).
* **BES Boards**: A reference hardware board from the [mobly-bluetooth-ref-validation](https://github.com/google/mobly-bluetooth-ref-validation) project.

## System Prerequisites

Ensure the host machine has the following software installed:

* [Android Debug Bridge (adb)](https://developer.android.com/tools/adb) (1.0.40+ recommended)
* python3.11+

## Setup Instructions

1.  **Enable Developer Options on Android Devices**:
    * On each Android device, enable [developer options](https://developer.android.com/studio/debug/dev-options) and turn on **USB debugging**.
    * Connect the devices to the host machine via USB and authorize the connection.
    * Verify the devices are connected by running `adb devices`.

### Prepare BES Device

If you use the BES Bluetooth dev board as the reference device, please follow
these steps:

1.  Prepare *one* BES board (or a pair for TWS tests).
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

For MacOS, first install the
[PL2303 serial driver](https://apps.apple.com/cn/app/pl2303-serial/id1624835354?l=en-GB&mt=12)
from App Store if using PL2303. The serial port is something like
`/dev/tty.usbserial-XXXXXXXX` or `/dev/tty.PL2303G-USBtoUARTXXXX`. Command to
list the available ports:

```bash
ls /dev/tty.*
```

For Windows, the serial port is something like `COM3`. You can find it in the
Device Manager or list available ports with:

```bash
mode
```

## Configure Testbed

1.  Modify the Mobly device config YAML file `BluetoothLocalTestbed.yaml` to match your setup.
2.  Update the `serial` under `AndroidDevice` with your device's serial number obtained from `adb devices`.
3.  Update `serial_port` and `bluetooth_address` for the `BluetoothReferenceDevice` section based on your BES device setup.

    To query the pcm name for audio recording on Linux, run `arecord -l`.
        Example command output to device name conversion:
        Command output "card 0: PCH [HDA Intel PCH], device 0: ALC662 rev3 \
        Analog"
        The pcm name of the above capture device is `hw:0,0` or `plughw:0,0`.

    Note: Windows audio recording is WIP and will be skipped for now.

    Example `BluetoothLocalTestbed.yaml`:
    ```yaml
    TestBeds:
    - Name: BluetoothLocalTestbed
      Controllers:
        AndroidDevice:
          - serial: 'YOUR_DUT_SERIAL'
        BluetoothReferenceDevice:
          - controller_name: 'TwsDevice'
            controller_type: 'BesDevice'
            primary_ear: 'RIGHT'
            left_config:
              remote_mode: false
              serial_port: 'YOUR_LEFT_BES_PORT' # e.g. COM8 or /dev/ttyUSB0
              bluetooth_address: '11:11:22:33:33:50'
              audio_configs:
                pcm_name: 'hw:0,0' # See above for how to query pcm name
                sample_rate: 8000
                sample_format: 'S16_LE'
                channels: 2
            right_config:
              remote_mode: false
              serial_port: 'YOUR_RIGHT_BES_PORT' # e.g. COM3 or /dev/ttyUSB1
              bluetooth_address: '11:11:22:33:33:51'
              audio_configs:
                pcm_name: 'hw:1,0' # See above for how to query pcm name
                sample_rate: 8000
                sample_format: 'S16_LE'
                channels: 2
    MoblyParams:
      LogPath: '/tmp/mobly_logs' # Or 'C:/Users/testuser/AppData/Local/Temp' for Windows
    ```

## Run Tests

1.  Create a new python virtual environment to run the test or activte an
    existing virtual environment.

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2.  Install the python dependencies on the **host machine**(your PC/workstation).

    ```bash
    pip3 install -r requirements.txt
    ```

3.  Run a test file using your configuration:

    ```bash
    python3 android_beat/tests/bluetooth_lea_connection_test.py -c android_beat/BluetoothLocalTestbed.yaml
    ```

### Run Specific Test Cases / Classes

Running the whole test suite could be time consuming. For debugging purposes,
you can run a single test case / class or a subset of the test suite by adding
`--tests` flag.

+   To run a specific test case, add `--tests TestClass.test_method` to the
    execution command. For example:

    ```bash
    python3 android_beat/tests/bluetooth_lea_connection_test.py -c android_beat/BluetoothLocalTestbed.yaml --tests BluetoothLeaConnectionTest.test_pairing
    ```

+   To run all tests in a specific test class, add `--tests TestClass` to the
    execution command. For example:

    ```bash
    python3 android_beat/tests/bluetooth_lea_connection_test.py -c android_beat/BluetoothLocalTestbed.yaml --tests BluetoothLeaConnectionTest
    ```