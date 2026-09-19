# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import abc
import argparse
import datetime as dt
import pathlib
from unittest import mock

from typing_extensions import override

import crossbench.path as pth
from crossbench import plt
from crossbench.plt.posix import PosixPlatform
from tests.crossbench.base import CrossbenchFakeFsTestCase
from tests.crossbench.mock_helper import MockPlatform


class BaseMockPlatformTestCase(CrossbenchFakeFsTestCase, metaclass=abc.ABCMeta):
  __test__ = False

  @override
  def setUp(self) -> None:
    super().setUp()
    self.host_platform: MockPlatform = self.setup_host_platform()
    self.platform: plt.Platform = self.setup_platform()

  def setup_host_platform(self) -> MockPlatform:
    return MockPlatform()

  def setup_platform(self) -> MockPlatform:
    return self.host_platform

  def mock_platform_str(self, platform, name) -> None:
    # Mock out str(platform) to avoid secondary errors when printing the
    # platform name in failing tests.
    patcher = mock.patch.object(type(platform), "__str__", return_value=name)
    self.addCleanup(patcher.stop)
    patcher.start()

  def tearDown(self):
    expected_sh_cmds = self.host_platform.expected_sh_cmds
    if expected_sh_cmds is not None:
      self.assertListEqual(expected_sh_cmds, [],
                           "Got additional unused shell cmds.")
    self.assertTrue(self.platform.ports.is_empty)
    super().tearDown()

  def expect_sh(self, *args, result="", returncode: int = 0):
    self.platform.expect_sh(*args, result=result, returncode=returncode)

  def test_is_android(self):
    self.assertFalse(self.platform.is_android)

  def test_is_macos(self):
    self.assertFalse(self.platform.is_macos)

  def test_is_ios(self):
    self.assertFalse(self.platform.is_ios)

  def test_is_linux(self):
    self.assertFalse(self.platform.is_linux)

  def test_is_win(self):
    self.assertFalse(self.platform.is_win)

  def test_is_posix(self):
    self.assertFalse(self.platform.is_posix)

  def test_is_remote_ssh(self):
    self.assertFalse(self.platform.is_remote_ssh)

  def test_is_chromeos(self):
    self.assertFalse(self.platform.is_chromeos)

  def test_port_forward_invalid(self):
    with self.platform.ports.nested() as ports:
      with self.assertRaisesRegex(argparse.ArgumentTypeError, "local_port"):
        ports.forward(-1, -1)

  def test_reverse_port_forward_invalid(self):
    with self.platform.ports.nested() as ports:
      with self.assertRaisesRegex(argparse.ArgumentTypeError, "remote_port"):
        ports.reverse_forward(-1, -1)

  def test_is_remote_desktop_no_script(self):
    if not self.platform.is_local and self.platform.is_linux:
      self.expect_sh(
          "'[' -e /opt/google/chrome-remote-desktop/is-remoting-session ']'",
          returncode=1)
    self.assertFalse(self.platform.is_remote_desktop)


class BaseLocalMockPlatformTestMixin:

  def test_local_port_forward_invalid(self):
    with self.platform.ports.nested() as ports:
      with self.assertRaisesRegex(ValueError, "local platform"):
        ports.forward(1000, 2000)

  def test_local_reverse_port_forward_invalid(self):
    with self.platform.ports.nested() as ports:
      with self.assertRaisesRegex(ValueError, "local platform"):
        ports.reverse_forward(1000, 2000)

  def test_local_reverse_port_forward(self):
    with self.platform.ports.nested() as ports:
      port = self.platform.get_free_port()
      self.assertEqual(ports.reverse_forward(port, port), port)
      ports.stop_reverse_forward(port)

  def test_local_port_forward(self):
    with self.platform.ports.nested() as ports:
      port = self.platform.get_free_port()
      self.assertEqual(ports.forward(port, port), port)
      ports.stop_forward(port)


class BasePosixMockPlatformTestCase(BaseMockPlatformTestCase):
  platform: PosixPlatform

  @override
  def tearDown(self) -> None:
    assert isinstance(self.platform, PosixPlatform)
    super().tearDown()

  def test_is_posix(self):
    self.assertTrue(self.platform.is_posix)

  def test_path_conversion(self):
    self.assertIsInstance(self.platform.path("foo/bar"), pathlib.PurePosixPath)
    self.assertIsInstance(
        self.platform.path(pathlib.PurePath("foo/bar")), pathlib.PurePosixPath)
    self.assertIsInstance(
        self.platform.path(pathlib.PureWindowsPath("foo/bar")),
        pathlib.PurePosixPath)
    self.assertIsInstance(
        self.platform.path(pathlib.PurePosixPath("foo/bar")),
        pathlib.PurePosixPath)

  def test_win_absolute_path_conversion(self):
    if not plt.PLATFORM.is_win:
      return
    windows_path = pth.AnyWindowsPath("/foo/bar/file")
    abs_path = self.platform.absolute(windows_path)
    self.assertEqual(str(abs_path), "/foo/bar/file")
    self.assertIsInstance(abs_path, pth.AnyPosixPath)
    self.assertTrue(abs_path.is_absolute())
    self.assertTrue(self.platform.is_absolute(abs_path))

  def test_win_absolute_path_conversion_drive(self):
    if not plt.PLATFORM.is_win:
      return
    windows_path = pth.AnyWindowsPath("C:/foo/bar/file")
    abs_path = self.platform.absolute(windows_path)
    self.assertEqual(str(abs_path), "/foo/bar/file")
    self.assertIsInstance(abs_path, pth.AnyPosixPath)
    self.assertTrue(abs_path.is_absolute())
    self.assertTrue(self.platform.is_absolute(abs_path))

  def test_uptime(self):
    self.expect_sh(
        "uptime",
        result="12:25  up  3:26, 2 users, load averages: 4.27 4.29 4.80\n")
    uptime = self.platform.uptime()
    self.assertEqual(uptime, dt.timedelta(hours=3, minutes=26))
    self.expect_sh(
        "uptime",
        result=("12:54:27 up 5 days,  2:48,  3 users,  "
                "load average: 1.62, 2.15, 2.07\n"))
    uptime = self.platform.uptime()
    self.assertEqual(uptime, dt.timedelta(days=5, hours=2, minutes=48))
