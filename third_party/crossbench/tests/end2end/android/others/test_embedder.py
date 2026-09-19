# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from crossbench.cli.cli import CrossBenchCLI
from crossbench.parse import NumberParser
from tests import test_helper

if TYPE_CHECKING:
  from tests.test_helper import TestEnv


def _browser_config(device_id, adb_path) -> str:
  return json.dumps({
      "browser": "com.google.android.googlequicksearchbox",
      "driver": {
          "type": "adb",
          "device_id": device_id,
          "adb_bin": adb_path
      }
  })


def _embedder_config() -> str:
  return json.dumps({"js": "return {WSRT: google.timers.load.wsrt}"})


def test_embedder(device_id, adb_path, test_env: TestEnv, adb_root) -> None:
  del adb_root
  browser_config = _browser_config(device_id, adb_path)
  CrossBenchCLI().run((
      "embedder",
      f"--browser={browser_config}",
      "--splashscreen=skip",
      f"--cuj-config={test_env.root_dir}/config/team/woa/embedder_cuj_config.hjson",
      # TODO(zbikowski): Add this flag once embedder in the emulator image is
      # updated.
      # "--embedder-process-name=googleapp",
      f"--probe=embedder:{_embedder_config()}",
      f"--out-dir={test_env.results_dir}") + test_env.cq_flags)

  with (test_env.results_dir / "embedder.csv").open() as csv:
    lines = csv.readlines()
    error_message = f"csv content: {lines}"
    assert "WSRT" in lines[-1], error_message
    assert NumberParser.positive_zero_float(
        lines[-1].split("\t")[-1]) > 0, error_message


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
