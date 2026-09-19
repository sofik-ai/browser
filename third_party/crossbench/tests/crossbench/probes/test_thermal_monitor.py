# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import json
import unittest

from crossbench.browsers.settings import Settings
from crossbench.probes.thermal_monitor import ThermalMonitorProbe, \
    ThermalStatus
from tests import test_helper
from tests.crossbench.mock_browser import MockChromeAndroidStable
from tests.crossbench.mock_helper import AndroidAdbMockPlatform, MockAdb, \
    ShResult
from tests.crossbench.runner.helper import BaseRunnerTestCase


class ThermalStatusTestCase(unittest.TestCase):

  def test_thermal_status_short_names(self):
    self.assertIs(ThermalStatus.parse("none"), ThermalStatus.NONE)
    self.assertIs(ThermalStatus.parse("light"), ThermalStatus.LIGHT)
    self.assertIs(ThermalStatus.parse("moderate"), ThermalStatus.MODERATE)
    self.assertIs(ThermalStatus.parse("severe"), ThermalStatus.SEVERE)
    self.assertIs(ThermalStatus.parse("critical"), ThermalStatus.CRITICAL)
    self.assertIs(ThermalStatus.parse("emergency"), ThermalStatus.EMERGENCY)
    self.assertIs(ThermalStatus.parse("shutdown"), ThermalStatus.SHUTDOWN)

  def test_thermal_status_long_names(self):
    self.assertIs(
        ThermalStatus.parse("THERMAL_STATUS_NONE"), ThermalStatus.NONE)
    self.assertIs(
        ThermalStatus.parse("THERMAL_STATUS_LIGHT"), ThermalStatus.LIGHT)
    self.assertIs(
        ThermalStatus.parse("THERMAL_STATUS_MODERATE"), ThermalStatus.MODERATE)
    self.assertIs(
        ThermalStatus.parse("THERMAL_STATUS_SEVERE"), ThermalStatus.SEVERE)
    self.assertIs(
        ThermalStatus.parse("THERMAL_STATUS_CRITICAL"), ThermalStatus.CRITICAL)
    self.assertIs(
        ThermalStatus.parse("THERMAL_STATUS_EMERGENCY"),
        ThermalStatus.EMERGENCY)
    self.assertIs(
        ThermalStatus.parse("THERMAL_STATUS_SHUTDOWN"), ThermalStatus.SHUTDOWN)

  def test_thermal_status_numbers(self):
    self.assertIs(ThermalStatus.parse("-1"), ThermalStatus.UNAVAILABLE)
    self.assertIs(ThermalStatus.parse("0"), ThermalStatus.NONE)
    self.assertIs(ThermalStatus.parse("1"), ThermalStatus.LIGHT)
    self.assertIs(ThermalStatus.parse("2"), ThermalStatus.MODERATE)
    self.assertIs(ThermalStatus.parse("3"), ThermalStatus.SEVERE)
    self.assertIs(ThermalStatus.parse("4"), ThermalStatus.CRITICAL)
    self.assertIs(ThermalStatus.parse("5"), ThermalStatus.EMERGENCY)
    self.assertIs(ThermalStatus.parse("6"), ThermalStatus.SHUTDOWN)


class TestThermalMonitorProbe(BaseRunnerTestCase):

  def test_android_run(self):
    self.fs.create_file("/usr/bin/adb", contents="adb")
    if self.platform.is_macos:
      self.platform.expect_sh("brew", "--prefix", result=ShResult(returncode=1))
    self.platform.expect_sh(
        "/usr/bin/adb",
        "devices",
        "-l",
        result="List of devices attached\n123 device usb:0 product:a model:b")
    adb_platform = AndroidAdbMockPlatform(
        self.platform, adb=MockAdb(self.platform))
    runner = self.default_runner(browsers=[
        MockChromeAndroidStable(
            "adb:chrome", settings=Settings(platform=adb_platform))
    ])

    adb_platform.expect_sh(
        "dumpsys",
        "thermalservice",
        result="HAL Ready: true\nThermal Status: 0")
    adb_platform.expect_sh(
        "dumpsys",
        "thermalservice",
        result="HAL Ready: true\nThermal Status: 1")
    adb_platform.expect_sh(
        "dumpsys",
        "thermalservice",
        result="HAL Ready: true\nThermal Status: 2")
    adb_platform.expect_sh(
        "dumpsys",
        "thermalservice",
        result="HAL Ready: true\nThermal Status: 0")

    runner.run(is_dry_run=False)

    self.assertEqual(len(runner.runs), 2)
    self.assertTrue(runner.is_success)

    run = runner.runs[0]
    self.assertTrue(run.is_success)
    results = run.results.get_by_name(ThermalMonitorProbe.NAME)
    assert results
    with results.json.open() as f:
      thermal_data = json.load(f)
      self.assertIn("max_observed_status", thermal_data)
      self.assertEqual(thermal_data["max_observed_status"], 1)

    run = runner.runs[1]
    self.assertTrue(run.is_success)
    results = run.results.get_by_name(ThermalMonitorProbe.NAME)
    assert results
    with results.json.open() as f:
      thermal_data = json.load(f)
      self.assertIn("max_observed_status", thermal_data)
      self.assertEqual(thermal_data["max_observed_status"], 2)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
