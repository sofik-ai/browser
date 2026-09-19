# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse
import json
import pathlib
from typing import TYPE_CHECKING, Type
from unittest import mock

import hjson

from crossbench.browsers.settings import Settings
from crossbench.cli.cli import CrossBenchCLI
from crossbench.cli.config.driver import BrowserDriverType
from crossbench.cli.subcommand.benchmark import BenchmarkSubcommand
from crossbench.network.local_file_server import LocalFileNetwork
from crossbench.probes.internal.summary import ResultsSummaryProbe
from tests import test_helper
from tests.crossbench import mock_browser
from tests.crossbench.base import BaseCliTestCase, SysExitTestException

if TYPE_CHECKING:
  from crossbench.browsers.browser import Browser
  from crossbench.cli.config.browser import BrowserConfig
  from tests.crossbench.mock_helper import MockCLI


class CliSlowTestCase(BaseCliTestCase):
  """Collection of slower tests that are not worth running
  as part of the presubmit"""

  def get_test_subcommands(self, benchmark_cls) -> tuple[str, ...]:
    subcommands = (benchmark_cls.NAME,)
    # Only test one alias for speeding up testing:
    if aliases := benchmark_cls.aliases():
      subcommands = subcommands + (aliases[0],)
    return subcommands

  def test_subcommand_help(self):
    with self.cli() as cli:
      for benchmark_cls in CrossBenchCLI.BENCHMARKS:
        subcommands = self.get_test_subcommands(benchmark_cls)
        for subcommand in subcommands:
          self.verify_subcommand_help(cli, subcommand)

  def verify_subcommand_help(self, cli, subcommand):
    with self.assertRaises(SysExitTestException) as cm:
      cli.run([subcommand, "--help"])
    self.assertEqual(cm.exception.exit_code, 0)

    with self.capture_io() as io_capture:
      with self.assertRaises(SysExitTestException):
        cli.run([subcommand, "--help"])
    self.assertFalse(io_capture.stderr)
    self.assertIn("--env-validation ENV_VALIDATION", io_capture.stdout)

  def test_subcommand_describe_subcommand(self):
    with self.cli() as cli:
      for benchmark_cls in CrossBenchCLI.BENCHMARKS:
        subcommands = self.get_test_subcommands(benchmark_cls)
        for subcommand in subcommands:
          print(subcommand)
          self.verify_subcommand_describe_subcommand(cli, subcommand)

  def verify_subcommand_describe_subcommand(self, cli: MockCLI,
                                            subcommand: str):
    with self.assertRaises(SysExitTestException) as cm:
      cli.run([subcommand, "describe"])
    self.assertEqual(cm.exception.exit_code, 0)

    with self.capture_io() as io_capture:
      with self.assertRaises(SysExitTestException):
        cli.run([subcommand, "describe"])
    output = io_capture.stderr + io_capture.stdout
    self.assertIn(subcommand, output)
    self.assertIn("See `", output)
    self.assertIn(" --help`", output)

  def test_browser_identifiers(self):
    # Use BrowserAliasesTestCase for more detailed aliases
    browsers: dict[str, Type[mock_browser.MockBrowser]] = {
        "chrome": mock_browser.MockChromeStable,
        "edge": mock_browser.MockEdgeStable,
        "firefox": mock_browser.MockFirefox,
    }
    if self.platform.is_macos:
      browsers.update({
          "safari": mock_browser.MockSafari,
      })

    items_chunk: list[tuple[str, Type[mock_browser.MockBrowser]]] = list(
        browsers.items())
    with self.cli() as cli:
      for identifier, browser_cls in items_chunk:
        self.verify_browser_identifier(cli, identifier, browser_cls)

  def verify_browser_identifier(self, cli, identifier, browser_cls):
    out_dir = self.out_dir / identifier
    self.assertFalse(out_dir.exists())
    with self._patch_get_browser_cls(browser_cls) as get_browser_cls:
      url = "http://test.com"
      cli.run([
          "loading", f"--browser={identifier}", f"--urls={url}",
          "--env-validation=skip", f"--out-dir={out_dir}"
      ])
      self.assertTrue(out_dir.exists())
      get_browser_cls.assert_called_once()
      result_files = list(out_dir.glob(f"**/{ResultsSummaryProbe.NAME}.json"))
      result_file = result_files[1]
      with result_file.open(encoding="utf-8") as f:
        results = json.load(f)
      self.assertEqual(results["browser"]["version"], browser_cls.VERSION)
      self.assertIn("test.com", results["stories"])

  def test_config_file_with_network(self):
    local_server_path = pathlib.Path("custom/server")
    local_server_path.mkdir(parents=True)
    self.fs.create_file(local_server_path / "index.html", st_size=100)
    config_file = pathlib.Path("/config.hjson")
    config_data = {
        "probes": {},
        "env": {},
        "browsers": {},
        "network": str(local_server_path),
    }
    with config_file.open("w", encoding="utf-8") as f:
      hjson.dump(config_data, f)

    browsers: list[Browser] = []

    def get_browser(self, args: argparse.Namespace):
      session = Settings(
          platform=self.cli.platform,
          network=args.network.create(self.cli.platform))
      browsers = [
          mock_browser.MockChromeDev("dev", settings=session),
      ]
      return browsers

    with (mock.patch.object(BenchmarkSubcommand, "_get_browsers", get_browser),
          mock.patch.object(LocalFileNetwork, "_open_local_file_server") as
          mock_network_open):
      url = "http://test.com"
      self.run_cli("loading", f"--config={config_file}", f"--urls={url}",
                   "--env-validation=skip")
      mock_network_open.assert_called_once()
      for browser in browsers:
        self.assertListEqual([url], browser.url_list[self.SPLASH_URLS_LEN:])
        assert isinstance(browser.network, LocalFileNetwork)
        network: LocalFileNetwork = browser.network
        self.assertFalse(network.is_live)
        self.assertEqual(network.path, local_server_path)

  def test_multiple_browser_compatible_flags(self):
    mock_browsers: list[Type[mock_browser.MockBrowser]] = [
        mock_browser.MockChromeStable,
        mock_browser.MockFirefox,
        mock_browser.MockChromeDev,
    ]

    def mock_get_browser_cls(browser_config: BrowserConfig):
      self.assertEqual(browser_config.driver.type, BrowserDriverType.WEB_DRIVER)
      for mock_browser_cls in mock_browsers:
        if mock_browser_cls.mock_app_path(self.platform) == browser_config.path:
          return mock_browser_cls
      raise ValueError("Unknown browser path")

    with self.cli() as cli:
      for chrome_flag in ("--js-flags=--no-opt", "--enable-features=Foo",
                          "--disable-features=bar"):
        # Fail for chrome flags for non-chrome browser
        with self.assertRaises(
            argparse.ArgumentTypeError), self._patch_get_browser_cls(
                side_effect=mock_get_browser_cls):
          cli.run([
              "loading", "--urls=http://test.com", "--env-validation=skip",
              "--throw", "--browser=firefox", chrome_flag
          ])
        # Fail for mixed browsers and chrome flags
        with self.assertRaises(
            argparse.ArgumentTypeError), self._patch_get_browser_cls(
                side_effect=mock_get_browser_cls):
          cli.run([
              "loading", "--urls=http://test.com", "--env-validation=skip",
              "--throw", "--browser=chrome", "--browser=firefox", chrome_flag
          ])
        with self.assertRaises(
            argparse.ArgumentTypeError), self._patch_get_browser_cls(
                side_effect=mock_get_browser_cls):
          cli.run([
              "loading", "--urls=http://test.com", "--env-validation=skip",
              "--throw", "--browser=chrome", "--browser=firefox", "--",
              chrome_flag
          ])
      # Flags for the same type are allowed.
      with self._patch_get_browser():
        cli.run([
            "loading", "--urls=http://test.com", "--env-validation=skip",
            "--throw", "--browser=chrome", "--browser=chrome-dev", "--",
            "--js-flags=--no-opt"
        ])


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
