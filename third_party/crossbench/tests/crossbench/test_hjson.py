# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import unittest

from crossbench import hjson as cb_hjson
from tests import test_helper


class HjsonTestCase(unittest.TestCase):

  def test_different_keys_success(self):

    parsed = cb_hjson.loads_unique_keys("""
    {
      key: 1
      key2: 2
    }
    """)

    self.assertEqual(parsed["key"], 1)
    self.assertEqual(parsed["key2"], 2)

  def test_duplicate_keys_throws(self):
    with self.assertRaisesRegex(ValueError, "Duplicate"):
      cb_hjson.loads_unique_keys("""
    {
      key: 1
      key: 2
    }
    """)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
