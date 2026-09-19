# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import datetime as dt
import os
import pathlib
import textwrap
from typing import TYPE_CHECKING
from unittest import mock

from pyfakefs.fake_filesystem import OSType
from typing_extensions import override

from crossbench.helper.version import VersionParseError
from crossbench.plt.win import WinVersion
from tests import test_helper
from tests.crossbench.mock_helper import WinMockPlatform
from tests.crossbench.plt.helper import BaseLocalMockPlatformTestMixin, \
    BaseMockPlatformTestCase

if TYPE_CHECKING:
  from crossbench import path as pth


class WinMockPlatformTestCase(BaseLocalMockPlatformTestMixin,
                              BaseMockPlatformTestCase):
  __test__ = True

  @override
  def setUp(self) -> None:
    super().setUp()
    self.fs.os = OSType.WINDOWS

  @override
  def setup_host_platform(self):
    return WinMockPlatform()

  def path(self, path: pth.AnyPathLike) -> pathlib.PureWindowsPath:
    return pathlib.PureWindowsPath(path)

  def test_is_win(self):
    self.assertTrue(self.platform.is_win)

  def test_version(self):
    self.platform.mock_version_str = None
    ver_output = "\nMicrosoft Windows [Version 10.0.22631.3593]\n"
    self.expect_sh("cmd", "/c", "ver", result=ver_output)
    self.assertEqual(self.platform.version_str, ver_output.strip())
    version = self.platform.version
    self.assertEqual(version.parts, (10, 0, 22631, 3593))
    self.assertEqual(version.version_str, ver_output.strip())

  def test_killall(self):
    self.expect_sh("taskkill", "/F", "/IM", "chrome.exe", result="")
    self.platform.killall("chrome")

  def test_path_conversion(self):
    self.assertIsInstance(
        self.platform.path("foo/bar"), pathlib.PureWindowsPath)
    self.assertIsInstance(
        self.platform.path(pathlib.PurePath("foo/bar")),
        pathlib.PureWindowsPath)
    self.assertIsInstance(
        self.platform.path(pathlib.PureWindowsPath("foo/bar")),
        pathlib.PureWindowsPath)
    self.assertIsInstance(
        self.platform.path(pathlib.PurePosixPath("foo/bar")),
        pathlib.PureWindowsPath)

  def test_which(self):
    bin_path = self.path("foo/bar/default/crossbench_mock_binary.exe")
    self.assertIsNone(self.platform.which(bin_path))
    with mock.patch("shutil.which", return_value=bin_path) as cm:
      self.assertEqual(self.platform.which(bin_path), bin_path)
    cm.assert_called_once_with(os.fspath(bin_path))

  def test_which_invalid(self):
    with self.assertRaises(ValueError) as cm:
      self.platform.which("")
    self.assertIn("empty", str(cm.exception))

  def test_search_binary_invalid(self):
    with self.assertRaises(ValueError) as cm:
      self.platform.search_binary("")
    self.assertIn("empty", str(cm.exception))
    with self.assertRaises(ValueError) as cm:
      self.platform.search_binary("foo/bar")
    self.assertIn(".exe", str(cm.exception))

  def test_search_binary_broken_which(self):
    bin_path = self.path("foo/bar/default/crossbench_mock_binary.exe")
    self.assertIsNone(self.platform.search_app(bin_path))
    with mock.patch("shutil.which", return_value=bin_path) as cm:
      with self.assertRaises(AssertionError) as search_cm:
        self.assertEqual(self.platform.search_app(bin_path), bin_path)
      self.assertIn("exist", str(search_cm.exception))
    cm.assert_called_once_with(os.fspath(bin_path))

  def test_search_binary(self):
    bin_path = self.path("foo/bar/default/crossbench_mock_binary.exe")
    self.assertFalse(self.platform.exists(bin_path))
    self.assertIsNone(self.platform.search_app(bin_path))
    self.fs.create_file(self.platform.local_path(bin_path), st_size=100)
    self.assertTrue(self.platform.exists(bin_path))
    with mock.patch("shutil.which", return_value=bin_path) as cm:
      self.assertEqual(self.platform.search_app(bin_path), bin_path)
    cm.assert_called_once_with(os.fspath(bin_path))

  def test_machine_arch_amd64(self):
    cpu_caption = textwrap.dedent("""
        Caption
        -------
        Intel64 Family 6 Model 154 Stepping 3


    """)
    self.expect_sh(
        "powershell",
        "-c",
        "Get-CIMInstance -query 'select * from Win32_Processor' | ft Caption",
        result=cpu_caption)
    self.platform.use_mock_machine = False
    with mock.patch("platform.machine", return_value="AMD64"):
      self.assertTrue(self.platform.is_x64)
      self.assertFalse(self.platform.is_arm64)

  def test_machine_arch_arm64(self):
    cpu_caption = textwrap.dedent("""
        Caption
        -------
        ARMv8 (64-bit) Family 8 Model 1 Revision 201


    """)
    self.expect_sh(
        "powershell",
        "-c",
        "Get-CIMInstance -query 'select * from Win32_Processor' | ft Caption",
        result=cpu_caption)
    self.platform.use_mock_machine = False
    self.assertTrue(self.platform.is_arm64)
    self.assertFalse(self.platform.is_x64)

  def test_uptime(self):
    time_span = textwrap.dedent("""
        Days              : 14
        Hours             : 2
        Minutes           : 19
        Seconds           : 54
        Milliseconds      : 978
        Ticks             : 12179949789862
        TotalDays         : 14.0971641086366
        TotalHours        : 338.331938607278
        TotalMinutes      : 20299.9163164367
        TotalSeconds      : 1217994.9789862
        TotalMilliseconds : 1217994978.9862
    """)
    self.expect_sh(
        "powershell",
        "-c", ("(New-TimeSpan -Start "
               "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime)"),
        result=time_span)
    uptime = self.platform.uptime()
    self.assertEqual(
        uptime,
        dt.timedelta(
            days=14, hours=2, minutes=19, seconds=54, milliseconds=978))

  def test_platform_version_cls(self):
    ver_output = "\nMicrosoft Windows [Version 10.0.22631.3593]\n"
    version = WinVersion.parse(ver_output)
    self.assertEqual(version.parts, (10, 0, 22631, 3593))
    self.assertEqual(version.version_str, ver_output)
    with self.assertRaises(VersionParseError):
      WinVersion.parse("foo")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
