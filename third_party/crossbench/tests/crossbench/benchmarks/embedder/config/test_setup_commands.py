# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
import pathlib
from typing import Any, Sequence

import hjson

from crossbench.benchmarks.embedder.config.setup_commands import \
    SetupCommandConfig, SetupCommandsConfig
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase


class SetupCommandsConfigTestCase(CrossbenchFakeFsTestCase):

  def test_parse_unknown_type(self):
    with self.assertRaises(argparse.ArgumentTypeError) as cm:
      SetupCommandsConfig.parse(self)
    self.assertIn("type", str(cm.exception))

  def test_parse_empty_command(self):
    config_data: dict[str, Any] = {"setup_commands": {"some command": []}}
    config = SetupCommandsConfig.parse(config_data)
    self.assertEqual(len(config.commands), 1)
    self.assertEqual(config.commands[0].label, "some command")
    self.assertEqual(len(config.commands[0].command), 0)

    config_data = {"setup_commands": {}}
    with self.assertRaises(argparse.ArgumentTypeError) as cm:
      SetupCommandsConfig.parse(config_data)
    self.assertIn("empty", str(cm.exception).lower())

  def test_example(self):
    config_data = {
        "setup_commands": {
            "echo hello": ["echo", "hello"],
            "list files": ["ls", "-l"],
        }
    }
    config = SetupCommandsConfig.parse(config_data)
    self.assert_example_commands(config.commands)
    # Loading the same config from a file should result in the same actions.
    file = pathlib.Path("setup_commands.config.hjson")
    assert not file.exists()
    with file.open("w", encoding="utf-8") as f:
      hjson.dump(config_data, f)
    file_config = SetupCommandsConfig.parse(str(file))
    self.assertEqual(config, file_config)
    commands = file_config.commands
    self.assert_example_commands(commands)

  def assert_example_commands(self, commands: Sequence[SetupCommandConfig]):
    self.assertEqual(len(commands), 2)
    command1 = commands[0]
    self.assertEqual(command1.label, "echo hello")
    self.assertTupleEqual(command1.command, ("echo", "hello"))
    command2 = commands[1]
    self.assertEqual(command2.label, "list files")
    self.assertTupleEqual(command2.command, ("ls", "-l"))

  def test_no_commands(self):
    with self.assertRaises(argparse.ArgumentTypeError):
      SetupCommandsConfig.parse_dict({})
    with self.assertRaises(argparse.ArgumentTypeError):
      SetupCommandsConfig.parse_dict({"setup_commands": {}})

  def test_invalid_command(self):
    invalid_commands: list[Any] = [None, "", {}, "invalid string", 12]
    for invalid_command in invalid_commands:
      config_dict: dict[str, Any] = {
          "setup_commands": {
              "name": invalid_command
          }
      }
      with self.subTest(invalid_command=invalid_command):
        with self.assertRaises(argparse.ArgumentTypeError):
          SetupCommandsConfig.parse_dict(config_dict)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
