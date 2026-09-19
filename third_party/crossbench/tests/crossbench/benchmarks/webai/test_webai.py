# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import copy
import json
from typing import TYPE_CHECKING
from unittest import mock

from typing_extensions import override

from crossbench.benchmarks.webai.webai import WebAIBenchmark, WebAIProbe, \
    WebAIProbeContext, WebAIStory
from crossbench.env.runner_env import EnvConfig, ValidationMode
from crossbench.runner.runner import Runner
from tests import test_helper
from tests.crossbench.benchmarks import helper

if TYPE_CHECKING:
  from tests.crossbench.mock_browser import MockBrowser


class WebAITestCase(helper.PressBaseBenchmarkTestCase):

  @property
  @override
  def benchmark_cls(self):
    return WebAIBenchmark

  @property
  @override
  def story_cls(self):
    return WebAIStory

  @property
  def probe_cls(self):
    return WebAIProbe

  @property
  def probe_context_cls(self):
    return WebAIProbeContext

  def _setup_run_js_expect(self, browser: MockBrowser,
                           probe_results: dict) -> None:
    # wait_js_condition for window.benchmarkClient
    browser.expect_js(result=True)
    # js client setup (testDone = false)
    browser.expect_js()
    # js startTest / button.click()
    browser.expect_js()
    # wait_js_condition for window.testDone
    browser.expect_js(result=True)
    # window.benchmarkClient.metrics
    browser.expect_js(result=json.dumps(probe_results))

  def test_run_default(self):
    # Prepare stories
    stories = self.story_cls.from_names(["webai_default"])
    benchmark = self.benchmark_cls(stories)
    self.assertTrue(len(benchmark.describe()) > 0)

    # Set up expectations for mock browsers
    probe_results = {
        "Score": 5678.9,
        "Total Time": {
            "average": 12.3,
            "stddev": 1.1
        }
    }

    repetitions = 2
    for _ in range(repetitions):
      for browser in self.browsers:
        self._setup_run_js_expect(browser, probe_results)

    for browser in self.browsers:
      browser.expected_js = copy.deepcopy(browser.expected_js)

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

    with mock.patch.object(self.benchmark_cls, "validate_url") as cm:
      runner.run()
    cm.assert_called_once()

    # Verification
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertEqual(len(urls), repetitions)
      self.assertIn(self.story_cls.URL, urls)
      self.assertListEqual(browser.expected_js, [])

    # Check log output
    with self.assertLogs(level="INFO") as log_cm:
      for probe in runner.probes:
        for run in runner.runs:
          probe.log_run_result(run)
    output = "\n".join(log_cm.output)
    self.assertIn("WebAI results", output)
    self.assertIn("Score", output)

  def test_run_custom_url(self):
    custom_url = "http://test.example.com/webai"
    stories = self.story_cls.from_names(["webai_default"], url=custom_url)
    benchmark = self.benchmark_cls(stories)

    probe_results = {"Score": 1234.5}
    repetitions = 1
    for _ in range(repetitions):
      for browser in self.browsers:
        self._setup_run_js_expect(browser, probe_results)

    for browser in self.browsers:
      browser.expected_js = copy.deepcopy(browser.expected_js)

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

    with mock.patch.object(self.benchmark_cls, "validate_url") as cm:
      runner.run()
    cm.assert_called_once()

    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertEqual(len(urls), repetitions)
      self.assertIn(custom_url, urls)
      self.assertListEqual(browser.expected_js, [])


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
