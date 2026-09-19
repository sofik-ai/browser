# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import unittest

from crossbench.flags.base import Flags, FrozenFlagsError
from tests import test_helper


class TestFlags(unittest.TestCase):

  CLASS = Flags

  def test_construct(self):
    flags = self.CLASS()
    self.assertEqual(len(flags), 0)
    self.assertNotIn("foo", flags)

  def test_construct_dict(self):
    flags = self.CLASS({"--foo": "v1", "--bar": "v2"})
    self.assertIn("--foo", flags)
    self.assertIn("--bar", flags)
    self.assertEqual(flags["--foo"], "v1")
    self.assertEqual(flags["--bar"], "v2")

  def test_construct_list(self):
    flags = self.CLASS(("--foo", "--bar"))
    self.assertIn("--foo", flags)
    self.assertIn("--bar", flags)
    self.assertIsNone(flags["--foo"])
    self.assertIsNone(flags["--bar"])
    with self.assertRaises(ValueError):
      self.CLASS(("--foo=v1", "--bar=v2"))
    flags = self.CLASS((("--foo", "v3"), "--bar"))
    self.assertEqual(flags["--foo"], "v3")
    self.assertIsNone(flags["--bar"])

  def test_construct_flags(self):
    original_flags = self.CLASS({"--foo": "v1", "--bar": "v2"})
    flags = self.CLASS(original_flags)
    self.assertIn("--foo", flags)
    self.assertIn("--bar", flags)
    self.assertEqual(flags["--foo"], "v1")
    self.assertEqual(flags["--bar"], "v2")

  def test_clear(self):
    flags = self.CLASS({"--foo": "v1", "--bar": "v2"})
    self.assertTrue(flags)
    flags.clear()
    self.assertFalse(flags)

  def test_set(self):
    flags = self.CLASS()
    flags["--foo"] = "v1"
    with self.assertRaises(ValueError):
      flags["--foo"] = "v2"
    # setting the same value is ok
    flags["--foo"] = "v1"
    self.assertEqual(flags["--foo"], "v1")
    flags.set("--bar")
    self.assertIn("--foo", flags)
    self.assertIn("--bar", flags)
    self.assertIsNone(flags["--bar"])
    with self.assertRaises(ValueError):
      flags.set("--bar", "v3")
    flags.set("--bar", "v4", should_override=True)
    self.assertEqual(flags["--foo"], "v1")
    self.assertEqual(flags["--bar"], "v4")

  def test_set_invalid(self):
    flags = self.CLASS()
    with self.assertRaises(TypeError) as cm:
      flags["--foo"] = 123
    self.assertIn("123", str(cm.exception))
    with self.assertRaises(ValueError) as cm:
      flags["foo"] = 123
    self.assertIn("-", str(cm.exception))

  def test_set_invalid_flag_name(self):
    flags = self.CLASS()
    for invalid in ("- -foo", "--f oo", "", "-", "--", "--foo\n", "--\nfoo",
                    "--foo,"):
      with self.subTest(invalid_flag=invalid):
        with self.assertRaises(ValueError):
          flags.set(invalid)
        self.assertFalse(invalid in flags)

  def test_get_list(self):
    flags = self.CLASS({"--foo": "v1", "--bar": None})
    self.assertEqual(list(flags), ["--foo=v1", "--bar"])

  def test_copy(self):
    flags = self.CLASS({"--foo": "v1", "--bar": None})
    copy = flags.copy()
    self.assertEqual(list(flags), list(copy))
    self.assertEqual(str(flags), str(copy))
    self.assertTrue(copy)

  def test_copy_frozen(self):
    flags = self.CLASS({"--foo": "v1", "--bar": None})
    flags.freeze()
    self.assertTrue(flags.is_frozen)
    copy = flags.copy()
    with self.assertRaises(FrozenFlagsError):
      flags["--custom"] = "123"
    self.assertNotIn("--custom", flags)
    copy["--custom"] = "123"
    self.assertEqual(copy["--custom"], "123")
    copy.freeze()
    with self.assertRaises(FrozenFlagsError):
      copy["--custom-other"] = "123"

  def test_update(self):
    flags = self.CLASS({"--foo": "v1", "--bar": None})
    with self.assertRaises(ValueError):
      flags.update({"--bar": "v2"})
    self.assertEqual(flags["--foo"], "v1")
    self.assertIsNone(flags["--bar"])
    flags.update({"--bar": "v2"}, should_override=True)
    self.assertEqual(flags["--foo"], "v1")
    self.assertEqual(flags["--bar"], "v2")
    self.assertTrue(flags)

  def test_str_basic(self):
    flags = self.CLASS({"--foo": None})
    self.assertEqual(str(flags), "--foo")
    flags = self.CLASS({"--foo": "bar"})
    self.assertEqual(str(flags), "--foo=bar")

  def test_str_multiple(self):
    flags = self.CLASS({
        "--flag1": "value1",
        "--flag2": None,
        "--flag3": "value3"
    })
    self.assertEqual(str(flags), "--flag1=value1 --flag2 --flag3=value3")

  def test_merge_dict(self):
    flags = self.CLASS({"--foo": "v1", "--bar": None})
    flags.merge({"--other": "v3"})
    self.assertEqual(flags["--foo"], "v1")
    self.assertIsNone(flags["--bar"])
    self.assertEqual(flags["--other"], "v3")
    self.assertEqual(len(flags), 3)

  def test_merge_conflict(self):
    flags = self.CLASS({"--foo": "v1", "--bar": None})
    with self.assertRaises(ValueError):
      flags.merge({"--bar": "v2"})
    self.assertEqual(flags["--foo"], "v1")
    self.assertIsNone(flags["--bar"])
    self.assertEqual(len(flags), 2)

  def test_merge_empty(self):
    flags = self.CLASS({"--foo": "v1", "--bar": None})
    flags.merge(self.CLASS())
    self.assertEqual(flags["--foo"], "v1")
    self.assertIsNone(flags["--bar"])
    self.assertEqual(len(flags), 2)
    empty = self.CLASS()
    empty.merge(self.CLASS())
    self.assertFalse(empty)

  def test_parse_single(self):
    flags = self.CLASS.parse("--foo")
    self.assertEqual(len(flags), 1)
    self.assertTrue(flags)
    self.assertEqual(flags["--foo"], None)
    self.assertEqual(str(flags), "--foo")

    flags = self.CLASS.parse("--foo=123")
    self.assertEqual(len(flags), 1)
    self.assertTrue(flags)
    self.assertEqual(flags["--foo"], "123")
    self.assertEqual(str(flags), "--foo=123")

    flags = self.CLASS.parse("--foo=--bar123")
    self.assertEqual(len(flags), 1)
    self.assertTrue(flags)
    self.assertEqual(flags["--foo"], "--bar123")
    self.assertEqual(str(flags), "--foo=--bar123")

  def test_parse_nested(self):
    flags = self.CLASS.parse("--foo=--bar=123")
    self.assertEqual(len(flags), 1)
    self.assertTrue(flags)
    self.assertEqual(flags["--foo"], "--bar=123")
    self.assertEqual(str(flags), "--foo=--bar=123")

  def test_parse_multiple(self):
    flags = self.CLASS.parse("--foo --bar")
    self.assertEqual(len(flags), 2)
    self.assertTrue(flags)
    self.assertEqual(flags["--foo"], None)
    self.assertEqual(flags["--bar"], None)
    flags = self.CLASS.parse("--foo --bar=1")
    self.assertEqual(len(flags), 2)
    self.assertTrue(flags)
    self.assertEqual(flags["--foo"], None)
    self.assertEqual(flags["--bar"], "1")
    flags = self.CLASS.parse("--foo=1 --bar=2")
    self.assertEqual(len(flags), 2)
    self.assertTrue(flags)
    self.assertEqual(flags["--foo"], "1")
    self.assertEqual(flags["--bar"], "2")
    flags = self.CLASS.parse("--foo='1' --bar='2'")
    self.assertEqual(len(flags), 2)
    self.assertTrue(flags)
    self.assertEqual(flags["--foo"], "1")
    self.assertEqual(flags["--bar"], "2")

  def test_hashable(self):
    flags = self.CLASS.parse("--foo")
    flags["--bar"] = "10"
    test_set = {flags}
    self.assertIn(flags, test_set)
    self.assertIn(self.CLASS.parse("--foo --bar=10"), test_set)
    self.assertNotIn(self.CLASS.parse("--foo --bar=999"), test_set)
    # post-hash modification are not allowed anymore:
    with self.assertRaises(FrozenFlagsError) as cm:
      flags["--bar"] = "0"
    self.assertIn("frozen", str(cm.exception))

  def test_iter(self):
    flags = self.CLASS.parse("--foo --bar=1")
    self.assertListEqual(list(flags), ["--foo", "--bar=1"])
    self.assertListEqual([*flags], ["--foo", "--bar=1"])

  def test_bool_basic(self):
    self.assertFalse(self.CLASS())
    self.assertTrue(self.CLASS.parse("--foo --bar"))

  def test_filtered(self):
    self.assertFalse(self.CLASS().filtered([]))
    self.assertFalse(self.CLASS.parse("--foo --bar").filtered([]))
    self.assertEqual(
        self.CLASS.parse("--foo --bar").filtered(["--foo"]),
        self.CLASS.parse("--foo"))
    self.assertEqual(
        self.CLASS.parse("--foo --bar").filtered(["--bar"]),
        self.CLASS.parse("--bar"))
    self.assertEqual(
        self.CLASS.parse("--foo --bar=1").filtered(["--bar"]),
        self.CLASS.parse("--bar=1"))
    self.assertEqual(
        self.CLASS.parse("--foo --bar").filtered(["--foo", "--bar"]),
        self.CLASS.parse("--foo --bar"))
    self.assertEqual(
        self.CLASS.parse("--foo --bar").filtered(["--bar", "--foo"]),
        self.CLASS.parse("--foo --bar"))
    self.assertEqual(
        self.CLASS.parse("--foo=0 --bar").filtered(["--bar", "--foo"]),
        self.CLASS.parse("--foo=0 --bar"))

  def test_parse_with_value(self):
    self.assertEqual(
        self.CLASS.parse("--foo=bar"), self.CLASS({"--foo": "bar"}))
    self.assertEqual(
        self.CLASS.parse("--foo='bar'"), self.CLASS({"--foo": "bar"}))
    self.assertEqual(
        self.CLASS.parse('--foo="bar"'), self.CLASS({"--foo": "bar"}))
    self.assertEqual(
        self.CLASS.parse("--foo=123"), self.CLASS({"--foo": "123"}))
    self.assertEqual(
        self.CLASS.parse("--foo='123'"), self.CLASS({"--foo": "123"}))
    self.assertEqual(
        self.CLASS.parse('--foo="123"'), self.CLASS({"--foo": "123"}))

  def test_parse_with_flag_value(self):
    self.assertEqual(
        self.CLASS.parse("--foo=-bar"), self.CLASS({"--foo": "-bar"}))
    self.assertEqual(
        self.CLASS.parse("--foo='-bar'"), self.CLASS({"--foo": "-bar"}))
    self.assertEqual(
        self.CLASS.parse('--foo="-bar"'), self.CLASS({"--foo": "-bar"}))
    self.assertEqual(
        self.CLASS.parse("--foo=--other"), self.CLASS({"--foo": "--other"}))
    self.assertEqual(
        self.CLASS.parse("--foo='--other'"), self.CLASS({"--foo": "--other"}))
    self.assertEqual(
        self.CLASS.parse('--foo="--other"'), self.CLASS({"--foo": "--other"}))
    self.assertEqual(
        self.CLASS.parse("--foo=--other=1"), self.CLASS({"--foo": "--other=1"}))
    self.assertEqual(
        self.CLASS.parse("--foo='--other=1'"),
        self.CLASS({"--foo": "--other=1"}))
    self.assertEqual(
        self.CLASS.parse('--foo="--other=1"'),
        self.CLASS({"--foo": "--other=1"}))

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
