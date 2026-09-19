# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, call

from crossbench.action_runner.action.click import ClickAction
from crossbench.action_runner.base import ActionRunner
from tests import test_helper


class MockActionRunner(ActionRunner):

  def __init__(self):
    super().__init__()
    self.click_js = MagicMock(name="Mock click_js")


class BaseActionRunnerTestCase(unittest.TestCase):

  def test_click_attempts_first_success(self):
    mock_run = MagicMock(name="Mock Run")
    mock_action_runner = MockActionRunner()

    config_dict = {"action": "click", "selector": "#button", "attempts": 3}
    action = ClickAction.config_parser().parse(config_dict)

    mock_action_runner.click_js.side_effect = [None]

    mock_action_runner.click(mock_run, action)

    mock_action_runner.click_js.assert_called_once_with(mock_run, action)

  def test_click_attempts_last_success(self):
    mock_run = MagicMock(name="Mock Run")
    mock_action_runner = MockActionRunner()

    config_dict = {"action": "click", "selector": "#button", "attempts": 3}
    action = ClickAction.config_parser().parse(config_dict)

    mock_action_runner.click_js.side_effect = [
        Exception("fail first"),
        Exception("and second"), None
    ]

    mock_action_runner.click(mock_run, action)

    mock_action_runner.click_js.assert_has_calls([
        call(mock_run, action),
        call(mock_run, action),
        call(mock_run, action),
    ])

  def test_click_attempts_fail(self):
    mock_run = MagicMock(name="Mock Run")
    mock_action_runner = MockActionRunner()

    config_dict = {"action": "click", "selector": "#button", "attempts": 3}
    action = ClickAction.config_parser().parse(config_dict)

    class TestException(Exception):
      pass

    mock_action_runner.click_js.side_effect = [
        TestException("fail first"),
        TestException("and second"),
        TestException("and third")
    ]

    with self.assertRaises(TestException):
      mock_action_runner.click(mock_run, action)

    mock_action_runner.click_js.assert_has_calls([
        call(mock_run, action),
        call(mock_run, action),
        call(mock_run, action),
    ])


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
