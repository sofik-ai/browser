# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Original Source: telemetry/internal/backends/chrome/minidump_finder.py
from __future__ import annotations

import datetime
import time
from typing import TYPE_CHECKING, Optional

from crossbench.browsers.chromium_based.crash import helper
from crossbench.helper import path_finder

if TYPE_CHECKING:
  from crossbench import path as pth
  from crossbench.plt.base import Platform


def _parse_crashpad_date_time(date_time_str: str) -> datetime.datetime:
  # Python strptime does not support time zone parsing, strip it.
  date_time_parts = date_time_str.split()
  if len(date_time_parts) >= 3:
    date_time_str = " ".join(date_time_parts[:2])
  return datetime.datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")


class MinidumpFinder:
  """Handles finding Crashpad/Breakpad minidumps.

  In addition to whatever data is expected to be returned, most public methods
  also return a list of strings. These strings are what would normally be
  logged, but returned in the list instead of being logged directly to help
  cut down on log spam from uses such as
  BrowserBackend.GetRecentMinidumpPathWithTimeout().
  """

  def __init__(self,
               platform: Platform,
               build_dir: Optional[pth.LocalPath] = None) -> None:
    self._platform: Platform = platform
    self._build_dir: Optional[pth.LocalPath] = build_dir
    self._os: str = platform.name
    self._arch: str = str(platform.machine)
    self._minidump_path_crashpad_retrieval: dict[pth.AnyPath, bool] = {}
    self._explanation: list[str] = []

  def minidump_obtained_from_crashpad(self, minidump: pth.AnyPath) -> bool:
    """Returns whether the given minidump was found via Crashpad or not.

    Args:
      minidump: the path to the minidump being checked.

    Returns:
      False if the dump was found via globbing, else True.
    """
    # Default to Crashpad where we hope to be eventually.
    return self._minidump_path_crashpad_retrieval.get(minidump, True)

  def get_all_crashpad_minidumps(
      self, minidump_dir: pth.AnyPath
  ) -> tuple[Optional[list[tuple[datetime.datetime, pth.AnyPath]]], list[str]]:
    """Returns all minidumps in the given directory findable by Crashpad.

    Args:
      minidump_dir: The directory to look for minidumps in.

    Returns:
      A tuple. The first element is a list of paths to minidumps found by
      Crashpad, or None in the event of an error. The second element is a list
      of strings containing logging information generated while searching for
      the minidumps.
    """
    self._explanation = [
        "Attempting to find all Crashpad minidump files for a "
        "suspected Chrome crash."
    ]
    return self._get_all_crashpad_minidumps(minidump_dir), self._explanation

  # TODO: find better name, since this does not return all paths
  def get_all_minidump_paths(
      self, minidump_dir: pth.AnyPath) -> tuple[list[pth.AnyPath], list[str]]:
    """Finds all minidumps for either Crashpad or Breakpad.

    If any Crashpad minidumps are found, only they will be returned. Otherwise,
    Breakpad minidumps will be returned.

    Args:
      minidump_dir: The directory to look for minidumps in.

    Returns:
      A tuple. The first element is a list of paths to the found minidumps, or
      None in the event of an error. The second element is a list of strings
      containing logging information generated while searching for the
      minidumps.
    """
    self._explanation = [
        "Attempting to find all minidump files for a "
        "suspected Chrome crash. Crashpad minidumps will be "
        "searched for first, falling back to Breakpad "
        "minidumps if none are found."
    ]
    return self._get_all_minidump_paths(minidump_dir), self._explanation

  def get_most_recent_minidump(
      self,
      minidump_dir: pth.AnyPath) -> tuple[Optional[pth.AnyPath], list[str]]:
    """Finds the most recently created Crashpad or Breakpad minidump.

    Args:
      minidump_dir: The directory to look for minidumps in.

    Returns:
      A tuple. The first element is a path to the found minidump, or None if
      no minidumps were found. The second element is a list of strings
      containing logging information generated while searching for the
      minidumps.
    """
    self._explanation = [
        "Attempting to find the most recent minidump file for "
        "a suspected Chrome crash. Crashpad minidumps will be "
        "searched for first, falling back to Breakpad "
        "minidumps if none are found."
    ]
    return self._get_most_recent_minidump(minidump_dir), self._explanation

  def _get_all_crashpad_minidumps(
      self,
      minidump_dir: pth.AnyPath) -> list[tuple[datetime.datetime, pth.AnyPath]]:
    if not minidump_dir:
      self._explanation.append("No minidump directory provided. Likely "
                               "attempted to retrieve the Crashpad minidumps "
                               "after the browser was already closed.")
      return []

    crashpad_database_util = helper.find_crash_binary(
        self._platform, "crashpad_database_util", self._build_dir,
        path_finder.CrashpadDatabaseUtilFinder)
    if not crashpad_database_util:
      self._explanation.append("Unable to find crashpad_database_util. This "
                               "is likely due to running on a platform that "
                               "does not support Crashpad.")
      return []

    self._explanation.append(
        f"Found crashpad_database_util at {crashpad_database_util}")

    report_output = self._platform.sh_stdout(crashpad_database_util,
                                             f"--database={minidump_dir}",
                                             "--show-pending-reports",
                                             "--show-completed-reports",
                                             "--show-all-report-info")

    last_indentation = -1
    reports_list: list[tuple[datetime.datetime, pth.AnyPath]] = []
    report_dict: dict[str, str] = {}
    for report_line in report_output.splitlines():
      # Report values are grouped together by the same indentation level.
      current_indentation = 0
      for report_char in report_line:
        if not report_char.isspace():
          break
        current_indentation += 1

      # Decrease in indentation level indicates a new report is being printed.
      if current_indentation >= last_indentation:
        if ":" in report_line:
          report_key, report_value = report_line.split(":", 1)
          if report_value:
            report_dict[report_key.strip()] = report_value.strip()
      elif report_dict:
        try:
          report_time = _parse_crashpad_date_time(report_dict["Creation time"])
          report_path = self._platform.path(report_dict["Path"].strip())
          reports_list.append((report_time, report_path))
        except (ValueError, KeyError) as e:
          self._explanation.append("Expected to find keys 'Path' and 'Creation "
                                   "time' in Crashpad report, but one or both "
                                   f"don't exist: {e}")
        finally:
          report_dict = {}

      last_indentation = current_indentation

    # Include the last report.
    if report_dict:
      try:
        report_time = _parse_crashpad_date_time(report_dict["Creation time"])
        report_path = self._platform.path(report_dict["Path"].strip())
        reports_list.append((report_time, report_path))
      except (ValueError, KeyError) as e:
        self._explanation.append("Expected to find keys 'Path' and 'Creation "
                                 "time' in Crashpad report, but one or both "
                                 f"don't exist: {e}")

    return reports_list

  def _get_all_minidump_paths(self,
                              minidump_dir: pth.AnyPath) -> list[pth.AnyPath]:
    if reports_list := self._get_all_crashpad_minidumps(minidump_dir):
      for _, path in reports_list:
        self._minidump_path_crashpad_retrieval[path] = True
      return [report[1] for report in reports_list]
    self._explanation.append("No minidumps found via crashpad_database_util, "
                             "falling back to globbing for Breakpad "
                             "minidumps.")
    if dumps := self._get_breakpad_minidump_paths(minidump_dir):
      self._explanation.append("Found Breakpad minidump via globbing.")
      for dump in dumps:
        self._minidump_path_crashpad_retrieval[dump] = False
      return dumps
    self._explanation.append(
        "Failed to find any Breakpad minidumps via globbing.")
    return []

  def _get_most_recent_crashpad_minidump(
      self, minidump_dir: pth.AnyPath) -> Optional[pth.AnyPath]:
    if reports_list := self._get_all_crashpad_minidumps(minidump_dir):
      _, most_recent_report_path = max(reports_list)
      return most_recent_report_path

    return None

  def _get_breakpad_minidump_paths(
      self, minidump_dir: pth.AnyPath) -> list[pth.AnyPath]:
    if not minidump_dir:
      self._explanation.append("Attempted to fetch Breakpad minidump paths "
                               "without a minidump directory. The browser was "
                               "likely closed before attempting to fetch.")
      return []
    return list(self._platform.glob(minidump_dir, "*.dmp"))

  def _get_most_recent_minidump(
      self, minidump_dir: pth.AnyPath) -> Optional[pth.AnyPath]:
    # Crashpad dump layout will be the standard eventually, check it first.
    crashpad_dump = True
    most_recent_dump = self._get_most_recent_crashpad_minidump(minidump_dir)

    # Typical breakpad format is simply dump files in a folder.
    if not most_recent_dump:
      crashpad_dump = False
      self._explanation.append("No minidump found via crashpad_database_util, "
                               "falling back to globbing for Breakpad "
                               "minidump.")
      dumps = self._get_breakpad_minidump_paths(minidump_dir)
      if dumps:
        most_recent_dump = max(dumps, key=self._platform.last_modified)
        if most_recent_dump:
          self._explanation.append("Found Breakpad minidump via globbing.")

    # As a sanity check, make sure the crash dump is recent.
    if most_recent_dump:
      mtime = self._platform.last_modified(most_recent_dump)
      if mtime < (time.time() - (5 * 60)):
        self._explanation.append(
            "Crash dump is older than 5 minutes. May not be correct.")

    if most_recent_dump:
      self._minidump_path_crashpad_retrieval[most_recent_dump] = crashpad_dump
    return most_recent_dump
