# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from unittest import mock

import requests

from crossbench.exception import MultiException
from crossbench.pinpoint.api import PINPOINT_BUILDS_API_URL_TEMPLATE
from crossbench.pinpoint.list_builds import Build, fetch_builds, list_builds
from tests import test_helper
from tests.crossbench.pinpoint.http_requests_mixin import MockHttpRequestsMixin


class ListBuildsTest(MockHttpRequestsMixin):

  def setUp(self):
    super().setUp()

    def mock_get_side_effect(url, *args, **kwargs):
      bot = url.split("/")[-1]
      self.assertEqual(url, PINPOINT_BUILDS_API_URL_TEMPLATE.format(bot=bot),
                       f"Unexpected URL called: {url}")

      mock_response = mock.Mock()
      if bot == "test-bot":
        mock_response.json.return_value = {
            "builds": [{
                "input": {
                    "gitilesCommit": {
                        "id": f"commit{i}"
                    }
                },
                "endTime": F"2025-11-1{i}T00:00:00Z",
                "number": i,
                "status": "SUCCESS"
            } for i in range(3)]
        }
      else:
        mock_response.json.return_value = {"builds": []}

      mock_response.raise_for_status.return_value = None
      return mock_response

    self.mock_get.side_effect = mock_get_side_effect

  def test_fetch_builds_contain_correct_builds(self):
    builds = fetch_builds("test-bot")
    self.assertEqual(builds, [
        Build(commit="commit2", number=2, date="2025-11-12 00:00:00"),
        Build(commit="commit1", number=1, date="2025-11-11 00:00:00"),
        Build(commit="commit0", number=0, date="2025-11-10 00:00:00"),
    ])

  def test_list_builds_prints_correct_commit_hashes(self):
    with mock.patch("builtins.print") as mock_print:
      list_builds("test-bot", 10)
      output = mock_print.call_args[0][0]
      self.assertIn("commit2", output)
      self.assertIn("commit1", output)
      self.assertIn("commit0", output)

  def test_list_builds_api_error(self):
    self.mock_get.side_effect = requests.exceptions.HTTPError("API Error")
    with self.assertRaises(MultiException):
      list_builds("test-bot", 1)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
