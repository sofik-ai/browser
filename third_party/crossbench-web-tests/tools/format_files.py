#!/usr/bin/env vpython3

# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import subprocess
import sys
from pathlib import Path
from typing import Callable

from eslint import PERFETTO, PERFETTO_UI, WEB_TESTS_ROOT, eslint
from immutabledict import immutabledict

NODE_BIN = (
    WEB_TESTS_ROOT / "third_party" / "node" / "linux" / "node-linux-x64" /
    "bin" / "node")
HJSON_JS_BIN = WEB_TESTS_ROOT / "third_party" / "hjson_js" / "bin" / "hjson"


def get_txtpbfmt() -> Path:
  go_bin_path = (Path(
      subprocess.run(
          ["go", "env", "GOPATH"], check=True,
          capture_output=True).stdout.decode(encoding="utf-8").strip())) / "bin"
  txtpbfmt_bin = go_bin_path / "txtpbfmt"

  if not txtpbfmt_bin.exists():
    subprocess.run([
        "go", "install",
        "github.com/protocolbuffers/txtpbfmt/cmd/txtpbfmt@latest"
    ],
                   check=True,
                   capture_output=True)

  return txtpbfmt_bin


def format_textproto_file(textproto_file: Path) -> None:
  subprocess.run([str(get_txtpbfmt()), str(textproto_file)],
                 check=True,
                 capture_output=True)


def format_sql_file(sql_file: Path) -> None:
  subprocess.run(
      [str(PERFETTO / "tools" / "format-sql-sources"),
       str(sql_file)],
      check=True,
      cwd=PERFETTO,
      capture_output=True)


def format_hjson_file(hjson_file: Path) -> None:
  formatted_file = subprocess.run(
      [
          NODE_BIN, HJSON_JS_BIN, "-rt", "-sl", "-nocol", "-cond=0",
          str(hjson_file)
      ],
      check=True,
      capture_output=True).stdout.decode(encoding="utf-8")
  hjson_file.write_text(formatted_file, encoding="utf-8")


def format_js_file(js_file: Path) -> None:

  subprocess.run([str(PERFETTO_UI / "prettier"), "--write",
                  str(js_file)],
                 check=True,
                 capture_output=True)

  try:
    eslint(js_files=[str(js_file)], fix=True)
  except subprocess.CalledProcessError:
    # eslint formatting is best effort here.
    # If there are additional errors beyond automatically fixable
    # formatting errors, they will be caught by presubmit later.
    pass


FORMATTERS: immutabledict[str, Callable] = immutabledict({
    ".sql": format_sql_file,
    ".hjson": format_hjson_file,
    ".js": format_js_file,
    ".textproto": format_textproto_file,
    ".pbtxt": format_textproto_file,
})


def format_files(files: list[str]) -> None:
  for file in files:
    full_path: Path = Path(file).resolve()

    if full_path.suffix not in FORMATTERS:
      logging.warning("No formatter for file: %s", str(full_path))
      continue

    logging.info("Formatting: %s", str(full_path))
    try:
      FORMATTERS[full_path.suffix](full_path)
    except subprocess.CalledProcessError as e:
      msg = e.stderr.decode(encoding="utf-8")
      logging.error("Failed to format file (%s): %s", str(full_path), msg)


if __name__ == "__main__":
  logging.getLogger().setLevel(logging.INFO)
  format_files(sys.argv[1:])
