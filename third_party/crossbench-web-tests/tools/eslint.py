#!/usr/bin/env vpython3

# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import subprocess
import sys
from pathlib import Path

WEB_TESTS_ROOT = Path(__file__).resolve().parent.parent
PERFETTO = WEB_TESTS_ROOT / "third_party" / "perfetto"
PERFETTO_TOOLS = PERFETTO / "tools"
PERFETTO_UI = PERFETTO / "ui"
PERFETTO_NODE_MODULES = PERFETTO_UI / "node_modules"


def eslint(js_files: list[str], fix: bool = False) -> None:
  for file in js_files:
    full_path: Path = Path(file).resolve()

    logging.info("eslint for: %s", str(full_path))

    eslint_env = os.environ.copy()
    eslint_env[
        "PATH"] = f"{PERFETTO_TOOLS}{os.pathsep}{eslint_env.get('PATH', '')}"
    eslint_env["NODE_PATH"] = (
        f"{PERFETTO_NODE_MODULES}{os.pathsep}{eslint_env.get('NODE_PATH', '')}")

    cmd: list[str] = [str(PERFETTO_NODE_MODULES / ".bin" / "eslint"), str(file)]

    if fix:
      cmd.append("--fix")

    subprocess.run(cmd, env=eslint_env, check=True)


if __name__ == "__main__":
  logging.getLogger().setLevel(logging.INFO)
  eslint(sys.argv[1:])
