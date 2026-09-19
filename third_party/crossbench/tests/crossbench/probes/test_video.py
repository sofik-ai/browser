# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import unittest

from crossbench.probes.video import Orientation, VideoProbe
from tests import test_helper


class V8LogProbeTestCase(unittest.TestCase):

  def test_default(self):
    probe = VideoProbe.parse_dict({})
    self.assertEqual(probe.primary_orientation, Orientation.HORIZONTAL)
    self.assertEqual(probe.secondary_orientation, Orientation.VERTICAL)

  def test_from_config(self):
    probe = VideoProbe.parse_dict({"orientation": "vertical"})
    self.assertEqual(probe.primary_orientation, Orientation.VERTICAL)
    self.assertEqual(probe.secondary_orientation, Orientation.HORIZONTAL)

    probe = VideoProbe.parse_dict({"dir": "horizontal"})
    self.assertEqual(probe.primary_orientation, Orientation.HORIZONTAL)
    self.assertEqual(probe.secondary_orientation, Orientation.VERTICAL)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
