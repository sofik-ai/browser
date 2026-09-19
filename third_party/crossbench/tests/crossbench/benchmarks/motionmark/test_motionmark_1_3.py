# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing_extensions import override

from crossbench.benchmarks.motionmark.motionmark_1_3 import \
    MotionMark13Benchmark, MotionMark13Probe, MotionMark13ProbeContext, \
    MotionMark13Story
from tests import test_helper
from tests.crossbench.benchmarks.motionmark.helper import \
    MotionMark1BaseTestCase


class MotionMark13TestCase(MotionMark1BaseTestCase):

  @property
  @override
  def benchmark_cls(self):
    return MotionMark13Benchmark

  @property
  @override
  def story_cls(self):
    return MotionMark13Story

  @property
  @override
  def probe_cls(self):
    return MotionMark13Probe

  @property
  @override
  def probe_context_cls(self):
    return MotionMark13ProbeContext


del MotionMark1BaseTestCase

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
