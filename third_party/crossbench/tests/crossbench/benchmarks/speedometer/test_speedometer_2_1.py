# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing_extensions import override

from crossbench.benchmarks.speedometer.speedometer_2_1 import \
    Speedometer21Benchmark, Speedometer21Probe, Speedometer21ProbeContext, \
    Speedometer21Story
from tests import test_helper
from tests.crossbench.benchmarks.speedometer.helper import \
    Speedometer2BaseTestCase


class Speedometer21TestCase(Speedometer2BaseTestCase):

  @property
  @override
  def benchmark_cls(self):
    return Speedometer21Benchmark

  @property
  @override
  def story_cls(self):
    return Speedometer21Story

  @property
  @override
  def probe_cls(self):
    return Speedometer21Probe

  @property
  @override
  def probe_context_cls(self):
    return Speedometer21ProbeContext

  @property
  @override
  def name(self):
    return "speedometer_2.1"


#  Don't expose abstract BaseTestCase to test runner
del Speedometer2BaseTestCase

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
