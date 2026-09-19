# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
from typing import TYPE_CHECKING, Optional, Type
from unittest import mock

import hjson

from crossbench import plt
from crossbench.browsers import viewport
from crossbench.browsers.splash_screen import SplashScreen, URLSplashScreen
from crossbench.cli.config.browser import BrowserConfig
from crossbench.cli.config.driver import DriverConfig
from crossbench.cli.config.driver_type import BrowserDriverType
from crossbench.cli.subcommand.benchmark import BenchmarkSubcommand
from crossbench.env.runner_env import ValidationMode
from crossbench.parse import LateArgumentError
from crossbench.probes.internal.summary import ResultsSummaryProbe
from crossbench.probes.power_sampler import PowerSamplerProbe
from crossbench.runner.runner import Runner
from tests import test_helper
from tests.crossbench import mock_browser
from tests.crossbench.base import BaseCliTestCase, SysExitTestException
from tests.crossbench.cli.config.base import IOS_DEVICES_SINGLE_OUTPUT

if TYPE_CHECKING:
  from crossbench.path import AnyPath


class FastCliTestCasePartB(BaseCliTestCase):
  """These tests are run as part of the presubmit and should be
  reasonably fast.
  Slow tests run on the CQ are in CliSlowTestCase.

  Keep FastCliTestCasePartA and FastCliTestCasePartB balanced for faster local
  presubmit checks.
  """

  def test_custom_chrome_browser_binary(self):
    if self.platform.is_win:
      self.skipTest("No auto-download available on windows")
    browser_cls = mock_browser.MockChromeStable
    browser_bin = browser_cls.mock_app_path(
        self.platform).with_stem("Custom Google Chrome")
    browser_cls.setup_bin(self.fs, browser_bin, "Chrome")

    with self._patch_get_browser_cls(browser_cls) as get_browser_cls:
      self.run_cli("loading", f"--browser={browser_bin}",
                   "--urls=http://test.com", "--env-validation=skip")
    get_browser_cls.assert_called_once_with(
        BrowserConfig(browser_bin, DriverConfig.default()))

  def test_custom_chrome_browser_binary_custom_flags(self):
    if self.platform.is_win:
      self.skipTest("No auto-download available on windows")
    browser_cls = mock_browser.MockChromeStable
    browser_bin = browser_cls.mock_app_path(
        self.platform).with_stem("Custom Google Chrome")
    browser_cls.setup_bin(self.fs, browser_bin, "Chrome")

    with self._patch_get_browser_cls(browser_cls), mock.patch.object(
        BenchmarkSubcommand, "_run_benchmark") as run_benchmark:
      self.run_cli("loading", f"--browser={browser_bin}",
                   "--urls=http://test.com", "--env-validation=skip", "--",
                   "--chrome-flag1=value1", "--chrome-flag2")
    run_benchmark.assert_called_once()
    runner = run_benchmark.call_args[0][1]
    self.assertIsInstance(runner, Runner)
    self.assertEqual(len(runner.browsers), 1)
    browser = runner.browsers[0]
    self.assertListEqual(["--chrome-flag1=value1", "--chrome-flag2"],
                         list(browser.flags))

  def test_browser_identifiers_duplicate(self):
    with self.assertRaises(argparse.ArgumentTypeError):
      self.run_cli("loading", "--browser=chrome", "--browser=chrome",
                   "--urls=http://test.com", "--env-validation=skip", "--throw")

  def test_browser_identifiers_multiple(self):
    mock_browsers: list[Type[mock_browser.MockBrowser]] = [
        mock_browser.MockChromeStable,
        mock_browser.MockChromeBeta,
        mock_browser.MockChromeDev,
    ]

    def mock_get_browser_cls(browser_config: BrowserConfig):
      self.assertEqual(browser_config.driver.type, BrowserDriverType.WEB_DRIVER)
      for mock_browser_cls in mock_browsers:
        if mock_browser_cls.mock_app_path(self.platform) == browser_config.path:
          return mock_browser_cls
      raise ValueError("Unknown browser path")

    with self._patch_get_browser_cls(
        side_effect=mock_get_browser_cls) as get_browser_cls:
      url = "http://test.com"
      self.run_cli("loading", "--browser=chrome-beta",
                   "--browser=chrome-stable", "--browser=chrome-dev",
                   f"--urls={url}", "--env-validation=skip",
                   f"--out-dir={self.out_dir}", "--no-symlinks")
      self.assertTrue(self.out_dir.exists())
      get_browser_cls.assert_called()
      # Example:  BROWSER / "cb.results.json"
      result_files = list(
          self.out_dir.glob(f"*/*/{ResultsSummaryProbe.NAME}.json"))
      self.assertEqual(len(result_files), 3)
      versions = []
      for result_file in result_files:
        with result_file.open(encoding="utf-8") as f:
          results = json.load(f)
        versions.append(results["browser"]["version"])
        self.assertIn("test.com", results["stories"])
      self.assertTrue(len(set(versions)), 3)
      for mock_browser_cls in mock_browsers:
        self.assertIn(mock_browser_cls.VERSION, versions)

  def test_browser_identifiers_multiple_same_major_version(self):

    class MockChromeBeta2(mock_browser.MockChromeBeta):
      VERSION = "100.22.33.100"

    class MockChromeDev2(mock_browser.MockChromeDev):
      VERSION = "100.22.33.200"

    mock_browsers: list[Type[mock_browser.MockBrowser]] = [
        MockChromeBeta2,
        MockChromeDev2,
    ]

    def mock_get_browser_cls(browser_config: BrowserConfig):
      self.assertEqual(browser_config.driver.type, BrowserDriverType.WEB_DRIVER)
      for mock_browser_cls in mock_browsers:
        if mock_browser_cls.mock_app_path(self.platform) == browser_config.path:
          return mock_browser_cls
      raise ValueError("Unknown browser path")

    with self._patch_get_browser_cls(
        side_effect=mock_get_browser_cls) as get_browser_cls:
      url = "http://test.com"
      self.run_cli("loading", "--browser=chrome-dev", "--browser=chrome-beta",
                   f"--urls={url}", "--env-validation=skip",
                   f"--out-dir={self.out_dir}", "--no-symlinks")
      self.assertTrue(self.out_dir.exists())
      get_browser_cls.assert_called()
      # Example:  BROWSER / "cb.results.json"
      result_files = list(
          self.out_dir.glob(f"*/*/{ResultsSummaryProbe.NAME}.json"))
      self.assertEqual(len(result_files), 2)
      versions = []
      for result_file in result_files:
        with result_file.open(encoding="utf-8") as f:
          results = json.load(f)
        versions.append(results["browser"]["version"])
        self.assertIn("test.com", results["stories"])
      self.assertTrue(len(set(versions)), 2)
      for mock_browser_cls in mock_browsers:
        self.assertIn(mock_browser_cls.VERSION, versions)

  def test_browser_identifiers_multiple_same_version(self):

    class MockChromeBeta2(mock_browser.MockChromeBeta):
      VERSION = "100.22.33.999"

    class MockChromeDev2(mock_browser.MockChromeDev):
      VERSION = "100.22.33.999"

    mock_browsers: list[Type[mock_browser.MockBrowser]] = [
        MockChromeBeta2,
        MockChromeDev2,
    ]

    def mock_get_browser_cls(browser_config: BrowserConfig):
      self.assertEqual(browser_config.driver.type, BrowserDriverType.WEB_DRIVER)
      for mock_browser_cls in mock_browsers:
        if mock_browser_cls.mock_app_path(self.platform) == browser_config.path:
          return mock_browser_cls
      raise ValueError("Unknown browser path")

    with self._patch_get_browser_cls(
        side_effect=mock_get_browser_cls) as get_browser_cls:
      url = "http://test.com"
      self.run_cli("loading", "--browser=chrome-dev", "--browser=chrome-beta",
                   f"--urls={url}", "--env-validation=skip",
                   f"--out-dir={self.out_dir}", "--no-symlinks")
      self.assertTrue(self.out_dir.exists())
      get_browser_cls.assert_called()
      # Example:  BROWSER / "cb.results.json"
      result_files = list(
          self.out_dir.glob(f"*/*/{ResultsSummaryProbe.NAME}.json"))
      self.assertEqual(len(result_files), 2)
      versions = []
      for result_file in result_files:
        with result_file.open(encoding="utf-8") as f:
          results = json.load(f)
        versions.append(results["browser"]["version"])
        self.assertIn("test.com", results["stories"])
      self.assertTrue(len(set(versions)), 1)
      for mock_browser_cls in mock_browsers:
        self.assertIn(mock_browser_cls.VERSION, versions)

  def test_browser_different_drivers(self):

    def mock_get_browser_cls(browser_config: BrowserConfig):
      if browser_config.driver.type == BrowserDriverType.IOS:
        self.assertEqual(
            browser_config.path,
            mock_browser.MockChromeStable.mock_app_path(self.platform))
        return mock_browser.MockChromeStable
      if browser_config.driver.type == BrowserDriverType.WEB_DRIVER:
        self.assertEqual(
            browser_config.path,
            mock_browser.MockChromeBeta.mock_app_path(self.platform))
        return mock_browser.MockChromeBeta
      self.assertEqual(browser_config.driver.type,
                       BrowserDriverType.APPLE_SCRIPT)
      self.assertEqual(browser_config.path,
                       mock_browser.MockChromeDev.mock_app_path(self.platform))
      return mock_browser.MockChromeDev

    with (mock.patch(
        "crossbench.cli.config.driver.ios_devices",
        return_value=IOS_DEVICES_SINGLE_OUTPUT),
          mock.patch(
              "crossbench.plt.ios.ios_devices",
              return_value=IOS_DEVICES_SINGLE_OUTPUT),
          self._patch_get_browser_cls(side_effect=mock_get_browser_cls) as
          get_browser_cls):
      url = "http://test.com"
      self.run_cli("loading", "--browser=ios:chrome-stable",
                   "--browser=selenium:chrome-beta",
                   "--browser=applescript:chrome-dev", f"--urls={url}",
                   "--env-validation=skip", f"--out-dir={self.out_dir}",
                   "--no-symlinks")
      self.assertTrue(self.out_dir.exists())
      get_browser_cls.assert_called()
      # Example:  BROWSER / "cb.results.json"
      result_files = list(
          self.out_dir.glob(f"*/*/{ResultsSummaryProbe.NAME}.json"))
      self.assertEqual(len(result_files), 3)
      versions = []
      for result_file in result_files:
        with result_file.open(encoding="utf-8") as f:
          results = json.load(f)
        versions.append(results["browser"]["version"])
        self.assertIn("test.com", results["stories"])
      self.assertTrue(len(set(versions)), 1)
      self.assertIn(mock_browser.MockChromeStable.VERSION, versions)
      self.assertIn(mock_browser.MockChromeBeta.VERSION, versions)
      self.assertIn(mock_browser.MockChromeDev.VERSION, versions)

  def test_probe_invalid_inline_json_config(self):
    with self.assertRaises(
        argparse.ArgumentError) as cm, self._patch_get_browser():
      self.run_cli("loading", "--probe=v8.log{invalid json: d a t a}",
                   "--urls=cnn", "--env-validation=skip", "--throw")
    message = str(cm.exception)
    self.assertIn("{invalid json: d a t a}", message)

  def test_probe_empty_inline_json_config(self):
    js_flags = ["--log-foo", "--log-bar"]
    with self._patch_get_browser():
      url = "http://test.com"
      self.run_cli("loading", "--probe=v8.log{}", f"--urls={url}",
                   "--env-validation=skip")
      for browser in self.browsers:
        self.assertListEqual([url], browser.url_list[self.SPLASH_URLS_LEN:])
        for flag in js_flags:
          self.assertNotIn(flag, browser.js_flags)

  def test_probe_inline_json_config(self):
    js_flags = ["--log-foo", "--log-bar"]
    json_config = json.dumps({"js_flags": js_flags})
    with self._patch_get_browser():
      url = "http://test.com"
      self.run_cli("loading", f"--probe=v8.log{json_config}", f"--urls={url}",
                   "--env-validation=skip")
      for browser in self.browsers:
        self.assertListEqual([url], browser.url_list[self.SPLASH_URLS_LEN:])
        for flag in js_flags:
          self.assertIn(flag, browser.js_flags)

  def test_env_config_name(self):
    with self._patch_get_browser():
      self.run_cli("loading", "--env=strict", "--urls=http://test.com",
                   "--env-validation=skip", "--throw")

  def test_env_config_inline_hjson(self):
    with self._patch_get_browser():
      self.run_cli("loading", '--env={"power_use_battery":false}',
                   "--urls=http://test.com", "--env-validation=skip")

  def test_env_config_inline_invalid(self):
    with self.cli() as cli:
      with self.assertRaises(SysExitTestException):
        cli.run([
            "loading", "--env=not a valid name", "--urls=http://test.com",
            "--env-validation=skip"
        ])
      with self.assertRaises(SysExitTestException):
        cli.run([
            "loading", "--env={not valid hjson}", "--urls=http://test.com",
            "--env-validation=skip"
        ])
      with self.assertRaises(SysExitTestException):
        cli.run([
            "loading", "--env={unknown_property:1}", "--urls=http://test.com",
            "--env-validation=skip"
        ])

  def test_conflicting_driver_path(self):
    mock_browsers: list[Type[mock_browser.MockBrowser]] = [
        mock_browser.MockChromeStable,
        mock_browser.MockFirefox,
    ]

    def mock_get_browser_cls(browser_config: BrowserConfig):
      self.assertEqual(browser_config.driver.type, BrowserDriverType.WEB_DRIVER)
      for mock_browser_cls in mock_browsers:
        if mock_browser_cls.mock_app_path(self.platform) == browser_config.path:
          return mock_browser_cls
      raise ValueError("Unknown browser path")

    driver_path = self.out_dir / "driver"
    self.fs.create_file(driver_path, st_size=1024)
    with self.assertRaises(LateArgumentError) as cm:
      with self._patch_get_browser_cls(side_effect=mock_get_browser_cls):
        self.run_cli("loading", "--browser=chrome", "--browser=firefox",
                     f"--driver-path={driver_path}", "--urls=http://test.com",
                     "--env-validation=skip", "--throw")
    self.assertIn("--driver-path", str(cm.exception))

  def test_env_config_invalid_file(self):
    config = pathlib.Path("/test.config.hjson")
    with self.cli() as cli:
      # No "env" property
      with config.open("w", encoding="utf-8") as f:
        hjson.dump({}, f)
      with self.assertRaises(SysExitTestException):
        cli.run([
            "loading", f"--env-config={config}", "--urls=http://test.com",
            "--env-validation=skip"
        ])
      # "env" not a dict
      with config.open("w", encoding="utf-8") as f:
        hjson.dump({"env": []}, f)
      with self.assertRaises(SysExitTestException):
        cli.run([
            "loading", f"--env-config={config}", "--urls=http://test.com",
            "--env-validation=skip"
        ])
      with config.open("w", encoding="utf-8") as f:
        hjson.dump({"env": {"unknown_property_name": 1}}, f)
      with self.assertRaises(SysExitTestException):
        cli.run([
            "loading", f"--env-config={config}", "--urls=http://test.com",
            "--env-validation=skip"
        ])

  def test_parse_env_config_file(self):
    config = pathlib.Path("/test.config.hjson")
    with config.open("w", encoding="utf-8") as f:
      hjson.dump({"env": {}}, f)
    with self._patch_get_browser():
      self.run_cli("loading", f"--env-config={config}",
                   "--urls=http://test.com", "--env-validation=skip")

  def test_env_invalid_inline_and_file(self):
    config = pathlib.Path("/test.config.hjson")
    with config.open("w", encoding="utf-8") as f:
      hjson.dump({"env": {}}, f)
    with self.assertRaises(SysExitTestException):
      self.run_cli("loading", "--env=strict", f"--env-config={config}",
                   "--urls=http://test.com", "--env-validation=skip")

  def test_invalid_splashscreen(self):
    with self.assertRaises(argparse.ArgumentError) as cm:
      self.run_cli("loading", "--browser=chrome", "--urls=http://test.com",
                   "--env-validation=skip", "--splash-screen=unknown-value",
                   "--throw")
    message = str(cm.exception)
    self.assertIn("--splash-screen", message)
    self.assertIn("unknown-value", message)

  def test_splash_screen_none(self):
    with self._patch_get_browser_cls():
      url = "http://test.com"
      cli = self.run_cli("loading", f"--urls={url}", "--env-validation=skip",
                         "--throw", "--splash-screen=none")
      for browser in cli.last_subcommand.runner.browsers:
        assert isinstance(browser, mock_browser.MockChromeStable)
        self.assertEqual(browser.settings.splash_screen, SplashScreen.NONE)
        self.assertListEqual([url], browser.url_list)
        self.assertEqual(len(browser.js_flags), 0)

  def test_splash_screen_minimal(self):
    with self._patch_get_browser_cls():
      url = "http://test.com"
      cli = self.run_cli("loading", f"--urls={url}", "--env-validation=skip",
                         "--throw", "--splash-screen=minimal")
      for browser in cli.last_subcommand.runner.browsers:
        assert isinstance(browser, mock_browser.MockChromeStable)
        self.assertEqual(browser.settings.splash_screen, SplashScreen.MINIMAL)
        self.assertEqual(len(browser.url_list), 3)
        self.assertIn(url, browser.url_list)
        self.assertEqual(len(browser.js_flags), 0)

  def test_splash_screen_url(self):
    with self._patch_get_browser_cls():
      splash_url = "http://splash.com"
      url = "http://test.com"
      cli = self.run_cli("loading", f"--urls={url}", "--env-validation=skip",
                         "--throw", f"--splash-screen={splash_url}")
      for browser in cli.last_subcommand.runner.browsers:
        assert isinstance(browser, mock_browser.MockChromeStable)
        self.assertIsInstance(browser.settings.splash_screen, URLSplashScreen)
        self.assertEqual(len(browser.url_list), 3)
        self.assertEqual(splash_url, browser.url_list[0])
        self.assertEqual(len(browser.js_flags), 0)

  def test_viewport_invalid(self):
    with self.assertRaises(argparse.ArgumentError) as cm:
      self.run_cli("loading", "--browser=chrome", "--urls=http://test.com",
                   "--env-validation=skip", "--viewport=-123", "--throw")
    message = str(cm.exception)
    self.assertIn("--viewport", message)
    self.assertIn("-123", message)

  def test_viewport_maximized(self):
    with self._patch_get_browser_cls():
      url = "http://test.com"
      cli = self.run_cli("loading", f"--urls={url}", "--env-validation=skip",
                         "--throw", "--viewport=maximized")
      for browser in cli.last_subcommand.runner.browsers:
        assert isinstance(browser, mock_browser.MockChromeStable)
        self.assertEqual(browser.viewport, viewport.Viewport.MAXIMIZED)
        self.assertEqual(len(browser.url_list), 3)
        self.assertEqual(len(browser.js_flags), 0)

  def test_powersampler_invalid_multiple_runs(self):
    powersampler_bin = self.out_dir / "powersampler"
    config_str = json.dumps({"bin_path": str(powersampler_bin)})
    with self._patch_get_browser_cls(), mock.patch.object(
        PowerSamplerProbe, "validate_browser"):
      with self.assertRaises(argparse.ArgumentTypeError) as cm:
        self.run_cli("loading", "--browser=chrome",
                     f"--probe=powersampler:{config_str}", "--repeat=10",
                     "--urls=http://test.com", "--env-validation=skip",
                     "--throw")
      self.assertIn("powersampler", str(cm.exception))

  def test_fast(self):
    with self._patch_get_browser_cls():
      url = "http://test.com"
      cli = self.run_cli("loading", f"--urls={url}", "--throw", "--fast")
      self.assertEqual(cli.args.splash_screen, SplashScreen.NONE)
      self.assertEqual(cli.args.cool_down_time, dt.timedelta(0))
      self.assertEqual(cli.args.env_validation, ValidationMode.SKIP)
      for browser in cli.last_subcommand.runner.browsers:
        assert isinstance(browser, mock_browser.MockChromeStable)
        self.assertIs(browser.settings.splash_screen, SplashScreen.NONE)
        self.assertListEqual(browser.url_list, [url])
        self.assertEqual(len(browser.js_flags), 0)

  def test_fast_startup_delay_input(self):
    with self._patch_get_browser_cls():
      url = "http://test.com"
      with mock.patch("builtins.input", return_value="") as mock_input:
        cli = self.run_cli("loading", "--startup-delay=input", f"--urls={url}",
                           "--throw", "--fast")
        self.assertEqual(len(mock_input.call_args_list), 1)
        self.assertIn("Press enter to continue...", mock_input.call_args[0][0])
      self.assertEqual(cli.args.cool_down_time, dt.timedelta(0))
      self.assertEqual(cli.args.start_delay, dt.timedelta.max)
      self.assertEqual(cli.args.stop_delay, dt.timedelta(0))

  def test_fast_custom_input_delays(self):
    with self._patch_get_browser_cls():
      url = "http://test.com"
      with mock.patch("builtins.input", return_value="") as mock_input:
        cli = self.run_cli("loading", "--startup-delay=input",
                           "--stop-delay=input", f"--urls={url}", "--throw",
                           "--fast")
        self.assertEqual(len(mock_input.call_args_list), 2)
        self.assertIn("Press enter to continue...",
                      mock_input.call_args_list[0].args[0])
        self.assertIn("Press enter to continue...",
                      mock_input.call_args_list[1].args[0])
      self.assertEqual(cli.args.cool_down_time, dt.timedelta(0))
      self.assertEqual(cli.args.start_delay, dt.timedelta.max)
      self.assertEqual(cli.args.stop_delay, dt.timedelta.max)

  def test_create_symlinks(self):
    with self._patch_get_browser_cls():
      out_dir = self.out_dir / "create_symlinks"
      self.assertFalse(out_dir.exists())
      url = "http://test.com"
      cli = self.run_cli("loading", f"--urls={url}", "--throw", "--fast",
                         f"--out-dir={out_dir}")
      self.assertTrue(cli.args.create_symlinks)
      links = list(out_dir.glob("*/sessions/*"))
      self.assertEqual(len(links), 1)
      self.assertTrue(links[0].is_symlink())
      links = list(out_dir.glob("*/stories/**/session"))
      self.assertEqual(len(links), 1)
      self.assertTrue(links[0].is_symlink())

  def test_no_symlinks(self):
    with self._patch_get_browser_cls():
      out_dir = self.out_dir / "no_symlinks"
      self.assertFalse(out_dir.exists())
      url = "http://test.com"
      cli = self.run_cli("loading", f"--urls={url}", "--throw", "--fast",
                         "--no-symlinks", f"--out-dir={out_dir}")
      self.assertFalse(cli.args.create_symlinks)
      for dirpath, dirnames, filenames in os.walk(out_dir):
        dirpath = pathlib.Path(dirpath)
        for name in dirnames + filenames:
          self.assertFalse((dirpath / name).is_symlink())

  def test_debug(self):
    with self._patch_get_browser_cls():
      url = "http://test.com"
      cli = self.run_cli("loading", f"--urls={url}", "--debug")
      self.assertTrue(cli.args.throw)
      self.assertEqual(cli.args.verbosity, 3)
      for browser in cli.last_subcommand.runner.browsers:
        assert isinstance(browser, mock_browser.MockChromeStable)
        self.assertEqual(len(browser.url_list), 3)
        self.assertEqual(len(browser.js_flags), 0)

  def test_debugger_not_found(self):
    searched_binaries = []
    original_search_binary = plt.PLATFORM.search_binary

    def mock_search_binary(binary) -> Optional[AnyPath]:
      searched_binaries.append(binary)
      if "gdb" in str(binary) or "lldb" in str(binary):
        return None
      return original_search_binary(binary)

    for debugger in ("lldb", "gdb", "lldb"):
      searched_binaries = []
      with self._patch_get_browser_cls(), mock.patch.object(
          plt.PLATFORM, "search_binary", side_effect=mock_search_binary):
        with self.assertRaises(ValueError) as cm:
          self.run_cli("loading", "--urls=cnn", f"--{debugger}", "--throw")
        self.assertIn(debugger, str(cm.exception))
        _, _, stderr = self.run_cli_output(
            "loading",
            "--urls=cnn",
            f"--{debugger}",
            raises=SysExitTestException)
        self.assertIn(f"Unknown binary: {debugger}", stderr)
        self.assertIn(pathlib.Path(debugger), searched_binaries)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
