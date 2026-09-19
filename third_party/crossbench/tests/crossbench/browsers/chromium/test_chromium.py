# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import datetime as dt
import pathlib
import re
import unittest
from unittest import mock

from crossbench import path as pth
from crossbench.browsers.chromium.base import ChromiumBaseMixin
from crossbench.browsers.chromium.driver_finder import ChromeDriverFinder
from crossbench.browsers.chromium.webdriver import ChromiumWebDriver, \
    LocalChromiumWebDriverAndroid
from crossbench.browsers.chromium_based import helper
from crossbench.browsers.chromium_based.webdriver import ChromiumBasedWebDriver
from crossbench.browsers.settings import Settings
from tests import test_helper
from tests.crossbench import mock_browser
from tests.crossbench.base import BaseCrossbenchTestCase
from tests.crossbench.mock_helper import AndroidAdbMockPlatform, \
    LinuxMockPlatform, MacOsMockPlatform, MockPlatform


class LocalChromeWebDriverAndroidTestCase(BaseCrossbenchTestCase):

  def test_is_apk_helper(self):
    self.assertTrue(
        LocalChromiumWebDriverAndroid.is_apk_helper(
            pth.AnyPath("/home/user/Documents/chrome/src/"
                        "out/arm64.apk/bin/chrome_public_apk")))
    self.assertFalse(LocalChromiumWebDriverAndroid.is_apk_helper(None))
    self.assertFalse(
        LocalChromiumWebDriverAndroid.is_apk_helper(
            pth.AnyPath("org.chromium.chrome")))

  def test_is_local_build_mock_browser(self):
    self.assertTrue(self.browsers)
    for browser in self.browsers:
      self.assertFalse(browser.is_local_build)

  def test_is_local_build(self):
    build_dir = pathlib.Path("/home/testuser/chrome/src/out/release")
    path = build_dir / mock_browser.MockChromium.mock_app_binary()
    self.fs.create_file(path, st_size=1000)
    self.assertFalse(helper.is_in_build_dir(path, self.platform))

    version_str = mock_browser.MockChromium.VERSION
    with mock.patch.object(
        self.platform, "app_version", return_value=version_str):
      # Missing args.gn => cannot detect local build:
      browser = ChromiumWebDriver(
          "local", path=path, settings=Settings(platform=self.platform))
      self.assertFalse(browser.is_local_build)
      self.assertEqual(browser.version.version_str, version_str)

      self.fs.create_file(build_dir / "args.gn")
      self.assertTrue(helper.is_in_build_dir(path, self.platform))
      browser = ChromiumWebDriver(
          "local", path=path, settings=Settings(platform=self.platform))
      self.assertTrue(browser.is_local_build)
      self.assertFalse(browser.version.has_channel)
      self.assertEqual(browser.version.version_str, version_str)

  def test_profile_data_dir(self):
    build_dir = pathlib.Path("/home/testuser/chrome/src/out/release")
    path = build_dir / mock_browser.MockChromium.mock_app_binary()
    self.fs.create_file(path, st_size=1000)
    self.fs.create_file(build_dir / "args.gn")

    version_str = mock_browser.MockChromium.VERSION
    with mock.patch.object(
        self.platform, "app_version", return_value=version_str):
      cache_dir = pth.AnyPath("/tmp/my-cache-dir")
      browser = ChromiumWebDriver(
          "local",
          path=path,
          settings=Settings(platform=self.platform, cache_dir=cache_dir))
      browser.setup()

      self.assertEqual(browser.profile_data_dir, cache_dir)

  def test_user_data_dir_flags(self):
    build_dir = pathlib.Path("/home/testuser/chrome/src/out/release")
    path = build_dir / mock_browser.MockChromium.mock_app_binary()
    self.fs.create_file(path, st_size=1000)
    self.fs.create_file(build_dir / "args.gn")

    version_str = mock_browser.MockChromium.VERSION
    with mock.patch.object(
        self.platform, "app_version", return_value=version_str):
      browser = ChromiumWebDriver(
          "local", path=path, settings=Settings(platform=self.platform))

      custom_dir = pth.AnyPath("/tmp/custom-user-data-dir")
      browser.flags["--user-data-dir"] = str(custom_dir)
      browser.setup()

      self.assertEqual(browser.profile_data_dir, custom_dir)


class MockChromiumBasedWebDriver(ChromiumBaseMixin, ChromiumBasedWebDriver):

  def __init__(self, label, driver) -> None:
    mock_platform = mock.MagicMock(name="Mock Platform")
    mock_platform.app_version.side_effect = [mock_browser.MockChromium.VERSION]
    self._private_driver = driver
    super().__init__(
        label=label, path=None, settings=Settings(platform=mock_platform))

  def _create_driver(self, options, service):
    raise RuntimeError("start() should not be called")


