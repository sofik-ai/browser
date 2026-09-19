# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import hjson

from crossbench import path as pth
from crossbench.cli.config.probe import ProbeConfig
from crossbench.cli.config.probe_list import ProbeListConfig
from crossbench.probes.power_sampler import PowerSamplerProbe
from crossbench.probes.v8.log import V8LogProbe
from crossbench.probes.v8.rcs import V8RCSProbe
from tests import test_helper
from tests.crossbench.cli.config.base import BaseConfigTestCase

if TYPE_CHECKING:
  from crossbench.types import JsonDict


class TestProbeListConfig(BaseConfigTestCase):

  def parse_config(self, config_data) -> ProbeListConfig:
    probe_config_file = pth.LocalPath("/probe.config.hjson")
    with probe_config_file.open("w", encoding="utf-8") as f:
      hjson.dump(config_data, f)
    return ProbeListConfig.parse(probe_config_file)

  def test_invalid_empty(self):
    with self.assertRaises(argparse.ArgumentTypeError):
      _ = self.parse_config({}).probes
    with self.assertRaises(argparse.ArgumentTypeError):
      _ = self.parse_config({"foo": {}})

  def test_invalid_names(self):
    with self.assertRaises(argparse.ArgumentTypeError):
      _ = self.parse_config({"probes": {"invalid probe name": {}}}).probes

  def test_empty(self):
    config = self.parse_config({"probes": {}})
    self.assertTupleEqual(config.probes, ())

  def test_single_v8_log(self):
    js_flags = ["--log-maps", "--log-function-events"]
    config = self.parse_config({
        "probes": {
            "v8.log": {
                "prof": True,
                "log_all": True,
                "js_flags": js_flags,
            }
        }
    })
    self.assertTrue(len(config.probes), 1)
    probe = config.probes[0]
    assert isinstance(probe, V8LogProbe)
    for flag in js_flags + ["--log-all"]:
      self.assertIn(flag, probe.js_flags)

  def test_from_cli_args(self):
    file = pth.LocalPath("probe.config.hjson")
    js_flags = ["--log-maps", "--log-function-events"]
    config_data: JsonDict = {
        "probes": {
            "v8.log": {
                "prof": True,
                "log_all": True,
                "js_flags": js_flags,
            }
        }
    }
    with file.open("w", encoding="utf-8") as f:
      hjson.dump(config_data, f)
    args = self.mock_args(probe_config=file, probe=[])
    config = ProbeListConfig.from_cli_args(args)
    self.assertTrue(len(config.probes), 1)
    probe = config.probes[0]
    assert isinstance(probe, V8LogProbe)
    for flag in js_flags + ["--log-all"]:
      self.assertIn(flag, probe.js_flags)

  def test_inline_config(self):
    mock_d8_file = pth.LocalPath("out/d8")
    self.fs.create_file(mock_d8_file, st_size=8 * 1024)
    config_data = {"d8_binary": str(mock_d8_file)}
    args = self.mock_args(probe_config=None, throw=True, wraps=False)
    # without ":" separator:
    args.probe = [
        ProbeConfig.parse(f"v8.log{hjson.dumps(config_data)}"),
    ]
    config = ProbeListConfig.from_cli_args(args)
    self.assertTrue(len(config.probes), 1)
    probe = config.probes[0]
    self.assertTrue(isinstance(probe, V8LogProbe))
    # with ":" separator:
    args.probe = [
        ProbeConfig.parse(f"v8.log:{hjson.dumps(config_data)}"),
    ]
    config = ProbeListConfig.from_cli_args(args)
    self.assertTrue(len(config.probes), 1)
    probe = config.probes[0]
    self.assertTrue(isinstance(probe, V8LogProbe))

  def test_inline_config_path(self):
    mock_d8_file = pth.LocalPath("out/d8")
    self.fs.create_file(mock_d8_file, st_size=8 * 1024)
    config_data = {"d8_binary": str(mock_d8_file)}
    args = self.mock_args(probe_config=None, throw=True, wraps=False)

    probe_config_path = pth.LocalPath("config/v8.probe.config.hjson")
    probe_config_path.parent.mkdir()
    with probe_config_path.open("w", encoding="utf-8") as f:
      hjson.dump(config_data, f)
    # without ":" separator:
    args.probe = [
        ProbeConfig.parse(f"v8.log{probe_config_path.absolute()}"),
    ]
    config_without_sep = ProbeListConfig.from_cli_args(args)
    self.assertEqual(len(config_without_sep.probes), 1)
    probe_without_sep = config_without_sep.probes[0]
    self.assertIsInstance(probe_without_sep, V8LogProbe)
    # with ":" separator:
    args.probe = [
        ProbeConfig.parse(f"v8.log:{probe_config_path}"),
    ]
    config = ProbeListConfig.from_cli_args(args)
    self.assertEqual(len(config.probes), 1)
    probe = config.probes[0]
    self.assertIsInstance(probe, V8LogProbe)

  def test_inline_config_win_path(self):
    args = self.mock_args(probe_config=None, throw=True, wraps=False)
    win_mock_d8_file = "D:/out/d8.exe"
    self.fs.create_file(win_mock_d8_file, contents=b"d8")
    win_config_data = {"d8_binary": win_mock_d8_file}
    win_probe_config_path = pth.AnyWindowsPath(
        "C:/config/v8.probe.config.hjson")
    probe_config_path = pth.LocalPath(str(win_probe_config_path))
    self.fs.create_file(probe_config_path)
    with probe_config_path.open("w", encoding="utf-8") as f:
      hjson.dump(win_config_data, f)
    # with ":" separator:
    args.probe = [
        ProbeConfig.parse(f"v8.log:{win_probe_config_path}"),
    ]
    config = ProbeListConfig.from_cli_args(args)
    self.assertEqual(len(config.probes), 1)
    probe = config.probes[0]
    self.assertIsInstance(probe, V8LogProbe)

  def test_inline_config_invalid(self):
    mock_d8_file = pth.LocalPath("out/d8")
    self.fs.create_file(mock_d8_file)
    config_data = {"d8_binary": str(mock_d8_file)}
    trailing_brace = "}"
    with self.assertRaises(argparse.ArgumentTypeError):
      ProbeConfig.parse(f"v8.log{hjson.dumps(config_data)}{trailing_brace}")
    with self.assertRaises(argparse.ArgumentTypeError):
      ProbeConfig.parse(f"v8.log:{hjson.dumps(config_data)}{trailing_brace}")
    with self.assertRaises(argparse.ArgumentTypeError):
      ProbeConfig.parse("other.log")

  def test_parse_with_typo(self):
    v8_probe = ProbeConfig.parse("v8.log")
    with self.assertLogs(level="ERROR") as cm:
      v8_close_probe = ProbeConfig.parse("v8_log")
    self.assertEqual(v8_probe.probe_cls, v8_close_probe.probe_cls)
    self.assertEqual(v8_close_probe.probe_cls, V8LogProbe)
    output = "\n".join(cm.output)
    self.assertIn("v8.log", output)
    self.assertIn("v8_log", output)

    with self.assertLogs(level="ERROR") as cm:
      v8_close_probe = ProbeConfig.parse("v8_log:{}")
    self.assertEqual(v8_probe.probe_cls, v8_close_probe.probe_cls)
    self.assertEqual(v8_close_probe.probe_cls, V8LogProbe)
    output = "\n".join(cm.output)
    self.assertIn("v8.log", output)
    self.assertIn("v8_log", output)

  def test_inline_config_dir_instead_of_file(self):
    mock_dir = pth.LocalPath("some/dir")
    mock_dir.mkdir(parents=True)
    config_data = {"d8_binary": str(mock_dir)}
    args = self.mock_args(
        probe=[ProbeConfig.parse(f"v8.log{hjson.dumps(config_data)}")],
        probe_config=None,
        throw=True,
        wraps=False)
    with self.assertRaises(argparse.ArgumentTypeError) as cm:
      ProbeListConfig.from_cli_args(args)
    self.assertIn(str(mock_dir), str(cm.exception))

  def test_inline_config_non_existent_file(self):
    config_data = {"d8_binary": "does/not/exist/d8"}
    args = self.mock_args(
        probe=[ProbeConfig.parse(f"v8.log{hjson.dumps(config_data)}")],
        probe_config=None,
        throw=True,
        wraps=False)
    with self.assertRaises(argparse.ArgumentTypeError) as cm:
      ProbeListConfig.from_cli_args(args)
    expected_path = pth.LocalPath("does/not/exist/d8")
    self.assertIn(str(expected_path), str(cm.exception))

  def test_multiple_probes(self):
    powersampler_bin = pth.LocalPath("/powersampler.bin")
    powersampler_bin.touch()
    config = self.parse_config({
        "probes": {
            "v8.log": {
                "log_all": True,
            },
            "powersampler": {
                "bin_path": str(powersampler_bin)
            }
        }
    })
    self.assertTrue(len(config.probes), 2)
    log_probe = config.probes[0]
    assert isinstance(log_probe, V8LogProbe)
    powersampler_probe = config.probes[1]
    assert isinstance(powersampler_probe, PowerSamplerProbe)
    self.assertEqual(powersampler_probe.bin_path, powersampler_bin)

  def test_parse_args_empty(self):
    args = self.mock_args(probe_config=None, probe=[])
    probe_list = ProbeListConfig.from_cli_args(args)
    self.assertFalse(probe_list.probes)

  def test_parse_sequence(self):
    probe_list = ProbeListConfig.parse(["v8.rcs", "v8.log"])
    probes = probe_list.probes
    self.assertEqual(len(probes), 2)
    self.assertIsInstance(probes[0], V8RCSProbe)
    self.assertIsInstance(probes[1], V8LogProbe)

  def test_parse_dict_simple(self):
    probe_list = ProbeListConfig.parse({"v8.rcs": {}, "v8.log": {}})
    probes = probe_list.probes
    self.assertEqual(len(probes), 2)
    self.assertIsInstance(probes[0], V8RCSProbe)
    self.assertIsInstance(probes[1], V8LogProbe)
    # respect input order
    probe_list = ProbeListConfig.parse({"v8.log": {}, "v8.rcs": {}})
    probes = probe_list.probes
    self.assertEqual(len(probes), 2)
    self.assertIsInstance(probes[0], V8LogProbe)
    self.assertIsInstance(probes[1], V8RCSProbe)

  def test_parse_dict_nested_config(self):
    probe_list = ProbeListConfig.parse({"probes": {"v8.rcs": {}, "v8.log": {}}})
    probes = probe_list.probes
    self.assertEqual(len(probes), 2)
    self.assertIsInstance(probes[0], V8RCSProbe)
    self.assertIsInstance(probes[1], V8LogProbe)

  def test_parse_args_single_probe_config(self):
    args = self.mock_args(
        probe_config=None, probe=[ProbeConfig.parse("v8.log")])
    probe_list = ProbeListConfig.from_cli_args(args)
    probes = probe_list.probes
    self.assertEqual(len(probes), 1)
    probe = probes[0]
    self.assertIsInstance(probe, V8LogProbe)

  def test_parse_args_multiple_probe_config(self):
    args = self.mock_args(
        probe_config=None,
        probe=[
            ProbeConfig.parse("v8.log"),
            ProbeConfig.parse("v8.rcs"),
        ])
    probe_list = ProbeListConfig.from_cli_args(args)
    probes = probe_list.probes
    self.assertEqual(len(probes), 2)
    self.assertIsInstance(probes[0], V8LogProbe)
    self.assertIsInstance(probes[1], V8RCSProbe)

  def test_empty_config_file(self):
    with self.platform.NamedTemporaryFile("probe.config.hjson") as config_file:
      with config_file.open("w", encoding="utf-8") as f:
        hjson.dump({"probes": []}, f)
      args = self.mock_args(probe_config=config_file, probe=[])
      probe_list = ProbeListConfig.from_cli_args(args)
      self.assertFalse(probe_list.probes)

  def test_merge_empty_config_file_with_single_probe(self):
    with self.platform.NamedTemporaryFile("probe.config.hjson") as config_file:
      with config_file.open("w", encoding="utf-8") as f:
        hjson.dump({"probes": []}, f)
      args = self.mock_args(
          probe_config=config_file, probe=[ProbeConfig.parse("v8.log")])
      probe_list = ProbeListConfig.from_cli_args(args)
      probes = probe_list.probes
      self.assertEqual(len(probes), 1)
      probe = probes[0]
      self.assertIsInstance(probe, V8LogProbe)

  def test_merge_config_file_single_probe(self):
    with self.platform.NamedTemporaryFile("probe.config.hjson") as config_file:
      with config_file.open("w", encoding="utf-8") as f:
        hjson.dump({"probes": ["v8.rcs"]}, f)
      args = self.mock_args(
          probe_config=config_file, probe=[ProbeConfig.parse("v8.log")])
      probe_list = ProbeListConfig.from_cli_args(args)
      probes = probe_list.probes
      self.assertEqual(len(probes), 2)
      self.assertIsInstance(probes[0], V8RCSProbe)
      self.assertIsInstance(probes[1], V8LogProbe)

  def test_merge_config_file_conflict(self):
    # By default --probe args override --probe-config args
    with self.platform.NamedTemporaryFile("probe.config.hjson") as config_file:
      with config_file.open("w", encoding="utf-8") as f:
        hjson.dump({"probes": ["v8.rcs"]}, f)
      args = self.mock_args(
          probe_config=config_file, probe=[ProbeConfig.parse("v8.rcs")])
      probe_list = ProbeListConfig.from_cli_args(args)
      probes = probe_list.probes
      self.assertEqual(len(probes), 1)
      probe = probes[0]
      self.assertIsInstance(probe, V8RCSProbe)

  def test_merge_conflict_raw(self):
    probe_list_a = ProbeListConfig(
        [ProbeConfig.parse("v8.log"),
         ProbeConfig.parse("v8.rcs")])
    probe_list_b = ProbeListConfig([ProbeConfig.parse("v8.rcs")])
    with self.assertRaisesRegex(ValueError, "Duplicate"):
      probe_list_a.merge(probe_list_b)
    with self.assertRaisesRegex(ValueError, "Duplicate"):
      probe_list_b.merge(probe_list_a)

    merged_a_b = probe_list_a.merge(probe_list_b, should_override=True)
    probes = merged_a_b.probes
    self.assertEqual(len(probes), 2)
    self.assertIsInstance(probes[0], V8LogProbe)
    self.assertIsInstance(probes[1], V8RCSProbe)

    merged_b_a = probe_list_b.merge(probe_list_a, should_override=True)
    probes = merged_b_a.probes
    self.assertEqual(len(probes), 2)
    self.assertIsInstance(probes[0], V8RCSProbe)
    self.assertIsInstance(probes[1], V8LogProbe)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
