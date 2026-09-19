# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from unittest import mock

from crossbench import path as pth
from crossbench.browsers.attributes import BrowserAttributes
from crossbench.probes.crashdump import CrashdumpProbe, \
    LinuxCrashdumpProbeContext
from crossbench.probes.results import EmptyProbeResult
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase
from tests.crossbench.runner.helper import MockRun


class CrashdumpProbeTestCase(CrossbenchFakeFsTestCase):

  def test_probe_name(self):
    probe = CrashdumpProbe()
    self.assertEqual(probe.name, "cb.crashdump")
    self.assertTrue(probe.is_internal)

  def test_non_chromium_browser(self):
    probe = CrashdumpProbe()
    browser = mock.MagicMock()
    browser.unique_name = "mock_browser"
    browser.attributes = mock.MagicMock(return_value=set())

    platform = mock.MagicMock()
    platform.is_linux = True
    browser.platform = platform

    browser_session = mock.MagicMock()
    browser_session.browser = browser
    browser_session.root_dir = pth.LocalPath("/path/to/root")

    run = MockRun(mock.MagicMock(), browser_session)
    context = probe.create_context(run)

    self.assertIsInstance(context, LinuxCrashdumpProbeContext)
    result = context.teardown()
    self.assertIsInstance(result, EmptyProbeResult)

  def test_chromium_browser_no_user_data_dir(self):
    probe = CrashdumpProbe()
    browser = mock.MagicMock()
    browser.unique_name = "mock_browser"
    browser.attributes = mock.MagicMock(
        return_value={BrowserAttributes.CHROMIUM_BASED})
    browser.user_data_dir = None

    platform = mock.MagicMock()
    platform.is_linux = True
    browser.platform = platform

    browser_session = mock.MagicMock()
    browser_session.browser = browser
    browser_session.root_dir = pth.LocalPath("/path/to/root")

    run = MockRun(mock.MagicMock(), browser_session)
    context = probe.create_context(run)

    result = context.teardown()
    self.assertIsInstance(result, EmptyProbeResult)

  def test_chromium_browser_with_dumps(self):
    probe = CrashdumpProbe()
    browser = mock.MagicMock()
    browser.unique_name = "mock_browser"
    browser.attributes = mock.MagicMock(
        return_value={BrowserAttributes.CHROMIUM_BASED})

    user_data_dir = pth.LocalPath("/path/to/user/data")
    browser.user_data_dir = user_data_dir

    # Mock platform
    platform = mock.MagicMock()
    platform.is_dir = mock.MagicMock(return_value=True)
    platform.exists = mock.MagicMock(return_value=True)
    platform.is_linux = True

    browser.platform = platform

    browser_session = mock.MagicMock()
    browser_session.browser = browser
    browser_session.root_dir = pth.LocalPath("/path/to/root")

    # Mock MinidumpFinder
    mock_finder = mock.MagicMock()
    mock_finder.get_all_minidump_paths = mock.MagicMock(
        return_value=(
            [pth.LocalPath("/path/to/user/data/Crash Reports/dump1.dmp")],
            ["explanation"]))

    with mock.patch(
        "crossbench.probes.crashdump.MinidumpFinder", return_value=mock_finder):
      run = MockRun(mock.MagicMock(), browser_session)

      context = probe.create_context(run)

      result = context.teardown()

      self.assertFalse(result.is_empty)
      platform.pull.assert_called_once()

  def test_chromium_browser_no_dumps(self):
    probe = CrashdumpProbe()
    browser = mock.MagicMock()
    browser.unique_name = "mock_browser"
    browser.attributes = mock.MagicMock(
        return_value={BrowserAttributes.CHROMIUM_BASED})

    user_data_dir = pth.LocalPath("/path/to/user/data")
    browser.user_data_dir = user_data_dir

    platform = mock.MagicMock()
    platform.is_dir = mock.MagicMock(return_value=True)
    platform.is_linux = True
    browser.platform = platform

    browser_session = mock.MagicMock()
    browser_session.browser = browser
    browser_session.root_dir = pth.LocalPath("/path/to/root")

    # Mock MinidumpFinder
    mock_finder = mock.MagicMock()
    mock_finder.get_all_minidump_paths = mock.MagicMock(
        return_value=((), ["explanation"]))

    with mock.patch(
        "crossbench.probes.crashdump.MinidumpFinder", return_value=mock_finder):
      run = MockRun(mock.MagicMock(), browser_session)

      context = probe.create_context(run)

      result = context.teardown()

      self.assertTrue(result.is_empty)

  def test_log_results(self):
    probe = CrashdumpProbe()
    run = mock.MagicMock()
    run.name = "mock_run"

    result = mock.MagicMock()
    result.is_empty = False
    result.file_list = [pth.LocalPath("/path/to/result/dump1.dmp")]

    run.results = {probe: result}

    with mock.patch("logging.critical") as mock_critical:
      probe.log_run_result(run)

      # Only check for basic keywords in the logs
      log_output = "\n".join(str(call) for call in mock_critical.call_args_list)
      self.assertIn("Crash dumps found", log_output)
      self.assertIn("mock_run", log_output)
      self.assertIn("dump1.dmp", log_output)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
