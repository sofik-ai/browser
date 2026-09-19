# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import enum
from typing import TYPE_CHECKING

import pytest

from crossbench.cli.cli import CrossBenchCLI
from crossbench.parse import NumberParser
from tests import test_helper

if TYPE_CHECKING:
  from tests.test_helper import TestEnv


class SpeedometerVersion(enum.StrEnum):
  V2_0 = "2.0"
  V2_1 = "2.1"
  V3_0 = "3.0"


@pytest.mark.parametrize("version", SpeedometerVersion)
def test_speedometer(browser_config, version, test_env: TestEnv) -> None:
  CrossBenchCLI().run([
      f"sp{version}", f"--browser={browser_config}",
      f"--out-dir={test_env.results_dir}"
  ] + list(test_env.cq_flags))

  with (test_env.results_dir / f"speedometer_{version}.csv").open() as csv:
    lines = csv.readlines()
    error_message = f"csv content: {lines}"
    assert "Score" in lines[-1], error_message
    assert NumberParser.positive_zero_float(
        lines[-1].split("\t")[-1]) > 0, error_message


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
