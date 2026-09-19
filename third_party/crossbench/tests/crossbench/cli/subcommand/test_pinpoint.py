# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
import unittest
from unittest import mock

from crossbench import path as pth
from crossbench.cli.cli import CrossBenchCLI
from crossbench.cli.subcommand.pinpoint import PinpointHelpFormatter
from crossbench.pinpoint.config import BisectEndVariantConfig, \
    BisectStartVariantConfig, PinpointBisectJobConfig, PinpointTryJobConfig, \
    VariantConfig
from crossbench.pinpoint.user import UserEnum
from tests import test_helper


class PinpointSubcommandTest(unittest.TestCase):
  """Verifies that subcommands call the right functions."""

  def setUp(self):
    super().setUp()
    self.cli = CrossBenchCLI()
    self.mock_print = self.enterContext(mock.patch("builtins.print"))
    self.mock_init_metrics = self.enterContext(
        mock.patch("crossbench.cli.subcommand.pinpoint.init_metrics"))
    self.mock_collect_metrics = self.enterContext(
        mock.patch("crossbench.cli.subcommand.pinpoint.collect_metrics"))

  @mock.patch("crossbench.cli.subcommand.pinpoint.list_jobs")
  def test_pinpoint_user_metrics(self, _mock_list_job):
    self.cli.run(["pinpoint", "list", "-n", "100"])
    self.mock_init_metrics.assert_called_once_with()
    self.mock_collect_metrics.assert_called_once_with("list")

  @mock.patch("crossbench.cli.subcommand.pinpoint.list_jobs")
  def test_pinpoint_list(self, mock_list_job):
    self.cli.run([
        "pinpoint",
        "list",
        "--user",
        "all",
        "--number",
        "100",
        "--format",
        "csv",
        "--truncate",
        "50",
        "--extra-columns",
        "bug",
        "--extra-columns",
        "story",
    ])
    mock_list_job.assert_called_once_with(
        user=UserEnum.ALL,
        number=100,
        truncate=50,
        output_format="csv",
        extra_columns=["bug", "story"])

  @mock.patch("crossbench.cli.subcommand.pinpoint.fetch_bots")
  def test_pinpoint_bots_prints_filtered_bots(self, mock_fetch_bots):
    mock_fetch_bots.return_value = [
        "linux-r350-perf", "win-10-perf", "win-11-perf"
    ]
    self.cli.run(["pinpoint", "bots", "--filter", "win"])
    self.mock_print.assert_called_once_with("win-10-perf\nwin-11-perf")

  @mock.patch("crossbench.cli.subcommand.pinpoint.fetch_benchmarks")
  def test_pinpoint_benchmarks_prints_filtered_benchmarks(
      self, mock_fetch_benchmarks):
    mock_fetch_benchmarks.return_value = [
        "speedometer2", "speedometer3", "jetstream2"
    ]
    self.cli.run(["pinpoint", "benchmarks", "--filter", "speedometer"])
    self.mock_print.assert_called_once_with("speedometer2\nspeedometer3")

  @mock.patch("crossbench.cli.subcommand.pinpoint.fetch_stories")
  def test_pinpoint_benchmarks_prints_filtered_stories(self,
                                                       mock_fetch_stories):
    mock_fetch_stories.return_value = ["story1", "story2", "default"]
    self.cli.run(["pinpoint", "stories", "speedometer3", "--filter", "story"])
    mock_fetch_stories.assert_called_once_with("speedometer3")
    self.mock_print.assert_called_once_with("story1\nstory2")

  @mock.patch("crossbench.cli.subcommand.pinpoint.list_builds")
  def test_pinpoint_list_builds(self, mock_list_builds):
    self.cli.run(["pinpoint", "builds", "linux-r350-perf", "--limit", "42"])
    mock_list_builds.assert_called_once_with("linux-r350-perf", 42)

  @mock.patch("crossbench.cli.subcommand.pinpoint.start_job")
  @mock.patch(
      "crossbench.pinpoint.config.PinpointTryJobConfig.parse_and_override")
  def test_pinpoint_start_job(self, mock_parse_and_override, mock_start_job):
    test_config = PinpointTryJobConfig(
        benchmark="speedometer3",
        bot="linux-r350-perf",
        story="default",
        story_tags="tag1,tag2",
        repeat=42,
        bug="12345",
        base=VariantConfig(
            commit="HEAD",
            patch="https://base.patch",
        ),
        experiment=VariantConfig(
            commit="recent",
            patch="https://exp.patch",
        ),
    )
    mock_parse_and_override.return_value = test_config
    self.cli.run([
        *["pinpoint", "start"],
        *["--config", "{benchmark: 'speedometer3', bot: 'linux-r350-perf'}"],
        *["--benchmark", "speedometer3"],
        *["--bot", "linux-r350-perf"],
        *["--story", "default"],
        *["--story-tags", "tag1,tag2"],
        *["--repeat", "42"],
        *["--bug", "12345"],
        *["--base-commit", "HEAD"],
        *["--exp-commit", "recent"],
        *["--base-patch", "http://base.patch"],
        *["--exp-patch", "http://exp.patch"],
        "--base-js-flags=--flag1",
        "--exp-js-flags=--flag2",
        *["--base-enable-features", "base_feat"],
        *["--exp-enable-features", "exp_feat"],
        *["--base-disable-features", "base_dis"],
        *["--exp-disable-features", "exp_dis"],
    ])
    mock_parse_and_override.assert_called_once_with(
        config="{benchmark: 'speedometer3', bot: 'linux-r350-perf'}",
        benchmark="speedometer3",
        bot="linux-r350-perf",
        story="default",
        story_tags="tag1,tag2",
        repeat=42,
        bug=12345,
        base_commit="HEAD",
        exp_commit="recent",
        base_patch="http://base.patch",
        exp_patch="http://exp.patch",
        base_js_flags="--flag1",
        exp_js_flags="--flag2",
        base_enable_features="base_feat",
        exp_enable_features="exp_feat",
        base_disable_features="base_dis",
        exp_disable_features="exp_dis",
    )
    mock_start_job.assert_called_with(test_config)

  @mock.patch("crossbench.cli.subcommand.pinpoint.bisect_job")
  @mock.patch(
      "crossbench.pinpoint.config.PinpointBisectJobConfig.parse_and_override")
  def test_pinpoint_bisect_job(self, mock_parse_and_override, mock_bisect_job):
    test_config = PinpointBisectJobConfig(
        benchmark="speedometer3",
        bot="linux-r350-perf",
        chart="my_chart",
        story="default",
        story_tags="tag1,tag2",
        repeat=42,
        bug="12345",
        start=BisectStartVariantConfig(
            commit="HEAD",
        ),
        end=BisectEndVariantConfig(
            commit="recent",
        ),
    )
    mock_parse_and_override.return_value = test_config
    self.cli.run([
        *["pinpoint", "bisect"],
        *["--config", "{benchmark: 'speedometer3', bot: 'linux-r350-perf'}"],
        *["--benchmark", "speedometer3"],
        *["--bot", "linux-r350-perf"],
        *["--chart", "my_chart"],
        *["--story", "default"],
        *["--story-tags", "tag1,tag2"],
        *["--repeat", "42"],
        *["--bug", "12345"],
        *["--start-commit", "HEAD"],
        *["--end-commit", "recent"],
        "--js-flags=--flag1",
        *["--enable-features", "base_feat"],
        *["--disable-features", "base_dis"],
    ])
    mock_parse_and_override.assert_called_once_with(
        config="{benchmark: 'speedometer3', bot: 'linux-r350-perf'}",
        benchmark="speedometer3",
        bot="linux-r350-perf",
        chart="my_chart",
        story="default",
        story_tags="tag1,tag2",
        repeat=42,
        bug=12345,
        start_commit="HEAD",
        end_commit="recent",
        js_flags="--flag1",
        enable_features="base_feat",
        disable_features="base_dis",
    )
    mock_bisect_job.assert_called_with(test_config)

  @mock.patch("crossbench.cli.subcommand.pinpoint.start_job")
  @mock.patch(
      "crossbench.pinpoint.config.PinpointTryJobConfig.parse_and_override")
  def test_pinpoint_start_job_js_flags(self, mock_parse_and_override,
                                       _mock_start_job):
    test_config = PinpointTryJobConfig(
        benchmark="speedometer3", bot="linux-r350-perf")
    mock_parse_and_override.return_value = test_config

    self.cli.run([
        *["pinpoint", "start"],
        *["--benchmark", "speedometer3"],
        "--js-flags=--flag1",
    ])

    self.assertEqual(
        {
            key: value
            for key, value in mock_parse_and_override.call_args.kwargs.items()
            if value is not None
        }, {
            "benchmark": "speedometer3",
            "base_js_flags": "--flag1",
            "exp_js_flags": "--flag1",
        })

  @mock.patch("crossbench.cli.subcommand.pinpoint.start_job")
  @mock.patch(
      "crossbench.pinpoint.config.PinpointTryJobConfig.parse_and_override")
  def test_pinpoint_start_job_enable_features(self, mock_parse_and_override,
                                              _mock_start_job):
    test_config = PinpointTryJobConfig(
        benchmark="speedometer3", bot="linux-r350-perf")
    mock_parse_and_override.return_value = test_config

    self.cli.run([
        *["pinpoint", "start"],
        *["--benchmark", "speedometer3"],
        "--enable-features=Feature1",
    ])

    self.assertEqual(
        {
            key: value
            for key, value in mock_parse_and_override.call_args.kwargs.items()
            if value is not None
        }, {
            "benchmark": "speedometer3",
            "base_enable_features": "Feature1",
            "exp_enable_features": "Feature1",
        })

  @mock.patch("crossbench.cli.subcommand.pinpoint.start_job")
  @mock.patch(
      "crossbench.pinpoint.config.PinpointTryJobConfig.parse_and_override")
  def test_pinpoint_start_job_disable_features(self, mock_parse_and_override,
                                               _mock_start_job):
    test_config = PinpointTryJobConfig(
        benchmark="speedometer3", bot="linux-r350-perf")
    mock_parse_and_override.return_value = test_config

    self.cli.run([
        *["pinpoint", "start"],
        *["--benchmark", "speedometer3"],
        "--disable-features=Feature1",
    ])

    self.assertEqual(
        {
            key: value
            for key, value in mock_parse_and_override.call_args.kwargs.items()
            if value is not None
        }, {
            "benchmark": "speedometer3",
            "base_disable_features": "Feature1",
            "exp_disable_features": "Feature1",
        })

  @mock.patch("crossbench.cli.subcommand.pinpoint.start_job")
  @mock.patch(
      "crossbench.pinpoint.config.PinpointTryJobConfig.parse_and_override")
  def test_pinpoint_start_job_commit(self, mock_parse_and_override,
                                     _mock_start_job):
    test_config = PinpointTryJobConfig(
        benchmark="speedometer3", bot="linux-r350-perf")
    mock_parse_and_override.return_value = test_config

    self.cli.run([
        *["pinpoint", "start"],
        *["--benchmark", "speedometer3"],
        "--commit=1234567890",
    ])

    self.assertEqual(
        {
            key: value
            for key, value in mock_parse_and_override.call_args.kwargs.items()
            if value is not None
        }, {
            "benchmark": "speedometer3",
            "base_commit": "1234567890",
            "exp_commit": "1234567890",
        })

  @mock.patch("crossbench.cli.subcommand.pinpoint.start_job")
  @mock.patch(
      "crossbench.pinpoint.config.PinpointTryJobConfig.parse_and_override")
  def test_pinpoint_start_job_by_benchmark(self, mock_parse_and_override,
                                           mock_start_job):
    test_config = PinpointTryJobConfig(
        benchmark="speedometer3.1.crossbench", bot="win-11-perf")
    mock_parse_and_override.return_value = test_config
    self.cli.run(["pinpoint", "sp3", "--bot", "win-11-perf"])
    mock_parse_and_override.assert_called_once_with(
        benchmark="speedometer3.1.crossbench",
        bot="win-11-perf",
        config=None,
        story=None,
        story_tags=None,
        repeat=None,
        bug=None,
        base_commit=None,
        exp_commit=None,
        base_patch=None,
        exp_patch=None,
        base_js_flags=None,
        exp_js_flags=None,
        base_enable_features=None,
        exp_enable_features=None,
        base_disable_features=None,
        exp_disable_features=None,
    )
    mock_start_job.assert_called_with(test_config)

  @mock.patch("crossbench.cli.subcommand.pinpoint.print_job_config")
  def test_pinpoint_job_config(self, mock_print_job_config):
    self.cli.run(["pinpoint", "config", "123abc", "--raw", "--full"])
    mock_print_job_config.assert_called_once_with(
        job_id="123abc", raw=True, full=True)

    mock_print_job_config.reset_mock()
    self.cli.run(["pinpoint", "config", "123abc"])
    mock_print_job_config.assert_called_once_with(
        job_id="123abc", raw=False, full=False)

  def test_pinpoint_job_config_full_without_raw(self):
    with self.assertRaises(ValueError):
      self.cli.run(["pinpoint", "config", "123abc", "--full"])

  @mock.patch("crossbench.cli.subcommand.pinpoint.cancel_job")
  def test_pinpoint_cancel_job(self, mock_cancel_job):
    self.cli.run(
        ["pinpoint", "cancel", "--job", "123abc", "--reason", "test reason"])
    mock_cancel_job.assert_called_once_with(
        job_id="123abc", reason="test reason")

  @mock.patch("crossbench.cli.subcommand.pinpoint.cancel_job")
  def test_pinpoint_cancel_job_positional_job_id(self, mock_cancel_job):
    self.cli.run(["pinpoint", "cancel", "123abc", "--reason", "test reason"])
    mock_cancel_job.assert_called_once_with(
        job_id="123abc", reason="test reason")

  def test_pinpoint_cancel_job_positional_and_explicit_job_id(self):
    with self.assertRaises(SystemExit) as cm:
      self.cli.run([
          "pinpoint", "cancel", "123abc", "--job", "123abc", "--reason",
          "test reason"
      ])
    self.assertEqual(cm.exception.code, 2)

  def test_pinpoint_cancel_without_job(self):
    with self.assertRaises(SystemExit) as cm:
      self.cli.run(["pinpoint", "cancel", "--reason", "test reason"])
    self.assertEqual(cm.exception.code, 2)

  @mock.patch("crossbench.cli.subcommand.pinpoint.download_results")
  def test_pinpoint_download_results(self, mock_download_results):
    self.cli.run(
        ["pinpoint", "results", "123abc", "--out-dir", "test_dir", "--force"])
    mock_download_results.assert_called_once_with(
        job_id="123abc", out_dir=pth.LocalPath("test_dir"), force=True)

  def test_help_formatter(self):
    parser = argparse.ArgumentParser(
        formatter_class=PinpointHelpFormatter, allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="action")
    subparsers.add_parser("list", help="Command")
    subparsers.add_parser("speedometer_main", help="Benchmark")

    help_text = parser.format_help()

    self.assertRegex(help_text, r"(?s)list.*Benchmarks:.*speedometer_main")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
