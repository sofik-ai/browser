# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import atexit
import json
import os
import pathlib
from unittest import mock

from pyfakefs import fake_filesystem_unittest

from crossbench.runner.runner_state import RunnerState, RunnerStateMachine
from tests import test_helper


class TestRunnerStateMachine(fake_filesystem_unittest.TestCase):

  def setUp(self) -> None:
    super().setUp()
    self.setUpPyfakefs()
    self.out_dir = pathlib.Path("/test/results")
    self.out_dir.mkdir(parents=True, exist_ok=True)

    self.mock_runner = mock.MagicMock()
    self.mock_runner.out_dir = self.out_dir
    self.mock_runner.runs_dir = self.out_dir / "runs"

    self.state = RunnerStateMachine(self.mock_runner)

  def tearDown(self) -> None:
    atexit.unregister(self.state._atexit_handler)
    super().tearDown()

  def status_json(self) -> dict:
    with self.state.path.open() as f:
      return json.load(f)

  def test_initialization(self):
    self.assertEqual(self.state.state, RunnerState.INITIAL)
    self.assertEqual(self.state.path, self.out_dir / "status.json")

    self.assertTrue(self.state.path.exists())

    data = self.status_json()
    self.assertEqual(data["pid"], os.getpid())
    self.assertEqual(data["status"], "INITIAL")
    self.assertEqual(data["runs"]["total"], 0)
    self.assertListEqual(data["runs"]["current"], [])

  def test_transition(self):
    self.state.transition(RunnerState.INITIAL, to=RunnerState.SETUP)
    self.assertEqual(self.state.state, RunnerState.SETUP)

    data = self.status_json()
    self.assertEqual(data["status"], "SETUP")

  def test_set_total_runs(self):
    data = self.status_json()
    self.assertEqual(data["runs"]["total"], 0)
    self.state.set_total_runs(10)
    data = self.status_json()
    self.assertEqual(data["runs"]["total"], 10)

  def test_active_run(self):
    run = mock.MagicMock()
    run.index = 5
    run.is_success = True

    with self.state.active_run(run):
      data = self.status_json()
      self.assertListEqual(data["runs"]["current"], [5])

    data = self.status_json()
    self.assertListEqual(data["runs"]["current"], [])
    self.assertEqual(data["runs"]["success"], 1)

  def test_multiple_active_runs(self):
    run1 = mock.MagicMock()
    run1.index = 1
    run1.is_success = True

    run2 = mock.MagicMock()
    run2.index = 2
    run2.is_success = True

    data = self.status_json()
    self.assertListEqual(data["runs"]["current"], [])

    with self.state.active_run(run2):
      data = self.status_json()
      self.assertListEqual(data["runs"]["current"], [2])

      with self.state.active_run(run1):
        data = self.status_json()
        self.assertListEqual(data["runs"]["current"], [1, 2])

      data = self.status_json()
      self.assertListEqual(data["runs"]["current"], [2])

    data = self.status_json()
    self.assertListEqual(data["runs"]["current"], [])

  def test_interrupt(self):
    data = self.status_json()
    self.assertEqual(data["status"], "INITIAL")
    self.state.interrupt()
    self.assertEqual(self.state.state, RunnerState.INTERRUPTING)
    data = self.status_json()
    self.assertEqual(data["status"], "INTERRUPTING")
    self.assertIsNotNone(data["pid"])

  def test_atexit_handler(self):
    data = self.status_json()
    self.assertIsNotNone(data["pid"])
    self.assertEqual(data["status"], "INITIAL")
    self.state._atexit_handler()
    data = self.status_json()
    self.assertIsNone(data["pid"])
    self.assertEqual(data["status"], "DONE_ERRORED")

  def test_atexit_handler_interrupting(self):
    data = self.status_json()
    self.assertEqual(data["status"], "INITIAL")
    self.state.interrupt()
    self.assertEqual(self.state.state, RunnerState.INTERRUPTING)
    self.state._atexit_handler()
    data = self.status_json()
    self.assertIsNone(data["pid"])
    self.assertEqual(data["status"], "DONE_INTERRUPTED")

  def test_atexit_handler_teardown(self):
    data = self.status_json()
    self.state.transition(RunnerState.INITIAL, to=RunnerState.TEARDOWN)
    self.assertEqual(self.state.state, RunnerState.TEARDOWN)
    self.state._atexit_handler()
    data = self.status_json()
    self.assertIsNone(data["pid"])
    self.assertEqual(data["status"], "DONE_ERRORED")

  def test_last_modified_changes(self):
    with mock.patch(
        "crossbench.runner.runner_state.dt.datetime") as mock_datetime:
      mock_datetime.now.return_value.isoformat.side_effect = [
          "2026-04-29T12:00:00",
          "2026-04-29T12:00:00",
          "2026-04-29T12:00:01",
      ]

      state = RunnerStateMachine(self.mock_runner)
      # Unregister local instance not covered by tearDown
      atexit.unregister(state._atexit_handler)

      data_before = self.status_json()
      self.assertEqual(data_before["created"], "2026-04-29T12:00:00")
      self.assertEqual(data_before["last_modified"], "2026-04-29T12:00:00")

      state.update()

      data_after = self.status_json()
      self.assertEqual(data_after["created"], "2026-04-29T12:00:00")
      self.assertEqual(data_after["last_modified"], "2026-04-29T12:00:01")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
