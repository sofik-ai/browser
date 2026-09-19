# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Original Source: telemetry/internal/backends/chrome/desktop_minidump_symbolizer.py
from __future__ import annotations

import logging
import re
from typing import Optional

from typing_extensions import override

from crossbench import path as pth
from crossbench.browsers.chromium_based.crash import helper
from crossbench.browsers.chromium_based.crash.minidump_symbolizer import \
    MinidumpSymbolizer
from crossbench.helper import path_finder
from crossbench.plt.base import SubprocessError

_MINIDUMP_BINARY_RE = re.compile(r'\(code_file\)\s+=\s+\"(?P<path>.*)\"')
_BUNDLED_DYLIB_RE = re.compile(
    r"Framework\.framework/Versions/\d+.\d+.\d+.\d+/Libraries/.*\.dylib")


class DesktopMinidumpSymbolizer(MinidumpSymbolizer):

  @override
  def symbolize_minidump(self, minidump: pth.LocalPath) -> Optional[str]:
    """Gets the stack trace from the given minidump.

    Args:
      minidump: the path to the minidump on disk

    Returns:
      None if the stack could not be retrieved for some reason, otherwise a
      string containing the stack trace.
    """
    if self._platform.is_win:
      return self.symbolize_minidump_win(minidump)
    return super().symbolize_minidump(minidump)

  def symbolize_minidump_win(self, minidump: pth.LocalPath) -> Optional[str]:
    cdb = self._get_cdb_path()
    if not cdb:
      logging.warning("cdb.exe not found.")
      return None
    # Move to the thread which triggered the exception (".ecxr"). Then include
    # a description of the exception (".lastevent"). Also include all the
    # threads' stacks ("~*kb30") as well as the ostensibly crashed stack
    # associated with the exception context record ("kb30"). Note that stack
    # dumps, including that for the crashed thread, may not be as precise as
    # the one starting from the exception context record.
    # Specify kb instead of k in order to get four arguments listed, for
    # easier diagnosis from stacks.
    output = self._platform.sh_stdout(cdb, "-y", self._build_dir, "-c",
                                      ".ecxr;.lastevent;kb30;~*kb30;q", "-z",
                                      minidump)

    # The output we care about starts with "Last event:" or possibly
    # other things we haven't seen yet. If we can't find the start of the
    # last event entry, include output from the beginning.
    info_start = output.find("Last event:")
    if info_start == -1:
      info_start = 0
    info_end = output.find("quit:")
    if info_end == -1:
      return output[info_start:]
    return output[info_start:info_end]

  @override
  def get_symbol_binaries(self, minidump: pth.LocalPath) -> list[pth.LocalPath]:
    """Returns a list of paths to binaries where symbols may be located.

    Args:
      minidump: The path to the minidump being symbolized.
    """
    minidump_dump = helper.find_crash_binary(self._platform, "minidump_dump",
                                             self._build_dir,
                                             path_finder.MinidumpDumpFinder)
    if not minidump_dump:
      logging.warning("minidump_dump not found.")
      return []

    symbol_binaries: list[pth.LocalPath] = []

    try:
      minidump_output = self._platform.sh_stdout(
          minidump_dump, minidump, quiet=True)
    except SubprocessError as e:
      # For some reason minidump_dump always fails despite successful dumping.
      minidump_output = e.stdout.decode() if e.stdout else ""

    for minidump_line in minidump_output.splitlines():
      if line_match := _MINIDUMP_BINARY_RE.search(minidump_line):
        binary_path_str = line_match.group("path")
        binary_path = self._platform.local_path(binary_path_str)
        if not binary_path.is_file():
          continue

        # Filter out system binaries.
        if binary_path_str.startswith(
            ("/usr/lib/", "/System/Library/", "/lib/")):
          continue

        # Filter out other binary file types which have no symbols.
        if binary_path.suffix in (".pak", ".bin", ".dat", ".ttf"):
          continue

        symbol_binaries.append(binary_path)
    return self._filter_symbol_binaries(symbol_binaries)

  def _filter_symbol_binaries(
      self, symbol_binaries: list[pth.LocalPath]) -> list[pth.LocalPath]:
    """Filters out unnecessary symbol binaries to save symbolization time.

    Args:
      symbol_binaries: A list of paths to binaries that will have their
          symbols dumped.

    Returns:
      A copy of |symbol_binaries| with any unnecessary paths removed.
    """
    if self._platform.is_macos:
      self._filter_symbol_binaries_macos(symbol_binaries)
    return symbol_binaries

  def _filter_symbol_binaries_macos(
      self, symbol_binaries: list[pth.LocalPath]) -> list[pth.LocalPath]:
    # The vast majority of the symbol binaries for component builds on Mac
    # are .dylib, and none of them appear to contribute any additional
    # information. So, remove them to save a *lot* of time.
    # Do process dylibs that aren't component build dylibs though.
    filtered_binaries = []
    for binary in symbol_binaries:
      binary_name = binary.name
      if not binary_name.endswith(".dylib") or _BUNDLED_DYLIB_RE.search(
          binary_name):
        filtered_binaries.append(binary)
    return filtered_binaries

  def _get_cdb_path(self) -> Optional[pth.LocalPath]:
    # cdb.exe might have been co-located with the browser's executable
    # during the build, but that's not a certainty. (This is only done
    # in Chromium builds on the bots, which is why it's not a hard
    # requirement.) See if it's available.
    colocated_cdb = self._build_dir / "cdb" / "cdb.exe"
    if colocated_cdb.is_file():
      return colocated_cdb

    possible_paths = (
        # Installed copies of the Windows SDK.
        "Windows Kits/*/Debuggers/x86",
        "Windows Kits/*/Debuggers/x64",
        # Old copies of the Debugging Tools for Windows.
        "Debugging Tools For Windows",
        "Debugging Tools For Windows (x86)",
        "Debugging Tools For Windows (x64)",
        # The hermetic copy of the Windows toolchain in depot_tools.
        "win_toolchain/vs_files/*/win_sdk/Debuggers/x86",
        "win_toolchain/vs_files/*/win_sdk/Debuggers/x64",
    )

    for possible_path in possible_paths:
      # Wildcard search using platform.glob
      for path in pth.LocalPath("/").glob(possible_path):
        app_path = path / "cdb.exe"
        if app_path.is_file():
          return app_path
    return None
