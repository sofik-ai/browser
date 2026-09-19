# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing_extensions import override

from crossbench.helper.state import UnexpectedStateError
from crossbench.runner.run import ProbeRunContextManager
from tests import test_helper
from tests.crossbench.runner.helper import BaseRunnerTestCase, MockProbe, \
    MockProbeContext
from tests.crossbench.test_exception import CustomException


class FailingMockProbeContext(MockProbeContext):

  @override
  def setup(self):
    raise CustomException("failing setup")


class ProbeContextManagerTestCase(BaseRunnerTestCase):

  def setup_context_manager(self, throw: bool = True):
    self.runner = self.single_story_runner(throw=throw)
    self.cb_run = list(self.runner._get_runs())[0]
    self.context_manager = ProbeRunContextManager(self.cb_run,
                                                  self.cb_run.results)

  def test_basic_accessor(self):
    self.setup_context_manager()
    self.assertTrue(self.context_manager.is_success)
    self.assertFalse(self.context_manager.is_ready)
    self.assertFalse(self.context_manager.is_running)

  def test_wrong_order(self):
    self.setup_context_manager()
    with self.assertRaisesRegex(UnexpectedStateError, "INITIAL"):
      with self.context_manager.open(is_dry_run=False):
        pass
    with self.assertRaisesRegex(UnexpectedStateError, "INITIAL"):
      self.context_manager.teardown(is_dry_run=False)

  def test_setup_no_probes(self):
    self.setup_context_manager()
    self.assertFalse(self.context_manager.is_ready)
    with self.assertRaises(AssertionError):
      self.context_manager.setup([], is_dry_run=False)
    self.assertFalse(self.context_manager.is_ready)

  def test_setup_detached_probe(self):
    self.setup_context_manager()
    probe = MockProbe("custom_probe_data")
    self.assertFalse(self.context_manager.is_ready)
    with self.assertRaisesRegex(AssertionError, "attached"):
      self.context_manager.setup([probe], is_dry_run=False)
    self.assertFalse(self.context_manager.is_ready)

  def test_setup_single_probe(self):
    self.setup_context_manager()
    probe = MockProbe("custom_probe_data")
    self.runner.attach_probe(probe)
    self.assertFalse(self.context_manager.is_ready)
    self.context_manager.setup([probe], is_dry_run=False)
    self.assertTrue(self.context_manager.is_ready)

  def test_setup_single_probe_dry_run(self):
    self.setup_context_manager()
    probe = MockProbe("custom_probe_data")
    self.runner.attach_probe(probe)
    self.assertFalse(self.context_manager.is_ready)
    self.context_manager.setup([probe], is_dry_run=True)
    self.assertFalse(self.context_manager.is_running)
    self.assertTrue(self.context_manager.is_ready)

  def test_setup_teardown_dry_run(self):
    self.setup_context_manager()
    probe = MockProbe("custom_probe_data")
    self.runner.attach_probe(probe)
    self.context_manager.setup([probe], is_dry_run=True)
    self.assertTrue(self.context_manager.is_ready)
    self.context_manager.teardown(is_dry_run=True)
    self.assertFalse(self.context_manager.is_ready)
    self.assertNotIn(probe, self.cb_run.results)

  def test_direct_setup_teardown(self):
    self.setup_context_manager()
    probe = MockProbe("custom_probe_data")
    self.runner.attach_probe(probe)
    self.cb_run.out_dir.mkdir(parents=True)
    self.context_manager.setup([probe], is_dry_run=False)
    self.assertTrue(self.context_manager.is_ready)
    self.context_manager.teardown(is_dry_run=False)
    self.assertFalse(self.context_manager.is_ready)
    self.assertTrue(self.context_manager.is_success)
    children = list(self.cb_run.out_dir.iterdir())
    self.assertEqual(len(children), 1)
    result_file = self.cb_run.results[probe].file
    self.assertTrue(result_file.exists())
    self.assertEqual(result_file, children[0])

  def test_setup_open_teardown_dry_run(self):
    self.setup_context_manager()
    probe = MockProbe("custom_probe_data")
    self.runner.attach_probe(probe)
    self.context_manager.setup([probe], is_dry_run=True)
    self.assertFalse(self.context_manager.is_running)
    with self.context_manager.open(is_dry_run=True):
      self.assertTrue(self.context_manager.is_running)
    self.context_manager.teardown(is_dry_run=True)
    self.assertFalse(self.context_manager.is_running)
    self.assertTrue(self.context_manager.is_success)
    self.assertNotIn(probe, self.cb_run.results)

  def test_setup_open_teardown(self):
    self.setup_context_manager()
    probe = MockProbe("custom_probe_data")
    self.runner.attach_probe(probe)
    self.cb_run.out_dir.mkdir(parents=True)
    self.context_manager.setup([probe], is_dry_run=False)
    self.assertFalse(self.context_manager.is_running)
    with self.context_manager.open(is_dry_run=False):
      self.assertTrue(self.context_manager.is_running)
    self.context_manager.teardown(is_dry_run=False)
    self.assertFalse(self.context_manager.is_running)
    self.assertTrue(self.context_manager.is_success)
    children = list(self.cb_run.out_dir.iterdir())
    self.assertEqual(len(children), 1)
    result_file = self.cb_run.results[probe].file
    self.assertTrue(result_file.exists())
    self.assertEqual(result_file, children[0])

  def test_setup_error_throw(self):
    self.setup_context_manager()
    probe = MockProbe("custom_probe_data", FailingMockProbeContext)
    self.runner.attach_probe(probe)
    with self.assertRaisesRegex(CustomException, "failing setup"):
      self.context_manager.setup([probe], is_dry_run=False)
    self.assertFalse(self.context_manager.is_success)

  def test_setup_error(self):
    self.setup_context_manager(throw=False)
    probe = MockProbe("custom_probe_data", FailingMockProbeContext)
    self.runner.attach_probe(probe)

    self.context_manager.setup([probe], is_dry_run=False)
    self.assertFalse(self.context_manager.is_success)
    self.assertEqual(len(self.cb_run.exceptions), 1)
    self.assertTrue(self.cb_run.results[probe].is_empty)

    exception = self.cb_run.exceptions[0].exception
    self.assertIsInstance(exception, CustomException)


del BaseRunnerTestCase

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
