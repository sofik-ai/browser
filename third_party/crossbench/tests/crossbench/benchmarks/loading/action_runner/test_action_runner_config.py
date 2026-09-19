# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
import unittest

from crossbench import plt
from crossbench.action_runner.android_input_action_runner import \
    AndroidInputActionRunner
from crossbench.action_runner.chromeos_input_action_runner import \
    ChromeOSInputActionRunner
from crossbench.action_runner.config import ActionRunnerConfig, \
    ActionRunnerType
from crossbench.action_runner.default_action_runner import DefaultActionRunner
from tests import test_helper


class ActionRunnerConfigTest(unittest.TestCase):

  def test_parse_invalid(self):
    for invalid in ["bas", "adnroid", "chroms"]:
      with self.subTest(pattern=invalid):
        with self.assertRaises((argparse.ArgumentTypeError, ValueError)):
          ActionRunnerConfig.parse(invalid)

  def test_parse_basic(self):
    action_runner = ActionRunnerConfig.parse("basic")
    self.assertIsInstance(action_runner, ActionRunnerConfig)
    self.assertEqual(action_runner.type, ActionRunnerType.BASIC)
    self.assertIsInstance(
        action_runner.instantiate(plt.PLATFORM), DefaultActionRunner)

  def test_parse_auto(self):
    action_runner = ActionRunnerConfig.parse("auto")
    self.assertIsInstance(action_runner, ActionRunnerConfig)
    self.assertEqual(action_runner.type, ActionRunnerType.AUTO)
    self.assertIsInstance(
        action_runner.instantiate(plt.PLATFORM), DefaultActionRunner)

  def test_parse_auto_android(self):
    action_runner = ActionRunnerConfig.parse("auto")
    mock_platform = unittest.mock.MagicMock()
    mock_platform.is_android = True
    self.assertIsInstance(
        action_runner.instantiate(mock_platform), AndroidInputActionRunner)

  def test_parse_auto_chromeos(self):
    action_runner = ActionRunnerConfig.parse("auto")
    mock_platform = unittest.mock.MagicMock()
    mock_platform.is_android = False
    mock_platform.is_chromeos = True
    self.assertIsInstance(
        action_runner.instantiate(mock_platform), ChromeOSInputActionRunner)

  def test_parse_android(self):
    action_runner = ActionRunnerConfig.parse("android")
    self.assertIsInstance(action_runner, ActionRunnerConfig)
    self.assertEqual(action_runner.type, ActionRunnerType.ANDROID)
    self.assertIsInstance(
        action_runner.instantiate(plt.PLATFORM), AndroidInputActionRunner)

  def test_parse_chromeos(self):
    action_runner = ActionRunnerConfig.parse("chromeos")
    self.assertIsInstance(action_runner, ActionRunnerConfig)
    self.assertEqual(action_runner.type, ActionRunnerType.CHROMEOS)
    self.assertIsInstance(
        action_runner.instantiate(plt.PLATFORM), ChromeOSInputActionRunner)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
