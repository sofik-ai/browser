# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

from unittest import mock

from crossbench.network.live import LiveNetwork
from tests import test_helper
from tests.crossbench.base import BaseCrossbenchTestCase


class LiveNetworkTestCase(BaseCrossbenchTestCase):

  def test_defaults(self):
    network = LiveNetwork(browser_platform=self.platform)
    self.assertTrue(network.traffic_shaper.is_live)
    self.assertFalse(network.traffic_shaper.is_running)
    self.assertFalse(network.is_running)
    self.assertIn("live", str(network).lower())

  def test_open(self):
    network = LiveNetwork(browser_platform=self.platform)
    mock_browser_session = mock.Mock()
    with network.open(mock_browser_session):
      self.assertTrue(network.is_running)
      self.assertFalse(network.extra_flags(self.browsers[0].attributes()))
      # Should not be able to double open the network.
      with self.assertRaises(AssertionError):
        with network.open(mock_browser_session):
          pass
    self.assertFalse(network.is_running)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
