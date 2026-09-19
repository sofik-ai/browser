# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import datetime as dt
import unittest

from crossbench.action_runner.action.get import GetAction
from crossbench.benchmarks.loading.config.blocks import ActionBlock
from crossbench.benchmarks.loading.config.login.custom import LoginBlock
from crossbench.benchmarks.loading.config.login.google import GoogleLogin
from tests import test_helper


class ActionBlockTestCase(unittest.TestCase):

  def test_create_empty_valid(self):
    block = ActionBlock()
    self.assertFalse(bool(block))
    self.assertFalse(block.is_login)
    self.assertEqual(len(block), 0)
    self.assertTupleEqual(tuple(block), ())
    self.assertEqual(block.duration, dt.timedelta(seconds=0))
    self.assertTrue(hash(block))
    self.assertSetEqual({block}, {block, block})

  def test_single_action(self):
    action = GetAction("http://test.com", duration=dt.timedelta(seconds=3))
    block = ActionBlock(actions=(action,))
    self.assertTrue(bool(block))
    self.assertFalse(block.is_login)
    self.assertEqual(len(block), 1)
    self.assertTupleEqual(tuple(block), (action,))
    self.assertEqual(block.duration, dt.timedelta(seconds=3))
    self.assertTrue(hash(block))
    self.assertSetEqual({block}, {block, block})

    block = ActionBlock.parse(block.to_json())
    self.assertTrue(bool(block))
    self.assertFalse(block.is_login)
    self.assertEqual(len(block), 1)
    self.assertEqual(block.duration, dt.timedelta(seconds=3))

  def test_multi_action(self):
    action_2 = GetAction("http://test.com/0", duration=dt.timedelta(seconds=1))
    action_1 = GetAction("http://test.com/1", duration=dt.timedelta(seconds=2))
    block = ActionBlock(actions=(action_1, action_2))
    self.assertTrue(bool(block))
    self.assertFalse(block.is_login)
    self.assertEqual(len(block), 2)
    self.assertTupleEqual(tuple(block), (action_1, action_2))
    self.assertEqual(block.duration, dt.timedelta(seconds=3))
    self.assertTrue(hash(block))
    self.assertSetEqual({block}, {block, block})

    block = ActionBlock.parse(block.to_json())
    self.assertTrue(bool(block))
    self.assertFalse(block.is_login)
    self.assertEqual(len(block), 2)
    self.assertEqual(block.duration, dt.timedelta(seconds=3))


class LoginBlockTestCase(unittest.TestCase):

  def test_single_action(self):
    action = GetAction("http://test.com", duration=dt.timedelta(seconds=3))
    block = LoginBlock(actions=(action,))
    self.assertTrue(bool(block))
    self.assertTrue(block.is_login)
    self.assertEqual(len(block), 1)
    self.assertTupleEqual(tuple(block), (action,))
    self.assertEqual(block.duration, dt.timedelta(seconds=3))

    block = LoginBlock.parse(block.to_json())
    self.assertTrue(bool(block))
    self.assertTrue(block.is_login)
    self.assertEqual(len(block), 1)
    self.assertEqual(block.duration, dt.timedelta(seconds=3))

  def test_multi_action(self):
    action_2 = GetAction("http://test.com/0", duration=dt.timedelta(seconds=1))
    action_1 = GetAction("http://test.com/1", duration=dt.timedelta(seconds=2))
    block = LoginBlock(actions=(action_1, action_2))
    self.assertTrue(bool(block))
    self.assertTrue(block.is_login)
    self.assertEqual(len(block), 2)
    self.assertTupleEqual(tuple(block), (action_1, action_2))
    self.assertEqual(block.duration, dt.timedelta(seconds=3))

    block = LoginBlock.parse(block.to_json())
    self.assertTrue(bool(block))
    self.assertTrue(block.is_login)
    self.assertEqual(len(block), 2)
    self.assertEqual(block.duration, dt.timedelta(seconds=3))


class PresetLoginBlockTestCase(unittest.TestCase):

  def test_google_login_block(self):
    block = GoogleLogin()
    self.assertTrue(bool(block))
    self.assertTrue(block.is_login)
    self.assertEqual(len(block), 1)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
