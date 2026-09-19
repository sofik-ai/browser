# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import abc
import logging
from typing import TYPE_CHECKING, ClassVar, Iterable

from typing_extensions import override

from crossbench.browsers.attributes import BrowserAttributes
from crossbench.browsers.chromium_based.crash.minidump_finder import \
    MinidumpFinder
from crossbench.probes.internal.base import InternalProbe
from crossbench.probes.probe_context import ProbeContext
from crossbench.probes.results import EmptyProbeResult, LocalProbeResult, \
    ProbeResult

if TYPE_CHECKING:
  from crossbench import path as pth
  from crossbench.runner.groups.browsers import BrowsersRunGroup
  from crossbench.runner.run import Run


class CrashdumpProbe(InternalProbe):
  """Probe to find and copy crash dumps for Chromium-based browsers."""
  NAME: ClassVar[str] = "cb.crashdump"

  @override
  def validate_result(self, run: Run) -> None:
    # Crashdump probe can be empty if no crashes occurred.
    pass

  def create_context(self, run: Run) -> ProbeContext:
    if run.browser_platform.is_linux:
      return LinuxCrashdumpProbeContext(self, run)
    if run.browser_platform.is_macos:
      return MacosCrashdumpProbeContext(self, run)
    return UnsupportedPlatformCrashdumpProbeContext(self, run)

  def log_run_result(self, run: Run) -> None:
    self._log_results([run])

  def log_browsers_result(self, group: BrowsersRunGroup) -> None:
    self._log_results(group.runs)

  def _log_results(self, runs: Iterable[Run]) -> None:
    filtered_runs = [run for run in runs if self in run.results]
    if not filtered_runs:
      return

    runs_with_dumps = []
    for run in filtered_runs:
      result = run.results[self]
      if not result.is_empty:
        runs_with_dumps.append((run, result))

    if not runs_with_dumps:
      return

    logging.info("-" * 80)
    logging.critical("💥 Crash dumps found:")
    for run, result in runs_with_dumps:
      logging.critical("  Run: %s", run.name)
      for path in result.file_list:
        logging.critical("    %s", path)


class CrashdumpProbeContext(ProbeContext[CrashdumpProbe], abc.ABC):

  def start(self) -> None:
    pass

  def stop(self) -> None:
    pass

  def teardown(self) -> ProbeResult:
    browser = self.run.browser
    if BrowserAttributes.CHROMIUM_BASED not in browser.attributes():
      return EmptyProbeResult()

    user_data_dir = browser.profile_data_dir
    if not user_data_dir:
      logging.debug("Browser %s user_data_dir is None", browser)
      return EmptyProbeResult()

    minidump_dir = self._get_minidump_dir(user_data_dir)
    if not minidump_dir or not self.browser_platform.is_dir(minidump_dir):
      logging.debug("No Crash Reports directory found in %s", user_data_dir)
      return EmptyProbeResult()

    finder = MinidumpFinder(self.browser_platform)
    paths, explanation = finder.get_all_minidump_paths(minidump_dir)

    if not paths:
      logging.debug("No minidumps found by MinidumpFinder: %s", explanation)
      return EmptyProbeResult()

    result_dir = self.local_result_path
    if not self.host_platform.exists(result_dir):
      self.host_platform.mkdir(result_dir, parents=True)

    copied_files = []
    for path in paths:
      dest = result_dir / path.name
      # Use pull to support both local and remote platforms
      self.browser_platform.pull(path, dest)
      copied_files.append(dest)

    logging.debug("🩺 Copied %d crash dumps to %s", len(copied_files),
                  result_dir)
    return LocalProbeResult(file=copied_files)

  @abc.abstractmethod
  def _get_minidump_dir(self, user_data_dir: pth.AnyPath) -> pth.AnyPath | None:
    pass


class LinuxCrashdumpProbeContext(CrashdumpProbeContext):

  def _get_minidump_dir(self, user_data_dir: pth.AnyPath) -> pth.AnyPath | None:
    minidump_dir = user_data_dir / "Crash Reports"
    if not self.browser_platform.is_dir(minidump_dir):
      minidump_dir = user_data_dir / "Default" / "Crash Reports"
    return minidump_dir


class MacosCrashdumpProbeContext(CrashdumpProbeContext):

  def _get_minidump_dir(self, user_data_dir: pth.AnyPath) -> pth.AnyPath | None:
    minidump_dir = user_data_dir / "Crash Reports"
    if not self.browser_platform.is_dir(minidump_dir):
      minidump_dir = user_data_dir / "Default" / "Crash Reports"
    return minidump_dir


class UnsupportedPlatformCrashdumpProbeContext(CrashdumpProbeContext):
  """Context for unsupported platforms that does nothing."""

  def _get_minidump_dir(self, user_data_dir: pth.AnyPath) -> pth.AnyPath | None:
    del user_data_dir
    return None
