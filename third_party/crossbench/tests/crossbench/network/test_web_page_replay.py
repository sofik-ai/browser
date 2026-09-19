# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

from crossbench.network.replay.web_page_replay import _WPR_PORT_RE
from tests import test_helper
from tests.crossbench.base import BaseCrossbenchTestCase


class TestWprLogLineRegex(BaseCrossbenchTestCase):

  def test_no_match(self):
    line = "2025/10/13 10:26:23 ScriptInjector(https://www.google.com/search?q=cats): succesfully injected"
    match = _WPR_PORT_RE.match(line)
    self.assertIsNone(match)

  def test_ipv4_line(self):
    line = "2025/10/13 10:26:29 Starting server on https://127.0.0.1:36013"
    match = _WPR_PORT_RE.match(line)
    self.assertIsNotNone(match)
    self.assertEqual(match["protocol"], "https")
    self.assertEqual(match["host"], "127.0.0.1")
    self.assertEqual(match["port"], "36013")

  def test_ipv6_line(self):
    line = "2025/10/13 10:26:29 Starting server on http://[::]:80"
    match = _WPR_PORT_RE.match(line)
    self.assertIsNotNone(match)
    self.assertEqual(match["protocol"], "http")
    self.assertEqual(match["host"], "[::]")
    self.assertEqual(match["port"], "80")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
