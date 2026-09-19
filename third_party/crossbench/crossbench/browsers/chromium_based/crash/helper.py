# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Type

if TYPE_CHECKING:
  from crossbench import path as pth
  from crossbench.helper.path_finder import BasePathFinder
  from crossbench.plt.base import Platform


# TODO: merge with path finder helper
def find_crash_binary(
    platform: Platform,
    binary_name: str,
    build_dir: Optional[pth.LocalPath] = None,
    finder_cls: Optional[Type[BasePathFinder]] = None
) -> Optional[pth.LocalPath]:
  if build_dir:
    candidate = build_dir / binary_name
    if candidate.is_file():
      return candidate

  if finder_cls:
    if path := finder_cls.local_binary():
      return path

  if which_path := platform.which(binary_name):
    return platform.local_path(which_path)

  return None
