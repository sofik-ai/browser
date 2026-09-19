# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from crossbench.probes.probe import Probe
from tests import test_helper
from tests.crossbench.runner.helper import BaseRunnerTestCase

if TYPE_CHECKING:
  from crossbench.runner.runner import Runner


class MockProbeWithName(Probe):

  def __init__(self, name: str = "additional_probe"):
    self._name = name
    super().__init__()


class MockProbeWithAdditional(MockProbeWithName):

  def __init__(self, additional_probe: Probe, name: str):
    super().__init__(name)
    self.additional_probe = additional_probe

  @property
  def name(self) -> str:
    return self._name

  def get_extra_probes(self, runner: Runner) -> Iterable[Probe]:
    del runner
    return [self.additional_probe]


class TestRunnerProbes(BaseRunnerTestCase):

  def test_auto_add_probe(self):
    additional_probe = MockProbeWithName()
    main_probe = MockProbeWithAdditional(additional_probe, "main_probe")

    runner = self.default_runner(probes=[main_probe])

    self.assertIn(main_probe, runner.probes)
    self.assertIn(additional_probe, runner.probes)
    self.assertTrue(runner.has_probe(main_probe.name))
    self.assertTrue(runner.has_probe(additional_probe.name))

  def test_auto_add_probe_recursive(self):
    additional_probe_2 = MockProbeWithName("additional_probe_2")
    additional_probe_1 = MockProbeWithAdditional(additional_probe_2,
                                                 "additional_probe_1")
    main_probe = MockProbeWithAdditional(additional_probe_1, "main_probe")

    runner = self.default_runner(probes=[main_probe])

    self.assertIn(main_probe, runner.probes)
    self.assertIn(additional_probe_1, runner.probes)
    self.assertIn(additional_probe_2, runner.probes)

  def test_auto_add_probe_deduplicate(self):
    additional_probe = MockProbeWithName()
    probe_1 = MockProbeWithAdditional(additional_probe, "probe_1")
    probe_2 = MockProbeWithAdditional(additional_probe, "probe_2")

    with self.assertRaisesRegex(ValueError, additional_probe.name):
      self.default_runner(probes=[probe_1, probe_2])


del BaseRunnerTestCase

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
