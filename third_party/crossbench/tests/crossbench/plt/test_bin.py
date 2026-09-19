# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import os
import pathlib
import unittest
from unittest import mock

from pyfakefs.fake_filesystem import OSType
from typing_extensions import override

import crossbench.path as pth
from crossbench import plt
from crossbench.plt import PLATFORM
from crossbench.plt.bin import Binary, BinaryNotFoundError, ChromeOSBinary, \
    LinuxBinary, MacOsBinary, PosixBinary, WinBinary
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase
from tests.crossbench.mock_helper import ChromeOsSshMockPlatform, \
    LinuxMockPlatform, MacOsMockPlatform, WinMockPlatform


class BinaryTestCase(CrossbenchFakeFsTestCase):

  @override
  def setUp(self) -> None:
    super().setUp()
    self._all_mock_platforms = (
        LinuxMockPlatform(),
        MacOsMockPlatform(),
        WinMockPlatform(),
        # TODO: add adb testing
    )
    self._all_platforms = (PLATFORM,) + self._all_mock_platforms

  def all_mock_platforms(self):
    yield from self._all_mock_platforms

  def all_platforms(self):
    yield from self._all_platforms

  def create_binary_path(self, path: pth.AnyPathLike) -> pth.LocalPath:
    result = pth.LocalPath(path)
    self.fs.create_file(result, st_size=100)
    return result

  def test_create_without_binary(self):
    with self.assertRaises(ValueError):
      Binary(name="test")
    with self.assertRaises(ValueError):
      Binary(name="test", posix="")

  def test_new_windows_binary_invalid(self):
    with self.assertRaises(ValueError):
      WinBinary("custom")
    with self.assertRaises(ValueError):
      WinBinary(pth.AnyPath("custom"))
    with self.assertRaises(ValueError):
      WinBinary(pth.AnyPath("foo/bar/custom.py"))

  def test_new_windows_binary(self):
    binary = WinBinary("crossbench_mock_binary.exe")
    self.assertEqual(binary.name, "crossbench_mock_binary.exe")
    platform = WinMockPlatform()
    path = platform.local_path("C:/Users/user-name/AppData/Local/Programs/"
                               "crossbench/crossbench_mock_binary.exe")
    with self.assertRaises(ValueError):
      with platform.override_binary(binary, path):
        self.assertEqual(binary.resolve(platform), path)

    self.fs.create_file(path, st_size=100)
    with mock.patch("shutil.which", return_value=path) as cm:
      with platform.override_binary(binary, path):
        self.assertEqual(binary.resolve(platform), path)
        self.assertEqual(binary.resolve_cached(platform), path)
    cm.assert_called_once_with(os.fspath(path))

    # Still cached
    self.assertEqual(binary.resolve_cached(platform), path)
    with self.assertRaises(BinaryNotFoundError):
      self.assertEqual(binary.resolve(platform), path)

    binary.resolve_cached.cache_clear()
    with self.assertRaises(BinaryNotFoundError):
      self.assertEqual(binary.resolve(platform), path)
    with self.assertRaises(BinaryNotFoundError):
      self.assertEqual(binary.resolve_cached(platform), path)

  def test_basic_accessor(self):
    binary = Binary("test", default="foo/bar/test")
    self.assertEqual(binary.name, "test")

  def test_basic_accessor_multiple(self):
    binary = Binary("test", default=("foo/bar/test1", "foo/bar/test2"))
    self.assertEqual(binary.name, "test")

  def test_unknown_binary(self):
    binary = Binary("crossbench_mock_binary", default="crossbench_mock_binary")
    for platform in self.all_platforms():
      with self.subTest(platform=str(platform)):
        with self.assertRaises(BinaryNotFoundError):
          binary.resolve(platform)

  def test_known_binary_default(self):
    for platform in self.all_mock_platforms():
      with self.subTest(platform=str(platform)):
        default = pth.AnyPath("foo/bar/default/crossbench_mock_binary")
        result = default
        if platform.is_win:
          result = pth.AnyPath("foo/bar/default/crossbench_mock_binary.exe")
        binary = Binary("crossbench_mock_binary", default=default)
        self.assertEqual(binary.platform_path(platform), (pth.AnyPath(result),))
        with self.assertRaises(BinaryNotFoundError):
          binary.resolve(platform)
        with self.assertRaises(BinaryNotFoundError):
          binary.resolve_cached(platform)
        self.fs.create_file(result, st_size=100)
        self.assertEqual(pth.AnyPath(binary.resolve(platform)), result)
        self.assertEqual(pth.AnyPath(binary.resolve_cached(platform)), result)
        self.fs.remove(result)

  def test_known_binary_default_multiple(self):
    for platform in self.all_mock_platforms():
      with self.subTest(platform=str(platform)):
        default_miss = pth.AnyPath("foo/bar/default/fake")
        default = pth.AnyPath("foo/bar/default/crossbench_mock_binary")
        result = default
        if platform.is_win:
          default_miss = pth.AnyPath("foo/bar/default/fake.exe")
          result = pth.AnyPath("foo/bar/default/crossbench_mock_binary.exe")
        binary = Binary(
            "crossbench_mock_binary", default=(default_miss, default))
        self.assertEqual(
            binary.platform_path(platform), (
                pth.AnyPath(default_miss),
                pth.AnyPath(result),
            ))
        with self.assertRaises(BinaryNotFoundError):
          binary.resolve(platform)
        with self.assertRaises(BinaryNotFoundError):
          binary.resolve_cached(platform)
        self.fs.create_file(result, st_size=100)
        self.assertEqual(pth.AnyPath(binary.resolve(platform)), result)
        self.assertEqual(pth.AnyPath(binary.resolve_cached(platform)), result)
        self.fs.remove(result)

  @unittest.skipUnless(plt.PLATFORM.is_posix, "Only supported on posix")
  def test_known_binary_chromeos(self):
    path = pth.AnyPosixPath("foo/bar/default/crossbench_mock_binary")
    binary = Binary("crossbench_mock_binary", chromeos=path)
    self.validate_known_binary_chromeos(path, binary)
    binary = ChromeOSBinary(path)
    self.validate_known_binary_chromeos(path, binary)

  def validate_known_binary_chromeos(self, result, binary):
    result = pth.AnyPosixPath(result)
    platform = ChromeOsSshMockPlatform(
        host_platform=LinuxMockPlatform(),
        host="dut",
        port=0,
        ssh_port=22,
        ssh_user="root")

    platform.expect_sh("which", result, result=str(result))
    platform.expect_sh("[", "-e", result, "]", result="")
    platform.expect_sh("[", "-e", result, "]", result="")
    self.assertEqual(str(binary.resolve(platform)), str(result))

    platform.expect_sh("which", result, result=str(result))
    platform.expect_sh("[", "-e", result, "]", result="")
    platform.expect_sh("[", "-e", result, "]", result="")
    self.assertEqual(str(binary.resolve_cached(platform)), str(result))

    self.assertEqual(str(binary.resolve_cached(platform)), str(result))

    for platform in self.all_mock_platforms():
      if platform.is_chromeos:
        continue
      self.assertEqual(binary.platform_path(platform), ())
      with self.assertRaises(BinaryNotFoundError):
        binary.resolve(platform)
      with self.assertRaises(BinaryNotFoundError):
        binary.resolve_cached(platform)

  @unittest.skipUnless(plt.PLATFORM.is_posix, "Only supported on posix")
  def test_known_binary_linux(self):
    result = self.create_binary_path(
        pth.AnyPosixPath("foo/bar/default/crossbench_mock_binary"))
    binary = Binary("crossbench_mock_binary", linux=result)
    self.validate_known_binary_linux(result, binary)
    binary = LinuxBinary(result)
    self.validate_known_binary_linux(result, binary)

  def validate_known_binary_linux(self, result, binary):
    result = pth.AnyPosixPath(result)
    platform = LinuxMockPlatform()
    self.assertEqual(str(binary.resolve(platform)), str(result))
    self.assertEqual(str(binary.resolve_cached(platform)), str(result))

    for platform in self.all_mock_platforms():
      if platform.is_linux:
        continue
      self.assertEqual(binary.platform_path(platform), ())
      with self.assertRaises(BinaryNotFoundError):
        binary.resolve(platform)
      with self.assertRaises(BinaryNotFoundError):
        binary.resolve_cached(platform)

  @unittest.skipUnless(plt.PLATFORM.is_posix, "Only supported on posix")
  def test_known_binary_macos(self):
    result = self.create_binary_path("foo/bar/default/crossbench_mock_binary")
    binary = Binary("crossbench_mock_binary", macos=result)
    self.validate_known_binary_macos(result, binary)
    binary = MacOsBinary(result)
    self.validate_known_binary_macos(result, binary)

  def validate_known_binary_macos(self, result, binary):
    platform = MacOsMockPlatform()
    self.assertEqual(binary.resolve(platform), result)
    self.assertEqual(binary.resolve_cached(platform), result)

    for platform in self.all_mock_platforms():
      if platform.is_macos:
        continue
      self.assertEqual(binary.platform_path(platform), ())
      with self.assertRaises(BinaryNotFoundError):
        binary.resolve(platform)
      with self.assertRaises(BinaryNotFoundError):
        binary.resolve_cached(platform)

  @unittest.skipUnless(plt.PLATFORM.is_posix, "Only supported on posix")
  def test_known_binary_posix(self):
    result = self.create_binary_path("foo/bar/default/crossbench_mock_binary")
    binary = Binary("crossbench_mock_binary", posix=result)
    self.validate_known_binary_posix(result, binary)
    binary = PosixBinary(result)
    self.validate_known_binary_posix(result, binary)

  def validate_known_binary_posix(self, result, binary):
    for platform in self.all_mock_platforms():
      if not platform.is_posix:
        continue
      self.assertEqual(binary.resolve(platform), result)
      self.assertEqual(binary.resolve_cached(platform), result)

    for platform in self.all_mock_platforms():
      if platform.is_posix:
        continue
      self.assertEqual(binary.platform_path(platform), ())
      with self.assertRaises(BinaryNotFoundError):
        binary.resolve(platform)
      with self.assertRaises(BinaryNotFoundError):
        binary.resolve_cached(platform)

  def test_known_binary_win(self):
    self.fs.os = OSType.WINDOWS
    result = self.create_binary_path(
        "foo/bar/default/crossbench_mock_binary.exe")
    result = pathlib.PureWindowsPath(result)
    binary = Binary("crossbench_mock_binary", win=result)
    self.validate_known_binary_win(result, binary)
    binary = WinBinary(result)
    self.validate_known_binary_win(result, binary)

  def validate_known_binary_win(self, result, binary):
    platform = WinMockPlatform()
    self.assertEqual(binary.resolve(platform), result)
    self.assertEqual(binary.resolve_cached(platform), result)

    for platform in self.all_mock_platforms():
      if platform.is_win:
        continue
      self.assertEqual(binary.platform_path(platform), ())
      with self.assertRaises(BinaryNotFoundError):
        binary.resolve(platform)
      with self.assertRaises(BinaryNotFoundError):
        binary.resolve_cached(platform)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
