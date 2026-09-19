# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing_extensions import override

from crossbench.benchmarks.motionmark.motionmark_main import \
    MotionMarkMainBenchmark, MotionMarkMainProbe, MotionMarkMainProbeContext, \
    MotionMarkMainStory
from tests import test_helper
from tests.crossbench.benchmarks.motionmark.helper import \
    MotionMark1BaseTestCase


class MotionMarkMainTestCase(MotionMark1BaseTestCase):

  @property
  @override
  def benchmark_cls(self):
    return MotionMarkMainBenchmark

  @property
  @override
  def story_cls(self):
    return MotionMarkMainStory

  @property
  @override
  def probe_cls(self):
    return MotionMarkMainProbe

  @property
  @override
  def probe_context_cls(self):
    return MotionMarkMainProbeContext


del MotionMark1BaseTestCase

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
