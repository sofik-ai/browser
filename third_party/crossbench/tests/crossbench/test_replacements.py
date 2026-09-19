# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import unittest
from typing import Self

from typing_extensions import override

from crossbench.config import ConfigObject, ConfigParser
from crossbench.parse import ObjectParser
from crossbench.replacements import Replacements
from tests import test_helper


class CustomConfigObjectWithReplacements(ConfigObject):

  @classmethod
  @override
  def parse_str(cls, value: str) -> Self:
    raise ValueError("Cannot parse directly from strings")

  @classmethod
  @override
  def config_parser(cls) -> ConfigParser[Self]:
    parser = ConfigParser(cls)
    parser.add_argument("name", type=ObjectParser.non_empty_str, required=True)
    parser.add_argument("replacements", type=Replacements, required=True)
    return parser

  @property
  def name(self) -> str:
    return self._name

  def __init__(self, name: str, replacements: Replacements) -> None:
    self._name = replacements.apply(name)


class ConfigParserTestCase(unittest.TestCase):

  def test_one_replacement(self):
    config = CustomConfigObjectWithReplacements.parse({
        "name": "crossbench",
        "replacements": {
            "cross": "chrome"
        }
    })
    self.assertIsInstance(config, CustomConfigObjectWithReplacements)
    self.assertEqual(config.name, "chromebench")

  def test_multiple_replacements_overlapping(self):
    config = CustomConfigObjectWithReplacements.parse({
        "name": "crossbench",
        "replacements": {
            "cross": "chrome",
            "chrome": "android"
        }
    })
    self.assertIsInstance(config, CustomConfigObjectWithReplacements)
    self.assertEqual(config.name, "androidbench")

  def test_replacement_non_str(self):
    config = CustomConfigObjectWithReplacements.parse({
        "name": "crossbench",
        "replacements": {
            "cross": 1,
        }
    })
    self.assertIsInstance(config, CustomConfigObjectWithReplacements)
    self.assertEqual(config.name, "1bench")

  def test_replacement_key_non_str_raises(self):
    with self.assertRaisesRegex(ValueError, "replacements"):
      CustomConfigObjectWithReplacements.parse({
          "name": "crossbench",
          "replacements": {
              1: 1,
          }
      })


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
