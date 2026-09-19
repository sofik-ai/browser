# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import os
import pathlib
from unittest import mock

from typing_extensions import override

from crossbench.helper.path_finder import ChromiumBuildBinaryFinder, \
    ChromiumCheckoutFinder, TraceboxFinder, TraceconvFinder, \
    TraceProcessorFinder, V8CheckoutFinder, V8ToolsFinder, WprCloudBinary, \
    WprGoFinder
from crossbench.plt import PLATFORM
from tests import test_helper
from tests.crossbench.base import BaseCrossbenchTestCase
from tests.crossbench.mock_helper import AndroidAdbMockPlatform, \
    ChromeOsSshMockPlatform, LinuxMockPlatform, MacOsMockPlatform, MockAdb, \
    ShResult, WinMockPlatform


class BaseCheckoutTestCase(BaseCrossbenchTestCase):

  def _add_v8_checkout_files(self, checkout_dir: pathlib.Path) -> None:
    self.assertIsNone(V8CheckoutFinder(self.platform).path)
    (checkout_dir / ".git").mkdir(parents=True)
    self.assertIsNone(V8CheckoutFinder(self.platform).path)
    self.fs.create_file(checkout_dir / "include" / "v8.h", st_size=100)

  def _add_chrome_checkout_files(self, checkout_dir: pathlib.Path) -> None:
    self.assertIsNone(ChromiumCheckoutFinder(self.platform).path)
    self._add_v8_checkout_files(checkout_dir / "v8")
    (checkout_dir / ".git").mkdir(parents=True)
    self.assertIsNone(ChromiumCheckoutFinder(self.platform).path)
    (checkout_dir / "chrome").mkdir(parents=True)


class V8CheckoutFinderTestCase(BaseCheckoutTestCase):

  def test_find_none(self):
    self.assertIsNone(V8CheckoutFinder(self.platform).path)
    self.assertIsNone(V8CheckoutFinder(self.platform).local_path)

  def test_d8_path(self):
    with mock.patch.dict(os.environ, {}, clear=True):
      self.assertIsNone(V8CheckoutFinder(self.platform).path)
    candidate_dir = pathlib.Path("/custom/v8/")
    d8_path = candidate_dir / "out/x64.release/d8"
    with mock.patch.dict(os.environ, {"D8_PATH": str(d8_path)}, clear=True):
      self.assertIsNone(V8CheckoutFinder(self.platform).path)
    self._add_v8_checkout_files(candidate_dir)
    with mock.patch.dict(os.environ, {"D8_PATH": str(d8_path)}, clear=True):
      self.assertEqual(
          pathlib.Path(V8CheckoutFinder(self.platform).path), candidate_dir)
      self.assertEqual(
          V8CheckoutFinder(self.platform).local_path, candidate_dir)
    # Still NONE without custom D8_PATH env var.
    self.assertIsNone(V8CheckoutFinder(self.platform).path)

  def test_known_location(self):
    checkout_dir = pathlib.Path.home() / "v8/v8"
    self.assertIsNone(V8CheckoutFinder(self.platform).path)
    checkout_dir.mkdir(parents=True)
    self._add_v8_checkout_files(checkout_dir)
    self.assertEqual(V8CheckoutFinder(self.platform).path, checkout_dir)

  def test_module_relative(self):
    with mock.patch.dict(os.environ, {}, clear=True):
      self.assertIsNone(V8CheckoutFinder(self.platform).path)
      path = pathlib.Path(__file__)
      self.assertFalse(path.exists())
      # In:   chromium/src/third_party/crossbench/tests/crossbench/probes/test_helper.py
      # Out:  chromium/src
      fake_chrome_root = path.parents[5]
      checkout_dir = fake_chrome_root / "v8"
      self.assertIsNone(V8CheckoutFinder(self.platform).path)
      self._add_chrome_checkout_files(fake_chrome_root)
      self.assertIsNotNone(ChromiumCheckoutFinder(self.platform).path)
      self.assertEqual(
          pathlib.Path(V8CheckoutFinder(self.platform).path), checkout_dir)


