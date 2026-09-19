# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from typing_extensions import override

from crossbench import config
from crossbench import path as pth
from crossbench.benchmarks.loading.config.pages import PagesConfig
from crossbench.benchmarks.loading.loading_benchmark import LoadingBenchmark

if TYPE_CHECKING:
  import argparse


class BrowserStartupBenchmark(LoadingBenchmark):
  """Benchmark for measuring browser startup performance."""

  NAME = "browser-startup"

  @classmethod
  @override
  def aliases(cls) -> tuple[str, ...]:
    return ()

  @classmethod
  def _base_dir(cls) -> pth.LocalPath:
    return config.config_dir() / "benchmark" / "browser_startup"

  @classmethod
  @override
  def default_probe_config_path(cls) -> pth.LocalPath:
    return cls._base_dir() / "probe.hjson"

  @classmethod
  def default_pages_config_path(cls) -> pth.LocalPath:
    return cls._base_dir() / "story.hjson"

  @classmethod
  def get_pages_config(
      cls, args: Optional[argparse.Namespace] = None) -> PagesConfig:
    del args
    return PagesConfig.parse(cls.default_pages_config_path())
