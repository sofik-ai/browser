# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from crossbench.probes.cb_perfetto import traceconv
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase


class PerfettoVersionTestCase(CrossbenchFakeFsTestCase):

  def test_parse(self):
    self.assertEqual(
        traceconv.PerfettoVersion.parse("Perfetto v53.0").parts, (53, 0))
    self.assertEqual(
        traceconv.PerfettoVersion.parse("Perfetto v53.1").parts, (53, 1))
    self.assertEqual(
        traceconv.PerfettoVersion.parse("Perfetto v53.0-7a9a6a0").parts,
        (53, 0))
    self.assertEqual(
        traceconv.PerfettoVersion.parse(
            "some noise Perfetto v54.2-abc (hash)").parts, (54, 2))

  def test_comparison(self):
    v53_0 = traceconv.PerfettoVersion.parse("Perfetto v53.0")
    v53_1 = traceconv.PerfettoVersion.parse("Perfetto v53.1")
    v54_0 = traceconv.PerfettoVersion.parse("Perfetto v54.0")
    v52_9 = traceconv.PerfettoVersion.parse("Perfetto v52.9")

    self.assertTrue(v53_0 >= traceconv.MIN_VERSION)
    self.assertTrue(v53_1 >= traceconv.MIN_VERSION)
    self.assertTrue(v54_0 >= traceconv.MIN_VERSION)
    self.assertTrue(v52_9 < traceconv.MIN_VERSION)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