class ChromiumBuildBinaryFinderTestCase(BaseCheckoutTestCase):

  def test_find_none(self):
    finder = ChromiumBuildBinaryFinder(self.platform, "custom_binary", ())
    self.assertIsNone(finder.path)
    self.assertIsNone(finder.path)
    self.assertEqual(finder.binary_name, "custom_binary")
    candidate_dir = pathlib.Path("/chr/src/out/x64.Release")
    self.assertIsNone(
        ChromiumBuildBinaryFinder(self.platform, "custom_binary",
                                  (candidate_dir,)).path)

  def test_find_candidate(self):
    checkout_dir = pathlib.Path("/foo/bar/chr/src/")
    candidate = checkout_dir / "out/x64.Release/custom_binary"
    self.fs.create_file(candidate, st_size=100)
    self.assertTrue(candidate.is_file)
    self.assertIsNone(
        ChromiumBuildBinaryFinder(self.platform, "custom_binary",
                                  (candidate.parent,)).path)
    self._add_chrome_checkout_files(checkout_dir)
    self.assertEqual(
        ChromiumBuildBinaryFinder(self.platform, "custom_binary",
                                  (candidate.parent,)).path, candidate)

  def test_find_default(self):
    checkout_dir = pathlib.Path.home() / "Documents/chromium/src"
    candidate = checkout_dir / "out/Release/custom_binary"
    self.fs.create_file(candidate, st_size=100)
    assert checkout_dir.is_dir()
    self._add_chrome_checkout_files(checkout_dir)
    self.assertEqual(
        ChromiumBuildBinaryFinder(self.platform, "custom_binary", ()).path,
        candidate)

  def test_find_build_dir_from_candite(self):
    checkout_dir = pathlib.Path.home() / "Documents/some_chr/src"
    candidate = checkout_dir / "out/Release/custom_binary"
    self.fs.create_file(candidate, st_size=100)
    assert checkout_dir.is_dir()
    self._add_chrome_checkout_files(checkout_dir)
    self.assertIsNone(
        ChromiumBuildBinaryFinder(self.platform, "custom_binary", ()).path,)
    self.assertEqual(
        ChromiumBuildBinaryFinder(self.platform, "custom_binary",
                                  (checkout_dir / "out",)).path, candidate)
    self.assertEqual(
        ChromiumBuildBinaryFinder(self.platform, "custom_binary",
                                  (candidate.parent,)).path, candidate)


class PerfettoToolFinderTestCase(BaseCheckoutTestCase):

  def test_find_traceconv(self):
    self._find_tool(TraceconvFinder, "traceconv")

  def test_find_tracebox(self):
    self._find_tool(TraceboxFinder, "tracebox")

  def test_find_trace_processor(self):
    self._find_tool(TraceProcessorFinder, "trace_processor")

  def _find_tool(self, finder_cls, name):
    finder = finder_cls(self.platform)
    self.assertIsNone(finder.path)
    self.assertIsNone(finder.path)
    checkout_dir = pathlib.Path.home() / "Documents/chromium/src"
    false_candidate = checkout_dir / "third_party/perfetto/tools/another_binary"
    self.fs.create_file(false_candidate, st_size=100)
    self.assertIsNone(finder_cls(self.platform).path)
    candidate = checkout_dir / "third_party/perfetto/tools" / name
    self.fs.create_file(candidate, st_size=100)
    self.assertIsNone(finder_cls(self.platform).path)
    self._add_chrome_checkout_files(checkout_dir)
    self.assertEqual(finder_cls(self.platform).path, candidate)