class ChromiumBasedWebDriverTestCase(unittest.TestCase):

  def _make_tab_switch_mocks(self, handles, current):
    mock_driver = mock.MagicMock(name="Mock Driver")
    browser = MockChromiumBasedWebDriver("test-driver", mock_driver)

    def switch_to_window(handle):
      mock_driver.current_window_handle = handle
      mock_driver.title = handle
      mock_driver.current_url = f"https://{handle}.com"

    switch_to_window(current)

    mock_driver.switch_to.window.side_effect = switch_to_window
    mock_driver.window_handles = handles
    return (browser, mock_driver)

  def test_switch_tab_title(self):
    browser, mock_driver = self._make_tab_switch_mocks(["a", "b", "c"], "b")

    browser.switch_tab(title=re.compile("^c$"), timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "c")
    self.assertEqual(mock_driver.current_url, "https://c.com")

    browser.switch_tab(title=re.compile("^a$"), timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "a")
    self.assertEqual(mock_driver.current_url, "https://a.com")

    browser.switch_tab(title=re.compile("^b$"), timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "b")
    self.assertEqual(mock_driver.current_url, "https://b.com")

  def test_switch_tab_url(self):
    browser, mock_driver = self._make_tab_switch_mocks(["1", "2", "3"], "2")

    browser.switch_tab(url=re.compile(".*3.*"), timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "3")
    self.assertEqual(mock_driver.current_url, "https://3.com")

    browser.switch_tab(url=re.compile(".*1.*"), timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "1")
    self.assertEqual(mock_driver.current_url, "https://1.com")

    browser.switch_tab(url=re.compile(".*2.*"), timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "2")
    self.assertEqual(mock_driver.current_url, "https://2.com")

  def test_switch_tab_index(self):
    browser, mock_driver = self._make_tab_switch_mocks(["1", "2", "3"], "2")

    # Switch to current tab.
    browser.switch_tab(tab_index=1, timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "2")
    self.assertEqual(mock_driver.current_url, "https://2.com")

    # Switch to first tab.
    browser.switch_tab(tab_index=0, timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "1")
    self.assertEqual(mock_driver.current_url, "https://1.com")

    # Overflow tab_index.
    with self.assertRaises(IndexError):
      browser.switch_tab(tab_index=3, timeout=dt.timedelta(seconds=5))

    # Switch to last tab using negative tab_index.
    browser.switch_tab(tab_index=-1, timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "3")
    self.assertEqual(mock_driver.current_url, "https://3.com")

    # Underflow tab_index.
    with self.assertRaises(IndexError):
      browser.switch_tab(tab_index=-4, timeout=dt.timedelta(seconds=5))

  def test_switch_relative_tab_index(self):
    browser, mock_driver = self._make_tab_switch_mocks(["1", "2", "3"], "2")

    # Switch to current tab
    browser.switch_tab(relative_tab_index=0, timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "2")
    self.assertEqual(mock_driver.current_url, "https://2.com")

    # Next tab.
    browser.switch_tab(relative_tab_index=1, timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "3")
    self.assertEqual(mock_driver.current_url, "https://3.com")

    # Wrap positive.
    browser.switch_tab(relative_tab_index=1, timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "1")
    self.assertEqual(mock_driver.current_url, "https://1.com")

    # Wrap negative
    browser.switch_tab(relative_tab_index=-1, timeout=dt.timedelta(seconds=5))
    self.assertEqual(mock_driver.title, "3")
    self.assertEqual(mock_driver.current_url, "https://3.com")


class ChromeDriverFinderTestCase(BaseCrossbenchTestCase):

  def setUp(self) -> None:
    super().setUp()
    self.mock_browser = mock.MagicMock()
    self.mock_browser.platform.is_linux = False
    self.mock_browser.platform.is_macos = False
    self.mock_browser.platform.is_android = False
    self.mock_browser.platform.is_win = False
    self.mock_browser.platform.host_platform = self.platform
    self.mock_browser.version.major = 120

  def test_find_local_build_macos(self):
    self.mock_browser.platform.is_macos = True
    out_dir = pth.AnyPath("/Users/user/chromium/src/out/Official")
    app_path = out_dir / "Chromium.app"
    bin_path = app_path / "Contents" / "MacOS" / "Chromium"
    driver_path = out_dir / "chromedriver"

    self.fs.create_file(bin_path, st_size=1000)
    self.fs.create_file(driver_path, st_size=1000)

    self.mock_browser.app_path = app_path
    self.mock_browser.path = bin_path

    finder = ChromeDriverFinder(self.mock_browser)

    found_driver = finder.find_local_build()
    self.assertEqual(str(found_driver), str(driver_path))

  def test_find_local_build_linux(self):
    self.mock_browser.platform.is_linux = True
    out_dir = pth.AnyPath("/home/user/chromium/src/out/Default")
    app_path = out_dir / "chrome"
    driver_path = out_dir / "chromedriver"

    self.fs.create_file(app_path, st_size=1000)
    self.fs.create_file(driver_path, st_size=1000)

    self.mock_browser.app_path = app_path
    self.mock_browser.path = app_path

    finder = ChromeDriverFinder(self.mock_browser)

    found_driver = finder.find_local_build()
    self.assertEqual(str(found_driver), str(driver_path))

  def test_find_local_build_android(self):
    self.mock_browser.platform.is_android = True

    out_dir = pth.AnyPath("/home/user/chromium/src/out/Android")
    app_path = out_dir / "bin/chrome_apk"
    driver_path = out_dir / "clang_x64/chromedriver"

    self.fs.create_file(app_path, st_size=1000)
    self.fs.create_file(driver_path, st_size=1000)

    self.mock_browser.app_path = app_path
    self.mock_browser.path = app_path

    finder = ChromeDriverFinder(self.mock_browser)

    found_driver = finder.find_local_build()
    self.assertEqual(str(found_driver), str(driver_path))


