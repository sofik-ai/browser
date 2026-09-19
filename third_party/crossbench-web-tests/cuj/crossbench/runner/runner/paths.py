# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import logging
from pathlib import Path

WEB_TESTS_ROOT: Path = Path(
    __file__).resolve().parent.parent.parent.parent.parent
THIRD_PARTY_CROSSBENCH: Path = WEB_TESTS_ROOT / "third_party" / "crossbench"

if not (THIRD_PARTY_CROSSBENCH).is_dir():
  logging.warning(
      "web-tests does not have the expected layout. Imports may fail.")

BENCHMARKS: Path = WEB_TESTS_ROOT / "cuj" / "crossbench" / "benchmarks"
CUJS: Path = WEB_TESTS_ROOT / "cuj" / "crossbench" / "cujs"
RESULTS: Path = WEB_TESTS_ROOT / "cuj" / "crossbench" / "runner" / "results"
