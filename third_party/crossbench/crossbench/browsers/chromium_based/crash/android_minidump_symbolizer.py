# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Original Source: telemetry/internal/backends/chrome/android_minidump_symbolizer.py
from __future__ import annotations

import datetime
import logging
import re
from typing import TYPE_CHECKING, Optional

from typing_extensions import override

from crossbench import path as pth
from crossbench.browsers.chromium_based.crash import helper
from crossbench.browsers.chromium_based.crash.minidump_symbolizer import \
    MinidumpSymbolizer
from crossbench.helper import path_finder

if TYPE_CHECKING:
  from crossbench.browsers.chromium_based.crash.minidump_finder import \
      MinidumpFinder
  from crossbench.plt.base import Platform

# Directories relative to the build directory that may contain symbol binaries
# that can be dumped to symbolize a minidump.
_POSSIBLE_SYMBOL_BINARY_DIRECTORIES: tuple[pth.LocalPath, ...] = (
    pth.LocalPath("lib.unstripped"),
    pth.LocalPath("android_clang_arm") / "lib.unstripped",
    pth.LocalPath("android_clang_arm64") / "lib.unstripped",
)

# Mappings from Crashpad/Breakpad processor architecture values to regular
# expressions that will match the output of running "file" on a .so compiled
# for that architecture.
# The Breakpad processor architecture values are hex representations of the
# values in MDCPUArchitecture from Breakpad's minidump_format.h.
_BREAKPAD_ARCH_TO_FILE_RE: dict[str, re.Pattern] = {
    # 32-bit x86 (emulators).
    "0x0": re.compile(r"32-bit.*Intel"),
    # 64-bit x86 (Android desktop).
    "0x9": re.compile(r"64-bit.*x86-64"),
    # 32-bit ARM.
    "0x5": re.compile(r"32-bit.*ARM"),
    # 64-bit ARM.
    "0xc": re.compile(r"64-bit.*ARM"),
}

# Line looks like " processor_architecture = 0xc ".
_PROCESSOR_ARCH_RE = re.compile(
    r"\s*processor_architecture\s*\=\s*(?P<arch>\w*)\s*")

_MODULE_LIBRARY_LINE_RE = re.compile(
    r"\((code_file\))\s+= \"(?P<library_name>lib[^. ]+\.so)\"")


