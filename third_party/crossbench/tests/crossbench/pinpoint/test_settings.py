# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import json
import pathlib
from typing import Any
from unittest import mock

from crossbench.pinpoint.settings import Settings
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase


class SettingsTestCase(CrossbenchFakeFsTestCase):

  def setUp(self):
    super().setUp()
    self.config_dir = "/config"
    self.fs.create_dir(self.config_dir)
    self.enterContext(
        mock.patch(
            "platformdirs.user_config_dir", return_value=self.config_dir))
    self.enterContext(
        mock.patch("crossbench.pinpoint.settings.LocalPath", pathlib.Path))

  def tearDown(self):
    Settings._instance = None

  def assert_settings_file_includes(self, key: str, value: Any) -> None:
    with Settings.path().open("r") as f:
      actual_content = f.read()
    actual_content_dict = json.loads(actual_content)
    self.assertEqual(actual_content_dict[key], value)

  def test_default_values(self):
    settings = Settings()
    self.assertIsNone(settings.user_id)
    self.assertIsNone(settings.collect_metrics)

  def test_load_no_file(self):
    settings = Settings()
    self.assertIsNone(settings.user_id)
    self.assertIsNone(settings.collect_metrics)

  def test_save_and_load(self):
    settings = Settings()
    settings.user_id = "test-user"
    settings.collect_metrics = True
    settings.save()

    self.assertTrue(settings.path().exists())
    self.assert_settings_file_includes("user_id", "test-user")
    self.assert_settings_file_includes("collect_metrics", True)

  def test_load_user_id(self):
    with Settings.path().open("w") as f:
      f.write(json.dumps({"user_id": "test-user"}))
    self.assertEqual(Settings().user_id, "test-user")

  def test_load_collect_metrics(self):
    with Settings.path().open("w") as f:
      f.write(json.dumps({"collect_metrics": True}))
    self.assertTrue(Settings().collect_metrics)

  def test_save_updates_existing(self):
    settings = Settings()
    settings.user_id = "test-user"
    settings.collect_metrics = True
    settings.save()

    settings.user_id = "user2"
    settings.save()

    self.assertTrue(settings.path().exists())
    self.assert_settings_file_includes("user_id", "user2")

  def test_save_does_nothing_when_not_dirty(self):
    settings = Settings()
    settings.save()
    self.assertFalse(settings.path().exists())


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
