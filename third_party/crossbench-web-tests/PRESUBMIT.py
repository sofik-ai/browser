#!/usr/bin/env python3
# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

USE_PYTHON3 = True

SOURCE_SKIP_RE = [r"^protoc/gen.*", r"^third_party/.*"]


def GlobalSkipChecks(input_api, file_path: str):
  if input_api.fnmatch.fnmatch(file_path, "*protoc/gen/*"):
    return True
  if input_api.fnmatch.fnmatch(file_path, "*third_party/*"):
    return True
  return False


def CheckChange(input_api, output_api):
  tests = []
  results = []
  modified_py_files: list[str] | None = ModifiedFiles(
      input_api, filename_pattern="*.py")
  # ---------------------------------------------------------------------------
  # Validate the vpython spec:
  # ---------------------------------------------------------------------------
  if platform.system() in ("Linux", "Darwin"):
    tests += input_api.canned_checks.CheckVPythonSpec(input_api, output_api)

  # ---------------------------------------------------------------------------
  # License header checks:
  # ---------------------------------------------------------------------------
  files_to_check = list(input_api.DEFAULT_FILES_TO_CHECK) + [
      r".+\.hjson$",
      r".+\.sql$",
  ]

  results += input_api.canned_checks.CheckLicense(
      input_api,
      output_api,
      source_file_filter=lambda x: input_api.FilterSourceFile(
          x, files_to_check=files_to_check))

  # ---------------------------------------------------------------------------
  # Pylint:
  # ---------------------------------------------------------------------------
  tests += input_api.canned_checks.GetPylint(
      input_api,
      output_api,
      files_to_check=[r"^[^\.]+\.py$"],
      files_to_skip=SOURCE_SKIP_RE,
      pylintrc=".pylintrc",
      version="3.2")

  # ---------------------------------------------------------------------------
  # MyPy:
  # ---------------------------------------------------------------------------
  mypy_files_to_check: list[str] = MypyFilesToCheck(input_api,
                                                    modified_py_files)
  tests.append(
      input_api.Command(
          name="mypy",
          cmd=[
              input_api.python3_executable,
              "-m",
              "mypy",
              "--check-untyped-defs",
              "--pretty",
          ] + mypy_files_to_check,
          message=output_api.PresubmitError,
          kwargs={},
          python3=True,
      ))

  # ---------------------------------------------------------------------------
  # JS eslint:
  # ---------------------------------------------------------------------------
  modified_js_files: list[str] | None = ModifiedFiles(
      input_api, filename_pattern="*.js")
  tests.append(
      input_api.Command(
          name="eslint",
          cmd=[
              input_api.python3_executable,
              str(
                  Path(input_api.change.RepositoryRoot()) / "tools" /
                  "eslint.py"),
          ] + (modified_js_files if modified_js_files else []),
          message=output_api.PresubmitError,
          kwargs={},
          python3=True,
      ))

  # ---------------------------------------------------------------------------
  # isort:
  # ---------------------------------------------------------------------------
  SortImports(input_api, output_api, results, modified_py_files)

  # ---------------------------------------------------------------------------
  # format all supported files:
  # ---------------------------------------------------------------------------
  FormatFiles(input_api, output_api, results,
              ModifiedFiles(input_api, filename_pattern="*"))

  # ---------------------------------------------------------------------------
  # crossbench:
  # ---------------------------------------------------------------------------
  runner_path = str(
      Path(input_api.change.RepositoryRoot()) / "cuj" / "crossbench" /
      "runner" / "run.py")
  tests.append(
      input_api.Command(
          name="crossbench dry run",
          cmd=[
              input_api.python3_executable,
              runner_path,
              "--platform=local",
              "--dry-run",
              # Loadline does not cooporate with --dry-run, so ignore it.
              "--tests",
              "^(?!.*loadline).*$"
          ],
          message=output_api.PresubmitError,
          kwargs={},
          python3=True,
      ))

  # ---------------------------------------------------------------------------
  # Run all test
  # ---------------------------------------------------------------------------
  results += input_api.RunTests(tests)
  return results


def ModifiedFiles(input_api, filename_pattern: str) -> list[str] | None:
  files = [file.AbsoluteLocalPath() for file in input_api.AffectedFiles()]
  files_to_check = []
  for file_path in files:
    if not input_api.fnmatch.fnmatch(file_path, filename_pattern):
      continue
    if not input_api.os_path.exists(file_path):
      continue
    file_path = input_api.os_path.relpath(file_path,
                                          input_api.PresubmitLocalPath())
    files_to_check.append(file_path)
  return files_to_check


def MypyFilesToCheck(input_api, modified_py_files) -> list[str]:
  mypy_files_to_check = {"PRESUBMIT.py"}
  mypy_files_to_check.update(modified_py_files)

  result = []
  for file in mypy_files_to_check:
    if GlobalSkipChecks(input_api, file):
      continue
    result.append(file)
  return result


def SortImports(input_api, output_api, results, modified_py_files):
  for py_file in (modified_py_files or []):
    full_py_path = Path(input_api.change.RepositoryRoot()) / py_file
    original_contents = input_api.ReadFile(str(full_py_path), "r")
    subprocess.run([input_api.python_executable, "-m", "isort", full_py_path],
                   check=True)
    formatted_contents = input_api.ReadFile(str(full_py_path), "r")
    if original_contents != formatted_contents:
      results.append(
          output_api.PresubmitPromptWarning(
              "Unsorted python imports in file:",
              items=[str(full_py_path)],
              long_text="Please update your commit with the formatted file."))


def FormatFiles(input_api, output_api, results, modified_files):
  repo_root = Path(input_api.change.RepositoryRoot())
  formatter = repo_root / "tools" / "format_files.py"

  for file in (modified_files or []):
    full_path = repo_root / file
    original_contents = input_api.ReadFile(str(full_path), "r")

    try:
      subprocess.run(
          [input_api.python_executable,
           str(formatter),
           str(full_path)],
          check=True,
          capture_output=True)
      formatted_contents = input_api.ReadFile(str(full_path), "r")
    except subprocess.CalledProcessError as e:
      results.append(
          output_api.PresubmitPromptWarning(
              "Failed to format file:",
              items=[str(full_path)],
              long_text=str(e)))
      continue

    if original_contents != formatted_contents:
      results.append(
          output_api.PresubmitPromptWarning(
              "Unformatted file:",
              items=[str(full_path)],
              long_text="Please update your commit with the formatted file."))

def CheckChangeOnUpload(input_api, output_api):
  return CheckChange(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):
  return CheckChange(input_api, output_api)
