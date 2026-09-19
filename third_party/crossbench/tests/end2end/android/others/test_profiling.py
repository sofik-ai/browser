# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import json

from perfetto.trace_processor.api import TraceProcessor

from crossbench.cli.cli import CrossBenchCLI
from tests import test_helper


def _profiling_config() -> str:
  return json.dumps({
      "target": "renderer_main_only",
      "pprof": False,
      "events": ["cpu-clock"],
      "count": 500000,
      "add_counters": ["context-switches"]
  })


def test_profiling_probe(browser_config, test_env, adb_root) -> None:
  del adb_root
  cli = CrossBenchCLI()
  profiling_config = _profiling_config()
  cli.run([
      "load", "--url=blank,2s", "--throw", f"--browser={browser_config}",
      f"--probe=profiling{profiling_config}",
      f"--out-dir={test_env.results_dir}"
  ] + list(test_env.cq_flags))

  simpleperf_files = list(test_env.results_dir.rglob("simpleperf.perf.data"))
  assert len(simpleperf_files) == 1
  assert simpleperf_files[0].is_file()

  with TraceProcessor(trace=str(simpleperf_files[0])) as tp:
    perf_sample_count = tp.query(
        "SELECT count(*) AS cnt FROM perf_sample").as_pandas_dataframe()
    assert perf_sample_count["cnt"][0] > 0
    perf_counters = list(
        tp.query("SELECT name FROM perf_counter_track").as_pandas_dataframe()
        ["name"])
    assert "cpu-clock" in perf_counters
    assert "context-switches" in perf_counters


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
