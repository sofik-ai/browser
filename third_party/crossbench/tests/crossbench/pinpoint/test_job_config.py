# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from unittest import mock

import requests

from crossbench.exception import MultiException
from crossbench.pinpoint.api import PINPOINT_JOB_API_URL_TEMPLATE
from crossbench.pinpoint.config import PinpointTryJobConfig
from crossbench.pinpoint.job_config import convert_job_config, \
    fetch_job_config, print_job_config
from tests import test_helper
from tests.crossbench.pinpoint.http_requests_mixin import MockHttpRequestsMixin

_TEST_JOB_ID = "1234567890"
_TEST_JOB_RESPONSE = {
    "job_id": _TEST_JOB_ID,
    "configuration": "win-11-perf",
    "results_url": "https://storage.cloud.google.com/1234567890.html",
    "arguments": {
        "comparison_mode": "try",
        "benchmark": "speedometer3",
        "configuration": "win-11-perf",
        "story": "Speedometer3",
        "initial_attempt_count": "100",
        "base_git_hash": "HEAD",
        "end_git_hash": "HEAD",
        "base_extra_args":
            '--extra-browser-args="--my-flag --js-flags=--flag1 '
            '--enable-features=enfeat1 --disable-features=disfeat1"'
    },
    "bug_id": None,
    "comparison_mode": "try",
    "name": "Try job on win-11-perf/speedometer3",
}


class JobConfigTest(MockHttpRequestsMixin):

  def setUp(self):
    super().setUp()

    def mock_post_side_effect(url, *args, **kwargs):
      self.assertEqual(
          url, PINPOINT_JOB_API_URL_TEMPLATE.format(job_id=_TEST_JOB_ID))

      mock_response = mock.Mock()
      mock_response.json.return_value = _TEST_JOB_RESPONSE
      mock_response.raise_for_status.return_value = None
      return mock_response

    self.mock_get.side_effect = mock_post_side_effect

  def test_fetch_job_config(self):
    config_dict = fetch_job_config(_TEST_JOB_ID)
    self.assertEqual(config_dict, _TEST_JOB_RESPONSE)

  def test_fetch_job_config_full(self):
    fetch_job_config(_TEST_JOB_ID, full=True)
    _, kwargs = self.mock_get.call_args
    self.assertEqual(kwargs, {"params": {"o": ["STATE", "ESTIMATE"]}})

  def test_fetch_job_config_api_error(self):
    self.mock_get.side_effect = requests.exceptions.HTTPError("API Error")

    with self.assertRaises(MultiException):
      fetch_job_config(_TEST_JOB_ID)

  def test_convert_job_config(self):
    config_dict = fetch_job_config(job_id=_TEST_JOB_ID)
    converted_config_dict = convert_job_config(config_dict)
    expected_config = PinpointTryJobConfig.from_response_dict(
        _TEST_JOB_RESPONSE)
    self.assertEqual(converted_config_dict, expected_config.to_dict())

  def test_job_config_raises_when_full_and_not_raw(self):
    with self.assertRaises(ValueError):
      print_job_config(_TEST_JOB_ID, raw=False, full=True)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
