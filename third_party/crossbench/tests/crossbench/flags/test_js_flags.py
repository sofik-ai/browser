# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

from crossbench.flags.js_flags import JSFlags
from crossbench.flags.known_chrome_flags import KNOWN_CHROME_FLAGS
from crossbench.flags.known_js_flags import KNOWN_JS_FLAGS
from tests import test_helper
from tests.crossbench.flags.test_flags import TestFlags


class TestJSFlags(TestFlags):
  CLASS = JSFlags

  def test_invalid_js_flags(self):
    flags = self.CLASS()
    with self.assertRaises(ValueError) as cm:
      flags.set("-foo")
    self.assertIn("'-foo'", str(cm.exception))
    with self.assertRaises(ValueError) as cm:
      flags.set("--foo,--bar")
    self.assertIn("'--foo,--bar'", str(cm.exception))
    with self.assertRaises(ValueError) as cm:
      flags.set("--v8-log", "foo,bar")
    self.assertIn("comma", str(cm.exception).lower())
    self.assertIn("--v8-log", str(cm.exception))
    self.assertIn("foo,bar", str(cm.exception))
    with self.assertRaises(ValueError) as cm:
      flags["--foo"] = "a b c d"
    self.assertIn("whitespace", str(cm.exception).lower())
    self.assertIn("--foo", str(cm.exception))
    self.assertIn("a b c d", str(cm.exception))

  def test_conflicting_flags(self):
    with self.assertRaises(ValueError):
      flags = self.CLASS(("--foo", "--no-foo"))
    with self.assertRaises(ValueError):
      flags = self.CLASS(("--foo", "--nofoo"))
    flags = self.CLASS(("--foo", "--no-bar"))
    self.assertIsNone(flags["--foo"])
    self.assertIsNone(flags["--no-bar"])
    self.assertIn("--foo", flags)
    self.assertNotIn("--no-foo", flags)
    self.assertNotIn("--bar", flags)
    self.assertIn("--no-bar", flags)

  def test_conflicting_override(self):
    flags = self.CLASS(("--foo", "--no-bar"))
    with self.assertRaises(ValueError):
      flags.set("--no-foo")
    with self.assertRaises(ValueError):
      flags.set("--nofoo")
    flags.set("--nobar")
    with self.assertRaises(ValueError):
      flags.set("--bar")
    with self.assertRaises(ValueError):
      flags.set("--foo", "v2")
    self.assertIsNone(flags["--foo"])
    self.assertIsNone(flags["--no-bar"])

    flags.set("--no-foo", should_override=True)
    self.assertNotIn("--foo", flags)
    self.assertIn("--no-foo", flags)
    self.assertNotIn("--bar", flags)
    self.assertIn("--no-bar", flags)

    flags.set("--bar", should_override=True)
    self.assertNotIn("--foo", flags)
    self.assertIn("--no-foo", flags)
    self.assertIn("--bar", flags)
    self.assertNotIn("--no-bar", flags)

  def test_str_multiple(self):
    flags = self.CLASS({
        "--flag-a": "value1",
        "--flag-b": None,
        "--flag-c": "value3"
    })
    self.assertEqual(str(flags), "--flag-a=value1,--flag-b,--flag-c=value3")

  def test_initial_data_empty(self):
    flags = self.CLASS()
    flags_copy = self.CLASS(flags)
    self.assertEqual(str(flags), str(flags_copy))
    flags_copy = self.CLASS()
    flags_copy.update(flags)
    self.assertEqual(str(flags), str(flags_copy))

  def test_initial_data(self):
    flags = self.CLASS({
        "--flag-a": "value1",
        "--flag-b": None,
        "--flag-c": "value3"
    })
    flags_copy = self.CLASS(flags)
    self.assertEqual(str(flags), str(flags_copy))
    flags_copy = self.CLASS()
    flags_copy.update(flags)
    self.assertEqual(str(flags), str(flags_copy))

  def test_parse_nested(self):
    self.skipTest("Not supported for JSFlags")

  def test_known_flags(self):
    self.assertNotIn(
        "--help", KNOWN_JS_FLAGS,
        "--help is also present in chrome, this should be filtered out")
    for flag in KNOWN_JS_FLAGS:
      self.assertFalse(
          flag.startswith("--no"), "Strip --no prefix from all flags.")
      self.assertNotIn("=", flag, "Only allow names, no values")

  def test_known_flags_chrome_overlap(self):
    for js_flag in KNOWN_JS_FLAGS:
      self.assertNotIn(js_flag, KNOWN_CHROME_FLAGS)

  def test_parse_with_flag_value(self):
    self.assertEqual(
        self.CLASS.parse("--foo=--other"), self.CLASS({"--foo": "--other"}))
    self.assertEqual(
        self.CLASS.parse("--foo='--other'"), self.CLASS({"--foo": "--other"}))
    self.assertEqual(
        self.CLASS.parse('--foo="--other"'), self.CLASS({"--foo": "--other"}))
    self.assertEqual(
        self.CLASS.parse("--foo='--other=1'"),
        self.CLASS({"--foo": "--other=1"}))
    self.assertEqual(
        self.CLASS.parse('--foo="--other=1"'),
        self.CLASS({"--foo": "--other=1"}))


del TestFlags

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
