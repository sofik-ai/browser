# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import abc
import argparse
import datetime as dt
from typing import Sequence

import pandas as pd
from typing_extensions import override

from crossbench.action_runner.default_action_runner import DefaultActionRunner
from crossbench.benchmarks.loading.playback_controller import \
    PlaybackController
from crossbench.benchmarks.loading.tab_controller import TabController
from crossbench.benchmarks.loadline import LoadLine1PhoneBenchmark, \
    LoadLine1TabletBenchmark, loadline_1
from crossbench.benchmarks.loadline.loadline import LoadLinePageFilter
from tests import test_helper
from tests.crossbench.base import BaseCliTestCase, BaseCrossbenchTestCase
from tests.crossbench.benchmarks.helper import SubStoryTestCase


# TODO(378584786): use shared helper mixin with TestPageLoadBenchmark
class BaseLoadLineBenchmarkTestCase(SubStoryTestCase, metaclass=abc.ABCMeta):

  @override
  def setUp(self):
    super().setUp()
    self.setup_loadline_configs()

  @override
  def story_filter(
      self,
      patterns: Sequence[str],
      separate: bool = True,
  ) -> LoadLinePageFilter:
    args = argparse.Namespace(
        about_blank_duration=dt.timedelta(),
        playback=PlaybackController.default(),
        tabs=TabController.default(),
        action_runner=DefaultActionRunner(),
        run_login=True,
        run_setup=True)
    story_filter = super().story_filter(patterns, args=args, separate=separate)
    assert isinstance(story_filter, LoadLinePageFilter)
    return story_filter

  def test_all_stories(self):
    # TODO: preload the story names from the config files
    stories = self.story_filter(["all"]).stories
    self.assertFalse(stories)

  def test_default_stories(self):
    # TODO: preload the story names from the config files
    stories = self.story_filter(["default"]).stories
    self.assertFalse(stories)

  def test_get_pages_config(self):
    config = self.benchmark_cls.get_pages_config()
    # Ensure it's cached
    self.assertIs(config, self.benchmark_cls.get_pages_config())

  def test_get_pages_config_variants(self):
    configs = [
        LoadLine1TabletBenchmark.get_pages_config(),
        LoadLine1PhoneBenchmark.get_pages_config()
    ]
    self.assertNotEqual(configs[0], configs[1])


class TestLoadLine1TabletBenchmark(BaseLoadLineBenchmarkTestCase):

  @property
  @override
  def benchmark_cls(self):
    return LoadLine1TabletBenchmark


class TestLoadLine1PhoneBenchmark(BaseLoadLineBenchmarkTestCase):

  @property
  @override
  def benchmark_cls(self):
    return LoadLine1PhoneBenchmark


class LoadLine1BenchmarkCliTestCase(BaseCliTestCase):

  def test_run_default_phone(self):
    # TODO(378584786): implement
    pass

  def test_run_default_tablet(self):
    # TODO(378584786): implement
    pass


class TestLoadLine1Helpers(BaseCrossbenchTestCase):

  def test_process_scores(self):
    query_result = pd.DataFrame(
        columns=["score", "cb_browser", "cb_story", "cb_temperature", "cb_run"],
        data=[[4, "chrome", "story1", 0, 0], [6, "chrome", "story1", 0, 1],
              [19, "chrome", "story2", 0, 0], [21, "chrome", "story2", 0, 1]])
    scores = loadline_1.process_scores(query_result)

    self.assertEqual(scores.shape, (1, 3))
    self.assertAlmostEqual(scores["TOTAL_SCORE"].iloc[0], 10)
    self.assertAlmostEqual(scores["story1"].iloc[0], 5)
    self.assertAlmostEqual(scores["story2"].iloc[0], 20)

  def test_process_breakdown(self):
    query_result = pd.DataFrame(
        columns=[
            "network", "process_launch", "renderer", "compositor", "gpu",
            "surfaceflinger", "cb_browser", "cb_story", "cb_temperature",
            "cb_run"
        ],
        data=[[5, 3, 9, 11, 10, 10, "chrome", "story1", 0, 0],
              [5, 3, 11, 9, 10, 10, "chrome", "story1", 0, 1],
              [7, 10, 19, 21, 20, 20, "chrome", "story2", 0, 0],
              [7, 10, 21, 19, 20, 20, "chrome", "story2", 0, 1]])
    breakdown = loadline_1.process_breakdown(query_result)

    self.assertEqual(breakdown.shape, (2, 5))
    self.assertAlmostEqual(breakdown["os"].iloc[0], 5)
    self.assertAlmostEqual(breakdown["os"].iloc[1], 10)
    self.assertAlmostEqual(breakdown["renderer"].iloc[0], 10)
    self.assertAlmostEqual(breakdown["renderer"].iloc[1], 20)
    self.assertAlmostEqual(breakdown["compositor"].iloc[0], 10)
    self.assertAlmostEqual(breakdown["compositor"].iloc[1], 20)
    self.assertAlmostEqual(breakdown["gpu"].iloc[0], 10)
    self.assertAlmostEqual(breakdown["gpu"].iloc[1], 20)
    self.assertAlmostEqual(breakdown["surfaceflinger"].iloc[0], 10)
    self.assertAlmostEqual(breakdown["surfaceflinger"].iloc[1], 20)


# Don't expose abstract base test cases.
del BaseLoadLineBenchmarkTestCase
del BaseCrossbenchTestCase
del BaseCliTestCase
del SubStoryTestCase

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
