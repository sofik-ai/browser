# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import json

import pytest

from crossbench.plt import PLATFORM
from crossbench.plt.android_adb import Adb


@pytest.fixture
def adb_root(device_id, adb_path):
  adb = Adb(PLATFORM, device_id, adb_path)
  if adb.has_root():
    yield
  else:
    adb.root()
    yield
    adb.unroot()


@pytest.fixture
def browser_config(device_id, adb_path, bundletool) -> str:
  return json.dumps({
      "browser": "chrome",
      "driver": {
          "type": "adb",
          "device_id": device_id,
          "adb_bin": adb_path,
          "bundletool": bundletool
      }
  })
