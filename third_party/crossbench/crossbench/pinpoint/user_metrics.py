# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import logging
import uuid

from google.cloud import bigquery

from crossbench.cli import ui
from crossbench.pinpoint.settings import Settings


def init_metrics() -> None:
  settings = Settings()
  if settings.collect_metrics is None:
    settings.collect_metrics = _get_confirmation()
  if settings.user_id is None:
    settings.user_id = str(uuid.uuid4())
  settings.save()


def collect_metrics(command: str) -> None:
  settings = Settings()
  if not settings.collect_metrics:
    return

  try:
    rows = [{
        "user": settings.user_id,
        "command": command,
    }]
    bigquery.Client(project="chromeperf").insert_rows_json(
        "pinpoint_cli_metrics.usage", rows, timeout=3)
  except Exception as e:  # noqa: BLE001
    # Metrics collection is best-effort. We silently ignore all errors
    # (e.g. auth, network, BQ) to ensure the main command execution
    # is never interrupted by telemetry failures.
    logging.debug("Failed to upload metrics: %s", e)


def _get_confirmation() -> bool:
  prompt = (
      f"Usage Data Collection\n"
      f"To improve the application, we collect anonymous usage data. "
      f"This collection is voluntary and non-identifiable.\n\n"
      f"Data Collected:\n"
      f"- Anonymous User ID: A non-identifiable string for counting unique "
      f"users.\n"
      f"- Executed Command: The base command name (e.g., start, list).\n\n"
      f"Data NOT Collected:\n"
      f"We NEVER collect flags, arguments, file paths, or any sensitive "
      f"information.\n\n"
      f"Example: If you run `./cb.py pinpoint start --config=/personal/path` "
      f"only `start` is recorded.\n\n"
      f"You can always change your decision by flipping the boolean flag "
      f'"collect_metrics" in the settings file at {Settings.path()}.\n\n'
      f"Do you consent to sending this anonymous usage data?")

  user_input = ui.prompt(prompt, "[Y/n] ").lower().strip()
  return user_input in ["", "y", "yes"]
