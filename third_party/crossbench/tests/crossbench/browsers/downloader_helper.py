# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import abc
import pathlib
from unittest import mock

from typing_extensions import override

from tests.crossbench.base import BaseCrossbenchTestCase


class AbstractDownloaderTestCase(BaseCrossbenchTestCase, metaclass=abc.ABCMeta):
  __test__ = False

  @override
  def setUp(self) -> None:
    super().setUp()
    self.platform = mock.Mock(
        is_remote=False,
        is_linux=False,
        is_macos=False,
        exists=self.fs.exists,
        sh_results=[],
        path=pathlib.Path)
    self.platform.search_app = lambda x: x
    self.platform.which = pathlib.Path
    self.platform.host_platform = self.platform
    self.cache_dir = pathlib.Path("crossbench/binary_cache")
    self.fs.create_dir(self.cache_dir)
