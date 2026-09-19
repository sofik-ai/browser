# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

from crossbench.cli.config.probe_list import ProbeListConfig
from crossbench.probes.dtrace import DTraceProbe
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase


class DTraceProbeTestCase(CrossbenchFakeFsTestCase):

  def test_parse_example_config(self):
    config_file = test_helper.config_dir() / "doc/probe/dtrace.config.hjson"
    self.fs.add_real_file(config_file)
    self.assertTrue(config_file.is_file())
    example_script_file = config_file.parent / "dtrace.config.example.d"
    self.fs.create_file(example_script_file, st_size=100)
    self.assertTrue(example_script_file.is_file())
    probes = ProbeListConfig.parse(config_file).probes
    self.assertEqual(len(probes), 1)
    probe = probes[0]
    self.assertIsInstance(probe, DTraceProbe)
    isinstance(probe, DTraceProbe)
    self.assertEqual(probe.script_path, example_script_file)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