class V8ToolsFinderTestCase(BaseCheckoutTestCase):

  def test_defaults(self):
    # TODO: use AndroidAdbMockPlatform(self.platform) as well
    for platform in (self.platform, LinuxMockPlatform(), MacOsMockPlatform(),
                     WinMockPlatform()):
      finder = V8ToolsFinder(platform)
      self.assertIsNone(finder.d8_binary)
      self.assertIsNone(finder.v8_checkout)
      self.assertIsNone(finder.tick_processor)
      self.assertIsNone(finder.v8_logviewer)

  def test_find_v8_tools(self):
    checkout_dir = pathlib.Path.home() / "v8/v8"
    self._add_v8_checkout_files(checkout_dir)

    tick_processor_name = "tools/linux-tick-processor"
    if self.platform.is_macos:
      tick_processor_name = "tools/mac-tick-processor"
    elif self.platform.is_win:
      tick_processor_name = "tools/windows-tick-processor.bat"

    self.fs.create_file(checkout_dir / tick_processor_name, st_size=100)
    self.fs.create_file(checkout_dir / "tools/v8-logviewer", st_size=100)

    d8_binary = checkout_dir / "out/Release/d8"
    self.fs.create_file(d8_binary, st_size=100)

    finder = V8ToolsFinder(
        self.platform, d8_binary=d8_binary, v8_checkout=checkout_dir)
    self.assertEqual(finder.d8_binary, d8_binary)
    self.assertEqual(finder.v8_checkout, checkout_dir)
    self.assertEqual(finder.tick_processor, checkout_dir / tick_processor_name)
    self.assertEqual(finder.v8_logviewer, checkout_dir / "tools/v8-logviewer")


class WprToolsFinderTestCase(BaseCheckoutTestCase):

  __test__ = True

  @override
  def setUp(self):
    # Only one of these directories exists, depending on whether crossbench is
    # checked out standalone or within a different repo. The bots only run tests
    # on the first case, but it's best to make them pass in both cases to avoid
    # user surprise.
    third_party_inside = test_helper.root_dir() / "third_party"
    third_party_outside = test_helper.root_dir().parents[1] / "third_party"
    # Must be computed before super().setUp(), otherwise the fake filesystem
    # will be checked.
    using_third_party_inside = third_party_inside.exists()
    super().setUp()
    if using_third_party_inside:
      self.fs.add_real_directory(third_party_inside)
    else:
      self.fs.add_real_directory(third_party_outside)

  def _with_arch(self, platform, arch):
    platform.machine = arch
    platform.use_mock_name = False
    return platform

  def test_path_exists(self):
    finder = WprGoFinder(PLATFORM)
    self.assertTrue(finder.local_path.exists(),
                    f"{finder.local_path} not found")

  def test_cloud_binary(self):
    self.fs.create_file("/usr/bin/adb", contents="adb")
    for _ in range(3):
      if self.platform.is_macos:
        self.platform.expect_sh(
            "brew", "--prefix", result=ShResult(returncode=1))
      self.platform.expect_sh(
          "/usr/bin/adb",
          "devices",
          "-l",
          result="List of devices attached\n123 device usb:0 product:a model:b")
    platforms = [
        self._with_arch(
            AndroidAdbMockPlatform(self.platform, adb=MockAdb(self.platform)),
            "arm64"),
        self._with_arch(
            AndroidAdbMockPlatform(self.platform, adb=MockAdb(self.platform)),
            "arm32"),
        self._with_arch(
            AndroidAdbMockPlatform(self.platform, adb=MockAdb(self.platform)),
            "x64"),
        self._with_arch(
            ChromeOsSshMockPlatform(self.platform, "host", 0, 22, "user"),
            "arm64"),
        self._with_arch(
            ChromeOsSshMockPlatform(self.platform, "host", 0, 22, "user"),
            "x64"),
        self._with_arch(LinuxMockPlatform(), "x64"),
        self._with_arch(MacOsMockPlatform(), "arm64"),
        self._with_arch(MacOsMockPlatform(), "x64"),
        self._with_arch(WinMockPlatform(), "x64"),
    ]
    self.assertSetEqual({p.key for p in platforms},
                        set(WprGoFinder.WPR_PREBUILT_LOOKUP.keys()),
                        "Please add any new platform(s) to the list above")
    for platform in platforms:
      cloud_binary: WprCloudBinary = WprGoFinder(
          self.platform).cloud_binary(platform)
      self.assertTrue(cloud_binary.file_hash, f"Empty file hash for {platform}")
      self.assertTrue(cloud_binary.url, f"Empty url for {platform}")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