class ChromiumPathMacOSTest(BaseCrossbenchTestCase):

  def setup_platform(self) -> MockPlatform:
    return MacOsMockPlatform()

  def test_macos_app_path_resolution(self):
    app_path = pth.AnyPath("/Applications/Chromium.app")
    bin_path = app_path / "Contents" / "MacOS" / "Chromium"

    self.fs.create_file(bin_path, st_size=1000)
    self.platform.app_version = mock.MagicMock(return_value="120.0.0.0")

    # Test passing the bundle path
    browser = ChromiumWebDriver(
        "test-label", path=app_path, settings=Settings(platform=self.platform))
    self.assertEqual(str(browser.app_path), str(app_path))
    self.assertEqual(str(browser.path), str(bin_path))

    # Test passing the binary path
    browser2 = ChromiumWebDriver(
        "test-label-2",
        path=bin_path,
        settings=Settings(platform=self.platform))
    self.assertEqual(str(browser2.app_path), str(app_path))
    self.assertEqual(str(browser2.path), str(bin_path))


class ChromiumPathLinuxTest(BaseCrossbenchTestCase):

  def setup_platform(self) -> MockPlatform:
    return LinuxMockPlatform()

  def test_linux_path_resolution(self):
    bin_path = pth.AnyPath("/usr/bin/chromium")
    self.fs.create_file(bin_path, st_size=1000)
    self.platform.app_version = mock.MagicMock(return_value="120.0.0.0")

    browser = ChromiumWebDriver(
        "test-label", path=bin_path, settings=Settings(platform=self.platform))
    self.assertEqual(str(browser.app_path), str(bin_path))
    self.assertEqual(str(browser.path), str(bin_path))

  def test_linux_driver_lookup(self):
    out_dir = pth.AnyPath("/home/user/chromium/src/out/Default")
    bin_path = out_dir / "chrome"
    driver_path = out_dir / "chromedriver"

    self.fs.create_file(bin_path, st_size=1000)
    self.fs.create_file(driver_path, st_size=1000)
    self.fs.create_file(out_dir / "args.gn")

    self.platform.app_version = mock.MagicMock(return_value="120.0.0.0")

    browser = ChromiumWebDriver(
        "test-label", path=bin_path, settings=Settings(platform=self.platform))
    browser.validate_binary()

    self.assertEqual(str(browser.driver_path), str(driver_path))


class MockLocalChromiumWebDriverAndroid(ChromiumBaseMixin,
                                        LocalChromiumWebDriverAndroid):

  def _create_driver(self, options, service):
    raise RuntimeError("start() should not be called")


class ChromiumPathAndroidTest(BaseCrossbenchTestCase):

  def setup_platform(self) -> MockPlatform:
    mock_adb = mock.MagicMock()
    mock_adb.serial_id = "mock-serial-id"
    mock_adb.build_version = 30
    mock_adb.build_description = "mock-build-description"
    mock_adb.packages.return_value = ["org.chromium.chrome"]

    host_platform = LinuxMockPlatform()
    platform = AndroidAdbMockPlatform(host_platform=host_platform, adb=mock_adb)
    platform.exists = mock.MagicMock(return_value=True)
    platform.is_file = mock.MagicMock(return_value=True)
    return platform

  def test_android_driver_lookup(self):
    out_dir = pth.AnyPath("/home/user/chromium/src/out/Android")
    chrome_public_apk_path = out_dir / "bin/chrome_public_apk"
    driver_path = out_dir / "clang_x64/chromedriver"

    self.fs.create_file(chrome_public_apk_path, st_size=1000)
    self.fs.create_file(driver_path, st_size=1000)
    self.fs.create_file(out_dir / "args.gn")

    self.platform.host_platform.sh_stdout = mock.MagicMock(
        return_value="Package name: org.chromium.chrome\nversionName: 120.0.0.0"
    )

    browser = MockLocalChromiumWebDriverAndroid(
        "test-label",
        path=chrome_public_apk_path,
        settings=Settings(platform=self.platform))
    browser.validate_binary()

    self.assertEqual(str(browser.driver_path), str(driver_path))


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
