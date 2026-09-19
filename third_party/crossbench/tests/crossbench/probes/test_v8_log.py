# Copyright 2022 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse
import datetime as dt
import unittest

from crossbench.probes.all import V8LogProbe
from crossbench.probes.v8.log import DEFAULT_LOG_FLAGS
from tests import test_helper

DEFAULT_LOG_FLAGS_PROF = frozenset(DEFAULT_LOG_FLAGS + ("--prof",))


class V8LogProbeTestCase(unittest.TestCase):

  def test_invalid_flags(self):
    with self.assertRaises(ValueError):
      V8LogProbe(js_flags=["--no-opt"])

  def test_disabling_flag(self):
    probe = V8LogProbe(log_all=True, js_flags=["--no-log-maps"])
    self.assertSetEqual({"--log-all", "--no-log-maps"},
                        set(probe.js_flags.keys()))

  def test_conflicting_flags(self):
    with self.assertRaises(ValueError):
      V8LogProbe(js_flags=["--log-maps", "--no-log-maps"])
    with self.assertRaises(ValueError):
      V8LogProbe(prof=True, js_flags=["--no-prof"])
    with self.assertRaises(ValueError):
      V8LogProbe(
          prof_sampling_interval=dt.timedelta(milliseconds=12),
          js_flags=["--prof-sampling-interval=3"])

  def test_parse_invalid_config(self):
    with self.assertRaises(ValueError):
      # No logging enabled
      V8LogProbe.parse_dict({
          "log_all": False,
          "prof": False,
          "js_flags": [],
          "profview": False
      })
    with self.assertRaisesRegex(ValueError, "profview"):
      # profview needs prof
      V8LogProbe.parse_dict({
          "log_all": False,
          "js_flags": [],
          "prof": False,
          "profview": True
      })
    with self.assertRaises(argparse.ArgumentTypeError):
      V8LogProbe.parse_dict({"log_all": []})
    with self.assertRaises(argparse.ArgumentTypeError):
      V8LogProbe.parse_dict({"prof": 12})
    with self.assertRaises(ValueError):
      V8LogProbe.parse_dict({"js_flags": [1]})
    with self.assertRaises(ValueError):
      V8LogProbe.parse_dict({"js_flags": ["--log-all", True]})

  def test_parse_config(self):
    probe: V8LogProbe = V8LogProbe.parse_dict({})
    self.assertSetEqual(DEFAULT_LOG_FLAGS_PROF, set(probe.js_flags.keys()))

  def test_parse_config_prof(self):
    probe = V8LogProbe.parse_dict({"prof": False, "log_all": True})
    self.assertSetEqual({"--log-all"}, set(probe.js_flags.keys()))

    probe = V8LogProbe.parse_dict({"prof": False, "log_all": True})
    self.assertSetEqual({"--log-all"}, set(probe.js_flags.keys()))

    probe = V8LogProbe.parse_dict({"prof": True})
    self.assertSetEqual(DEFAULT_LOG_FLAGS_PROF, set(probe.js_flags.keys()))

  def test_parse_config_custom_js_flags(self):
    probe = V8LogProbe.parse_dict({"js_flags": None})
    self.assertSetEqual(DEFAULT_LOG_FLAGS_PROF, set(probe.js_flags.keys()))

    probe = V8LogProbe.parse_dict({"js_flags": []})
    self.assertSetEqual({"--prof"}, set(probe.js_flags.keys()))

    probe = V8LogProbe.parse_dict({
        "log_all": True,
        "js_flags": ["--no-log-ic", "--no-log-maps"]
    })
    self.assertSetEqual({"--log-all", "--no-log-ic", "--no-log-maps"},
                        set(probe.js_flags.keys()))

    probe = V8LogProbe.parse_dict(
        {"js_flags": ["--no-log-ic", "--no-log-maps"]})
    self.assertSetEqual({"--prof", "--no-log-ic", "--no-log-maps"},
                        set(probe.js_flags.keys()))

  def test_parse_config_prof_sampling_interval(self):
    probe = V8LogProbe.parse_dict({"log_all": False, "sampling_interval": 12})
    self.assertEqual(
        "--prof,--prof-sampling-interval=12000,--log,--log-code,--log-deopt,"
        "--log-source-code,--log-source-position,--log-code-disassemble",
        str(probe.js_flags))
    probe = V8LogProbe.parse_dict({
        "log_all": False,
        "sampling_interval": "13us"
    })
    self.assertEqual(
        "--prof,--prof-sampling-interval=13,--log,--log-code,--log-deopt,"
        "--log-source-code,--log-source-position,--log-code-disassemble",
        str(probe.js_flags))

  def test_parse_config_categories(self):
    probe = V8LogProbe.parse_dict({"categories": ["ic"]})
    expected_flags = set(DEFAULT_LOG_FLAGS) | {"--prof", "--log-ic"}
    self.assertSetEqual(expected_flags, set(probe.js_flags.keys()))

    with self.assertRaises(ValueError):
      V8LogProbe.parse_dict({"categories": ["invalid"]})

    probe = V8LogProbe.parse_str("all")
    expected_flags = set(DEFAULT_LOG_FLAGS) | {
        "--prof", "--log-ic", "--log-maps", "--log-code"
    }
    self.assertSetEqual(expected_flags, set(probe.js_flags.keys()))

    probe = V8LogProbe.parse_str("ic,map")
    expected_flags = set(DEFAULT_LOG_FLAGS) | {
        "--prof", "--log-ic", "--log-maps"
    }
    self.assertSetEqual(expected_flags, set(probe.js_flags.keys()))

  def test_parse_invalid_config_categories(self):
    with self.assertRaisesRegexp(argparse.ArgumentTypeError, "invalid"):
      V8LogProbe.parse_str("invalid")

    with self.assertRaisesRegexp(argparse.ArgumentTypeError, "ic"):
      V8LogProbe.parse_str("ic,invalid")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
