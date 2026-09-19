# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import json
import logging
import shlex
import tempfile
import urllib
from datetime import datetime as dt
from pathlib import Path
from typing import Any

from crossbench import hjson as cb_hjson
from crossbench.cli.cli import CrossBenchCLI
from crossbench.helper.cwd import change_cwd
from runner.config import RunConfig, TargetPlatform, TestInvocation
from runner.logging import setup_logging


def execute_crossbench(
    cb_benchmark_name: str,
    probe_config_file: Path | None,
    browser_config: str,
    additional_crossbench_args: str,
    debug: bool,
    dry_run: bool,
    no_symlinks: bool,
    results_path: Path,
    playback: str | None = None,
    page_config_file: Path | None = None,
    secrets_file: Path | None = None,
    setup_delay: str | None = None,
    startup_delay: str | None = None,
) -> None:
  with tempfile.NamedTemporaryFile() as browser_config_file:
    browser_config_file.write(browser_config.encode("utf-8"))
    browser_config_file.seek(0)

    crossbench_args: list[str] = []

    crossbench_args.append(cb_benchmark_name)

    crossbench_args.append("--out-dir")
    crossbench_args.append(str(results_path))

    if page_config_file:
      crossbench_args.append("--page-config")
      crossbench_args.append(str(page_config_file))

    if probe_config_file:
      crossbench_args.append("--probe-config")
      crossbench_args.append(str(probe_config_file))

    crossbench_args.append("--browser-config")
    crossbench_args.append(str(browser_config_file.name))

    if secrets_file:
      crossbench_args.append("--secrets")
      crossbench_args.append(str(secrets_file))

    if playback:
      crossbench_args.append("--playback")
      crossbench_args.append(playback)

    if setup_delay:
      crossbench_args.append("--setup-delay")
      crossbench_args.append(str(setup_delay))

    if startup_delay:
      crossbench_args.append("--startup-delay")
      crossbench_args.append(str(startup_delay))

    if debug:
      crossbench_args.append("--debug")

    if dry_run:
      crossbench_args.append("--dry-run")
      crossbench_args.append("--env-validation")
      crossbench_args.append("skip")

    if no_symlinks:
      crossbench_args.append("--no-symlinks")

    crossbench_args.append("--throw")

    for arg in shlex.split(additional_crossbench_args):
      crossbench_args.append(arg)

    logging.info("Running crossbench with args: %s", crossbench_args)

    try:
      CrossBenchCLI().run(crossbench_args)
    finally:
      # Crossbench sometimes tears down logging when tests fail,
      # so reinitialize it here.
      setup_logging()


def get_android_browser_config(run_config: RunConfig, browser_flags_file: Path,
                               extensions: Any) -> dict[str, Any]:
  # Default to normal chrome for android
  browser_string = "chrome"

  if run_config.browser:
    browser_string = run_config.browser

  driver_config: dict[str, Any] = {
      "type": "adb",
      "device_id": run_config.device
  }
  if run_config.adb_bin:
    driver_config["adb_bin"] = str(run_config.adb_bin)

  return {
      "flags": str(browser_flags_file),
      "browsers": {
          browser_string: {
              "browser": browser_string,
              "flags": ["flags"],
              "extensions": extensions,
              "driver": driver_config
          }
      }
  }


def get_chromeos_browser_config(run_config: RunConfig, browser_flags_file: Path,
                                extensions: Any) -> dict[str, Any]:
  # Default to normal chrome for ChromeOS
  browser_string = "/opt/google/chrome/chrome"

  if run_config.browser:
    browser_string = run_config.browser

  ssh_info = urllib.parse.urlparse(f"ssh://{run_config.device}")

  return {
      "flags": str(browser_flags_file),
      "browsers": {
          browser_string: {
              "browser": browser_string,
              "flags": ["flags"],
              "extensions": extensions,
              "driver": {
                  "type": "chromeos-ssh",
                  "settings": {
                      "host": ssh_info.hostname,
                      "ssh_port": ssh_info.port if ssh_info.port else 22,
                      "ssh_user": "root",
                  }
              }
          }
      }
  }


