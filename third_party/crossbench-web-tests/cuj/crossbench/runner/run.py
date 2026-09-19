#!/usr/bin/env vpython3
# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from runner.paths import THIRD_PARTY_CROSSBENCH

# This is the earliest entrypoint into the runner.
# Try to import some simple crossbench package here to
# check that crossbench is setup properly.
try:
  # pylint: disable=unused-import
  from crossbench.types import Json
except ImportError:
  # Manually add crossbench to the path.
  # This is necessary when running under vpython within web-tests
  # (such as when running presubmit).
  sys.path.append(str(THIRD_PARTY_CROSSBENCH))

# pylint: disable=ungrouped-imports
from runner.cli import runner_cli

if __name__ == "__main__":
  argv = sys.argv
  runner_cli(argv[1:])
