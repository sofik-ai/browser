# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

from unittest import mock

from immutabledict import immutabledict
from typing_extensions import override

from crossbench import path as pth
from crossbench.browsers.browser import Browser
from crossbench.env.runner_env import RunnerEnv
from crossbench.plt.linux import LinuxPlatform
from crossbench.probes.cpu_frequency_map import CPUFrequencyMap
from crossbench.probes.frequency import FrequencyProbe, FrequencyProbeContext
from crossbench.runner.run import Run
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase


class FrequencyProbeTestCase(CrossbenchFakeFsTestCase):

  @override
  def setUp(self):
    super().setUp()
    self.platform = LinuxPlatform()

  # Simply tests the communication between FrequencyProbe and CPUFrequencyMap.
  # Details for the latter are tested in CPUFrequencyMapTestCase.
  def test_validate(self):
    probe = FrequencyProbe.parse_dict(
        {"cpus": {
            "cpu10": "min",
            "cpu20": 20,
            "cpu30": "max"
        }})
    self._create_cpu_dir("cpu10", [20, 10, 30])
    self._create_cpu_dir("cpu20", [10, 20, 30])
    self._create_cpu_dir("cpu30", [10, 30, 20])
    self._create_cpu_dir("cpu40", [42, 42, 42])
    self._create_cpu_dir("cpu50", [42, 42, 42])
    browser = self._create_mock_browser()

    # Implicitly asserts no exception occurs.
    probe.validate_browser(mock.Mock(spec=RunnerEnv), browser)
    target_frequencies = probe.cpu_frequency_map.get_target_frequencies(
        browser.platform)

    self.assertDictEqual(
        dict(target_frequencies), {
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu10/cpufreq"): 10,
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu20/cpufreq"): 20,
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu30/cpufreq"): 30,
        })

  def test_start_and_stop(self):
    self._create_cpu_dir("cpu0", [1, 2, 3])
    mock_map = mock.Mock(spec=CPUFrequencyMap)
    mock_map.get_target_frequencies = mock.Mock(
        return_value=immutabledict(
            {pth.AnyPosixPath("/sys/devices/system/cpu/cpu0/cpufreq"): 2}))
    mock_probe = mock.Mock(spec=FrequencyProbe)
    type(mock_probe).cpu_frequency_map = mock.PropertyMock(
        return_value=mock_map)
    mock_run = mock.Mock(spec=Run)
    mock_run.browser = self._create_mock_browser()
    context = FrequencyProbeContext(mock_probe, mock_run)

    min_file = pth.AnyPosixPath(
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq")
    max_file = pth.AnyPosixPath(
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")
    self.assertEqual(self.platform.cat(min_file), "1\n")
    self.assertEqual(self.platform.cat(max_file), "3\n")

    context.start()

    self.assertEqual(self.platform.cat(min_file), "2\n")
    self.assertEqual(self.platform.cat(max_file), "2\n")
    mock_map.get_target_frequencies.assert_called_with(self.platform)

    context.stop()

    self.assertEqual(self.platform.cat(min_file), "1\n")
    self.assertEqual(self.platform.cat(max_file), "3\n")

  def _create_mock_browser(self):
    mock_browser = mock.Mock(spec=Browser)
    mock_browser.platform = self.platform
    return mock_browser

  def _create_cpu_dir(self, cpu_name: str, available_frequencies: list[int]):
    cpu_dir = pth.AnyPosixPath(f"/sys/devices/system/cpu/{cpu_name}/cpufreq")
    self.platform.mkdir(cpu_dir, parents=True, exist_ok=True)
    self.platform.write_text(cpu_dir / "scaling_available_frequencies",
                             " ".join(map(str, available_frequencies)) + "\n")
    self.platform.write_text(cpu_dir / "scaling_min_freq",
                             str(min(available_frequencies)) + "\n")
    self.platform.write_text(cpu_dir / "scaling_max_freq",
                             str(max(available_frequencies)) + "\n")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
