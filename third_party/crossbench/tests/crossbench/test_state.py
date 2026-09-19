# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import enum
import unittest

from crossbench.helper.state import BaseState, StateMachine, \
    UnexpectedStateError
from tests import test_helper


@enum.unique
class CustomState(BaseState):
  INITIAL = enum.auto()
  READY = enum.auto()
  DONE = enum.auto()


class StateMachineTestCase(unittest.TestCase):

  def test_init(self):
    state_machine = StateMachine(CustomState.INITIAL)
    self.assertIs(state_machine.state, CustomState.INITIAL)
    state_machine = StateMachine(CustomState.READY)
    self.assertIs(state_machine.state, CustomState.READY)

  def test_eq(self):
    state_machine = StateMachine(CustomState.READY)
    state_machine_2 = StateMachine(CustomState.READY)
    self.assertEqual(state_machine, state_machine)
    self.assertEqual(state_machine, state_machine_2)
    self.assertEqual(state_machine, CustomState.READY)
    self.assertNotEqual(state_machine, None)
    self.assertNotEqual(state_machine, CustomState.INITIAL)
    self.assertNotEqual(state_machine, StateMachine(CustomState.INITIAL))

  def test_transition(self):
    state_machine = StateMachine(CustomState.INITIAL)
    state_machine.transition(CustomState.INITIAL, to=CustomState.READY)
    self.assertEqual(state_machine.state, CustomState.READY)
    with self.assertRaises(UnexpectedStateError) as cm:
      state_machine.transition(CustomState.INITIAL, to=CustomState.READY)
    self.assertIn("INITIAL", str(cm.exception))
    self.assertIn("READY", str(cm.exception))

  def test_transition_multi_current(self):
    state_machine = StateMachine(CustomState.INITIAL)
    state_machine.transition(
        CustomState.INITIAL, CustomState.READY, to=CustomState.READY)
    self.assertEqual(state_machine.state, CustomState.READY)
    state_machine.transition(
        CustomState.INITIAL, CustomState.READY, to=CustomState.READY)
    self.assertEqual(state_machine.state, CustomState.READY)
    state_machine.transition(
        CustomState.INITIAL, CustomState.READY, to=CustomState.DONE)
    self.assertEqual(state_machine.state, CustomState.DONE)
    with self.assertRaises(UnexpectedStateError) as cm:
      state_machine.transition(
          CustomState.INITIAL, CustomState.READY, to=CustomState.DONE)
    self.assertIn("INITIAL", str(cm.exception))
    self.assertIn("READY", str(cm.exception))
    self.assertIn("DONE", str(cm.exception))

  def test_expect(self):
    state_machine = StateMachine(CustomState.INITIAL)
    state_machine.expect(CustomState.INITIAL)
    with self.assertRaises(RuntimeError) as cm:
      state_machine.expect(CustomState.READY)
    self.assertIn("INITIAL", str(cm.exception))
    self.assertIn("READY", str(cm.exception))

  def test_expect_before(self):
    state_machine = StateMachine(CustomState.INITIAL)
    state_machine.expect_before(CustomState.READY)
    state_machine.expect_before(CustomState.DONE)

    state_machine.transition(CustomState.INITIAL, to=CustomState.READY)
    with self.assertRaises(UnexpectedStateError) as cm:
      state_machine.expect_before(CustomState.READY)
    self.assertEqual(cm.exception.state, CustomState.READY)
    self.assertEqual(cm.exception.expected, (CustomState.INITIAL,))
    state_machine.expect_before(CustomState.DONE)

    state_machine.transition(CustomState.READY, to=CustomState.DONE)
    with self.assertRaises(UnexpectedStateError) as cm:
      state_machine.expect_before(CustomState.DONE)
    self.assertEqual(cm.exception.state, CustomState.DONE)
    self.assertEqual(cm.exception.expected,
                     (CustomState.INITIAL, CustomState.READY))

  def test_expect_at_least(self):
    state_machine = StateMachine(CustomState.INITIAL)
    with self.assertRaises(UnexpectedStateError) as cm:
      state_machine.expect_at_least(CustomState.READY)
    self.assertEqual(cm.exception.state, CustomState.INITIAL)
    self.assertEqual(cm.exception.expected,
                     (CustomState.READY, CustomState.DONE))
    with self.assertRaises(UnexpectedStateError) as cm:
      state_machine.expect_at_least(CustomState.DONE)
    self.assertEqual(cm.exception.state, CustomState.INITIAL)
    self.assertEqual(cm.exception.expected, (CustomState.DONE,))

    state_machine.transition(CustomState.INITIAL, to=CustomState.READY)
    state_machine.expect_at_least(CustomState.INITIAL)
    state_machine.expect_at_least(CustomState.READY)
    with self.assertRaises(UnexpectedStateError) as cm:
      state_machine.expect_at_least(CustomState.DONE)
    self.assertEqual(cm.exception.state, CustomState.READY)
    self.assertEqual(cm.exception.expected, (CustomState.DONE,))

    state_machine.transition(CustomState.READY, to=CustomState.DONE)
    state_machine.expect_at_least(CustomState.INITIAL)
    state_machine.expect_at_least(CustomState.READY)
    state_machine.expect_at_least(CustomState.DONE)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
