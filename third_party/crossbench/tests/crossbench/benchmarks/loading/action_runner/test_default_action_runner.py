# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Any, Type

from crossbench.action_runner.action.probe import ProbeAction
from crossbench.action_runner.default_action_runner import DefaultActionRunner
from crossbench.benchmarks.loading.config.blocks import ActionBlock
from crossbench.browsers.settings import Settings
from crossbench.exception import MultiException
from crossbench.flags.base import Flags
from crossbench.probes.downloads import DownloadsProbe, \
    FileWatchDownloadsProbeContext
from crossbench.probes.dump_html import DumpHtmlProbe
from crossbench.probes.meminfo import MeminfoProbe
from crossbench.probes.screenshot import ScreenshotProbe
from crossbench.probes.shell import ShellProbe
from crossbench.runner.groups.session import BrowserSessionRunGroup
from tests import test_helper
from tests.crossbench.action_runner.action_runner_test_case import \
    ActionRunnerTestCase
from tests.crossbench.mock_browser import MockChromeStable
from tests.crossbench.mock_helper import LinuxMockPlatform
from tests.crossbench.runner.helper import MockRun, MockRunner

if TYPE_CHECKING:
  from crossbench.probes.probe import Probe, ProbeContext


class DefaultActionRunnerTestCase(ActionRunnerTestCase):

  def set_up_with_probe(
      self,
      probe: Probe,
      probe_context_cls: Type[ProbeContext] | None = None,
      probe_context_args: dict[str, Any] | None = None) -> None:
    self.fs.create_file(
        "/usr/bin/google-chrome", contents="definitely a browser")

    self.root_dir = pathlib.Path()
    self.platform = LinuxMockPlatform()
    self.browser = MockChromeStable(
        "mock browser", settings=Settings(platform=self.platform))
    self.probe = probe
    self.runner = MockRunner(probes=[self.probe])
    self.root_dir = pathlib.Path()
    self.session = BrowserSessionRunGroup(self.runner.env,
                                          self.runner.probes, self.browser,
                                          Flags(), 1, self.root_dir, True, True)
    self.action_runner = DefaultActionRunner()
    self.mock_run = MockRun(
        self.runner,
        self.session,
        "run 1",
        self.action_runner,
        probe=self.probe)

    if not probe_context_cls:
      self.probe_context = self.probe.create_context(self.mock_run)
    else:
      self.probe_context = probe_context_cls(
          self.probe, self.mock_run,
          **(probe_context_args if probe_context_args else {}))

    self.mock_run.set_probe_context(self.probe_context)

  def test_probe_action_unsupported_probe(self):
    self.set_up_with_probe(ShellProbe(""))
    action_block = ActionBlock(actions=(ProbeAction(probe="shell", kwargs={}),))

    with self.assertRaisesRegex(MultiException,
                                "Invoke not implemented for probe"):
      self.action_runner.run_block(self.mock_run, action_block)

  def test_probe_action_screenshot(self):
    self.set_up_with_probe(ScreenshotProbe())
    action_block = ActionBlock(
        actions=(ProbeAction(probe="screenshot", kwargs={}),))
    self.action_runner.run_block(self.mock_run, action_block)
    self.assertEqual(len(self.platform.screenshots), 1)

  def test_probe_action_wait_for_download_missing_pattern(self):
    self.set_up_with_probe(DownloadsProbe(), FileWatchDownloadsProbeContext,
                           {"downloads_dir": "/Downloads"})
    action_block = ActionBlock(
        actions=(ProbeAction(probe="downloads", kwargs={}),))

    with self.assertRaisesRegex(MultiException, "pattern"):
      self.action_runner.run_block(self.mock_run, action_block)

  def test_probe_action_wait_for_download(self):
    downloads_dir = pathlib.Path("/Downloads")
    downloads_dir.mkdir()
    self.set_up_with_probe(DownloadsProbe(), FileWatchDownloadsProbeContext,
                           {"downloads_dir": downloads_dir})
    action_block = ActionBlock(
        actions=(
            ProbeAction(probe="downloads", kwargs={"pattern": "a_download"}),))

    with self.assertRaisesRegex(MultiException, "Waited for"):
      self.action_runner.run_block(self.mock_run, action_block)

  def test_probe_action_meminfo_no_kwargs(self):
    self.set_up_with_probe(MeminfoProbe())
    action_block = ActionBlock(
        actions=(ProbeAction(probe="meminfo", kwargs={}),))

    self.action_runner.run_block(self.mock_run, action_block)
    self.assertEqual(self.browser.performance_marks[-1], "crossbench-meminfo")

  def test_probe_action_meminfo_all_kwargs(self):
    self.set_up_with_probe(MeminfoProbe())
    action_block = ActionBlock(
        actions=(ProbeAction(
            probe="meminfo",
            kwargs={
                "browser": False,
                "system": False,
                "packages": [],
                "title": ""
            }),))

    self.action_runner.run_block(self.mock_run, action_block)
    self.assertEqual(self.browser.performance_marks[-1], "crossbench-meminfo")

  def test_probe_action_dump_html(self):
    self.set_up_with_probe(DumpHtmlProbe())
    action_block = ActionBlock(
        actions=(ProbeAction(probe="dump_html", kwargs={}),))
    self.browser.set_default_js_return(True)
    self.action_runner.run_block(self.mock_run, action_block)
    self.assertEqual(self.browser.invoked_js[-1].script,
                     "return document.children[0].outerHTML")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
