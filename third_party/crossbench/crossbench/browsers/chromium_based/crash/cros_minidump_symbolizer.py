# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Original Source: telemetry/internal/backends/chrome/cros_minidump_symbolizer.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from typing_extensions import override

if TYPE_CHECKING:
  from crossbench import path as pth

from crossbench.browsers.chromium_based.crash.minidump_symbolizer import \
    MinidumpSymbolizer


class CrOSMinidumpSymbolizer(MinidumpSymbolizer):

  @override
  def symbolize_minidump(self, minidump: pth.LocalPath) -> Optional[str]:
    if not self._platform.is_posix:
      logging.warning("Cannot get stack traces unless running on a Posix host.")
      return None
    if not self._build_dir:
      logging.warning("Missing build dir, cannot get stack traces")
      return None
    return super().symbolize_minidump(minidump)

  @override
  def get_symbol_binaries(self, minidump: pth.LocalPath) -> list[pth.LocalPath]:
    """Returns a list of paths to binaries where symbols may be located.

    Args:
      minidump: The path to the minidump being symbolized.
    """
    del minidump
    return [self._build_dir / "chrome"]

  @override
  def get_breakpad_platform_override(self) -> str:
    """Returns the platform to be passed to generate_breakpad_symbols."""
    return "chromeos"
