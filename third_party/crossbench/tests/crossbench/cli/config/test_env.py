# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import datetime as dt

from crossbench import hjson as cb_hjson
from crossbench.cli.config.env import ENV_CONFIG_PRESETS, EnvConfig
from tests import test_helper
from tests.crossbench.cli.config.base import BaseConfigTestCase


class EnvironmentConfigTestCase(BaseConfigTestCase):

  def test_parse_global_config_dict(self):
    env_config_data = {
        "screen_brightness_percent": 66,
        "cpu_max_usage_percent": 77,
    }
    config_data = {
        "probes": {},
        "env": env_config_data,
        "browsers": {},
        "network": {},
    }
    direct = EnvConfig.parse(env_config_data)
    nested = EnvConfig.parse(config_data)
    self.assertEqual(direct, nested)
    self.assertEqual(direct.disk_min_free_space_gib, EnvConfig.IGNORE)
    self.assertEqual(direct.screen_brightness_percent, 66)
    self.assertEqual(direct.cpu_max_usage_percent, 77)

  def test_parse_empty_dict(self):
    self.assertEqual(EnvConfig.parse({}), ENV_CONFIG_PRESETS["default"])

  def test_parse_dict(self):
    config_data = {"cpu_min_relative_speed": None, "cpu_max_usage_percent": 12}
    config = EnvConfig.parse(config_data)
    self.assertEqual(config, EnvConfig.parse({"env": config_data}))
    self.assertIsNone(config.cpu_min_relative_speed)
    self.assertEqual(config.cpu_max_usage_percent, 12)

  def test_combine_bool_value(self):
    default = EnvConfig()
    self.assertIsNone(default.power_use_battery)

    battery = EnvConfig(power_use_battery=True)
    self.assertTrue(battery.power_use_battery)
    self.assertTrue(battery.merge(battery).power_use_battery)
    self.assertTrue(default.merge(battery).power_use_battery)
    self.assertTrue(battery.merge(default).power_use_battery)

    power = EnvConfig(power_use_battery=False)
    self.assertFalse(power.power_use_battery)
    self.assertFalse(power.merge(power).power_use_battery)
    self.assertFalse(default.merge(power).power_use_battery)
    self.assertFalse(power.merge(default).power_use_battery)

    with self.assertRaises(ValueError):
      power.merge(battery)

  def test_combine_min_float_value(self):
    default = EnvConfig()
    self.assertIsNone(default.cpu_min_relative_speed)

    high = EnvConfig(cpu_min_relative_speed=1)
    self.assertEqual(high.cpu_min_relative_speed, 1)
    self.assertEqual(high.merge(high).cpu_min_relative_speed, 1)
    self.assertEqual(default.merge(high).cpu_min_relative_speed, 1)
    self.assertEqual(high.merge(default).cpu_min_relative_speed, 1)

    low = EnvConfig(cpu_min_relative_speed=0.5)
    self.assertEqual(low.cpu_min_relative_speed, 0.5)
    self.assertEqual(low.merge(low).cpu_min_relative_speed, 0.5)
    self.assertEqual(default.merge(low).cpu_min_relative_speed, 0.5)
    self.assertEqual(low.merge(default).cpu_min_relative_speed, 0.5)

    self.assertEqual(high.merge(low).cpu_min_relative_speed, 1)
    self.assertEqual(low.merge(high).cpu_min_relative_speed, 1)

  def test_combine_max_float_value(self):
    default = EnvConfig()
    self.assertIsNone(default.cpu_max_usage_percent)

    high = EnvConfig(cpu_max_usage_percent=100)
    self.assertEqual(high.cpu_max_usage_percent, 100)
    self.assertEqual(high.merge(high).cpu_max_usage_percent, 100)
    self.assertEqual(default.merge(high).cpu_max_usage_percent, 100)
    self.assertEqual(high.merge(default).cpu_max_usage_percent, 100)

    low = EnvConfig(cpu_max_usage_percent=0)
    self.assertEqual(low.cpu_max_usage_percent, 0)
    self.assertEqual(low.merge(low).cpu_max_usage_percent, 0)
    self.assertEqual(default.merge(low).cpu_max_usage_percent, 0)
    self.assertEqual(low.merge(default).cpu_max_usage_percent, 0)

    self.assertEqual(high.merge(low).cpu_max_usage_percent, 0)
    self.assertEqual(low.merge(high).cpu_max_usage_percent, 0)

  def test_combine_max_duration(self):
    default = EnvConfig()
    self.assertIsNone(default.system_min_uptime)

    high = EnvConfig(system_min_uptime=dt.timedelta(minutes=10))
    self.assertEqual(high.system_min_uptime, dt.timedelta(minutes=10))
    self.assertEqual(
        high.merge(high).system_min_uptime, dt.timedelta(minutes=10))
    self.assertEqual(
        default.merge(high).system_min_uptime, dt.timedelta(minutes=10))
    self.assertEqual(
        high.merge(default).system_min_uptime, dt.timedelta(minutes=10))

    low = EnvConfig(system_min_uptime=dt.timedelta(minutes=1))
    self.assertEqual(low.system_min_uptime, dt.timedelta(minutes=1))
    self.assertEqual(low.merge(low).system_min_uptime, dt.timedelta(minutes=1))
    self.assertEqual(
        default.merge(low).system_min_uptime, dt.timedelta(minutes=1))
    self.assertEqual(
        low.merge(default).system_min_uptime, dt.timedelta(minutes=1))

    self.assertEqual(
        low.merge(high).system_min_uptime, dt.timedelta(minutes=10))
    self.assertEqual(
        high.merge(low).system_min_uptime, dt.timedelta(minutes=10))

  def test_parse_example_config_file(self):
    example_config_file = test_helper.config_dir() / "doc/env.config.hjson"
    self.fs.add_real_file(example_config_file)
    with example_config_file.open(encoding="utf-8") as f:
      data = cb_hjson.load_unique_keys(f)
    EnvConfig(**data["env"])


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
