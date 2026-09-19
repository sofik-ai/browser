# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import hjson

from crossbench import path as pth
from crossbench.cli.config.probe import ProbeConfig
from crossbench.config import config_dir
from crossbench.probes.cb_perfetto.perfetto import TraceConfig
from tests import test_helper
from tests.crossbench.cli.config.base import BaseConfigTestCase


class ProbeConfigTestCase(BaseConfigTestCase):

  def test_parse_inline_str(self):
    mock_d8_file = pth.LocalPath("out/d8")
    self.fs.create_file(mock_d8_file, st_size=8 * 1024)
    config_data = {"d8_binary": str(mock_d8_file)}
    hjson_str = hjson.dumps(config_data)
    src_str = f"v8.log{hjson_str}"
    config = ProbeConfig.parse(src_str)
    self.assertEqual(config.src_str, src_str)
    self.assertIsNone(config.config_str)
    self.assertDictEqual(config.config_dict, config_data)

  def test_parse_inline_str_preset(self):
    src_str = "v8.log:all"
    config = ProbeConfig.parse(src_str)
    self.assertEqual(config.src_str, src_str)
    self.assertEqual(config.config_str, "all")
    self.assertIsNone(config.config_dict)

  def test_parse_hjson_inline_file(self):
    probe_config_file = config_dir() / "probe/perfetto/default.config.hjson"
    self.fs.add_real_file(str(probe_config_file))
    self.assertTrue(probe_config_file.is_file())
    src_str = f"perfetto:{probe_config_file}"
    config = ProbeConfig.parse(src_str)
    self.assertEqual(config.src_str, src_str)
    self.assertIsNone(config.config_str)
    self.assertDictEqual(config.config_dict,
                         hjson.loads(probe_config_file.read_text()))

  def test_parse_non_hjson_inline_file(self):
    trace_config_file = TraceConfig.preset_dir() / "v8.txtpb"
    self.fs.add_real_file(str(trace_config_file))
    self.assertTrue(trace_config_file.is_file())
    src_str = f"perfetto:{trace_config_file}"
    config = ProbeConfig.parse(src_str)
    self.assertEqual(config.src_str, src_str)
    self.assertEqual(config.config_str, str(trace_config_file))
    self.assertIsNone(config.config_dict)

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
