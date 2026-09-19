# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from unittest import mock

import requests

from crossbench.exception import MultiException
from crossbench.pinpoint.api import CHROMEPERF_DESCRIBE_API_URL
from crossbench.pinpoint.list_stories import fetch_stories
from tests import test_helper
from tests.crossbench.pinpoint.http_requests_mixin import MockHttpRequestsMixin


class ListStoriesTest(MockHttpRequestsMixin):

  def setUp(self):
    super().setUp()

    def mock_post_side_effect(url, params, *args, **kwargs):
      self.assertEqual(url, CHROMEPERF_DESCRIBE_API_URL,
                       f"Unexpected URL called: {url}")
      self.assertIn("test_suite", params)
      self.assertIn("master", params)
      self.assertEqual(params["master"], "ChromiumPerf")

      mock_response = mock.Mock()
      benchmark_name = params["test_suite"]
      if benchmark_name == "benchmark1":
        mock_response.json.return_value = {"cases": ["story1", "story2"]}
      else:
        mock_response.json.return_value = {"cases": []}

      mock_response.raise_for_status.return_value = None
      return mock_response

    self.mock_post.side_effect = mock_post_side_effect

  def test_fetch_stories(self):
    stories = fetch_stories("benchmark1")
    self.assertEqual(stories, ["story1", "story2"])
    self.mock_post.assert_called_once_with(
        CHROMEPERF_DESCRIBE_API_URL,
        params={
            "test_suite": "benchmark1",
            "master": "ChromiumPerf"
        })

  def test_fetch_stories_no_stories(self):
    stories = fetch_stories("benchmark_no_stories")
    self.assertEqual(stories, [])

  def test_fetch_stories_api_error(self):
    self.mock_post.side_effect = requests.exceptions.HTTPError("API Error")
    with self.assertRaises(MultiException):
      fetch_stories("benchmark1")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
