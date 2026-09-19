# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import contextlib
import datetime as dt
import json

from pyfakefs.fake_filesystem import OSType
from typing_extensions import override

from crossbench import path as pth
from crossbench.plt.ios import IOSPlatform
from crossbench.plt.version import PlatformVersion
from tests import test_helper
from tests.crossbench.mock_helper import MacOsMockPlatform
from tests.crossbench.plt.helper import BaseMockPlatformTestCase

DEVICES_SINGLE = {
    "result": {
        "devices": [{
            "hardwareProperties": {
                "udid": "00001111-11AA22BB33DD"
            },
            "deviceProperties": {
                "name": "An iPhone",
                "osVersionNumber": "17.1.2"
            },
            "connectionProperties": {
                "tunnelState": "connected"
            }
        }, {
            "hardwareProperties": {
                "udid": "00002222-11AA22BB33DD"
            },
            "deviceProperties": {
                "name": "An iPhone Pro",
                "osVersionNumber": "17.1.1"
            },
            "connectionProperties": {
                "tunnelState": "unavailable"
            }
        }]
    }
}

DEVICES_MULTIPLE = {
    "result": {
        "devices": [{
            "hardwareProperties": {
                "udid": "00001111-11AA22BB33DD"
            },
            "deviceProperties": {
                "name": "An iPhone",
                "osVersionNumber": "17.1.2"
            },
            "connectionProperties": {
                "tunnelState": "connected"
            }
        }, {
            "hardwareProperties": {
                "udid": "00002222-11AA22BB33DD"
            },
            "deviceProperties": {
                "name": "An iPhone Pro",
                "osVersionNumber": "17.1.1"
            },
            "connectionProperties": {
                "tunnelState": "connected"
            }
        }, {
            "hardwareProperties": {
                "udid": "00003333-11AA22BB33DD"
            },
            "deviceProperties": {
                "name": "An iPhone Pro Max",
                "osVersionNumber": "17.1.0"
            },
            "connectionProperties": {
                "tunnelState": "unavailable"
            }
        }]
    }
}

DEVICES_NONE = {
    "result": {
        "devices": [{
            "hardwareProperties": {
                "udid": "00002222-11AA22BB33DD"
            },
            "deviceProperties": {
                "name": "An iPhone Pro",
                "osVersionNumber": "17.1.1"
            },
            "connectionProperties": {
                "tunnelState": "unavailable"
            }
        }]
    }
}


class IOsMockPlatformTestCase(BaseMockPlatformTestCase):
  __test__ = True

  SAFARI_PATH = "/Applications/Safari.app"

  @override
  def setUp(self) -> None:
    super().setUp()
    self.fs.os = OSType.MACOS

  @override
  def setup_host_platform(self) -> MacOsMockPlatform:
    platform = MacOsMockPlatform()

    @contextlib.contextmanager
    def mock_named_temporary_file(suffix=None, prefix=None, dir=None):
      yield pth.LocalPath("/devicectl_output.json")

    platform.NamedTemporaryFile = mock_named_temporary_file
    return platform

  @override
  def setup_platform(self) -> IOSPlatform:
    self.expect_startup_devices()
    return IOSPlatform(self.host_platform)

  def expect_startup_devices(self, devices=None):
    if devices is None:
      devices = DEVICES_SINGLE
    # Use the fs directly to avoid issues with /tmp symlinks on MacOS fakefs
    if self.fs.exists("/devicectl_output.json"):
      self.fs.remove_object("/devicectl_output.json")
    self.fs.create_file("/devicectl_output.json", contents=json.dumps(devices))
    self.host_platform.expect_sh(
        "xcrun",
        "devicectl",
        "list",
        "devices",
        "--json-output=/devicectl_output.json",
        result="")

  def test_name(self):
    self.assertEqual(self.platform.name, "ios")

  def test_is_ios(self):
    self.assertTrue(self.platform.is_ios)

  def test_is_apple(self):
    self.assertTrue(self.platform.is_apple)

  def test_create_device_udid(self):
    self.expect_startup_devices()
    platform_a = IOSPlatform(self.host_platform, "00001111-11AA22BB33DD")
    self.assertEqual(platform_a.udid, "00001111-11AA22BB33DD")
    self.expect_startup_devices()
    platform_b = IOSPlatform(self.host_platform)
    self.assertEqual(platform_b.udid, "00001111-11AA22BB33DD")

  def test_create_device_udid_multiple(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "00001111-11AA22BB33DD")
    self.assertEqual(platform_a.udid, "00001111-11AA22BB33DD")
    with self.assertRaises(ValueError):
      self.expect_startup_devices(DEVICES_MULTIPLE)
      IOSPlatform(self.host_platform)
    with self.assertRaises(ValueError):
      self.expect_startup_devices(DEVICES_MULTIPLE)
      IOSPlatform(self.host_platform, "invalid device id")

  def test_create_device_name(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    self.assertEqual(platform_a.udid, "00002222-11AA22BB33DD")

  def test_create_device_name_non_unique(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    with self.assertRaisesRegex(ValueError, "2 devices"):
      IOSPlatform(self.host_platform, "iPhone")

  def test_create_no_devices(self):
    self.expect_startup_devices(DEVICES_NONE)
    with self.assertRaisesRegex(ValueError, "No devices"):
      IOSPlatform(self.host_platform, "iPhone")

  def test_uptime(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    self.assertEqual(platform_a.uptime(), dt.timedelta())

  def test_search_binary_safari(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    self.assertEqual(
        platform_a.search_binary(self.SAFARI_PATH),
        pth.AnyPath(self.SAFARI_PATH))

  def test_search_binary_not_safari(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    with self.assertRaisesRegex(ValueError, "Safari is the only supported app"):
      platform_a.search_binary("/usr/bin/safaridriver")

  def test_is_file_safari(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    self.assertTrue(platform_a.is_file(self.SAFARI_PATH))

  def test_is_file_not_safari(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    with self.assertRaisesRegex(ValueError, "Safari is the only supported app"):
      platform_a.is_file("/usr/bin/safaridriver")

  def test_app_version_safari(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    self.assertEqual(platform_a.app_version(self.SAFARI_PATH), "17.1.1")

  def test_app_version_not_safari(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    with self.assertRaisesRegex(ValueError, "Safari is the only supported app"):
      platform_a.app_version("/usr/bin/safaridriver")

  def test_process_children(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    self.assertEqual(platform_a.process_children(123), [])

  def test_os_details(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    self.assertEqual(
        platform_a.os_details(), {
            "system": "ios",
            "platform": "ios 17.1.1",
            "version": "17.1.1",
            "release": "17.1.1"
        })

  def test_version(self):
    self.expect_startup_devices(DEVICES_MULTIPLE)
    platform_a = IOSPlatform(self.host_platform, "iPhone Pro")
    self.assertEqual(platform_a.version, PlatformVersion([17, 1, 1]))


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
