# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing_extensions import override

from crossbench.benchmarks.speedometer.speedometer_main import \
    SpeedometerMainBenchmark, SpeedometerMainProbe, \
    SpeedometerMainProbeContext, SpeedometerMainStory
from tests import test_helper
from tests.crossbench.benchmarks.speedometer.helper import \
    Speedometer3BaseTestCase


class SpeedometeMainTestCase(Speedometer3BaseTestCase):

  @property
  @override
  def benchmark_cls(self):
    return SpeedometerMainBenchmark

  @property
  @override
  def story_cls(self):
    return SpeedometerMainStory

  @property
  @override
  def probe_cls(self):
    return SpeedometerMainProbe

  @property
  @override
  def probe_context_cls(self):
    return SpeedometerMainProbeContext

  @property
  @override
  def name(self):
    return "speedometer_main"


#  Don't expose abstract BaseTestCase to test runner
del Speedometer3BaseTestCase

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
