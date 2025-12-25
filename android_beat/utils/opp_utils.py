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

"""Utils for Bluetooth OPP tests."""

import datetime
import uuid

from mobly import asserts
from mobly.controllers import android_device

_FILE_TRANSFER_DEFAULT_TIMEOUT = datetime.timedelta(seconds=180)
_MD5_HEX_LENGTH = 32


def bt_send_file(
    ad_sender: android_device.AndroidDevice,
    ad_receiver: android_device.AndroidDevice,
    ad_receiver_address: str,
    send_file_path: str,
    received_file_path: str,
    is_secure: bool,
):
  """Sends file from the sender device to the receiver device."""
  uuid_value = str(uuid.uuid4())
  try:
    receiver_handler = ad_receiver.bt_snippet.btReceiveFile(
        uuid_value, received_file_path, is_secure
    )
    ad_sender.bt_snippet.btConnectSocket(
        ad_receiver_address, uuid_value, is_secure
    )
    sender_handler = ad_sender.bt_snippet.btSendFile(send_file_path)
    sender_event = sender_handler.waitAndGet(
        event_name="onFileSent",
        timeout=_FILE_TRANSFER_DEFAULT_TIMEOUT.total_seconds(),
    )
    sender_file_size = sender_event.data["fileSize"]
    receiver_event = receiver_handler.waitAndGet(
        event_name="onFileReceived",
        timeout=_FILE_TRANSFER_DEFAULT_TIMEOUT.total_seconds(),
    )
    receiver_file_size = receiver_event.data["fileSize"]
    # Check file size
    asserts.assert_true(
        sender_file_size != 0 and sender_file_size == receiver_file_size,
        "The file size at the receiver differs from the file size at the"
        " sender.",
    )
    # Check md5
    sender_file_md5_output = ad_sender.adb.shell(f"md5sum {send_file_path}")
    receiver_file_md5_output = ad_receiver.adb.shell(
        f"md5sum {received_file_path}"
    )
    # Extract the md5 value
    asserts.assert_equal(
        sender_file_md5_output[:_MD5_HEX_LENGTH],
        receiver_file_md5_output[:_MD5_HEX_LENGTH],
        "The MD5 checksum at the receiver differs from the MD5 checksum at"
        " the sender.",
    )
  finally:
    ad_sender.bt_snippet.btCloseSocket()
    ad_receiver.bt_snippet.btCloseServerSocket()
