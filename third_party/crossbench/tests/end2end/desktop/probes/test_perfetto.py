#!/usr/bin/env vpython3
# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Iterator

import pytest

from crossbench import plt
from crossbench.probes.cb_perfetto.downloader import PerfettoToolDownloader

if TYPE_CHECKING:
  from tests.test_helper import TestEnv


@contextlib.contextmanager
def setup_platform_cache_dir() -> Iterator[plt.Platform]:
  platform = plt.PLATFORM
  original_cache_dir = platform.cache_dir()
  with platform.TemporaryDirectory() as temp_dir:
    try:
      platform.set_cache_dir(temp_dir)
      yield platform
    finally:
      platform.set_cache_dir(original_cache_dir)


@pytest.mark.skipif(
    plt.PLATFORM.is_win, reason="No binary available on windows")
def test_perfetto_downloader(test_env: TestEnv):
  if plt.PLATFORM.is_linux and test_env.is_cq:
    raise pytest.skip("Old glibc on the CQ is too old for tracebox")
  with setup_platform_cache_dir() as platform:
    downloader = PerfettoToolDownloader("tracebox", platform=platform)
    assert not platform.exists(downloader.path)
    result = downloader.download()
    assert downloader.path == result
    assert platform.exists(result)
    version_str = platform.sh_stdout(result, "--version")
    assert downloader.version in version_str
