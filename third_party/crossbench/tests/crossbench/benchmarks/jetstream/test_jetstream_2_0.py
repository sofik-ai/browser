# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing_extensions import override

from crossbench.benchmarks.jetstream.jetstream_2_0 import \
    JetStream20Benchmark, JetStream20Probe, JetStream20ProbeContext, \
    JetStream20Story
from tests import test_helper
# Only import module to avoid exposing the abstract test classes to the runner.
from tests.crossbench.benchmarks.jetstream import jetstream_helper


class JetStream20TestCase(jetstream_helper.JetStream2BaseTestCase):

  @property
  @override
  def benchmark_cls(self):
    return JetStream20Benchmark

  @property
  @override
  def story_cls(self):
    return JetStream20Story

  @property
  @override
  def probe_cls(self):
    return JetStream20Probe

  @property
  @override
  def probe_context_cls(self):
    return JetStream20ProbeContext

  @property
  def name(self):
    return "jetstream_2.0"


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
