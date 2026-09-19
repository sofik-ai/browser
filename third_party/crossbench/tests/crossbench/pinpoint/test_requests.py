# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import json
import unittest
from unittest import mock

import requests

from crossbench.pinpoint import http_requests as pinpoint_requests
from tests import test_helper


class RequestsTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_response = mock.Mock()
    self.mock_response.raise_for_status.return_value = None
    error = requests.exceptions.HTTPError(
        "Base Error", response=self.mock_response)
    self.mock_response.raise_for_status.side_effect = error

    self.mock_session = mock.Mock(spec=requests.Session)
    self.mock_session.request.return_value = self.mock_response

    self.mock_get_auth_session = self.enterContext(
        mock.patch("crossbench.pinpoint.http_requests.auth.get_auth_session"))
    self.mock_get_auth_session.return_value = self.mock_session

  def test_get_success(self):
    self.mock_response.raise_for_status.side_effect = None
    response = pinpoint_requests.get("http://example.com", params={"a": 1})

    self.mock_session.request.assert_called_once_with(
        "GET", "http://example.com", params={"a": 1})
    self.assertEqual(response, self.mock_response)

  def test_post_success(self):
    self.mock_response.raise_for_status.side_effect = None
    response = pinpoint_requests.post("http://example.com", json={"a": 1})

    self.mock_session.request.assert_called_once_with(
        "POST", "http://example.com", json={"a": 1})
    self.assertEqual(response, self.mock_response)

  def test_error_with_message(self):
    self.mock_response.json.return_value = {"error": "Detailed error message"}

    with self.assertRaises(pinpoint_requests.ServerError) as cm:
      pinpoint_requests.get("http://example.com")

    self.assertIn("Base Error", str(cm.exception))
    self.assertIn("Detailed error message", str(cm.exception))

  def test_error_with_data(self):
    self.mock_response.json.return_value = {"other": "data"}

    with self.assertRaises(pinpoint_requests.ServerError) as cm:
      pinpoint_requests.get("http://example.com")

    self.assertIn("Base Error", str(cm.exception))
    self.assertIn("{'other': 'data'}", str(cm.exception))

  def test_error_non_json(self):
    self.mock_response.json.side_effect = json.JSONDecodeError("msg", "doc", 0)

    with self.assertRaises(pinpoint_requests.ServerError) as cm:
      pinpoint_requests.get("http://example.com")

    self.assertEqual(str(cm.exception), "Base Error")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
