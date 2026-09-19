# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import json
import logging

from crossbench.pinpoint import http_requests
from crossbench.pinpoint.api import PINPOINT_CANCEL_JOB_API_URL
from crossbench.pinpoint.helper import annotate


def cancel_job(job_id: str, reason: str) -> None:
  """Cancels a Pinpoint job."""
  payload = {
      "job_id": job_id,
      "reason": reason,
  }
  with annotate("Cancelling Pinpoint job"):
    response = http_requests.post(PINPOINT_CANCEL_JOB_API_URL, data=payload)
    response.raise_for_status()
  logging.info(json.dumps(response.json(), indent=2))
