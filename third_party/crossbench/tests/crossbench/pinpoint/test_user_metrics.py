# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import unittest
from unittest import mock

from crossbench.pinpoint import user_metrics
from crossbench.pinpoint.settings import Settings
from tests import test_helper


class TestUserMetrics(unittest.TestCase):

  def setUp(self):
    self.mock_settings = mock.Mock(spec=Settings)
    self.mock_settings.collect_metrics = None
    self.mock_settings.user_id = None
    self.enterContext(
        mock.patch(
            "crossbench.pinpoint.user_metrics.Settings",
            return_value=self.mock_settings))

    self.mock_prompt = self.enterContext(mock.patch("crossbench.cli.ui.prompt"))
    self.mock_bq_client_cls = self.enterContext(
        mock.patch("google.cloud.bigquery.Client"))

  def test_init_metrics_prompt_yes(self):
    self.mock_prompt.return_value = "y"
    user_metrics.init_metrics()
    self.assertTrue(self.mock_settings.collect_metrics)
    self.assertIsNotNone(self.mock_settings.user_id)
    self.mock_settings.save.assert_called_once()

  def test_init_metrics_prompt_no(self):
    self.mock_prompt.return_value = "n"
    user_metrics.init_metrics()
    self.assertFalse(self.mock_settings.collect_metrics)
    self.assertIsNotNone(self.mock_settings.user_id)
    self.mock_settings.save.assert_called_once()

  def test_init_metrics_already_set(self):
    self.mock_settings.collect_metrics = True
    self.mock_settings.user_id = "existing-id"
    user_metrics.init_metrics()
    self.mock_prompt.assert_not_called()
    self.assertEqual(self.mock_settings.user_id, "existing-id")

  def test_collect_metrics_enabled(self):
    self.mock_settings.collect_metrics = True
    self.mock_settings.user_id = "test-user-id"
    mock_client = self.mock_bq_client_cls.return_value

    user_metrics.collect_metrics("test_command")

    self.mock_bq_client_cls.assert_called_with(project="chromeperf")
    mock_client.insert_rows_json.assert_called_once()
    call_args = mock_client.insert_rows_json.call_args[0]
    self.assertEqual(call_args[0], "pinpoint_cli_metrics.usage")
    self.assertEqual(call_args[1], [{
        "user": "test-user-id",
        "command": "test_command"
    }])

  def test_collect_metrics_disabled(self):
    self.mock_settings.collect_metrics = False
    user_metrics.collect_metrics("test_command")
    self.mock_bq_client_cls.assert_not_called()

  def test_collect_metrics_exception(self):
    self.mock_settings.collect_metrics = True
    self.mock_settings.user_id = "test-user-id"

    mock_client = self.mock_bq_client_cls.return_value
    mock_client.insert_rows_json.side_effect = Exception("BQ Error")

    # Should not raise exception
    user_metrics.collect_metrics("test_command")

    mock_client.insert_rows_json.assert_called_once()


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