def get_local_browser_config(run_config: RunConfig, browser_flags_file: Path,
                             extensions: Any) -> dict[str, Any]:
  logging.warning(
      "The 'local' platform is not officially supported by this script. "
      "You may need to tweak the probe config manually for some tests to pass."
  )

  # Default to normal chrome for local
  browser_string = "chrome"

  if run_config.browser:
    browser_string = run_config.browser

  return {
      "flags": str(browser_flags_file),
      "browsers": {
          browser_string: {
              "browser": browser_string,
              "flags": ["flags"],
              "extensions": extensions,
          }
      }
  }


def get_browser_config(run_config: RunConfig, browser_flags_file: Path,
                       extensions: Any) -> str:
  # TODO support different chrome versions (i.e. dev/beta)

  if run_config.platform == TargetPlatform.ANDROID:
    config_dict = get_android_browser_config(run_config, browser_flags_file,
                                             extensions)
  elif run_config.platform == TargetPlatform.CHROME_OS:
    config_dict = get_chromeos_browser_config(run_config, browser_flags_file,
                                              extensions)
  elif run_config.platform == TargetPlatform.LOCAL:
    config_dict = get_local_browser_config(run_config, browser_flags_file,
                                           extensions)
  else:
    raise ValueError(f"Unsupported platform type: {run_config.platform}")

  return json.dumps(config_dict)


def load_extensions(extension_config_file: Path | None) -> Any:
  if not extension_config_file:
    return None

  with extension_config_file.open(encoding="utf-8") as f:
    extensions = cb_hjson.load_unique_keys(f)
  # Allow exentions config files to be a reference to another file.
  if isinstance(extensions, str):
    with change_cwd(extension_config_file.parent):
      extensions = load_extensions(Path(extensions))
  return extensions


def run_test(test_invocation: TestInvocation,
             run_config: RunConfig) -> tuple[int, int]:
  successes = 0
  failures = 0
  consecutive_failures = 0

  test_results_root = run_config.results_root / test_invocation.test.full_name

  success_path = test_results_root / "pass"
  success_path.mkdir(parents=True, exist_ok=True)
  fail_path = test_results_root / "fail"
  fail_path.mkdir(parents=True, exist_ok=True)

  with change_cwd(test_invocation.test.path):
    extensions = load_extensions(test_invocation.test.extensions)
    browser_config = get_browser_config(run_config,
                                        test_invocation.test.browser_flags,
                                        extensions)

    while True:
      timestamp = dt.now().strftime("%Y-%m-%d_%H%M%S")
      current_results_path: Path = test_results_root / timestamp

      logging.info("Executing crossbench for Test: %s",
                   test_invocation.test.full_name)

      try:
        execute_crossbench(
            cb_benchmark_name=test_invocation.test.crossbench_command,
            probe_config_file=test_invocation.test.probe_config,
            browser_config=browser_config,
            additional_crossbench_args=test_invocation.test.crossbench_args,
            debug=run_config.debug,
            dry_run=run_config.dry_run,
            no_symlinks=run_config.no_symlinks,
            results_path=current_results_path,
            playback=test_invocation.playback,
            page_config_file=test_invocation.test.page_config,
            setup_delay=test_invocation.setup_delay,
            startup_delay=test_invocation.startup_delay,
            secrets_file=run_config.secrets,
        )
        if current_results_path.is_dir():
          success_results_dest = success_path / timestamp
          current_results_path.rename(success_results_dest)
          current_results_path = success_results_dest
        successes += 1
        consecutive_failures = 0
      # pylint: disable=broad-exception-caught
      except Exception as e:
        logging.error("Crossbench invocation for Test: %s failed",
                      test_invocation.test.full_name)
        logging.error("Failure exception: %s", e)
        failures += 1
        consecutive_failures += 1
        try:
          fail_results_dest = fail_path / timestamp
          current_results_path.rename(fail_results_dest)
          current_results_path = fail_results_dest
        except Exception:
          pass

      logging.info("Web tests results: %s", str(current_results_path))

      if (test_invocation.max_consecutive_failures and
          consecutive_failures >= test_invocation.max_consecutive_failures):
        break

      if (not test_invocation.min_successes or
          successes >= test_invocation.min_successes):
        break

  return successes, failures
