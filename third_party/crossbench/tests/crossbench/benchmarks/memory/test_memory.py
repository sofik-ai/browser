# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse
import copy
import csv

from typing_extensions import override

from crossbench.benchmarks.loading.page.live import LivePage
from crossbench.benchmarks.loading.tab_controller import TabController
from crossbench.benchmarks.memory.memory_benchmark import MemoryBenchmark, \
    MemoryBenchmarkStoryFilter, MemoryProbe
from crossbench.env.runner_env import EnvConfig, ValidationMode
from crossbench.runner.runner import Runner
from tests import test_helper
from tests.crossbench.benchmarks import helper


class MemoryBenchmarkTestCase(helper.BaseBenchmarkTestCase):

  @property
  @override
  def benchmark_cls(self):
    return MemoryBenchmark

  @property
  @override
  def story_cls(self):
    return MemoryBenchmarkStoryFilter

  @property
  def probe_cls(self):
    return MemoryProbe

  def _create_stories(self, tab_count):
    args = argparse.Namespace(
        alloc_count=8,
        prefill_constant=8,
        compressibility=50,
        random_per_page=False,
        block_size=128,
        tabs=TabController.repeat(tab_count),
        action_runner_config=None)
    stories = self.story_cls.stories_from_cli_args(args=args)
    return stories

  def test_story(self):
    stories = self._create_stories(tab_count=2)
    self.assertEqual(len(stories), 1)
    story = stories[0]
    self.assertIsInstance(story, LivePage)
    expected_url = ("https://chromium-workloads.web.app/web-tests/main/"
                    "synthetic/memory?alloc=8&blocksize=128&compress=50"
                    "&prefill=8&randomperpage=false")
    self.assertEqual(story.first_url, expected_url)
    names = {story.name for story in stories}
    self.assertEqual(len(names), len(stories))

  def test_run_throw(self):
    self._test_run(throw=True)

  def test_run_default(self):
    self._test_run()

  def _test_run(self, throw: bool = False):
    tab_count = 2
    repetitions = 2
    stories = self._create_stories(tab_count=tab_count)
    for _ in range(repetitions):
      for _ in stories:
        for browser in self.browsers:
          # wait for ready state
          browser.expect_js(result=True)
          # Record navigation time
          browser.expect_js(result="1000")

          # wait for ready state
          browser.expect_js(result=True)
          # Record navigation time
          browser.expect_js(result="1001")
    for browser in self.browsers:
      browser.expected_js = copy.deepcopy(browser.expected_js)

    benchmark = self.benchmark_cls(stories, skippable_tab_count=2)
    self.assertTrue(len(benchmark.describe()) > 0)
    runner = Runner(
        self.out_dir,
        self.browsers,
        benchmark,
        env_config=EnvConfig(),
        env_validation_mode=ValidationMode.SKIP,
        platform=self.platform,
        repetitions=repetitions,
        throw=throw,
        in_memory_result_db=True)

    runner.run()
    assert runner.is_success
    story_urls = [story.first_url for story in stories]
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertEqual(len(urls), repetitions * tab_count)
      self.assertEqual(story_urls * repetitions * tab_count, urls)
      self.assertEqual(len(browser.tab_list) - 1, repetitions * tab_count)
      self.assertEqual(browser.tab_list, [0, 1, 2, 3, 4])

    with (self.out_dir /
          f"{self.probe_cls.NAME}.csv").open(encoding="utf-8") as f:
      csv_data = list(csv.DictReader(f, delimiter="\t"))
    self.assertListEqual(
        list(csv_data[0].keys()), ["label", "", "dev", "stable"])
    self.assertDictEqual(
        csv_data[1],
        {
            "label": "version",
            "dev": "102.22.33.44",
            "stable": "100.22.33.44",
            # One padding element (after "label"):
            "": "",
        })

    with self.assertLogs(level="INFO") as cm:
      for probe in runner.probes:
        for run in runner.runs:
          probe.log_run_result(run)
    output = "\n".join(cm.output)
    self.assertIn("Memory results", output)
    self.assertIn(f"Score {tab_count}", output)

    with self.assertLogs(level="INFO") as cm:
      for probe in runner.probes:
        probe.log_browsers_result(runner.browser_group)
    output = "\n".join(cm.output)
    self.assertIn("Memory results", output)
    self.assertIn("102.22.33.44", output)
    self.assertIn("100.22.33.44", output)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
