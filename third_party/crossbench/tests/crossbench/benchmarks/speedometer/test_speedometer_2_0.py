# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing_extensions import override

from crossbench.benchmarks.speedometer.speedometer_2_0 import \
    Speedometer20Benchmark, Speedometer20Probe, Speedometer20ProbeContext, \
    Speedometer20Story
from tests import test_helper
from tests.crossbench.benchmarks.speedometer.helper import \
    Speedometer2BaseTestCase


class Speedometer20TestCase(Speedometer2BaseTestCase):

  @property
  @override
  def benchmark_cls(self):
    return Speedometer20Benchmark

  @property
  @override
  def story_cls(self):
    return Speedometer20Story

  @property
  @override
  def probe_cls(self):
    return Speedometer20Probe

  @property
  @override
  def probe_context_cls(self):
    return Speedometer20ProbeContext

  @property
  @override
  def name(self):
    return "speedometer_2.0"

  def test_default_all(self):
    default_story_names = [
        story.name for story in self.story_cls.default(separate=True)
    ]
    all_story_names = [
        story.name for story in self.story_cls.all(separate=True)
    ]
    self.assertListEqual(default_story_names, all_story_names)


del Speedometer2BaseTestCase

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
