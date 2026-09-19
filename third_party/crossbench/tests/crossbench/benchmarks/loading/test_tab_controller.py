# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
import unittest

from crossbench.benchmarks.loading.tab_controller import \
    ForeverTabController, RepeatTabController, SingleTabController, \
    TabController
from tests import test_helper


class TabControllerTestCase(unittest.TestCase):

  def test_parse_invalid(self):
    for invalid in ["sing", "mult", "mlt", "x5"]:
      with self.subTest(pattern=invalid):
        with self.assertRaises((argparse.ArgumentTypeError, ValueError)):
          TabController.parse(invalid)

  def test_parse_repeat(self):
    tab = TabController.parse("3")
    self.assertIsInstance(tab, RepeatTabController)
    assert isinstance(tab, RepeatTabController)
    self.assertEqual(tab.count, 3)
    self.assertEqual(len(list(tab)), 3)

  def test_parse_single(self):
    tab = TabController.parse("single")
    self.assertIsInstance(tab, SingleTabController)
    self.assertEqual(len(list(tab)), 1)

  def test_parse_inf(self):
    tab = TabController.parse("inf")
    self.assertIsInstance(tab, ForeverTabController)
    tab = TabController.parse("infinity")
    self.assertIsInstance(tab, ForeverTabController)

  def test_repeat(self):
    iterations = sum(1 for _ in TabController.repeat(1))
    self.assertEqual(iterations, 1)
    iterations = sum(1 for _ in TabController.repeat(10))
    self.assertEqual(iterations, 10)

  def test_forever(self):
    count = 0
    for _ in TabController.forever():
      count += 1
      if count > 100:
        break
    self.assertEqual(count, 101)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
