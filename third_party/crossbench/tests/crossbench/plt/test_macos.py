# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import plistlib
import textwrap

from pyfakefs.fake_filesystem import OSType
from typing_extensions import override

from crossbench import path as pth
from crossbench.helper.version import VersionParseError
from crossbench.plt.macos import MacOsVersion
from tests import test_helper
from tests.crossbench.mock_helper import MacOsMockPlatform
from tests.crossbench.plt.helper import BaseLocalMockPlatformTestMixin, \
    BasePosixMockPlatformTestCase


class MacOsMockPlatformTestCase(BaseLocalMockPlatformTestMixin,
                                BasePosixMockPlatformTestCase):
  __test__ = True

  @override
  def setUp(self) -> None:
    super().setUp()
    self.fs.os = OSType.MACOS

  @override
  def setup_host_platform(self) -> None:
    return MacOsMockPlatform()

  def test_name(self):
    self.assertEqual(self.platform.name, "mock.macos")

  def test_is_macos(self):
    self.assertTrue(self.platform.is_macos)

  def test_is_apple(self):
    self.assertTrue(self.platform.is_apple)

  def test_app_version_non_existing(self):
    app_path = pth.AnyPosixPath("/Applications/Google Chrome.app")
    self.assertFalse(self.platform.exists(app_path))
    with self.assertRaisesRegex(ValueError, "not exist"):
      self.platform.app_version(app_path)
    app_path = pth.AnyPath("/Applications/Google Chrome.app")
    self.assertFalse(self.platform.exists(app_path))
    with self.assertRaisesRegex(ValueError, "not exist"):
      self.platform.app_version(app_path)

  def test_app_version_binary_any_path(self):
    app_path = pth.AnyPosixPath("/opt/homebrew/bin/brew")
    self.fs.create_file(app_path, st_size=100)
    self.expect_sh(app_path, "--version", result="111.22.3")
    self.assertEqual(self.platform.app_version(app_path), "111.22.3")

  def test_app_version_binary_local_path(self):
    app_path = pth.LocalPath("/opt/homebrew/bin/brew")
    self.fs.create_file(app_path, st_size=100)
    self.expect_sh(app_path, "--version", result="111.22.3")
    self.assertEqual(self.platform.app_version(app_path), "111.22.3")

  def test_app_version_binary_posix_path(self):
    app_path = pth.AnyPath("/opt/homebrew/bin/brew")
    self.fs.create_file(app_path, st_size=100)
    self.expect_sh(app_path, "--version", result="111.22.3")
    self.assertEqual(self.platform.app_version(app_path), "111.22.3")

  def test_app_version(self):
    app_path = pth.LocalPath("/Applications/Google Chrome.app")
    with self.assertRaisesRegex(ValueError, str(app_path)):
      self.platform.app_version(app_path)
    app_path.mkdir(parents=True)
    with self.assertRaisesRegex(ValueError, str(app_path)):
      self.platform.app_version(app_path)

    binary_path = app_path / "Contents/MacOS/Google Chrome"
    binary_path.parent.mkdir(parents=True)
    with self.assertRaisesRegex(ValueError, "Info.plist"):
      self.platform.app_version(app_path)

    info_plist = app_path / "Contents/Info.plist"
    self.fs.create_file(info_plist)
    with self.assertRaisesRegex(ValueError, "Invalid file"):
      self.platform.app_version(app_path)

    with info_plist.open("wb") as f:
      plistlib.dump({}, f)
    with self.assertRaisesRegex(ValueError, str(app_path)):
      self.platform.app_version(app_path)

    with info_plist.open("wb") as f:
      plistlib.dump(
          {
              "CFBundleShortVersionString": "129.9.6668.103",
              "CFBundleDisplayName": "Google Chrome",
          }, f)
    self.assertEqual(
        self.platform.app_version(app_path), "Google Chrome 129.9.6668.103")

    with info_plist.open("wb") as f:
      plistlib.dump(
          {
              "CFBundleShortVersionString": "129.9.6668.103",
              # CFBundleDisplayName is missing but CFBundleName is there.
              "CFBundleName": "Google Chrome",
          },
          f)
    self.assertEqual(
        self.platform.app_version(app_path), "Google Chrome 129.9.6668.103")

  def test_app_version_binary_inside_app(self):
    binary_path = pth.LocalPath("/Applications/Safari Technology Preview.app/"
                                "Contents/MacOS/safaridriver")
    self.fs.create_file(binary_path, st_size=100)
    self.expect_sh(binary_path, "--version", result="(Release 203, 19620.1.6)")
    self.assertEqual(
        self.platform.app_version(binary_path), "(Release 203, 19620.1.6)")

  def test_search_binary(self):
    app_path = pth.LocalPath("/Applications/Google Chrome.app")
    self.assertIsNone(self.platform.search_binary(app_path))
    binary_path = app_path / "Contents/MacOS/Google Chrome"
    self.fs.create_file(binary_path, st_size=100)
    self.assertEqual(self.platform.search_binary(app_path), binary_path)

  def test_search_binary_custom_bundle_executable(self):
    app_path = pth.LocalPath("/Applications/Google Chrome.app")
    self.assertIsNone(self.platform.search_binary(app_path))
    binary_path = app_path / "Contents/MacOS/Chrome"
    binary_path.parent.mkdir(parents=True)
    with self.assertRaisesRegex(ValueError, "Info.plist"):
      self.platform.search_binary(app_path)

    info_plist = app_path / "Contents/Info.plist"
    self.fs.create_file(info_plist)
    with self.assertRaisesRegex(ValueError, "Invalid file"):
      self.platform.search_binary(app_path)

    with info_plist.open("wb") as f:
      plistlib.dump({}, f)
    with self.assertRaisesRegex(ValueError, str(app_path)):
      self.platform.search_binary(app_path)

    with info_plist.open("wb") as f:
      plistlib.dump({"CFBundleExecutable": str(binary_path)}, f)
    with self.assertRaisesRegex(ValueError, str(app_path)):
      self.platform.search_binary(app_path)

    self.fs.create_file(binary_path, st_size=100)
    # Single binary is always resolved directly
    self.assertEqual(self.platform.search_binary(app_path), binary_path)

    # Adding another binary will still resolve to CFBundleExecutable
    self.fs.create_file(binary_path.parent / "Other", st_size=100)
    self.assertEqual(self.platform.search_binary(app_path), binary_path)

  def test_search_binary_single(self):
    app_path = pth.LocalPath("/Applications/Custom.app")
    binary_path = app_path / "Contents/MacOS/CustomA"
    self.fs.create_file(binary_path, st_size=100)
    self.assertEqual(self.platform.search_binary(app_path), binary_path)

  def test_search_binary_multiple_binaries(self):
    app_path = pth.LocalPath("/Applications/Custom.app")
    self.fs.create_file(app_path / "Contents/MacOS/CustomA", st_size=100)
    self.fs.create_file(app_path / "Contents/MacOS/CustomB", st_size=100)
    info_plist = app_path / "Contents/Info.plist"
    with info_plist.open("wb") as f:
      plistlib.dump({}, f)
    with self.assertRaisesRegex(ValueError, "binaries"):
      self.platform.search_binary(app_path)

  def test_search_app(self):
    app_path = pth.LocalPath("/Applications/Custom Chrome.app")
    binary_path = app_path / "Contents" / "MacOS" / "Custom Chrome"
    self.fs.create_file(binary_path, st_size=100)

    self.assertEqual(self.platform.search_app(app_path), app_path)
    self.assertEqual(self.platform.search_app(binary_path), app_path)
    self.assertIsNone(
        self.platform.search_app(
            pth.LocalPath("/Applications/NonExisting.app")))

  def test_search_app_deep_binary(self):
    # App bundle with a deeply nested binary
    app_path = pth.LocalPath("/Applications/Deep.app")
    # 4 levels deep: Deep.app/Contents/MacOS/inner/Deep
    binary_path = app_path / "Contents" / "MacOS" / "inner" / "Deep"
    self.fs.create_file(binary_path, st_size=100)

    info_plist = app_path / "Contents" / "Info.plist"
    with info_plist.open("wb") as f:
      plistlib.dump({"CFBundleExecutable": "inner/Deep"}, f)

    # Calling search_app with the binary path should return the .app bundle
    resolved_app_path = self.platform.search_app(binary_path)
    self.assertEqual(resolved_app_path, app_path)
    resolved_app_path = self.platform.search_app(app_path)
    self.assertEqual(resolved_app_path, app_path)

  def test_version(self):
    self.platform.mock_version_str = "15.6.1"
    version = self.platform.version
    self.assertEqual(version.parts, (15, 6, 1))
    self.assertEqual(version.version_str, "15.6.1")

  def test_version_sh_call(self):
    self.platform.mock_version_str = None
    self.expect_sh("sw_vers", "-productVersion", result="15.6.7")
    version = self.platform.version
    self.assertEqual(version.parts, (15, 6, 7))
    self.assertEqual(version.version_str, "15.6.7")

  def test_display_details(self):
    system_profiler_output = textwrap.dedent("""{
        "SPDisplaysDataType" : [
          {
            "_name" : "Apple M1 Max",
            "spdisplays_mtlgpufamilysupport" : "spdisplays_metal3",
            "spdisplays_ndrvs" : [
              {
                "_name" : "Color LCD",
                "_spdisplays_display-product-id" : "b123",
                "_spdisplays_display-serial-number" : "f12345",
                "_spdisplays_display-vendor-id" : "12",
                "_spdisplays_display-week" : "0",
                "_spdisplays_display-year" : "0",
                "_spdisplays_displayID" : "1",
                "_spdisplays_pixels" : "3456 x 2234",
                "_spdisplays_resolution" : "1728 x 1117 @ 60.00Hz",
                "spdisplays_ambient_brightness" : "spdisplays_no",
                "spdisplays_connection_type" : "spdisplays_internal",
                "spdisplays_display_type" : "spdisplays_built-in-liquid-retina-xdr",
                "spdisplays_main" : "spdisplays_yes",
                "spdisplays_mirror" : "spdisplays_off",
                "spdisplays_online" : "spdisplays_yes",
                "spdisplays_pixelresolution" : "spdisplays_3456x2234Retina"
              },
              {
                "_name" : "External LCD",
                "_spdisplays_display-product-id" : "c123",
                "_spdisplays_display-serial-number" : "e123456",
                "_spdisplays_display-vendor-id" : "13",
                "_spdisplays_display-week" : "1",
                "_spdisplays_display-year" : "2020",
                "_spdisplays_displayID" : "2",
                "_spdisplays_pixels" : "6720 x 3780",
                "_spdisplays_resolution" : "3360 x 1890 @ 30.00Hz",
                "spdisplays_mirror" : "spdisplays_off",
                "spdisplays_online" : "spdisplays_yes",
                "spdisplays_pixelresolution" : "6720 x 3780",
                "spdisplays_resolution" : "3360 x 1890 @ 30.00Hz",
                "spdisplays_rotation" : "spdisplays_supported"
              }
            ],
            "spdisplays_vendor" : "sppci_vendor_Apple",
            "sppci_bus" : "spdisplays_builtin",
            "sppci_cores" : "32",
            "sppci_device_type" : "spdisplays_gpu",
            "sppci_model" : "Apple M1"
          }
        ]
      }""")
    self.expect_sh(
        "system_profiler",
        "-json",
        "SPDisplaysDataType",
        result=system_profiler_output)
    displays = self.platform.display_details()
    self.assertEqual(len(displays), 2)
    self.assertDictEqual(displays[0], {
        "resolution": (1728, 1117),
        "refresh_rate": 60
    })
    self.assertDictEqual(displays[1], {
        "resolution": (3360, 1890),
        "refresh_rate": 30
    })
    self.assertTupleEqual(
        self.platform.display_resolution(),
        (1728, 1117),
    )

  def test_platform_version_cls(self):
    version = MacOsVersion.parse("12.3.4")
    self.assertEqual(version.parts, (12, 3, 4))
    self.assertEqual(version.version_str, "12.3.4")
    with self.assertRaises(VersionParseError):
      MacOsVersion.parse("foo")

  def test_killall(self):
    self.expect_sh("killall", "-9", "Google Chrome", result="")
    self.platform.killall("Google Chrome")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
