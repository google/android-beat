# Android BEAT (Bluetooth End-to-end Automation Test)

## What is Android BEAT?

Android BEAT (Bluetooth End-to-end Automation Test) is a test suite based on the [Mobly framework](https://github.com/google/mobly). It is designed to validate Bluetooth functionality by executing critical user journeys (CUJs).

The primary goal of this project is to provide a comprehensive, automated testing solution that ensures Bluetooth features are robust and reliable across a wide range of Android devices.

This is not an officially supported Google product. This project is not eligible for the [Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).

## Hardware Requirements

To run the tests, you will need the following hardware:

* **Android Devices**: Two Android devices with SIM cards - One to serve as the device under test (DUT) and one as the reference (REF).
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

![Work in Progress](https://img.shields.io/badge/status-WIP-orange.svg)