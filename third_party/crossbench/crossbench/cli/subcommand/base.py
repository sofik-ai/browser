# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import abc
import colorsys
import logging
import random
from typing import TYPE_CHECKING

from crossbench import __version__
from crossbench import path as pth
from crossbench import plt
from crossbench.cli import ui

if TYPE_CHECKING:
  import argparse

  from crossbench.cli.cli import CrossBenchCLI


BANNER = r"""
                   ▌           ▌      Browser Benchmark Runner
    ▞▀▖▙▀▖▞▀▖▞▀▘▞▀▘▛▀▖▞▀▖▛▀▖▞▀▖▛▀▖    v{version}
    ▌ ▖▌  ▌ ▌▝▀▖▝▀▖▌ ▌▛▀ ▌ ▌▌ ▖▌ ▌    {extra_info}
    ▝▀ ▘  ▝▀ ▀▀ ▀▀ ▀▀ ▝▀▘▘ ▘▝▀ ▘ ▘
"""


class CrossbenchSubcommand(abc.ABC):

  def __init__(self, cli: CrossBenchCLI) -> None:
    self._cli = cli
    self._parser: argparse.ArgumentParser = self.add_cli_parser()
    self._parser.set_defaults(crossbench_subcommand=self)

  @property
  def cli(self) -> CrossBenchCLI:
    return self._cli

  @property
  def parser(self) -> argparse.ArgumentParser:
    return self._parser

  @abc.abstractmethod
  def add_cli_parser(self) -> argparse.ArgumentParser:
    pass

  @abc.abstractmethod
  def run(self, args: argparse.Namespace) -> None:
    pass

  def error(self, message: str) -> None:
    self.cli.error(message)

  def fail(self, message: str) -> None:
    self._parser.error(message)

  def _get_version_info(self) -> str:
    try:
      root_dir = pth.LocalPath(__file__).parent
      if git_hash := plt.PLATFORM.sh_stdout(
          "git", "rev-parse", "HEAD", quiet=True, cwd=root_dir).strip():
        return f"{__version__} {git_hash[:12]}"
    except Exception as e:  # noqa: BLE001
      logging.debug("Could not get git commit: %s", e)
    return __version__

  def _log_version_info(self) -> None:
    logging.info("🛠 v%s", self._get_version_info())

  def _print_banner(self, extra_info: str | None = None) -> None:
    if self.cli.args.verbosity < 0:
      self._log_version_info()
    else:
      self._print_banner_logo(extra_info)

  def _print_banner_logo(self, extra_info: str | None = None) -> None:
    formatted_banner = BANNER.format(
        version=self._get_version_info(), extra_info=extra_info or "")
    lines = formatted_banner.strip("\n").split("\n")

    if not ui.COLOR_LOGGING:
      print(formatted_banner.strip("\n"))
      return
    max_y = len(lines)
    max_x = max(len(line_len) for line_len in lines) if lines else 1

    start_hue = random.random()  # noqa: S311

    for y, line in enumerate(lines):
      colored_line = ""
      for x, char in enumerate(line):
        if char.isspace():
          colored_line += char
        else:
          nx = x / max_x
          ny = y / max_y
          hue = (start_hue + nx * 0.15 + ny * 0.1) % 1.0
          r, g, b = colorsys.hsv_to_rgb(hue, 0.5, 0.9)
          ir = int(r * 255)
          ig = int(g * 255)
          ib = int(b * 255)
          colored_line += f"\033[38;2;{ir};{ig};{ib}m{char}\033[0m"
      print(colored_line)
