# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import json
from unittest import mock

from crossbench.pinpoint import api, cancel_job
from tests import test_helper
from tests.crossbench.pinpoint import http_requests_mixin


class CancelJobTest(http_requests_mixin.MockHttpRequestsMixin):

  def test_cancel_job(self):
    job_id = "123456"
    reason = "test reason"
    expected_response = {"status": "cancelled"}
    self.mock_post.return_value.json.return_value = expected_response

    with mock.patch("logging.info") as mock_logging_info:
      cancel_job.cancel_job(job_id, reason)

    self.mock_post.assert_called_once_with(
        api.PINPOINT_CANCEL_JOB_API_URL,
        data={
            "job_id": job_id,
            "reason": reason
        })
    self.mock_post.return_value.raise_for_status.assert_called_once()

    # Verify output
    mock_logging_info.assert_called_once_with(
        json.dumps(expected_response, indent=2))


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
