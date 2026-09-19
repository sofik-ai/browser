# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import enum
import json
import unittest
from typing import TYPE_CHECKING

from crossbench.cli.cli import CrossBenchCLI
from tests import test_helper

if TYPE_CHECKING:
  from tests.test_helper import TestEnv


def _browser_config(device_id, adb_path) -> str:
  return json.dumps({
      "browser": "chrome-stable",
      "driver": {
          "type": "adb",
          "device_id": device_id,
          "adb_bin": adb_path
      }
  })


class BenchmarkType(enum.StrEnum):
  PHONE = "loadline2-phone"
  TABLET = "loadline2-tablet"
  WEBAPI = "loadline2-webapi-phone"
  DEBUG = "loadline2-phone-debug"


def _verify_default_metrics(out_dir, only_total=False):
  result_csv = out_dir / "benchmark_score.csv"
  with result_csv.open() as csv:
    lines = csv.readlines()
    assert len(lines) == 12

    titles = lines[0].split(",")
    assert len(titles) == 2
    assert titles[0] == "Metric"

    metrics = dict(line.split(",") for line in lines[1:])

    assert "TOTAL_SCORE" in metrics, f"Total score missing: {lines}"
    value = metrics["TOTAL_SCORE"]
    assert value, f"Encountered empty value. CSV contents: {lines}"
    assert float(value) > 0, f"Expected positive number, but got {value}"
    if only_total:
      return

    for metric, value in metrics:
      assert metric, f"Encountered empty metric name. CSV contents: {lines}"
      assert value, f"Encountered empty value. CSV contents: {lines}"
      assert float(value) > 0, f"Expected positive number, but got {value}"


def test_loadline2_phone(device_id, adb_path, test_env: TestEnv) -> None:
  _test_loadline2_default(device_id, adb_path, BenchmarkType.PHONE, test_env)


def test_loadline2_tablet(device_id, adb_path, test_env: TestEnv) -> None:
  _test_loadline2_default(device_id, adb_path, BenchmarkType.TABLET, test_env)


# TODO(crbug.com/489679186): Find a way to test LoadLine 2 WebAPI without root.
@unittest.skip("LoadLine2 WebAPI requires root to run")
def test_loadline2_webapi(device_id, adb_path, test_env: TestEnv) -> None:
  _test_loadline2_default(device_id, adb_path, BenchmarkType.WEBAPI, test_env)


def test_loadline2_debug(device_id, adb_path, test_env: TestEnv) -> None:
  _test_loadline2_default(device_id, adb_path, BenchmarkType.DEBUG, test_env)


def _test_loadline2_default(device_id, adb_path, benchmark_type,
                            test_env: TestEnv) -> None:
  cli = CrossBenchCLI()
  browser_config = _browser_config(device_id, adb_path)
  out_dir = test_env.results_dir / f"default_{benchmark_type}"
  cli.run([
      benchmark_type,
      f"--browser={browser_config}",
      "--repeat=1",
      "--debug",
      f"--out-dir={out_dir}",
      "--time-unit=2s",
  ] + list(test_env.cq_flags))

  # With only 1 repetition, there's a chance that one story won't produce a
  # metric. To avoid flaky failures, we only check the total score here.
  _verify_default_metrics(out_dir, only_total=True)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
