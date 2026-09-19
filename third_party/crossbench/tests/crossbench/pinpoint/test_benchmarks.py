# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from crossbench.pinpoint.benchmarks import all_stories, default_story, \
    is_crossbench_benchmark, pinpoint_benchmark_name
from tests import test_helper
from tests.crossbench.base import BaseCrossbenchTestCase


class BenchmarksTest(BaseCrossbenchTestCase):

  def test_pinpoint_benchmark_name(self):
    self.assertEqual(
        pinpoint_benchmark_name("devtools_frontend"),
        "devtools_frontend.crossbench")
    self.assertEqual(
        pinpoint_benchmark_name("speedometer_3.0"), "speedometer3.0.crossbench")
    self.assertIsNone(pinpoint_benchmark_name("invalid_name"))

  def test_is_crossbench_benchmark(self):
    self.assertTrue(is_crossbench_benchmark("speedometer3.0.crossbench"))
    self.assertTrue(is_crossbench_benchmark("devtools_frontend.crossbench"))
    self.assertFalse(is_crossbench_benchmark("invalid_benchmark"))

  def test_all_stories_with_substories(self):
    stories = all_stories("speedometer3.0.crossbench")
    self.assertIn("default", stories)
    self.assertIn("TodoMVC-JavaScript-ES5", stories)

  def test_all_stories_without_substories(self):
    stories = all_stories("devtools_frontend.crossbench")
    self.assertEqual(stories, ["default"])

  def test_all_stories_invalid(self):
    self.assertEqual(all_stories("invalid_benchmark"), [])

  def test_default_story(self):
    self.assertEqual(default_story("speedometer3.0.crossbench"), "default")
    self.assertEqual(default_story("devtools_frontend.crossbench"), "default")
    self.assertIsNone(default_story("invalid_benchmark"))


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