class AndroidMinidumpSymbolizer(MinidumpSymbolizer):

  def __init__(self,
               platform: Platform,
               dump_finder: MinidumpFinder,
               build_dir: pth.LocalPath,
               symbols_dir: Optional[pth.LocalPath] = None,
               result_dir: Optional[pth.LocalPath] = None) -> None:
    """Class for handling all minidump symbolizing code on Android.

    Args:
      platform: The platform of the host or test machine.
      dump_finder: The minidump_finder.MinidumpFinder instance that is being
          used to find minidumps for the test.
      build_dir: The directory containing Chromium build artifacts to generate
          symbols from.
      symbols_dir: An optional path to a directory to store symbols for reuse.
          Reusing symbols will result in faster symbolization times, but the
          provided directory *must* be unique per browser binary, e.g. by
          including the hash of the binary in the directory name.
      result_dir: A path to a directory to store symbolization
          results and artifacts.
    """
    # Map from minidump path to minidump_dump output (string).
    self._minidump_dump_output: dict[pth.LocalPath, str] = {}
    # Map from minidump path to the directory that should be used when
    # looking for symbol binaries.
    self._minidump_symbol_binaries_directories: dict[
        pth.LocalPath, Optional[pth.LocalPath]] = {}
    super().__init__(
        platform.host_platform,
        dump_finder,
        build_dir,
        symbols_dir=symbols_dir,
        result_dir=result_dir)

  @override
  def symbolize_minidump(self, minidump: pth.LocalPath) -> Optional[str]:
    if not self._platform.is_posix:
      logging.warning(
          "Cannot get Android stack traces unless running on a Posix host.")
      return None
    if not self._build_dir:
      logging.warning(
          "Cannot get Android stack traces without build directory.")
      return None
    return super().symbolize_minidump(minidump)

  @override
  def get_symbol_binaries(self, minidump: pth.LocalPath) -> list[pth.LocalPath]:
    """Returns a list of paths to binaries where symbols may be located.

    Args:
      minidump: The path to the minidump being symbolized.
    """
    libraries = self._extract_library_names_from_dump(minidump)
    if symbol_binary_dir := self._get_symbol_binary_directory(
        minidump, libraries):
      return [symbol_binary_dir / lib for lib in libraries]
    return []

  @override
  def get_breakpad_platform_override(self) -> Optional[str]:
    return "android"

  def _extract_library_names_from_dump(self,
                                       minidump: pth.LocalPath) -> list[str]:
    """Extracts library names that may contain symbols from the minidump.

    This is a duplicate of the logic in Chromium's
    //build/android/stacktrace/crashpad_stackwalker.py.

    Returns:
      A list of strings containing library names of interest for symbols.
    """
    default_library_name = "libmonochrome.so"

    minidump_dump_output = self._get_minidump_dump_output(minidump)
    if not minidump_dump_output:
      logging.warning(
          "Could not get minidump_dump output, defaulting to library %s",
          default_library_name)
      return [default_library_name]

    library_names = []
    in_module = False
    for line in minidump_dump_output.splitlines():
      line = line.strip()
      if line == "MDRawModule":
        in_module = True
        continue
      if line == "":
        in_module = False
        continue
      if in_module:
        m = _MODULE_LIBRARY_LINE_RE.match(line)
        if m:
          library_names.append(m.group("library_name"))

    if not library_names:
      logging.warning(
          "Could not find any library name in the dump, "
          "default to: %s", default_library_name)
      return [default_library_name]
    return library_names

  def _get_symbol_binary_directory(
      self, minidump: pth.LocalPath,
      libraries: list[str]) -> Optional[pth.LocalPath]:
    """Gets the directory that should contain symbol binaries for |minidump|.

    Args:
      minidump: The path to the minidump being analyzed.
      libraries: A list of library names that are within the minidump.

    Returns:
      A string containing the path to the directory that should contain the
      symbol binaries that can be dumped to symbolize |minidump|. Returns None
      if the directory is unable to be determined for some reason.
    """
    if minidump in self._minidump_symbol_binaries_directories:
      return self._minidump_symbol_binaries_directories[minidump]

    # Get the processor architecture reported by the minidump.
    arch = None
    minidump_output = self._get_minidump_dump_output(minidump)
    if not minidump_output:
      return None

    for line in minidump_output.splitlines():
      match = _PROCESSOR_ARCH_RE.match(line)
      if match:
        arch = match["arch"].lower()
        break
    if not arch:
      logging.error("Unable to find processor architecture for minidump %s",
                    minidump)
      self._minidump_symbol_binaries_directories[minidump] = None
      return None
    if arch not in _BREAKPAD_ARCH_TO_FILE_RE:
      logging.error(
          "Unsupported processor architecture %s for minidump %s. "
          "This is likely fixable by adding the correct mapping for the "
          "architecture in "
          "android_minidump_symbolizer._BREAKPAD_ARCH_TO_FILE_RE.", arch,
          minidump)
      self._minidump_symbol_binaries_directories[minidump] = None
      return None

    # Look for a directory that contains binaries with the correct architecture.
    matcher = _BREAKPAD_ARCH_TO_FILE_RE[arch]
    symbol_dir = None
    for symbol_subdir in _POSSIBLE_SYMBOL_BINARY_DIRECTORIES:
      possible_symbol_dir = self._build_dir / symbol_subdir
      if not possible_symbol_dir.exists():
        continue
      for f in possible_symbol_dir.iterdir():
        if f.name not in libraries:
          continue
        stdout = self._platform.sh_stdout("file", f)
        if matcher.search(stdout):
          symbol_dir = possible_symbol_dir
          break

    if not symbol_dir:
      logging.error(
          "Unable to find suitable symbol binary directory for "
          "architecture %s. "
          "This is likely fixable by adding the correct directory to "
          "android_minidump_symbolizer._POSSIBLE_SYMBOL_BINARY_DIRECTORIES.",
          arch)
    self._minidump_symbol_binaries_directories[minidump] = symbol_dir
    return symbol_dir

  def _get_minidump_dump_output(self, minidump: pth.LocalPath) -> Optional[str]:
    """Runs minidump_dump on the given minidump.

    Caches the result for reuse.

    Args:
      minidump: The path to the minidump being analyzed.

    Returns:
      A string containing the output of minidump_dump, or None if it could not
      be retrieved for some reason.
    """
    if minidump in self._minidump_dump_output:
      logging.debug("Returning cached minidump_dump output for %s", minidump)
      return self._minidump_dump_output[minidump]

    dumper_path = helper.find_crash_binary(self._platform, "minidump_dump",
                                           self._build_dir,
                                           path_finder.MinidumpDumpFinder)
    if not dumper_path:
      logging.warning("Could not find minidump_dump.")
      return None

    # Using platform.sh with capture_output=True instead of sh_stdout to
    # combine stdout and stderr into a single string.
    process = self._platform.sh(
        dumper_path, minidump, capture_output=True, check=False)
    output = f"{process.stdout.decode()}\n{process.stderr.decode()}"

    if process.returncode != 0:
      # Dumper errors often do not affect stack walkability, just a warning.
      # It's possible for the same stack to be symbolized multiple times, so
      # add a timestamp suffix to prevent artifact collisions.
      now = datetime.datetime.now()
      suffix = now.strftime("%Y-%m-%d-%H-%M-%S")
      artifact_name = f"{minidump.name}-{suffix}.log"
      logging.warning(
          "Reading minidump failed, but likely not actually an issue. "
          "Saving output to artifact %s", artifact_name)

      dest_dir = self._result_dir / "dumper_errors"
      dest_dir.mkdir(parents=True, exist_ok=True)
      dest_path = dest_dir / artifact_name
      dest_path.write_text(output)
      logging.info("Crash artifact saved to %s", dest_path)

    if output:
      self._minidump_dump_output[minidump] = output
    return output
