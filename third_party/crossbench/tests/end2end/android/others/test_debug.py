# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import json

from crossbench.cli.cli import CrossBenchCLI
from tests import test_helper


def test_debug(browser_config, test_env) -> None:
  cli = CrossBenchCLI()
  cli.run([
      "loading", "--url=blank", f"--browser={browser_config}", "--debug",
      f"--out-dir={test_env.results_dir}"
  ] + list(test_env.cq_flags))

  result_files = list(test_env.results_dir.glob("cb.results.json"))
  assert len(result_files) == 1
  with result_files[0].open() as f:
    result = json.load(f)
    assert result["success"]
    assert not result["errors"]


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
