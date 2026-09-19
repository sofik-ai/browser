# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import datetime as dt
import unittest
from unittest.mock import Mock, call, patch

from requests import RequestException

from crossbench.helper import url_helper
from tests import test_helper

NOW_EPOCH = dt.datetime.now()


class MockRequestException(RequestException):
  pass


class UrlHelperTestCase(unittest.TestCase):

  def response_ok(self):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    return mock_response

  def response_fail(self):
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = MockRequestException()
    return mock_response

  @patch("crossbench.helper.url_helper.requests.get")
  def test_get(self, mock_get):
    mock_get.side_effect = [self.response_ok()]
    url_helper.get(url="http://invalid", timeout=12.3)
    mock_get.assert_has_calls([
        call("http://invalid", timeout=12.3),
    ])

  @patch("crossbench.helper.url_helper.requests.get")
  @patch("crossbench.helper.url_helper.dt.datetime")
  def test_get_retry(self, mock_datetime, mock_get):
    mock_datetime.now.side_effect = [
        NOW_EPOCH,
        NOW_EPOCH + dt.timedelta(seconds=1),
    ]
    mock_get.side_effect = [self.response_fail(), self.response_ok()]
    url_helper.get(url="http://invalid", timeout=3.0, retry=1)
    mock_get.assert_has_calls([
        call("http://invalid", timeout=3.0),
        call("http://invalid", timeout=2.0),
    ])

  @patch("crossbench.helper.url_helper.requests.get")
  @patch("crossbench.helper.url_helper.dt.datetime")
  def test_get_retry_fail(self, mock_datetime, mock_get):
    mock_datetime.now.side_effect = [
        NOW_EPOCH,
        NOW_EPOCH + dt.timedelta(seconds=1),
        NOW_EPOCH + dt.timedelta(seconds=2),
    ]
    mock_get.side_effect = [self.response_fail(), self.response_fail()]
    with self.assertRaises(MockRequestException):
      url_helper.get(url="http://invalid", timeout=3.0, retry=1)
    mock_get.assert_has_calls([
        call("http://invalid", timeout=3.0),
        call("http://invalid", timeout=2.0),
    ])

  @patch("crossbench.helper.url_helper.requests.get")
  @patch("crossbench.helper.url_helper.dt.datetime")
  def test_get_retry_timeout(self, mock_datetime, mock_get):
    mock_datetime.now.side_effect = [
        NOW_EPOCH,
        NOW_EPOCH + dt.timedelta(seconds=1),
        NOW_EPOCH + dt.timedelta(seconds=2),
    ]
    mock_get.side_effect = [self.response_fail(), self.response_fail()]
    with self.assertRaises(MockRequestException):
      url_helper.get(url="http://invalid", timeout=1.5, retry=10)
    mock_get.assert_has_calls([
        call("http://invalid", timeout=1.5),
        call("http://invalid", timeout=0.5),
    ])

  @patch("crossbench.helper.url_helper.requests.post")
  def test_post(self, mock_post):
    mock_post.side_effect = [self.response_ok()]
    body_json = {
        "foo": 123,
        "bar": False,
    }
    headers = {
        "a": "A",
        "b": "B",
    }
    url_helper.post(
        url="http://invalid",
        body_json=body_json,
        headers=headers,
        timeout=12.3)
    mock_post.assert_has_calls([
        call("http://invalid", json=body_json, headers=headers, timeout=12.3),
    ])

  @patch("crossbench.helper.url_helper.requests.post")
  @patch("crossbench.helper.url_helper.dt.datetime")
  def test_post_retry(self, mock_datetime, mock_post):
    mock_datetime.now.side_effect = [
        NOW_EPOCH,
        NOW_EPOCH + dt.timedelta(seconds=1),
    ]
    mock_post.side_effect = [self.response_fail(), self.response_ok()]
    url_helper.post(url="http://invalid", timeout=3.0, retry=1)
    mock_post.assert_has_calls([
        call("http://invalid", json=None, headers=None, timeout=3.0),
        call("http://invalid", json=None, headers=None, timeout=2.0),
    ])

  @patch("crossbench.helper.url_helper.requests.post")
  @patch("crossbench.helper.url_helper.dt.datetime")
  def test_post_retry_fail(self, mock_datetime, mock_post):
    mock_datetime.now.side_effect = [
        NOW_EPOCH,
        NOW_EPOCH + dt.timedelta(seconds=1),
        NOW_EPOCH + dt.timedelta(seconds=2),
    ]
    mock_post.side_effect = [self.response_fail(), self.response_fail()]
    with self.assertRaises(MockRequestException):
      url_helper.post(url="http://invalid", timeout=3.0, retry=1)
    mock_post.assert_has_calls([
        call("http://invalid", json=None, headers=None, timeout=3.0),
        call("http://invalid", json=None, headers=None, timeout=2.0),
    ])

  @patch("crossbench.helper.url_helper.requests.post")
  @patch("crossbench.helper.url_helper.dt.datetime")
  def test_post_retry_timeout(self, mock_datetime, mock_post):
    mock_datetime.now.side_effect = [
        NOW_EPOCH,
        NOW_EPOCH + dt.timedelta(seconds=1),
        NOW_EPOCH + dt.timedelta(seconds=2),
    ]
    mock_post.side_effect = [self.response_fail(), self.response_fail()]
    with self.assertRaises(MockRequestException):
      url_helper.post(url="http://invalid", timeout=1.5, retry=10)
    mock_post.assert_has_calls([
        call("http://invalid", json=None, headers=None, timeout=1.5),
        call("http://invalid", json=None, headers=None, timeout=0.5),
    ])


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
