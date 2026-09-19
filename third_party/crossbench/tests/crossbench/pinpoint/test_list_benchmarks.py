# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from unittest import mock

import requests

from crossbench.exception import MultiException
from crossbench.pinpoint.api import CHROMEPERF_TEST_SUITES_API_URL
from crossbench.pinpoint.list_benchmarks import fetch_benchmarks
from tests import test_helper
from tests.crossbench.pinpoint.http_requests_mixin import MockHttpRequestsMixin


class ListBenchmarksTest(MockHttpRequestsMixin):

  def setUp(self):
    super().setUp()

    def mock_post_side_effect(url, *args, **kwargs):
      self.assertEqual(url, CHROMEPERF_TEST_SUITES_API_URL,
                       f"Unexpected URL called: {url}")

      mock_response = mock.Mock()
      mock_response.json.return_value = [
          "benchmark1", "benchmark2", "benchmark3"
      ]
      mock_response.raise_for_status.return_value = None
      return mock_response

    self.mock_post.side_effect = mock_post_side_effect

  def test_fetch_benchmarks(self):
    benchmarks = fetch_benchmarks()

    self.assertEqual(benchmarks, ["benchmark1", "benchmark2", "benchmark3"])
    self.mock_post.assert_called_once_with(CHROMEPERF_TEST_SUITES_API_URL)

  def test_fetch_benchmarks_api_error(self):
    self.mock_post.side_effect = requests.exceptions.HTTPError("API Error")

    with self.assertRaises(MultiException):
      fetch_benchmarks()

    self.mock_post.assert_called_once_with(CHROMEPERF_TEST_SUITES_API_URL)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
