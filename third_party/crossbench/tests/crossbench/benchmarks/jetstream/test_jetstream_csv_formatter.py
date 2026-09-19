# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import unittest

from crossbench.benchmarks.jetstream.jetstream import JetStreamCSVFormatter
from crossbench.probes.metric import MetricsMerger
from tests import test_helper

# Only import module to avoid exposing the abstract test classes to the runner.


class JetStreamCSVFormatterTestCase(unittest.TestCase):

  def test_throw_missing_score(self):
    metrics = MetricsMerger({
        "Total/Average": 10,
        "cdjs/Average": 30,
        "cdjs/Score": 40,
    })
    with self.assertRaisesRegex(KeyError, "Total/Score"):
      _ = JetStreamCSVFormatter(metrics, lambda metric: metric.geomean).table

  def test_format_sorted(self):
    metrics = MetricsMerger({
        "Total/Average": 10,
        "Total/Score": 20,
        "cdjs/Average": 30,
        "cdjs/Score": 40,
    })
    table = JetStreamCSVFormatter(
        metrics, lambda metric: round(metric.geomean, 10)).table
    self.assertSequenceEqual(table, [
        ("Total/Score", "Total", "Score", 20.0),
        ("cdjs/Score", "cdjs", "Score", 40.0),
        ("Total/Average", "Total", "Average", 10.0),
        ("Total/Score", "Total", "Score", 20.0),
        ("cdjs/Average", "cdjs", "Average", 30.0),
        ("cdjs/Score", "cdjs", "Score", 40.0),
    ])

  def test_format_unsorted(self):
    metrics = MetricsMerger({
        "cdjs/Average": 30,
        "cdjs/Score": 40,
        "Total/Average": 10,
        "Total/Score": 20,
    })
    table = JetStreamCSVFormatter(
        metrics, lambda metric: round(metric.geomean, 10), sort=False).table
    self.assertSequenceEqual(table, [
        ("Total/Score", "Total", "Score", 20.0),
        ("cdjs/Score", "cdjs", "Score", 40.0),
        ("cdjs/Average", "cdjs", "Average", 30.0),
        ("cdjs/Score", "cdjs", "Score", 40.0),
        ("Total/Average", "Total", "Average", 10.0),
        ("Total/Score", "Total", "Score", 20.0),
    ])


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
