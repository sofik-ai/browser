# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import hjson

from crossbench.cli.config.driver import DriverConfig
from tests import test_helper


def test_specific_device_id(device_id, adb_path) -> None:
  config_dict = {"type": "adb", "device_id": device_id, "adb_bin": adb_path}
  driver_config = DriverConfig.parse(hjson.dumps(config_dict))
  assert driver_config.device_id == device_id


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
