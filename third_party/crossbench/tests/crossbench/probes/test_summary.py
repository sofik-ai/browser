# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import unittest
from unittest import mock

from crossbench import path as pth
from crossbench.probes.internal.summary import ResultsSummaryProbe
from crossbench.probes.results import EmptyProbeResult, ProbeResultDict
from tests import test_helper


class ResultsSummaryProbeTestCase(unittest.TestCase):

  def test_merge_missing(self):
    group = mock.Mock()
    group.first_run.results = ProbeResultDict(pth.AnyPath("test/out/results"))
    probe = ResultsSummaryProbe()
    result = probe.merge_cache_temperatures(group)
    self.assertTrue(result.is_empty)

  def test_merge_empty(self):
    group = mock.Mock()
    first_run = mock.Mock()
    group.runs = [first_run]
    first_run.results = ProbeResultDict(pth.AnyPath("test/out/results"))
    probe = ResultsSummaryProbe()
    first_run.results[probe] = EmptyProbeResult()
    with mock.patch.object(probe, "write_group_result") as mock_write:
      probe.merge_repetitions(group)
    mock_write.assert_called()


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
