# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse
import datetime as dt
import unittest
from typing import TYPE_CHECKING

from typing_extensions import override

from crossbench.benchmarks.base import PressBenchmarkStoryFilter, \
    RangePatternError, RegexFilter
from crossbench.stories.press_benchmark import PressBenchmarkStory
from tests import test_helper

if TYPE_CHECKING:
  from crossbench.runner.run import Run


class MockStory(PressBenchmarkStory):
  NAME = "MockStory"
  URL = "http://test.com"
  SUBSTORIES = (
      "Story-1",
      "Story-2",
      "Story-3",
      "Story-4",
  )

  @property
  @override
  def substory_duration(self) -> dt.timedelta:
    return dt.timedelta(seconds=0.1)

  def run(self, run: Run) -> None:
    pass


class PressBenchmarkStoryFilterTestCase(unittest.TestCase):

  def story_filter(self, *args, **kwargs):
    return PressBenchmarkStoryFilter(
        MockStory, *args, args=argparse.Namespace(), **kwargs)

  def test_empty(self):
    with self.assertRaises(ValueError):
      _ = self.story_filter([])

  def test_all(self):
    stories = self.story_filter(["all"]).stories
    self.assertEqual(len(stories), 1)
    story: MockStory = stories[0]
    self.assertSequenceEqual(story.substories, MockStory.SUBSTORIES)

  def test_all_separate(self):
    stories = self.story_filter(["all"], separate=True).stories
    self.assertSequenceEqual([story.substories[0] for story in stories],
                             MockStory.SUBSTORIES)
    for story in stories:
      self.assertTrue(len(story.substories), 1)

  def test_match_regexp_none(self):
    with self.assertRaisesRegex(ValueError, "Story"):
      _ = self.story_filter(["Story"]).stories

  def test_match_regexp_some(self):
    stories = self.story_filter([".*-3"]).stories
    self.assertEqual(len(stories), 1)
    story: MockStory = stories[0]
    self.assertSequenceEqual(story.substories, ["Story-3"])

  def test_match_regexp_all(self):
    stories = self.story_filter(["Story.*"]).stories
    self.assertEqual(len(stories), 1)
    story: MockStory = stories[0]
    self.assertSequenceEqual(story.substories, MockStory.SUBSTORIES)

  def test_match_regexp_all_wrong_case(self):
    stories = self.story_filter(["StOrY.*"]).stories
    self.assertEqual(len(stories), 1)
    story: MockStory = stories[0]
    self.assertSequenceEqual(story.substories, MockStory.SUBSTORIES)


class RegexFilterTestCase(unittest.TestCase):

  def test_all(self):
    regex_filter = RegexFilter(["story1", "story2"], ["story1"])
    selected = regex_filter.process_all(["all"])
    self.assertSequenceEqual(selected, ["story1", "story2"])

  def test_default(self):
    regex_filter = RegexFilter(["story1", "story2"], ["story1"])
    selected = regex_filter.process_all(["default"])
    self.assertSequenceEqual(selected, ["story1"])

  def test_match_regexp_none(self):
    regex_filter = RegexFilter(["story1", "story2"], ["story1"])
    with self.assertRaisesRegex(ValueError, "no_such_story"):
      regex_filter.process_all(["no_such_story"])

  def test_match_regexp_some(self):
    regex_filter = RegexFilter(["story1", "story2"], ["story1"])
    selected = regex_filter.process_all([".*2"])
    self.assertSequenceEqual(selected, ["story2"])

  def test_match_regexp_all(self):
    regex_filter = RegexFilter(["story1", "story2"], ["story1"])
    selected = regex_filter.process_all(["story.*"])
    self.assertSequenceEqual(selected, ["story1", "story2"])

  def test_match_regexp_all_wrong_case(self):
    regex_filter = RegexFilter(["story1", "story2"], ["story1"])
    selected = regex_filter.process_all(["StOrY.*"])
    self.assertSequenceEqual(selected, ["story1", "story2"])

  def test_range(self):
    regex_filter = RegexFilter(["A", "B", "C", "D", "E"],
                               ["A", "B", "C", "D", "E"])
    selected = regex_filter.process_all(["B...D"])
    self.assertSequenceEqual(selected, ["B", "C", "D"])

  def test_range_regex(self):
    regex_filter = RegexFilter(["A1", "A2", "B1", "B2", "C1", "C2"],
                               ["A1", "A2", "B1", "B2", "C1", "C2"])
    selected = regex_filter.process_all(["A.*...B.*"])
    # Start: A1 (first match of A.*)
    # End: B2 (last match of B.*)
    # Range: A1, A2, B1, B2
    self.assertSequenceEqual(selected, ["A1", "A2", "B1", "B2"])

  def test_range_regex_start_only(self):
    regex_filter = RegexFilter(["A1", "A2", "B1", "B2", "C1", "C2"],
                               ["A1", "A2", "B1", "B2", "C1", "C2"])
    selected = regex_filter.process_all(["B.*..."])
    # Start: B1 (first match of B.*)
    # End: C2 (last element)
    self.assertSequenceEqual(selected, ["B1", "B2", "C1", "C2"])

  def test_range_regex_end_only(self):
    regex_filter = RegexFilter(["A1", "A2", "B1", "B2", "C1", "C2"],
                               ["A1", "A2", "B1", "B2", "C1", "C2"])
    selected = regex_filter.process_all(["...B.*"])
    # Start: A1 (first element)
    # End: B2 (last match of B.*)
    self.assertSequenceEqual(selected, ["A1", "A2", "B1", "B2"])

  def test_range_start_only(self):
    regex_filter = RegexFilter(["A", "B", "C", "D", "E"],
                               ["A", "B", "C", "D", "E"])
    selected = regex_filter.process_all(["C..."])
    self.assertSequenceEqual(selected, ["C", "D", "E"])

  def test_range_end_only(self):
    regex_filter = RegexFilter(["A", "B", "C", "D", "E"],
                               ["A", "B", "C", "D", "E"])
    selected = regex_filter.process_all(["...C"])
    self.assertSequenceEqual(selected, ["A", "B", "C"])

  def test_range_invalid_order(self):
    regex_filter = RegexFilter(["A", "B"], ["A", "B"])
    with self.assertRaisesRegex(ValueError, "after"):
      regex_filter.process_all(["B...A"])

  def test_range_invalid_syntax(self):
    regex_filter = RegexFilter(["A", "B"], ["A", "B"])
    with self.assertRaisesRegex(RangePatternError, "empty"):
      regex_filter.process_all(["..."])
    with self.assertRaisesRegex(RangePatternError, "separator"):
      regex_filter.process_all(["A...B...C"])
    with self.assertRaisesRegex(RangePatternError, "negative"):
      regex_filter.process_all(["-A...B"])
    with self.assertRaisesRegex(RangePatternError, "negative"):
      regex_filter.process_all(["A...-B"])

  def test_range_with_other_patterns(self):
    regex_filter = RegexFilter(["A", "B", "C", "D", "E"],
                               ["A", "B", "C", "D", "E"])
    selected = regex_filter.process_all(["B...C", "E"])
    self.assertSequenceEqual(selected, ["B", "C", "E"])


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
