# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import unittest

from crossbench.flags.chrome_extensions import ChromeExtensions
from tests import test_helper


class ChromeExtensionsTestCase(unittest.TestCase):

  def test_empty(self):
    extensions = ChromeExtensions()
    self.assertEqual(str(extensions), "")
    self.assertFalse(extensions)
    self.assertFalse(extensions.disabled)
    self.assertFalse(extensions.enabled)

  def test_disable_flag(self):
    extensions = ChromeExtensions()
    extensions.disable()
    self.assertEqual(str(extensions), "--disable-extensions")
    self.assertTrue(extensions)
    self.assertTrue(extensions.disabled)
    self.assertFalse(extensions.enabled)

  def test_enable_flag(self):
    extensions = ChromeExtensions()
    extensions.enable("foo")
    self.assertEqual(str(extensions), "--load-extension=foo")
    self.assertTrue(extensions)
    self.assertFalse(extensions.disabled)
    self.assertTrue(extensions.enabled)

  def test_enable_selective(self):
    extensions = ChromeExtensions()
    extensions.enable("foo", selective=True)
    self.assertEqual(str(extensions), "--disable-extensions-except=foo")
    self.assertTrue(extensions)
    self.assertFalse(extensions.disabled)
    self.assertTrue(extensions.enabled)
    with self.assertRaisesRegex(ValueError, "ext_b"):
      extensions.add("ext_b")
    with self.assertRaisesRegex(ValueError, "ext_b"):
      extensions.enable("ext_b")
    with self.assertRaisesRegex(ValueError, "enabled"):
      extensions.disable()

  def test_enable_multiple(self):
    extensions = ChromeExtensions()
    extensions.enable("foo,bar")
    self.assertEqual(str(extensions), "--load-extension=foo,bar")

  def test_enable_selective_multiple(self):
    extensions = ChromeExtensions()
    extensions.enable("foo,bar", selective=True)
    self.assertEqual(str(extensions), "--disable-extensions-except=foo,bar")

  def test_merge_empty(self):
    extensions_a = ChromeExtensions()
    extensions_a.merge(ChromeExtensions())
    self.assertFalse(extensions_a)
    extensions_a.merge(ChromeExtensions(["foo", "bar"]))
    self.assertTrue(extensions_a)
    self.assertEqual(extensions_a.extensions, ("foo", "bar"))

  def test_merge(self):
    extensions_a = ChromeExtensions(["ext_a"])
    extensions_a.merge(ChromeExtensions())
    self.assertTrue(extensions_a)
    self.assertEqual(extensions_a.extensions, ("ext_a",))

    extensions_a.merge(ChromeExtensions(["foo", "bar"]))
    self.assertTrue(extensions_a)
    self.assertEqual(extensions_a.extensions, ("ext_a", "foo", "bar"))

    extensions_b = ChromeExtensions()
    extensions_b.disable()
    with self.assertRaisesRegex(ValueError, "modes"):
      extensions_a.merge(extensions_b)
    with self.assertRaisesRegex(ValueError, "modes"):
      extensions_b.merge(extensions_a)

  def test_add(self):
    extensions = ChromeExtensions(["ext_a"])
    with self.assertRaisesRegex(ValueError, "empty"):
      extensions.add("")
    extensions.add("ext_b")
    self.assertEqual(extensions.extensions, ("ext_a", "ext_b"))
    extensions.add("ext_c")
    self.assertEqual(extensions.extensions, ("ext_a", "ext_b", "ext_c"))

  def test_enable(self):
    extensions = ChromeExtensions(["ext_a"])
    with self.assertRaisesRegex(ValueError, "empty"):
      extensions.enable("")
    extensions.enable("ext_b")
    self.assertEqual(extensions.extensions, ("ext_a", "ext_b"))
    extensions.enable("ext_c,ext_d")
    self.assertEqual(extensions.extensions,
                     ("ext_a", "ext_b", "ext_c", "ext_d"))

  def test_disable(self):
    extensions = ChromeExtensions(["ext_a"])
    with self.assertRaisesRegex(ValueError, "ext_a"):
      extensions.disable()
    extensions = ChromeExtensions()
    extensions.disable()
    with self.assertRaisesRegex(ValueError, "ext_b"):
      extensions.add("ext_b")
    with self.assertRaisesRegex(ValueError, "ext_b"):
      extensions.enable("ext_b")

  def test_set(self):
    extensions = ChromeExtensions()
    extensions.set("--load-extension", "foo,bar")
    self.assertEqual(extensions.extensions, ("foo", "bar"))
    with self.assertRaisesRegex(ValueError, "--foo-bar"):
      extensions.set("--foo-bar")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
