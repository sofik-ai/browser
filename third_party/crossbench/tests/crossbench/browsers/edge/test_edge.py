# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse

from typing_extensions import override

from crossbench.browsers.edge.version import EdgeVersion
from crossbench.browsers.edge.webdriver import EdgeWebDriver
from crossbench.browsers.settings import Settings
from crossbench.flags.chrome import ChromeFlags
from tests import test_helper
from tests.crossbench import mock_browser
from tests.crossbench.base import BaseCrossbenchTestCase


class EdgeWebDriverForTesting(EdgeWebDriver):

  @override
  def _extract_version(self) -> EdgeVersion:
    return EdgeVersion.parse(mock_browser.MockEdgeStable.VERSION)


class EdgeWebdriverTestCase(BaseCrossbenchTestCase):

  def test_conflicting_finch_flags(self) -> None:
    with self.assertRaises(argparse.ArgumentTypeError) as cm:
      EdgeWebDriverForTesting(
          label="browser-label",
          path=mock_browser.MockEdgeStable.mock_app_path(),
          settings=Settings(
              js_flags=[],
              flags=[
                  "--disable-field-trial-config", "--enable-field-trial-config"
              ],
              platform=self.platform))
    msg = str(cm.exception)
    self.assertIn("--enable-field-trial-config", msg)
    self.assertIn("--disable-field-trial-config", msg)

  def test_auto_disabling_field_trials(self):
    browser = EdgeWebDriverForTesting(
        label="browser-label",
        path=mock_browser.MockEdgeStable.mock_app_path(),
        settings=Settings(platform=self.platform))
    self.assertIn("--disable-field-trial-config", browser.flags)

    browser_field_trial = EdgeWebDriverForTesting(
        label="browser-label",
        path=mock_browser.MockEdgeStable.mock_app_path(),
        settings=Settings(
            flags=["--force-fieldtrials"], platform=self.platform))
    self.assertIn("--force-fieldtrials", browser_field_trial.flags)
    self.assertNotIn("--disable-field-trial-config", browser_field_trial.flags)

  def test_auto_disabling_field_trials_all(self):
    for field_trial_flag in ChromeFlags.FIELD_TRIAL_ENABLE_FLAGS:
      if field_trial_flag == "--enable-benchmarking":
        continue
      browser = EdgeWebDriverForTesting(
          label="browser-label",
          path=mock_browser.MockEdgeStable.mock_app_path(),
          settings=Settings(flags=[field_trial_flag], platform=self.platform))
      flags: ChromeFlags = browser.flags
      self.assertIn(field_trial_flag, flags)
      self.assertFalse(flags.field_trial_disable_flags)

  def test_is_local_build_mock_browser(self):
    self.assertTrue(self.browsers)
    for browser in self.browsers:
      self.assertFalse(browser.is_local_build)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
