# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
import dataclasses
import enum
from pathlib import Path
from typing import Self

from crossbench.config import ConfigEnum, ConfigObject, ConfigParser
from crossbench.parse import NumberParser, ObjectParser
from typing_extensions import override


@enum.unique
class TargetPlatform(ConfigEnum):
  ANDROID = ("adb", "Android via adb")
  CHROME_OS = ("cros", "ChromeOS via ssh")
  LOCAL = ("local", "local browser")


@dataclasses.dataclass(frozen=True)
class Test:
  name: str
  variant: str
  path: Path
  probe_config: Path | None
  browser_flags: Path
  extensions: Path | None
  crossbench_args: str
  page_config: Path | None = None

  @property
  def full_name(self) -> str:
    if self.variant:
      return f"{self.name}_{self.variant}"

    return self.name

  @property
  def crossbench_command(self) -> str:
    return self.name


@dataclasses.dataclass(frozen=True)
class Benchmark(Test):
  pass


@dataclasses.dataclass(frozen=True)
class Cuj(Test):
  page_config: Path

  @property
  @override
  def crossbench_command(self) -> str:
    return "loading"


@dataclasses.dataclass(frozen=True)
class TestInvocation:
  test: Test
  min_successes: int | None = None
  max_consecutive_failures: int | None = None
  playback: str | None = None
  setup_delay: str | None = None
  startup_delay: str | None = None


@dataclasses.dataclass(frozen=True)
class TestGroup(ConfigObject):
  filter_regex: str = ".*"
  variants_filter_regex: str = ".*"
  min_successes: int | None = None
  max_consecutive_failures: int | None = None
  playback: str | None = None
  setup_delay: str | None = None
  startup_delay: str | None = None

  @classmethod
  @override
  def config_parser(cls) -> ConfigParser[Self]:
    parser = ConfigParser(cls)
    parser.add_argument(
        "filter_regex", type=ObjectParser.non_empty_str, default=".*")
    parser.add_argument(
        "variants_filter_regex", type=ObjectParser.non_empty_str, default=".*")
    parser.add_argument(
        "min_successes", type=NumberParser.positive_int, required=False)
    parser.add_argument(
        "max_consecutive_failures",
        type=NumberParser.positive_int,
        required=False)
    parser.add_argument(
        "playback", type=ObjectParser.non_empty_str, required=False)
    parser.add_argument(
        "setup_delay", type=ObjectParser.non_empty_str, required=False)
    parser.add_argument(
        "startup_delay", type=ObjectParser.non_empty_str, required=False)
    return parser

  @classmethod
  @override
  def parse_str(cls, value: str) -> Self:
    raise ValueError("Cannot parse TestGroup from string")


@dataclasses.dataclass(frozen=True)
class TestGroupConfig(ConfigObject):
  groups: list[TestGroup]

  @classmethod
  @override
  def config_parser(cls) -> ConfigParser[Self]:
    parser = ConfigParser(cls)
    parser.add_argument("groups", type=TestGroup, is_list=True, default=[])
    return parser

  @classmethod
  @override
  def parse_str(cls, value: str) -> Self:
    raise ValueError("Cannot parse TestGroupConfig from string")

  @classmethod
  def from_cmdline_flags(cls, tests: str, variants: str, playback: str | None,
                         setup_delay: str | None,
                         startup_delay: str | None) -> TestGroupConfig:
    return TestGroupConfig(groups=[
        TestGroup(
            filter_regex=tests,
            variants_filter_regex=variants,
            playback=playback,
            setup_delay=setup_delay,
            startup_delay=startup_delay)
    ])


@dataclasses.dataclass(frozen=True)
class CliConfig:
  platform: TargetPlatform
  device: str | None
  adb_bin: Path | None
  browser: str | None
  tests: str
  variants: str
  secrets: Path | None
  out_dir: Path | None
  results_prefix: str | None
  debug: bool
  dry_run: bool
  playback: str | None
  setup_delay: str | None
  startup_delay: str | None
  wait_for_debugger: bool
  no_symlinks: bool
  run_tast_analyzer: bool

  @classmethod
  def from_cmdline(cls, argv: list[str]) -> CliConfig:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", type=TargetPlatform.parse, required=True)
    parser.add_argument(
        "--device", type=ObjectParser.non_empty_str, required=False)
    parser.add_argument(
        "--adb-bin", type=Path, required=False)
    parser.add_argument(
        "--browser", type=ObjectParser.non_empty_str, required=False)
    parser.add_argument(
        "--playback", type=ObjectParser.non_empty_str, required=False)
    parser.add_argument(
        "--startup-delay", type=ObjectParser.non_empty_str, required=False)
    parser.add_argument(
        "--setup-delay", type=ObjectParser.non_empty_str, required=False)
    parser.add_argument(
        "--tests", type=ObjectParser.non_empty_str, default=None)
    parser.add_argument(
        "--variants", type=ObjectParser.non_empty_str, default=".*")
    parser.add_argument("--secrets", type=Path, required=False)
    parser.add_argument("--out-dir", type=Path, required=False)
    parser.add_argument(
        "--results-prefix", type=ObjectParser.any_str, default="")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--wait-for-debugger", action="store_true", default=False)
    parser.add_argument(
        "--no-symlinks", action="store_true", default=False)
    parser.add_argument(
        "--run-tast-analyzer", action="store_true", default=False)

    parsed = parser.parse_args(argv)

    secrets_file: Path | None = parsed.secrets.resolve(
    ) if parsed.secrets else None

    out_dir_path: Path | None = parsed.out_dir.resolve(
    ) if parsed.out_dir else None

    adb_bin_path: Path | None = parsed.adb_bin.resolve(
    ) if parsed.adb_bin else None

    return CliConfig(
        platform=parsed.platform,
        device=parsed.device,
        adb_bin=adb_bin_path,
        browser=parsed.browser,
        tests=parsed.tests,
        variants=parsed.variants,
        playback=parsed.playback,
        setup_delay=parsed.setup_delay,
        startup_delay=parsed.startup_delay,
        secrets=secrets_file,
        out_dir=out_dir_path,
        results_prefix=parsed.results_prefix,
        debug=parsed.debug,
        dry_run=parsed.dry_run,
        wait_for_debugger=parsed.wait_for_debugger,
        no_symlinks=parsed.no_symlinks,
        run_tast_analyzer=parsed.run_tast_analyzer,
    )


@dataclasses.dataclass(frozen=True)
class RunConfig:
  platform: TargetPlatform
  device: str | None
  adb_bin: Path | None
  browser: str | None
  secrets: Path | None
  results_root: Path
  debug: bool
  dry_run: bool
  no_symlinks: bool
  run_tast_analyzer: bool
  tests: list[TestInvocation]
