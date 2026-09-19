# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse

from crossbench import path as pth
from crossbench.browsers import all as all_browsers
from crossbench.cli.config.browser import BrowserConfig
from tests import test_helper
from tests.crossbench.cli.config.base import ADB_DEVICES_SINGLE_OUTPUT, \
    BaseConfigTestCase


class BrowserAliasesTestCase(BaseConfigTestCase):

  def test_chrome_aliases(self):
    aliases = ("chrome", "chrome-stable", "chr-stable", "chr")
    expected = all_browsers.Chrome.stable_path(self.platform)
    for alias in aliases:
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(alias)
        self.assertEqual(config.browser, expected)

  def test_chrome_beta_aliases(self):
    aliases = ("chrome-beta", "chr-beta")
    expected = all_browsers.Chrome.beta_path(self.platform)
    for alias in aliases:
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(alias)
        self.assertEqual(config.browser, expected)

  def test_chrome_dev_aliases(self):
    aliases = ("chrome-dev", "chr-dev")
    expected = all_browsers.Chrome.dev_path(self.platform)
    for alias in aliases:
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(alias)
        self.assertEqual(config.browser, expected)

  def test_chrome_canary_aliases(self):
    if self.platform.is_linux:
      return
    aliases = ("chrome-canary", "chr-canary")
    expected = all_browsers.Chrome.canary_path(self.platform)
    for alias in aliases:
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(alias)
        self.assertEqual(config.browser, expected)

  def test_edge_aliases(self):
    aliases = ("edge", "edge-stable")
    expected = all_browsers.Edge.stable_path(self.platform)
    for alias in aliases:
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(alias)
        self.assertEqual(config.browser, expected)

  def test_safari_aliases(self):
    aliases = ("safari", "sf", "safari-stable", "sf-stable")
    expected = all_browsers.Safari.default_path(self.platform)
    for alias in aliases:
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(alias)
        self.assertEqual(config.browser, expected)

  def test_safari_tp_aliases(self):
    aliases = ("safari-technology-preview", "safari-tech-preview", "safari-tp",
               "sf-tp", "stp", "tp")
    expected = all_browsers.Safari.technology_preview_path(self.platform)
    for alias in aliases:
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(alias)
        self.assertEqual(config.browser, expected)

  def test_firefox_aliases(self):
    aliases = ("firefox", "firefox-stable", "ff", "ff-stable")
    expected = all_browsers.Firefox.default_path(self.platform)
    for alias in aliases:
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(alias)
        self.assertEqual(config.browser, expected)

  def test_firefox_dev_aliases(self):
    aliases = ("firefox-dev", "firefox-developer-edition", "ff-dev")
    expected = all_browsers.Firefox.developer_edition_path(self.platform)
    for alias in aliases:
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(alias)
        self.assertEqual(config.browser, expected)

  def test_firefox_nightly_aliases(self):
    aliases = ("firefox-nightly", "ff-nightly", "ff-trunk")
    expected = all_browsers.Firefox.nightly_path(self.platform)
    for alias in aliases:
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(alias)
        self.assertEqual(config.browser, expected)

  def test_android_chrome_aliases(self):
    aliases = ("chrome", "chrome-stable", "chr-stable", "chr")
    expected = pth.AnyPosixPath("com.android.chrome")
    for alias in aliases:
      self.platform.sh_results = [ADB_DEVICES_SINGLE_OUTPUT]
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(f"adb:{alias}")
        self.assertEqual(config.browser, expected)

  def test_android_chrome_beta_aliases(self):
    aliases = ("chrome-beta", "chr-beta")
    expected = pth.AnyPosixPath("com.chrome.beta")
    for alias in aliases:
      self.platform.sh_results = [ADB_DEVICES_SINGLE_OUTPUT]
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(f"adb:{alias}")
        self.assertEqual(config.browser, expected)

  def test_android_chrome_dev_aliases(self):
    aliases = ("chrome-dev", "chr-dev")
    expected = pth.AnyPosixPath("com.chrome.dev")
    for alias in aliases:
      self.platform.sh_results = [ADB_DEVICES_SINGLE_OUTPUT]
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(f"adb:{alias}")
        self.assertEqual(config.browser, expected)

  def test_android_chrome_canary_aliases(self):
    aliases = ("chrome-canary", "chr-canary")
    expected = pth.AnyPosixPath("com.chrome.canary")
    for alias in aliases:
      self.platform.sh_results = [ADB_DEVICES_SINGLE_OUTPUT]
      with self.subTest(alias=alias):
        config = BrowserConfig.parse_str(f"adb:{alias}")
        self.assertEqual(config.browser, expected)

  def test_android_chromium_alias(self):
    alias = "chromium"
    expected = pth.AnyPosixPath("org.chromium.chrome")
    self.platform.sh_results = [ADB_DEVICES_SINGLE_OUTPUT]
    config = BrowserConfig.parse_str(f"adb:{alias}")
    self.assertEqual(config.browser, expected)

  def test_unknown_alias(self):
    with self.assertRaises(argparse.ArgumentTypeError):
      BrowserConfig.parse_str("unknown-browser")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
