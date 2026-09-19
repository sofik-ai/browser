# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from crossbench.runner.groups.browsers import BrowsersRunGroup
from crossbench.runner.groups.cache_temperatures import \
    CacheTemperaturesRunGroup
from crossbench.runner.groups.repetitions import RepetitionsRunGroup
from crossbench.runner.groups.stories import StoriesRunGroup
from tests import test_helper
from tests.crossbench.runner.groups.base import BaseRunGroupTestCase
from tests.crossbench.runner.helper import MockRun

if TYPE_CHECKING:
  from crossbench.runner.run import Run


class RunGroupTestCase(BaseRunGroupTestCase):

  def create_groups(self, runs: Iterable[Run], throw: bool = True):
    cache_temperatures_groups = CacheTemperaturesRunGroup.groups(
        runs, throw=throw)
    repetitions_groups = RepetitionsRunGroup.groups(cache_temperatures_groups,
                                                    throw)
    story_groups = StoriesRunGroup.groups(repetitions_groups, throw)
    browser_group = BrowsersRunGroup(story_groups, throw)
    return browser_group

  def test_create_empty(self):
    with self.assertRaises(ValueError):
      self.create_groups([])

  def test_create_single(self):
    session = self.default_session(throw=True)
    run_0 = MockRun(self.runner, session, "story 0")
    browser_group = self.create_groups([run_0])
    self.assertListEqual(list(browser_group.runs), [run_0])
    story_groups = list(browser_group.story_groups)
    self.assertEqual(len(story_groups), 1)
    self.assertListEqual(list(story_groups[0].runs), [run_0])
    repetitions_group = list(story_groups[0].repetitions_groups)
    self.assertEqual(len(repetitions_group), 1)

  def test_single_story_multiple_repetitions(self):
    session = self.default_session(throw=True)
    run_0 = MockRun(self.runner, session, "story 0", None, repetition=0)
    run_1 = MockRun(self.runner, session, "story 0", None, repetition=1)
    browser_group = self.create_groups([run_0, run_1])
    self.assertListEqual(list(browser_group.runs), [run_0, run_1])
    story_groups = list(browser_group.story_groups)
    self.assertEqual(len(story_groups), 1)
    repetitions_groups = list(story_groups[0].repetitions_groups)
    self.assertEqual(len(repetitions_groups), 1)
    repetitions_group = repetitions_groups[0]
    cache_temp_groups = list(repetitions_group.cache_temperatures_groups)
    self.assertEqual(len(cache_temp_groups), 2)
    self.assertListEqual(list(cache_temp_groups[0].runs), [run_0])
    self.assertListEqual(list(cache_temp_groups[1].runs), [run_1])
    cache_temp_repetitions_group = list(
        repetitions_group.cache_temperature_repetitions_groups)
    self.assertEqual(len(cache_temp_repetitions_group), 1)
    self.assertListEqual(
        list(cache_temp_repetitions_group[0].runs), [run_0, run_1])
    self.assertEqual(cache_temp_repetitions_group[0].cache_temperature,
                     "default")

  def test_single_story_multiple_repetitions_cache_temperatures(self):
    session = self.default_session(throw=True)
    run_0 = MockRun(
        self.runner, session, "story 0", None, repetition=0, temperature="cold")
    run_1 = MockRun(
        self.runner, session, "story 0", None, repetition=0, temperature="warm")
    run_2 = MockRun(
        self.runner, session, "story 0", None, repetition=1, temperature="cold")
    run_3 = MockRun(
        self.runner, session, "story 0", None, repetition=1, temperature="warm")

    browser_group = self.create_groups([run_0, run_1, run_2, run_3])
    self.assertListEqual(list(browser_group.runs), [run_0, run_1, run_2, run_3])
    story_groups = list(browser_group.story_groups)
    self.assertEqual(len(story_groups), 1)
    repetitions_groups = list(story_groups[0].repetitions_groups)
    self.assertEqual(len(repetitions_groups), 1)
    repetitions_group = repetitions_groups[0]
    cache_temp_groups = list(repetitions_group.cache_temperatures_groups)
    self.assertEqual(len(cache_temp_groups), 2)
    self.assertListEqual(list(cache_temp_groups[0].runs), [run_0, run_1])
    self.assertListEqual(list(cache_temp_groups[1].runs), [run_2, run_3])
    cache_temp_repetitions_group = list(
        repetitions_group.cache_temperature_repetitions_groups)
    self.assertEqual(len(cache_temp_groups), 2)
    self.assertListEqual(
        list(cache_temp_repetitions_group[0].runs), [run_0, run_2])
    self.assertListEqual(
        list(cache_temp_repetitions_group[1].runs), [run_1, run_3])
    self.assertEqual(cache_temp_repetitions_group[0].cache_temperature, "cold")
    self.assertEqual(cache_temp_repetitions_group[1].cache_temperature, "warm")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
