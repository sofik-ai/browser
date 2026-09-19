# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import unittest
from typing import TYPE_CHECKING, MutableSet

from ordered_set import OrderedSet

from crossbench.benchmarks.embedder.embedder_benchmark import EmbedderBenchmark
from crossbench.benchmarks.jetstream.jetstream_1_1 import JetStream11Benchmark
from crossbench.benchmarks.jetstream.jetstream_2_0 import JetStream20Benchmark
from crossbench.benchmarks.jetstream.jetstream_2_1 import JetStream21Benchmark
from crossbench.benchmarks.jetstream.jetstream_2_2 import JetStream22Benchmark
from crossbench.benchmarks.jetstream.jetstream_3_0 import JetStream30Benchmark
from crossbench.benchmarks.jetstream.jetstream_main import \
    JetStreamMainBenchmark
from crossbench.benchmarks.loading.browser_startup import BrowserStartupBenchmark
from crossbench.benchmarks.loading.loading_benchmark import LoadingBenchmark
from crossbench.benchmarks.loadline import LoadLine1PhoneBenchmark, \
    LoadLine1PhoneDebugBenchmark, LoadLine1PhoneFastBenchmark, \
    LoadLine1TabletBenchmark, LoadLine1TabletDebugBenchmark, \
    LoadLine1TabletFastBenchmark, LoadLine2PhoneBenchmark, \
    LoadLine2PhoneDebugBenchmark, LoadLine2TabletBenchmark, \
    LoadLine2TabletDebugBenchmark
from crossbench.benchmarks.manual.manual_benchmark import ManualBenchmark
from crossbench.benchmarks.memory.memory_benchmark import MemoryBenchmark
from crossbench.benchmarks.motionmark.motionmark_1_0 import \
    MotionMark10Benchmark
from crossbench.benchmarks.motionmark.motionmark_1_1 import \
    MotionMark11Benchmark
from crossbench.benchmarks.motionmark.motionmark_1_2 import \
    MotionMark12Benchmark
from crossbench.benchmarks.motionmark.motionmark_1_3 import \
    MotionMark13Benchmark
from crossbench.benchmarks.motionmark.motionmark_1_3_1 import \
    MotionMark131Benchmark
from crossbench.benchmarks.motionmark.motionmark_main import \
    MotionMarkMainBenchmark
from crossbench.benchmarks.speedometer.speedometer_1_0 import \
    Speedometer10Benchmark
from crossbench.benchmarks.speedometer.speedometer_2_0 import \
    Speedometer20Benchmark
from crossbench.benchmarks.speedometer.speedometer_2_1 import \
    Speedometer21Benchmark
from crossbench.benchmarks.speedometer.speedometer_3_0 import \
    Speedometer30Benchmark
from crossbench.benchmarks.speedometer.speedometer_3_1 import \
    Speedometer31Benchmark
from crossbench.benchmarks.speedometer.speedometer_main import \
    SpeedometerMainBenchmark
from tests import test_helper

if TYPE_CHECKING:
  from crossbench.stories.story import Story

ALL = (
    JetStream11Benchmark,
    JetStream20Benchmark,
    JetStream21Benchmark,
    JetStream22Benchmark,
    JetStream30Benchmark,
    JetStreamMainBenchmark,
    BrowserStartupBenchmark,
    LoadLine1PhoneBenchmark,
    LoadLine1PhoneDebugBenchmark,
    LoadLine1PhoneFastBenchmark,
    LoadLine1TabletBenchmark,
    LoadLine1TabletDebugBenchmark,
    LoadLine1TabletFastBenchmark,
    LoadLine2PhoneBenchmark,
    LoadLine2PhoneDebugBenchmark,
    LoadLine2TabletBenchmark,
    LoadLine2TabletDebugBenchmark,
    ManualBenchmark,
    MotionMark10Benchmark,
    MotionMark11Benchmark,
    MotionMark12Benchmark,
    MotionMark13Benchmark,
    MotionMark131Benchmark,
    MotionMarkMainBenchmark,
    LoadingBenchmark,
    Speedometer10Benchmark,
    Speedometer20Benchmark,
    Speedometer21Benchmark,
    Speedometer30Benchmark,
    Speedometer31Benchmark,
    SpeedometerMainBenchmark,
    MemoryBenchmark,
    EmbedderBenchmark,
)


class AllBenchmarksTestCase(unittest.TestCase):

  def test_unique_classes(self):
    self.assertTupleEqual(ALL, tuple(OrderedSet(ALL)))

  def test_aliases(self):
    seen_names: MutableSet[str] = OrderedSet()
    seen_aliases: MutableSet[str] = OrderedSet()
    for benchmark_cls in ALL:
      with self.subTest(benchmark_cls=benchmark_cls.__name__):
        self.assertNotIn(benchmark_cls.NAME, seen_names)
        seen_names.add(benchmark_cls.NAME)
        for alias in benchmark_cls.aliases():
          self.assertNotIn(alias, seen_aliases)
          seen_aliases.add(alias)

  def test_story_classes(self):
    seen_story_classes: MutableSet[type[Story]] = OrderedSet()
    for benchmark_cls in ALL:
      if benchmark_cls is MemoryBenchmark:
        continue
      if issubclass(benchmark_cls,
                    LoadingBenchmark) and (benchmark_cls
                                           is not LoadingBenchmark):
        continue
      self.assertNotIn(benchmark_cls.DEFAULT_STORY_CLS, seen_story_classes)
      seen_story_classes.add(benchmark_cls.DEFAULT_STORY_CLS)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
