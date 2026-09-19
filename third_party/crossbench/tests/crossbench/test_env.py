# Copyright 2022 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import datetime as dt
import pathlib
import unittest
from typing import Any
from unittest import mock

from typing_extensions import override

from crossbench import plt
from crossbench.browsers.settings import Settings
from crossbench.env.base import ValidationError
from crossbench.env.runner_env import EnvConfig, RunnerEnv, ValidationMode
from crossbench.helper import url_helper
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase
from tests.crossbench.mock_browser import MockSafari
from tests.crossbench.mock_helper import LinuxMockPlatform, \
    MacOsMockPlatform, MockPlatform, RemoteLinuxMockPlatform


class HostEnvironmentTestCase(CrossbenchFakeFsTestCase):

  @override
  def setUp(self):
    super().setUp()
    self.platform = self.setup_platform()
    self.platform.use_fs = True
    self.out_dir = pathlib.Path(
        "crossbench/results/current_benchmark_run_results")
    self.fs.create_dir(self.out_dir)
    self.mock_runner = mock.Mock(
        platform=plt.PLATFORM,
        repetitions=1,
        probes=[],
        browsers=[],
        out_dir=self.out_dir)

  def setup_platform(self):
    return MockPlatform()

  def patch_property(self, target: Any, name: str, **kwargs):
    new_callable = kwargs.pop("new_callable", mock.PropertyMock)
    return mock.patch.object(
        type(target), name, new_callable=new_callable, **kwargs)

  def create_env(self, *args, **kwargs) -> RunnerEnv:
    return RunnerEnv(self.platform, self.mock_runner.out_dir,
                     self.mock_runner.browsers, self.mock_runner.probes,
                     self.mock_runner.repetitions, *args, **kwargs)

  def test_instantiate(self):
    env = self.create_env()
    self.assertEqual(env.platform, self.platform)

    config = EnvConfig()
    env = self.create_env(config)
    self.assertSequenceEqual(env.browsers, self.mock_runner.browsers)
    self.assertEqual(env.config, config)

  def test_warn_mode_skip(self):
    config = EnvConfig()
    env = self.create_env(config, validation_mode=ValidationMode.SKIP)
    env.handle_warning("foo")

  def test_warn_mode_fail(self):
    config = EnvConfig()
    env = self.create_env(config, validation_mode=ValidationMode.THROW)
    with self.assertRaises(ValidationError) as cm:
      env.handle_warning("custom env check warning")
    self.assertIn("custom env check warning", str(cm.exception))

  def test_warn_mode_prompt(self):
    config = EnvConfig()
    env = self.create_env(config, validation_mode=ValidationMode.PROMPT)
    with mock.patch("builtins.input", return_value="Y") as cm:
      env.handle_warning("custom env check warning")
    cm.assert_called_once()
    self.assertIn("custom env check warning", cm.call_args[0][0])
    with mock.patch("builtins.input", return_value="n") as cm:
      with self.assertRaises(ValidationError):
        env.handle_warning("custom env check warning")
    cm.assert_called_once()
    self.assertIn("custom env check warning", cm.call_args[0][0])

  def test_warn_mode_warn(self):
    config = EnvConfig()
    env = self.create_env(config, validation_mode=ValidationMode.WARN)
    with mock.patch("logging.warning") as cm:
      env.handle_warning("custom env check warning")
    cm.assert_called_once()
    self.assertIn("custom env check warning", cm.call_args[0][0])

  def test_validate_skip(self):
    env = self.create_env(EnvConfig(), validation_mode=ValidationMode.SKIP)
    env.validate()

  def test_validate_warn(self):
    env = self.create_env(EnvConfig(), validation_mode=ValidationMode.WARN)
    with mock.patch("logging.warning") as cm:
      env.validate()
    cm.assert_not_called()
    self.assertFalse(self.platform.sh_cmds)

  def test_validate_warn_no_probes(self):
    env = self.create_env(
        EnvConfig(require_probes=True), validation_mode=ValidationMode.WARN)
    with mock.patch("logging.warning") as cm:
      env.validate()
    cm.assert_called_once()
    self.assertFalse(self.platform.sh_cmds)

  def test_failing_probe_validation(self):

    def mock_validate_env(env):
      env.handle_warning("invalid mock probe")

    mock_probe = mock.Mock()
    mock_probe.configure_mock(NAME="mock_probe")
    mock_probe.validate_env.side_effect = mock_validate_env
    self.mock_runner.probes = [mock_probe]
    env = self.create_env(validation_mode=ValidationMode.THROW)

    with self.assertRaises(ValidationError) as cm:
      env.validate()
    self.assertIn("invalid mock probe", str(cm.exception))

    mock_probe.validate_env.assert_called_once()

  def test_request_battery_power_on(self):
    with self.patch_property(self.platform, "is_battery_powered") as mocked:
      env = self.create_env(
          EnvConfig(power_use_battery=True),
          validation_mode=ValidationMode.THROW)
      mocked.return_value = True
      env.validate()

      mocked.return_value = False
      with self.assertRaises(Exception) as cm:
        env.validate()
      self.assertIn("battery", str(cm.exception).lower())

  def test_request_battery_power_off(self):
    env = self.create_env(
        EnvConfig(power_use_battery=False),
        validation_mode=ValidationMode.THROW)
    with self.patch_property(self.platform,
                             "is_battery_powered") as is_battery_powered:
      is_battery_powered.return_value = True
      with self.assertRaises(ValidationError) as cm:
        env.validate()
      self.assertIn("battery", str(cm.exception).lower())
      self.assertEqual(is_battery_powered.call_count, 1)

      is_battery_powered.return_value = False
      env.validate()
      self.assertEqual(is_battery_powered.call_count, 2)

  def test_mock_request_battery_power_off(self):
    with self.patch_property(self.platform,
                             "is_battery_powered") as is_battery_powered:
      is_battery_powered.return_value = False
      self.assertFalse(self.platform.is_battery_powered)
      is_battery_powered.return_value = True
      self.assertTrue(self.platform.is_battery_powered)

  def test_request_battery_power_off_conflicting_probe(self):
    with self.patch_property(self.platform,
                             "is_battery_powered") as is_battery_powered:
      is_battery_powered.return_value = False

      mock_probe = mock.Mock()
      mock_probe.configure_mock(BATTERY_ONLY=True, name="mock_probe")
      self.mock_runner.probes = [mock_probe]
      env = self.create_env(
          EnvConfig(power_use_battery=False),
          validation_mode=ValidationMode.THROW)

      with self.assertRaises(ValidationError) as cm:
        env.validate()
      message = str(cm.exception).lower()
      self.assertIn("mock_probe", message)
      self.assertIn("battery", message)

      mock_probe.BATTERY_ONLY = False
      env.validate()

  def test_request_is_headless_default(self):
    env = self.create_env(
        EnvConfig(browser_is_headless=EnvConfig.IGNORE),
        validation_mode=ValidationMode.THROW)
    mock_browser = mock.Mock(platform=self.platform)
    self.mock_runner.browsers = [mock_browser]

    mock_browser.viewport.is_headless = False
    env.validate()

    mock_browser.viewport.is_headless = True
    env.validate()

  def test_request_is_headless_true(self):
    mock_browser = mock.Mock(
        platform=self.platform, path=pathlib.Path("bin/browser_a"))
    self.mock_runner.browsers = [mock_browser]
    env = self.create_env(
        EnvConfig(browser_is_headless=True),
        validation_mode=ValidationMode.THROW)

    with self.patch_property(self.platform, "has_display") as has_display:
      has_display.return_value = True
      mock_browser.viewport.is_headless = False
      with self.assertRaisesRegex(ValidationError, "is_headless"):
        env.validate()
      mock_browser.viewport.is_headless = True
      with self.assertRaisesRegex(ValidationError, "is_headless"):
        env.validate()

      has_display.return_value = False
      mock_browser.viewport.is_headless = False
      with self.assertRaisesRegex(ValidationError, "is_headless"):
        env.validate()
      mock_browser.viewport.is_headless = True
      env.validate()

  def test_request_is_headless_false(self):
    self.platform = LinuxMockPlatform()
    self.platform.use_fs = True
    mock_browser = mock.Mock(
        platform=self.platform, path=pathlib.Path("bin/browser_a"))
    self.mock_runner.browsers = [mock_browser]
    env = self.create_env(
        EnvConfig(browser_is_headless=False),
        validation_mode=ValidationMode.THROW)
    with self.patch_property(self.platform, "has_display") as has_display:
      has_display.return_value = True
      self.assertTrue(self.platform.has_display)
      mock_browser.viewport.is_headless = True
      with self.assertRaisesRegex(ValidationError, " browser "):
        env.validate()
      mock_browser.viewport.is_headless = False
      env.validate()

      has_display.return_value = False
      self.assertFalse(self.platform.has_display)
      mock_browser.viewport.is_headless = True
      with self.assertRaisesRegex(ValidationError, "browser_is_headless"):
        env.validate()
      mock_browser.viewport.is_headless = False
      with self.assertRaisesRegex(ValidationError, "browser_is_headless"):
        env.validate()

  def test_results_dir_single(self):
    env = self.create_env()
    with mock.patch("logging.warning") as cm:
      env.validate()
    cm.assert_not_called()

  def test_results_dir_non_existent(self):
    self.mock_runner.out_dir = pathlib.Path("does/not/exist")
    env = self.create_env()
    with mock.patch("logging.warning") as cm:
      env.validate()
    cm.assert_not_called()

  def test_results_dir_many(self):
    # Create fake test result dirs:
    for i in range(30):
      (self.out_dir.parent / str(i)).mkdir()
    env = self.create_env()
    with mock.patch("logging.warning") as cm:
      env.validate()
    cm.assert_called_once()

  def test_results_dir_too_many(self):
    # Create fake test result dirs:
    for i in range(100):
      (self.out_dir.parent / str(i)).mkdir()
    env = self.create_env()
    with mock.patch("logging.error") as cm:
      env.validate()
    cm.assert_called_once()

  def test_check_installed_missing(self):

    def which_none(_):
      return None

    with mock.patch.object(
        self.platform, "which", side_effect=which_none) as mock_which:
      env = self.create_env()
      with self.assertRaises(ValidationError) as cm:
        env.check_installed(["custom_binary"])
      self.assertIn("custom_binary", str(cm.exception))
      with self.assertRaises(ValidationError) as cm:
        env.check_installed(["custom_binary_a", "custom_binary_b"])
      self.assertIn("custom_binary_a", str(cm.exception))
      self.assertIn("custom_binary_b", str(cm.exception))
      mock_which.assert_called()

  def test_check_installed_partially_missing(self):

    def which_custom(binary):
      if binary == "custom_binary_b":
        return "/bin/custom_binary_b"
      return None

    with mock.patch.object(
        self.platform, "which", side_effect=which_custom) as mock_which:
      env = self.create_env()
      env.check_installed(["custom_binary_b"])
      with self.assertRaises(ValidationError) as cm:
        env.check_installed(["custom_binary_a", "custom_binary_b"])
      self.assertIn("custom_binary_a", str(cm.exception))
      self.assertNotIn("custom_binary_b", str(cm.exception))
      mock_which.assert_called()

  def test_file_access_outdir(self):
    self._check_file_access()

  def _check_file_access(self):
    out_dir = self.mock_runner.out_dir
    self.assertTrue(out_dir.exists())
    env = self.create_env()
    env.validate()
    with mock.patch.object(
        self.platform, "mkdir", side_effect=ValueError("No File Access")):
      env = self.create_env()
      with self.assertRaisesRegex(ValidationError, str(out_dir.parent)):
        env.validate()
    with mock.patch.object(self.platform, "read_text", side_effect=""):
      env = self.create_env()
      with self.assertRaisesRegex(ValidationError, str(out_dir.parent)):
        env.validate()

  def test_macos_file_access_outdir(self):
    self.platform = MacOsMockPlatform()
    self.platform.use_fs = True
    self._check_file_access()

  def test_macos_safari_cache_dir(self):
    self.platform = MacOsMockPlatform()
    self.platform.use_fs = True
    MockSafari.setup_fs(self.fs, self.platform)

    mock_browser = MockSafari("sf", settings=Settings(platform=self.platform))
    self.mock_runner.browsers = [mock_browser]

    with mock.patch.object(self.platform, "read_text", side_effect=""):
      env = self.create_env()
      with self.assertRaisesRegex(ValidationError, "Safari"):
        env.validate()
    # success otherwise
    env.validate()

  def test_validate_url_skip(self):
    env = self.create_env(validation_mode=ValidationMode.SKIP)
    self.assertTrue(env.validate_url("something://google....com"))

  def test_validate_url_file(self):
    env = self.create_env()
    self.assertFalse(env.validate_url("file://some/test/"))
    with self.platform.TemporaryDirectory() as tmp_dir:
      self.assertTrue(env.validate_url(f"file:///{tmp_dir}"))

  def test_validate_url_unknown_protocol(self):
    env = self.create_env()
    self.assertFalse(env.validate_url("ftp://google.com"))

  def test_validate_url_localhost_remote(self):
    self.mock_platform_default_tmp_dir(RemoteLinuxMockPlatform)
    remote_platform = RemoteLinuxMockPlatform(self.platform)
    env = self.create_env()
    with mock.patch.object(url_helper, "get") as mock_get:
      self.assertTrue(
          env.validate_url("http://localhost:8000", remote_platform))
      self.assertTrue(
          env.validate_url("http://127.0.0.1:8000", remote_platform))
      mock_get.assert_not_called()

  def test_validate_url(self):
    with mock.patch.object(url_helper, "get") as mock_get:
      env = self.create_env()
      self.assertTrue(env.validate_url("http://google.com"))
      mock_get.assert_not_called()
    with mock.patch.object(url_helper, "get") as mock_get:
      env = self.create_env(validation_mode=ValidationMode.PROMPT)
      self.assertTrue(env.validate_url("http://google.com"))
      mock_get.assert_called_once()
    with mock.patch.object(
        url_helper, "get", side_effect=url_helper.HTTPError) as mock_get:
      env = self.create_env(validation_mode=ValidationMode.PROMPT)
      self.assertFalse(env.validate_url("http://google.com"))
      mock_get.assert_called_once()

  def test_cpu_max_usage_percent(self):
    env = self.create_env(
        EnvConfig(cpu_max_usage_percent=50),
        validation_mode=ValidationMode.THROW)
    with mock.patch.object(
        self.platform, "cpu_usage", return_value=0.4) as mock_cpu_usage:
      env.validate()
      mock_cpu_usage.assert_called_once()
    with mock.patch.object(
        self.platform, "cpu_usage", return_value=0.6) as mock_cpu_usage:
      with self.assertRaises(ValidationError):
        env.validate()
      mock_cpu_usage.assert_called_once()

  def test_cpu_min_relative_speed(self):
    env = self.create_env(
        EnvConfig(cpu_min_relative_speed=0.8),
        validation_mode=ValidationMode.THROW)
    with mock.patch.object(
        self.platform, "get_relative_cpu_speed",
        return_value=0.9) as mock_relative_cpu_speed:
      env.validate()
      mock_relative_cpu_speed.assert_called_once()
    with mock.patch.object(
        self.platform, "get_relative_cpu_speed",
        return_value=0.6) as mock_relative_cpu_speed:
      with self.assertRaises(ValidationError):
        env.validate()
      mock_relative_cpu_speed.assert_called_once()

  def test_disk_usage(self):
    env = self.create_env(
        EnvConfig(disk_min_free_space_gib=1.1),
        validation_mode=ValidationMode.THROW)
    gib = 1024 * 1024 * 1024
    with mock.patch.object(
        self.platform, "disk_usage",
        return_value=mock.Mock(free=0.7 * gib)) as mock_disk_usage:
      with self.assertRaises(ValidationError):
        env.validate()
      mock_disk_usage.assert_called_once()
    with mock.patch.object(
        self.platform, "disk_usage",
        return_value=mock.Mock(free=1.7 * gib)) as mock_disk_usage:
      env.validate()
      mock_disk_usage.assert_called_once()

  def test_system_min_uptime(self):
    env = self.create_env(
        EnvConfig(system_min_uptime=dt.timedelta(minutes=10)),
        validation_mode=ValidationMode.THROW)
    with mock.patch.object(
        self.platform, "uptime",
        return_value=dt.timedelta(minutes=11)) as mock_uptime:
      env.validate()
      mock_uptime.assert_called_once()
    with mock.patch.object(
        self.platform, "uptime",
        return_value=dt.timedelta(minutes=1)) as mock_uptime:
      with self.assertRaises(ValidationError):
        env.validate()
      mock_uptime.assert_called_once()


class ValidationModeTestCase(unittest.TestCase):

  def test_construct(self):
    self.assertIs(ValidationMode("throw"), ValidationMode.THROW)
    self.assertIs(ValidationMode("THROW"), ValidationMode.THROW)
    self.assertIs(ValidationMode("prompt"), ValidationMode.PROMPT)
    self.assertIs(ValidationMode("PROMPT"), ValidationMode.PROMPT)
    self.assertIs(ValidationMode("warn"), ValidationMode.WARN)
    self.assertIs(ValidationMode("WARN"), ValidationMode.WARN)
    self.assertIs(ValidationMode("skip"), ValidationMode.SKIP)
    self.assertIs(ValidationMode("SKIP"), ValidationMode.SKIP)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
