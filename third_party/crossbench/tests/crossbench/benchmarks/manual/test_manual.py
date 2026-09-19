# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import datetime as dt
from typing import Optional
from unittest import mock

from typing_extensions import override

from crossbench.benchmarks.manual.manual_benchmark import ManualBenchmark
from crossbench.env.runner_env import EnvConfig, ValidationMode
from crossbench.runner.runner import Runner
from tests import test_helper
from tests.crossbench.benchmarks.helper import BaseBenchmarkTestCase


class TestManualBenchmark(BaseBenchmarkTestCase):

  @property
  @override
  def benchmark_cls(self):
    return ManualBenchmark

  def test_run_default(self):
    with mock.patch("builtins.input", lambda *args: "y"):
      self._test_run()
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      # No automatic URLS.
      self.assertFalse(urls)

  def test_run_auto_start(self):
    with mock.patch("builtins.input", lambda *args: "y"):
      self._test_run(start_after=dt.timedelta(seconds=0.2))
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      # No automatic URLS.
      self.assertFalse(urls)

  def test_run_custom_duration(self):
    with mock.patch("builtins.input", lambda *args: "y"):
      self._test_run(run_for=dt.timedelta(seconds=0.2))
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      # No automatic URLS.
      self.assertFalse(urls)

  def _test_run(self,
                start_after: Optional[dt.timedelta] = None,
                run_for: Optional[dt.timedelta] = None):
    repetitions = 3
    benchmark = ManualBenchmark(None, start_after, run_for)
    self.assertTrue(len(benchmark.describe()) > 0)
    runner = Runner(
        self.out_dir,
        self.browsers,
        benchmark,
        env_config=EnvConfig(),
        env_validation_mode=ValidationMode.SKIP,
        platform=self.platform,
        repetitions=repetitions,
        throw=True,
        in_memory_result_db=True)

    with self.assertLogs(level="INFO") as cm:
      runner.run()
    output = "\n".join(cm.output)
    self.assertIn("Starting Manual Benchmark", output)

    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      # No automatic URLS.
      self.assertFalse(urls)


del BaseBenchmarkTestCase

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
