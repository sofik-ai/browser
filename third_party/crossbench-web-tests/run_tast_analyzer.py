#!/usr/bin/env python3
# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess
import sys
from pathlib import Path


def main():
  root_path = Path(__file__).resolve().parent
  tast_analyzer_path = (
      root_path / "third_party" / "tast-tests" / "tools" / "tast-analyzer")
  venv_path = tast_analyzer_path / ".venv"

  if not venv_path.exists():
    print(f"Creating venv at {venv_path}...")
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

  print("Installing/Updating dependencies...")
  subprocess.run([
      str(venv_path / "bin" / "pip"), "install", "--index-url",
      "https://pypi.org/simple", "-r",
      str(tast_analyzer_path / "requirements.txt")
  ],
                 check=True)

  print("Running tast-analyzer...")
  # Pass along any arguments received from the caller
  result = subprocess.run(
      [
          str(venv_path / "bin" / "python3"), "-m", "analyzer.run",
          "ingest-web-tests"
      ] + sys.argv[1:],
      check=False,  # Let the caller handle the exit code
      cwd=str(tast_analyzer_path))

  sys.exit(result.returncode)


if __name__ == "__main__":
  main()
