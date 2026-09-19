# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import unittest

from crossbench.cli.config.probe_list import ProbeListConfig
from tests import test_helper


class TestExampleProbeListConfig(unittest.TestCase):

  def test_team_configs(self):
    teams_dir = test_helper.config_dir() / "team"
    self._load_probe_config_glob(teams_dir.glob("**/*.probe.config.hjson"))

  def test_doc_configs(self):
    teams_dir = test_helper.config_dir() / "doc"
    self._load_probe_config_glob(teams_dir.glob("**/*probe.config.hjson"))

  def test_doc_probe_configs(self):
    teams_dir = test_helper.config_dir() / "doc/probe"
    self._load_probe_config_glob(teams_dir.glob("**/*config.hjson"))

  def _load_probe_config_glob(self, path_iter):
    config_paths = tuple(path_iter)
    self.assertGreater(len(config_paths), 0)
    for probe_config_path in config_paths:
      with self.subTest(probe_config=str(probe_config_path)):
        self._load_probe_config(probe_config_path)

  def _load_probe_config(self, page_config_path):
    file_config = ProbeListConfig.parse(page_config_path)
    self.assertGreater(len(file_config.probes), 0)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
