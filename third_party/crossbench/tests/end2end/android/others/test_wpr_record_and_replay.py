# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import json
import pathlib
import tempfile
from typing import Iterator

import pytest

from crossbench.cli.cli import CrossBenchCLI
from crossbench.helper.path_finder import WprGoFinder
from crossbench.path import check_hash
from crossbench.plt import PLATFORM
from tests import test_helper


@pytest.fixture(scope="session")
def tmp_dir() -> Iterator[pathlib.Path]:
  with tempfile.TemporaryDirectory() as tmp_dir_name:
    tmp_dir = pathlib.Path(tmp_dir_name)
    # Download prebuilt wprgo binary to run WPR on the host
    local_wpr = tmp_dir / "wprgo"
    wpr_cloud_binary = WprGoFinder(PLATFORM).cloud_binary(PLATFORM)
    PLATFORM.sh("gsutil", "cp", wpr_cloud_binary.url, local_wpr)
    assert check_hash(local_wpr, wpr_cloud_binary.file_hash)
    PLATFORM.sh("chmod", "+x", local_wpr)

    yield tmp_dir


def _wpr_record_config(wpr_go_bin) -> str:
  return json.dumps({"wpr_go_bin": str(wpr_go_bin)})


def _network_replay_config(archive) -> str:
  return json.dumps({
      "type": "wpr",
      "path": str(archive),
      "run_on_device": True
  })


def test_wpr_record_and_replay(browser_config, tmp_dir, test_env) -> None:
  cli = CrossBenchCLI()
  result_record_dir = tmp_dir / "result_record"
  target_url = "https://www.google.com/search?q=cats"
  local_wpr_go = tmp_dir / "wprgo"
  cli.run([
      "loading", f"--url={target_url}", f"--browser={browser_config}",
      f"--probe=wpr:{_wpr_record_config(local_wpr_go)}",
      f"--out-dir={result_record_dir}"
  ] + list(test_env.cq_flags))

  archives = list(
      result_record_dir.glob("*/stories/*/0/0_default/archive.wprgo"))
  assert len(archives) == 1
  assert archives[0].stat().st_size > 0

  result_replay_dir = tmp_dir / "result_replay"
  cli.run([
      "loading",
      f"--url={target_url}",
      f"--browser={browser_config}",
      f"--network={_network_replay_config(archives[0])}",
      f"--out-dir={result_replay_dir}",
  ])
  wpr_logs = list(
      result_replay_dir.glob("*/stories/*/0/0_default/network.wpr.log"))
  assert len(wpr_logs) == 1
  with wpr_logs[0].open() as wpr_log:
    lines = wpr_log.readlines()
  assert lines, "No logs"
  assert any(f'url="{target_url}" status=200' in line for line in lines)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
