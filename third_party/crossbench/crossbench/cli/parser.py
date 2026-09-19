# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
import logging
import sys
from typing import Never, Optional

import colorama

from crossbench.cli import ui


class CrossBenchArgumentParser(argparse.ArgumentParser):

  def __init__(self, **kwargs) -> None:
    kwargs["exit_on_error"] = False
    allow_abbrev = kwargs.pop("allow_abbrev", False)
    super().__init__(allow_abbrev=allow_abbrev, **kwargs)

  def fail(self, message: str) -> None:
    super().error(message)

  def exit(self, status: int = 0, message: Optional[str] = None) -> Never:
    if message:
      if status == 0:
        logging.info(message)
      else:
        # Hack to get red colored output
        if ui.COLOR_LOGGING:
          print(str(colorama.Fore.RED))
        logging.critical(message)
        if ui.COLOR_LOGGING:
          print(str(colorama.Style.RESET_ALL))
    sys.exit(status)
