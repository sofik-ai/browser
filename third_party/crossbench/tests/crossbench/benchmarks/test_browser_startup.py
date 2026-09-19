# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from tests import test_helper
from tests.crossbench.base import BaseCliTestCase, SysExitTestException


class TestBrowserStartupCli(BaseCliTestCase):

  def test_cli_help(self):
    # Verify it's visible in CLI help
    with self.assertRaises(SysExitTestException):
      self.run_cli("--help")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
