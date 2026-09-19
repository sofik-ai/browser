#!/usr/bin/env vpython3
# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# The --adb-device-id flag is required to run tests on your Android device.
# Otherwise, the Android tests will be ignored.

from __future__ import annotations

import argparse
import os
import pathlib
import sys
from typing import Final

FILE_PATH: Final = pathlib.Path(__file__).absolute()
END2END_TEST_DIR: Final = FILE_PATH.parent
REPO_DIR: Final = FILE_PATH.parents[2]

if REPO_DIR not in sys.path:
  sys.path.insert(0, str(REPO_DIR))

from tests import test_helper  # noqa: E402

if __name__ == "__main__":
  more_flags = []
  parser = argparse.ArgumentParser(allow_abbrev=False)
  parser.add_argument("--ignore-tests", required=False)
  parser.add_argument("--adb-device-id", required=False)
  parser.add_argument("--test-gsutil-path", required=False)

  args, _ = parser.parse_known_args()
  if args.ignore_tests:
    subfolders = args.ignore_tests.split(",")
    more_flags.extend([f"--ignore={END2END_TEST_DIR / x}" for x in subfolders])
  elif not args.adb_device_id:
    more_flags.append(f"--ignore={END2END_TEST_DIR / 'android'}")
  if args.test_gsutil_path:
    more_flags.append(f"--test-gsutil-path={args.test_gsutil_path}")
    current_path = os.environ["PATH"]
    new_path = pathlib.Path(args.test_gsutil_path).parent / "python-bin"
    updated_path = f"'{current_path}:{new_path}'"
    os.environ["PATH"] = updated_path
    os.environ["DEPOT_TOOLS_UPDATE"] = "0"

  test_helper.run_pytest(
      END2END_TEST_DIR,
      *more_flags,
  )
