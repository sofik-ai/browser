# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse

from typing_extensions import override

from crossbench import path as pth
from crossbench.plt.linux import LinuxPlatform
from crossbench.probes.cpu_frequency_map import CPUFrequencyMap
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase


class CPUFrequencyMapTestCase(CrossbenchFakeFsTestCase):

  @override
  def setUp(self):
    super().setUp()
    self.platform = LinuxPlatform()

  def test_parse_invalid_map_value(self):
    with self.assertRaisesRegex(argparse.ArgumentTypeError, "Invalid value"):
      CPUFrequencyMap.parse({"cpu0": "invalid"})

  def test_parse_conflicting_wildcard(self):
    with self.assertRaisesRegex(argparse.ArgumentTypeError,
                                "should be the only key"):
      CPUFrequencyMap.parse({"*": "max", "cpu0": "min"})

  def test_key(self):
    key1 = CPUFrequencyMap.parse({"cpu0": 1111}).key
    key2 = CPUFrequencyMap.parse({"*": 2222}).key

    self.assertIsNotNone(key1)
    self.assertIsNotNone(key2)
    self.assertNotEqual(key1, key2)
    self.assertTrue(hash(key1))
    self.assertTrue(hash(key2))

  def test_validate_fails_due_to_missing_cpus_dir(self):
    frequency_map = CPUFrequencyMap.parse({"cpu0": 42})
    # No call to self._create_cpu_dir().

    with self.assertRaisesRegex(FileNotFoundError,
                                "/sys/devices/system/cpu not found"):
      frequency_map.get_target_frequencies(self.platform)

  def test_validate_fails_due_to_missing_cpu_name(self):
    frequency_map = CPUFrequencyMap.parse({"nonexistent-cpu": 1})
    self._create_cpu_dir("cpu0", [1])

    with self.assertRaisesRegex(ValueError, "nonexistent-cpu"):
      frequency_map.get_target_frequencies(self.platform)

  def test_validate_fails_due_to_missing_numerical_frequency(self):
    frequency_map = CPUFrequencyMap.parse({"cpu0": 42})
    self._create_cpu_dir("cpu0", [1, 2])
    self._create_cpu_dir("cpu1", [42])

    with self.assertRaisesRegex(
        ValueError, r"Target frequency 42 for cpu0 not allowed in linux.*. "
        r"Available frequencies: \[1, 2\]"):
      frequency_map.get_target_frequencies(self.platform)

  def test_validate_fails_due_to_missing_numerical_frequency_with_wildcard(
      self):
    frequency_map = CPUFrequencyMap.parse({"*": 42})
    self._create_cpu_dir("cpu0", [1, 2])

    with self.assertRaisesRegex(
        ValueError, r"Target frequency 42 for cpu0 not allowed in linux.*. "
        r"Available frequencies: \[1, 2\]"):
      frequency_map.get_target_frequencies(self.platform)

  def test_validate_succeeds_with_extremes(self):
    frequency_map = CPUFrequencyMap.parse({"cpu0": "max", "cpu1": "min"})
    self._create_cpu_dir("cpu0", [1, 2])
    self._create_cpu_dir("cpu1", [1, 2])

    target_frequencies = frequency_map.get_target_frequencies(self.platform)

    self.assertDictEqual(
        dict(target_frequencies), {
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu0/cpufreq"): 2,
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu1/cpufreq"): 1,
        })

  def test_validate_succeeds_without_wildcard(self):
    frequency_map = CPUFrequencyMap.parse({"cpu0": 2, "cpu1": 2, "cpu2": 2})
    # Use different orders to stress the parsing logic.
    self._create_cpu_dir("cpu0", [2, 1, 3])
    self._create_cpu_dir("cpu1", [1, 2, 3])
    self._create_cpu_dir("cpu2", [1, 3, 2])
    self._create_cpu_dir("cpu3", [42, 42, 42])
    self._create_cpu_dir("cpu4", [42, 42, 42])

    target_frequencies = frequency_map.get_target_frequencies(self.platform)

    self.assertDictEqual(
        dict(target_frequencies), {
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu0/cpufreq"): 2,
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu1/cpufreq"): 2,
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu2/cpufreq"): 2,
        })

  def test_validate_succeeds_with_wildcard(self):
    frequency_map = CPUFrequencyMap.parse({"*": 2})
    # Use different orders to stress the parsing logic.
    self._create_cpu_dir("cpu0", [2, 1, 3])
    self._create_cpu_dir("cpu1", [1, 2, 3])
    self._create_cpu_dir("cpu2", [1, 3, 2])

    target_frequencies = frequency_map.get_target_frequencies(self.platform)

    self.assertDictEqual(
        dict(target_frequencies), {
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu0/cpufreq"): 2,
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu1/cpufreq"): 2,
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu2/cpufreq"): 2,
        })

  def test_validate_succeeds_for_empty_config(self):
    self._create_cpu_dir("cpu0", [1, 2, 3])

    target_frequencies = CPUFrequencyMap.parse({}).get_target_frequencies(
        self.platform)

    self.assertFalse(target_frequencies)

  def test_validate_string_wildcard(self):
    frequency_map = CPUFrequencyMap.parse("max")
    self._create_cpu_dir("cpu0", [1, 2, 3])
    self._create_cpu_dir("cpu1", [1, 2, 3])

    target_frequencies = frequency_map.get_target_frequencies(self.platform)

    self.assertDictEqual(
        dict(target_frequencies), {
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu0/cpufreq"): 3,
            pth.AnyPosixPath("/sys/devices/system/cpu/cpu1/cpufreq"): 3,
        })

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
