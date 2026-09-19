# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing_extensions import override

from crossbench.benchmarks.motionmark.motionmark_1_2 import \
    MotionMark12Benchmark, MotionMark12Probe, MotionMark12ProbeContext, \
    MotionMark12Story
from tests import test_helper
from tests.crossbench.benchmarks.motionmark.helper import \
    MotionMark1BaseTestCase


class MotionMark12TestCase(MotionMark1BaseTestCase):

  @property
  @override
  def benchmark_cls(self):
    return MotionMark12Benchmark

  @property
  @override
  def story_cls(self):
    return MotionMark12Story

  @property
  @override
  def probe_cls(self):
    return MotionMark12Probe

  @property
  @override
  def probe_context_cls(self):
    return MotionMark12ProbeContext


del MotionMark1BaseTestCase

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
