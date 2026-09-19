# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import logging

from crossbench.cli.ui import ColoredLogFormatter


def setup_logging() -> None:
  stream_handler = logging.StreamHandler()
  stream_handler.setFormatter(ColoredLogFormatter())
  logging.basicConfig(level=logging.INFO, handlers=[stream_handler], force=True)
