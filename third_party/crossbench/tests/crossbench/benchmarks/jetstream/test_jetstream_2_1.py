# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing_extensions import override

from crossbench.benchmarks.jetstream.jetstream_2_1 import \
    JetStream21Benchmark, JetStream21Probe, JetStream21ProbeContext, \
    JetStream21Story
from tests import test_helper
# Only import module to avoid exposing the abstract test classes to the runner.
from tests.crossbench.benchmarks.jetstream import jetstream_helper


class JetStream21TestCase(jetstream_helper.JetStream2BaseTestCase):

  @property
  @override
  def benchmark_cls(self):
    return JetStream21Benchmark

  @property
  @override
  def story_cls(self):
    return JetStream21Story

  @property
  @override
  def probe_cls(self):
    return JetStream21Probe

  @property
  @override
  def probe_context_cls(self):
    return JetStream21ProbeContext

  @property
  def name(self):
    return "jetstream_2.1"


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
