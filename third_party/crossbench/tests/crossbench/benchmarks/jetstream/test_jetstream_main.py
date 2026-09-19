# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing_extensions import override

from crossbench.benchmarks.jetstream.jetstream_main import \
    JetStreamMainBenchmark, JetStreamMainProbe, JetStreamMainProbeContext, \
    JetStreamMainStory
from tests import test_helper
# Only import module to avoid exposing the abstract test classes to the runner.
from tests.crossbench.benchmarks.jetstream import jetstream_helper


class JetStreamMainTestCase(jetstream_helper.JetStream3BaseTestCase):

  @property
  @override
  def benchmark_cls(self):
    return JetStreamMainBenchmark

  @property
  @override
  def story_cls(self):
    return JetStreamMainStory

  @property
  @override
  def probe_cls(self):
    return JetStreamMainProbe

  @property
  @override
  def probe_context_cls(self):
    return JetStreamMainProbeContext

  @property
  def name(self):
    return "jetstream_main"


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
