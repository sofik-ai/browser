# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from unittest import mock

from typing_extensions import override

from crossbench import path as pth
from crossbench.plt.ios import IOSDeviceInfo
from tests.crossbench.base import BaseCrossbenchTestCase
from tests.crossbench.mock_helper import ShResult

IOS_DEVICES_OUTPUT = {
    "00001111-11AA22BB33DD":
        IOSDeviceInfo("00001111-11AA22BB33DD", "An iPhone", "17.1.2"),
    "00002222-11AA22BB33DD":
        IOSDeviceInfo("00002222-11AA22BB33DDD", "An iPhone pro", "17.1.1"),
}

IOS_DEVICES_SINGLE_OUTPUT = {
    "00001111-11AA22BB33DD":
        IOSDeviceInfo("00001111-11AA22BB33DD", "An iPhone", "17.1.2"),
}

ADB_DEVICES_SINGLE_OUTPUT_RESULT = (
    "List of devices attached\n"
    "emulator-5556 device product:sdk_google_phone_x86_64 "
    "model:Android_SDK_built_for_x86_64 device:generic_x86_64\n")

ADB_DEVICES_SINGLE_OUTPUT = ShResult(ADB_DEVICES_SINGLE_OUTPUT_RESULT)

ADB_DEVICES_OUTPUT = ShResult(
    f"{ADB_DEVICES_SINGLE_OUTPUT_RESULT}"
    "emulator-5554 device product:sdk_google_phone_x86 "
    "model:Android_SDK_built_for_x86 device:generic_x86\n"
    "0a388e93      device usb:1-1 product:razor model:Nexus_7 device:flo\n")


class BaseConfigTestCase(BaseCrossbenchTestCase):

  @override
  def setUp(self) -> None:
    super().setUp()
    adb_patcher = mock.patch(
        "crossbench.plt.android_adb._find_adb_bin",
        return_value=pth.LocalPath("adb"))
    adb_patcher.start()
    self.addCleanup(adb_patcher.stop)
