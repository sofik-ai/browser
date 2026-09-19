# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
import unittest
from typing import Any

from crossbench.cli.config.browser_variants import FlagsConfig, \
    FlagsGroupConfig, FlagsVariantConfig
from crossbench.cli.config.flags import DEFAULT_LABEL
from crossbench.config import ConfigError
from crossbench.exception import ArgumentTypeMultiException
from crossbench.flags.base import Flags
from tests import test_helper
from tests.crossbench.base import CrossbenchMockArgsMixin


class FlagsConfigTestCase(CrossbenchMockArgsMixin, unittest.TestCase):

  def test_invalid_empty(self):
    with self.assertRaises(ArgumentTypeMultiException) as cm:
      FlagsConfig.parse("")
    self.assertIn("empty", str(cm.exception).lower())
    with self.assertRaises(ConfigError) as cm:
      FlagsConfig.parse_str("")
    self.assertIn("empty", str(cm.exception).lower())

  def test_empty_dict(self):
    config = FlagsConfig.parse({})
    self.assertFalse(config)

  def test_parse_empty_group(self):
    config = FlagsConfig.parse({
        "a": None,
        "b": {},
        "c": (),
    })
    self.assertEqual(len(config), 3)
    for group in config.values():
      self.assertFalse(group)
    self.assertFalse(config["a"])
    self.assertFalse(config["b"])
    self.assertFalse(config["c"])

  def test_parse_str(self):
    config = FlagsConfig.parse("--foo --bar")
    self.assertEqual(len(config), 1)
    self.assertEqual(str(config["default"][0].flags), "--foo --bar")

  def test_parse_single_str_groups(self):
    config = FlagsConfig.parse({
        "a": "--foo=1 --bar",
        "b": "--foo=2 --bar",
    })
    self.assertEqual(len(config), 2)
    self.assertEqual(len(config["a"]), 1)
    self.assertEqual(len(config["b"]), 1)
    flags_a = config["a"][0].flags
    flags_b = config["b"][0].flags
    self.assertEqual(len(flags_a), 2)
    self.assertEqual(len(flags_b), 2)
    self.assertEqual(str(flags_a), "--foo=1 --bar")
    self.assertEqual(str(flags_b), "--foo=2 --bar")

  def test_parse_single_dict_groups(self):
    config = FlagsConfig.parse({
        "a": {
            "--foo": "1",
            "--bar": None,
        },
        "b": {
            "--foo": "2",
            "--bar": None
        }
    })
    self.assertEqual(len(config), 2)
    self.assertEqual(len(config["a"]), 1)
    self.assertEqual(len(config["b"]), 1)
    flags_a = config["a"][0].flags
    flags_b = config["b"][0].flags
    self.assertEqual(len(flags_a), 2)
    self.assertEqual(len(flags_b), 2)
    self.assertEqual(str(flags_a), "--foo=1 --bar")
    self.assertEqual(str(flags_b), "--foo=2 --bar")

  def test_parse_multi_str_groups(self):
    config = FlagsConfig.parse({
        "a": [
            "--foo=1 --bar=1",
            "--foo=1 --bar=2",
        ],
        "b": "--foo=2 --bar",
    })
    self.assertEqual(len(config), 2)
    self.assertEqual(len(config["a"]), 2)
    self.assertEqual(len(config["b"]), 1)
    labels = tuple(v.label for v in config["a"])
    self.assertTupleEqual(labels, ("foo=1_bar=1", "foo=1_bar=2"))
    variants_a = config["a"]
    flags_a_1 = variants_a[0].flags
    flags_a_2 = variants_a[1].flags
    self.assertEqual(str(flags_a_1), "--foo=1 --bar=1")
    self.assertEqual(str(flags_a_2), "--foo=1 --bar=2")

    flags_b = config["b"][0].flags
    self.assertEqual(len(flags_b), 2)
    self.assertEqual(str(flags_b), "--foo=2 --bar")

  def test_parse_multi_dict_str_groups(self):
    config = FlagsConfig.parse({
        "a": {
            "label_a_1": "--foo=1 --bar=1",
            "label_a_2": "--foo=1 --bar=2",
        }
    })
    self.assertEqual(len(config), 1)
    self.assertEqual(len(config["a"]), 2)

    self.assertTupleEqual(
        tuple(v.label for v in config["a"]), ("label_a_1", "label_a_2"))
    variants_a = config["a"]
    flags_a_1 = variants_a[0].flags
    flags_a_2 = variants_a[1].flags
    self.assertEqual(str(flags_a_1), "--foo=1 --bar=1")
    self.assertEqual(str(flags_a_2), "--foo=1 --bar=2")

  def test_parse_multi_dict_list_groups(self):
    config = FlagsConfig.parse({
        "a": {
            "label_a_1": ["--foo=1", "--bar=1"],
            "label_a_2": ["--foo=1", "--bar=2"],
        }
    })
    self.assertEqual(len(config), 1)
    self.assertEqual(len(config["a"]), 2)
    self.assertTupleEqual(
        tuple(v.label for v in config["a"]), ("label_a_1", "label_a_2"))
    variants_a = config["a"]
    flags_a_1 = variants_a[0].flags
    flags_a_2 = variants_a[1].flags
    self.assertEqual(str(flags_a_1), "--foo=1 --bar=1")
    self.assertEqual(str(flags_a_2), "--foo=1 --bar=2")

  def test_parse_multi_dict_dict_groups(self):
    config = FlagsConfig.parse({
        "a": {
            "label_a_1": {
                "--foo": "1",
                "--bar": "1"
            },
            "label_a_2": {
                "--bar": "2",
                "--foo": "1",
            }
        }
    })
    self.assertEqual(len(config), 1)
    self.assertEqual(len(config["a"]), 2)
    self.assertTupleEqual(
        tuple(v.label for v in config["a"]), ("label_a_1", "label_a_2"))
    variants_a = config["a"]
    flags_a_1 = variants_a[0].flags
    flags_a_2 = variants_a[1].flags
    self.assertEqual(str(flags_a_1), "--foo=1 --bar=1")
    self.assertEqual(str(flags_a_2), "--bar=2 --foo=1")

  def test_parse_variants_groups(self):
    config = FlagsConfig.parse(
        {"a": {
            "--foo": [None, "1"],
            "--bar": ["1", "2"],
        }})
    self.assertEqual(len(config), 1)
    self.assertEqual(len(config["a"]), 4)

    self.assertTupleEqual(
        tuple(v.label for v in config["a"]),
        ("bar=1", "bar=2", "foo=1_bar=1", "foo=1_bar=2"))
    variants_a = config["a"]
    self.assertEqual(str(variants_a[0].flags), "--bar=1")
    self.assertEqual(str(variants_a[1].flags), "--bar=2")
    self.assertEqual(str(variants_a[2].flags), "--foo=1 --bar=1")
    self.assertEqual(str(variants_a[3].flags), "--foo=1 --bar=2")


class FlagsVariantConfigTestCase(unittest.TestCase):

  def test_empty(self):
    empty = FlagsVariantConfig("default")
    self.assertEqual(empty.label, "default")
    self.assertFalse(empty.flags)
    self.assertEqual(empty.index, 0)
    self.assertEqual(empty, empty)

  def test_merge_copy(self):
    flags_a = Flags.parse("--foo-a")
    flags_b = Flags.parse("--bar-b=1")
    variant_a = FlagsVariantConfig("label_a", 0, flags_a)
    variant_b = FlagsVariantConfig("label_b", 1, flags_b)
    variant = variant_a.merge_copy(variant_b)
    self.assertEqual(variant.label, "label_a_label_b")
    self.assertEqual(str(variant.flags), "--foo-a --bar-b=1")
    self.assertEqual(variant.index, 0)

    variant = variant_a.merge_copy(variant_b, index=11, label="custom_label")
    self.assertEqual(variant.label, "custom_label")
    self.assertEqual(str(variant.flags), "--foo-a --bar-b=1")
    self.assertEqual(variant.index, 11)

  def test_equal(self):
    variant_a = FlagsVariantConfig.parse("label_a", 0, "--foo=a")
    variant_b = FlagsVariantConfig.parse("label_b", 1, "--foo=a")
    variant_c = FlagsVariantConfig.parse("label_b", 1, "--foo=b")
    self.assertEqual(variant_a, variant_b)
    self.assertEqual(variant_b, variant_a)
    self.assertNotEqual(variant_a, variant_c)
    self.assertNotEqual(variant_b, variant_c)
    variants = {variant_a}
    self.assertIn(variant_a, variants)
    self.assertIn(variant_b, variants)
    self.assertNotIn(variant_c, variants)
    self.assertNotEqual(variant_a, {})


class FlagsGroupConfigTestCase(CrossbenchMockArgsMixin, unittest.TestCase):

  def test_parse_empty(self):
    empty: Any
    for empty in (None, [], (), {}, "", "  "):
      with self.subTest(flags=empty):
        self.assertFalse(FlagsGroupConfig.parse(empty))

  def test_parse_invalid(self):
    for invalid in (-1, 0, 1):
      with self.subTest(invalid=invalid):
        with self.assertRaises(ConfigError):
          FlagsGroupConfig.parse(invalid)

  def test_parse_str_single(self):
    group = FlagsGroupConfig.parse("--foo-a=1")
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--foo-a=1")
    self.assertEqual(group[0].label, "default")

  def test_parse_str_multiple(self):
    group = FlagsGroupConfig.parse(("--foo-a=1 --bar", "--foo-a=2"))
    self.assertEqual(len(group), 2)
    self.assertEqual(str(group[0].flags), "--foo-a=1 --bar")
    self.assertEqual(str(group[1].flags), "--foo-a=2")

  def test_parse_list_multiple(self):
    group = FlagsGroupConfig.parse((("--foo-a=1", "--bar"), "--foo-a=2"))
    self.assertEqual(len(group), 2)
    self.assertEqual(str(group[0].flags), "--foo-a=1 --bar")
    self.assertEqual(str(group[1].flags), "--foo-a=2")

  def test_parse_str_multiple_empty(self):
    group = FlagsGroupConfig.parse(("", "--foo", "-foo=v1"))
    self.assertEqual(len(group), 3)
    self.assertEqual(str(group[0].flags), "")
    self.assertEqual(str(group[1].flags), "--foo")
    self.assertEqual(str(group[2].flags), "-foo=v1")

  def test_parse_dict_simple(self):
    group = FlagsGroupConfig.parse({"--foo": "1", "--bar": "2"})
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--foo=1 --bar=2")
    self.assertEqual(group[0].label, "default")

  def test_parse_dict_invalid_variant(self):
    for invalid in (-1, 0):
      with self.subTest(invalid=invalid):
        with self.assertRaises(ValueError):
          FlagsGroupConfig.parse({
              "--foo": "1",
              "--invalid": invalid,
              "--bar": "2",
          })

  def test_parse_duplicate_variant_value(self):
    for duplicate in (None, "", "value"):
      with self.subTest(duplicate=duplicate):
        with self.assertRaises(ValueError) as cm:
          FlagsGroupConfig.parse({"--duplicate": [duplicate, duplicate]})
        self.assertIn("duplicate", str(cm.exception))
    with self.assertRaises(ConfigError) as cm:
      FlagsGroupConfig.parse(
          ["--foo --duplicate='foo'", "--foo --duplicate='foo'"])
    self.assertIn("duplicate", str(cm.exception))

  def test_parse_dict_single_with_labels(self):
    group = FlagsGroupConfig.parse({
        "config_1": "--foo=1 --bar",
        "config_2": "",
    })
    self.assertEqual(len(group), 2)
    self.assertEqual(str(group[0].flags), "--foo=1 --bar")
    self.assertEqual(str(group[1].flags), "")
    self.assertEqual(group[0].label, "config_1")
    self.assertEqual(group[1].label, "config_2")
    for index, variant in enumerate(group):
      self.assertEqual(variant.index, index)

  def test_parse_dict_with_labels_duplicate_flags(self):
    with self.assertRaises(argparse.ArgumentTypeError) as cm:
      _ = FlagsGroupConfig.parse({
          "config_1": "--foo=1 --bar",
          "config_2": "--foo=1 --bar",
      })
    self.assertIn("duplicate", str(cm.exception).lower())
    self.assertIn("--foo=1 --bar", str(cm.exception).lower())

  def test_parse_dict_single(self):
    group = FlagsGroupConfig.parse({
        "--foo": "1",
        "--bar": None,
    })
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--foo=1 --bar")

  def test_parse_dict_duplicates(self):
    with self.assertRaisesRegex(argparse.ArgumentTypeError, "duplicates"):
      FlagsGroupConfig.parse({
          "--foo": [None, "1", "1"],
      })

  def test_parse_dict_invalid_values(self):
    with self.assertRaisesRegex(argparse.ArgumentTypeError,
                                "Invalid flag variant value"):
      FlagsGroupConfig.parse({
          "--foo": [None, "1", 1],
      })

  def test_parse_invalid_value(self):
    with self.assertRaisesRegex(argparse.ArgumentTypeError,
                                "Invalid flag variant value"):
      FlagsGroupConfig.parse({
          "--foo": 1,
      })

  def test_parse_dict_multiple_3_x_1(self):
    group = FlagsGroupConfig.parse({
        "--foo": [None, "1", "2"],
        "--bar": None,
    })
    self.assertEqual(len(group), 3)
    self.assertEqual(str(group[0].flags), "--bar")
    self.assertEqual(str(group[1].flags), "--foo=1 --bar")
    self.assertEqual(str(group[2].flags), "--foo=2 --bar")
    for index, variant in enumerate(group):
      self.assertEqual(variant.index, index)

  def test_parse_dict_multiple_2_x_2(self):
    group = FlagsGroupConfig.parse({
        "--foo": [None, "a"],
        "--bar": [None, "b"],
    })
    self.assertEqual(len(group), 4)
    self.assertEqual(str(group[0].flags), "")
    self.assertEqual(str(group[1].flags), "--bar=b")
    self.assertEqual(str(group[2].flags), "--foo=a")
    self.assertEqual(str(group[3].flags), "--foo=a --bar=b")
    self.assertEqual(group[0].label, "default")
    self.assertEqual(group[1].label, "bar=b")
    self.assertEqual(group[2].label, "foo=a")
    self.assertEqual(group[3].label, "foo=a_bar=b")
    for index, variant in enumerate(group):
      self.assertEqual(variant.index, index)

  def test_product_single(self):
    group_a = FlagsGroupConfig.parse("--foo-a=1")
    group_b = FlagsGroupConfig.parse("--foo-b=1")
    self.assertEqual(group_a[0].label, "default")
    self.assertEqual(group_b[0].label, "default")
    group = group_a.product(group_b)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--foo-a=1 --foo-b=1")
    self.assertEqual(group[0].label, "default")

  def test_product_empty_empty(self):
    group_a = FlagsGroupConfig()
    group_b = FlagsGroupConfig()
    group = group_a.product(group_b)
    self.assertFalse(group)
    group = group_a.product(group_b, group_b, group_b)
    self.assertFalse(group)

  def test_product_same(self):
    group_a = FlagsGroupConfig.parse("--foo-b=1")
    self.assertEqual(group_a[0].label, "default")
    group = group_a.product(group_a)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--foo-b=1")
    self.assertEqual(group[0].label, "default")
    group = group_a.product(group_a, group_a, group_a)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--foo-b=1")
    self.assertEqual(group[0].label, "default")

  def test_product_same_values(self):
    group_a = FlagsGroupConfig.parse("--foo-b=1")
    group_b = FlagsGroupConfig.parse("--foo-b=1")
    group = group_a.product(group_b)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--foo-b=1")
    group = group_a.product(group_a, group_a, group_a)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--foo-b=1")

  def test_product_empty(self):
    group_a = FlagsGroupConfig.parse("")
    group_b = FlagsGroupConfig.parse("--foo-b=1")
    group = group_a.product(group_b)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--foo-b=1")
    group = group_b.product(group_a)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--foo-b=1")

  def test_product_2_x_1(self):
    group_a = FlagsGroupConfig.parse((
        None,
        "--foo-a=1",
    ))
    group_b = FlagsGroupConfig.parse("--foo-b=1")
    group = group_a.product(group_b)
    self.assertEqual(len(group), 2)
    self.assertEqual(str(group[0].flags), "--foo-b=1")
    self.assertEqual(str(group[1].flags), "--foo-a=1 --foo-b=1")
    self.assertEqual(group[0].label, "default")
    self.assertEqual(group[1].label, "foo_a=1")

  def test_product_2_x_2(self):
    group_a = FlagsGroupConfig.parse((
        None,
        "--foo-a=1",
    ))
    group_b = FlagsGroupConfig.parse((None, "--foo-b=1"))
    group = group_a.product(group_b)
    self.assertEqual(len(group), 4)
    self.assertEqual(str(group[0].flags), "")
    self.assertEqual(str(group[1].flags), "--foo-b=1")
    self.assertEqual(str(group[2].flags), "--foo-a=1")
    self.assertEqual(str(group[3].flags), "--foo-a=1 --foo-b=1")
    self.assertEqual(group[0].label, "default")
    self.assertEqual(group[1].label, "foo_b=1")
    self.assertEqual(group[2].label, "foo_a=1")
    self.assertEqual(group[3].label, "foo_a=1_foo_b=1")
    for index, variant in enumerate(group):
      self.assertEqual(variant.index, index)

  def test_product_conflicting(self):
    group_a = FlagsGroupConfig.parse(("--foo=1"))
    group_b = FlagsGroupConfig.parse(("--foo=2"))
    with self.assertRaises(ValueError) as cm:
      group_a.product(group_b)
    self.assertIn("different previous value", str(cm.exception))

  def test_parse_args_empty(self):
    args = self.mock_args()
    group_args = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_args), 1)
    variant = group_args[0]
    self.assertEqual(variant.label, DEFAULT_LABEL)
    self.assertFalse(variant.flags)

  def test_parse_args_other_browser_args_1(self):
    args = self.mock_args(other_browser_args=("--foo=1",))
    group_args = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_args), 1)
    group_a = FlagsGroupConfig.parse(("--foo=1",))
    group_b = FlagsGroupConfig.parse("--foo=1")
    self.assertEqual(group_args, group_a)
    self.assertEqual(group_args, group_b)

  def test_parse_args_other_browser_args_2(self):
    args = self.mock_args(other_browser_args=("--foo=1", "--bar"))
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 1)
    raw_flags = "--foo=1 --bar"
    group_a = FlagsGroupConfig.parse((raw_flags,))
    group_b = FlagsGroupConfig.parse(raw_flags)
    self.assertEqual(group_inline, group_a)
    self.assertEqual(group_inline, group_b)

  def test_parse_args_extra_browser_args_1(self):
    args = self.mock_args(extra_browser_args=("--foo=1",))
    group_args = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_args), 1)
    group_a = FlagsGroupConfig.parse(("--foo=1",))
    group_b = FlagsGroupConfig.parse("--foo=1")
    self.assertEqual(group_args, group_a)
    self.assertEqual(group_args, group_b)

  def test_parse_args_extra_browser_args_2(self):
    args = self.mock_args(extra_browser_args=("--foo=1", "--bar"))
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 1)
    raw_flags = "--foo=1 --bar"
    group_a = FlagsGroupConfig.parse((raw_flags,))
    group_b = FlagsGroupConfig.parse(raw_flags)
    self.assertEqual(group_inline, group_a)
    self.assertEqual(group_inline, group_b)
    args = self.mock_args(extra_browser_args=(raw_flags))
    group_space = FlagsGroupConfig.parse_args(args)
    self.assertEqual(group_inline, group_space)

  def test_parse_args_extra_browser_args_js_flags(self):
    args = self.mock_args(extra_browser_args=("--js-flags=--foo", "--bar"))
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 1)
    raw_flags = "--js-flags=--foo --bar"
    group_a = FlagsGroupConfig.parse((raw_flags,))
    group_b = FlagsGroupConfig.parse(raw_flags)
    self.assertEqual(group_inline, group_a)
    self.assertEqual(group_inline, group_b)
    args = self.mock_args(extra_browser_args=(raw_flags))
    group_space = FlagsGroupConfig.parse_args(args)
    self.assertEqual(group_inline, group_space)
    args = self.mock_args(
        extra_browser_args=("--bar",),
        js_flags=("--foo",),
    )
    group_separate = FlagsGroupConfig.parse_args(args)
    self.assertEqual(group_inline, group_separate)

  def test_parse_args_extra_browser_args_mixed(self):
    args = self.mock_args(
        extra_browser_args=("--js-flags=--no-turbofan --enable-features=FOO",))
    group = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group), 1)
    flags = group[0].flags
    self.assertEqual(str(flags.js_flags), "--no-turbofan")
    self.assertIn("FOO", flags.features.enabled)

  def test_parse_args_extra_and_other_browser_args(self):
    args = self.mock_args(
        extra_browser_args=("--foo=1",), other_browser_args=("--bar=2"))
    group_args = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_args), 1)
    group_a = FlagsGroupConfig.parse(("--bar=2 --foo=1"))
    group_b = FlagsGroupConfig.parse("--bar=2 --foo=1")
    self.assertEqual(group_args, group_a)
    self.assertEqual(group_args, group_b)

  def test_parse_args_extra_and_other_browser_args_js_flags(self):
    args = self.mock_args(
        extra_browser_args=("--js-flags=--foo=1",),
        other_browser_args=("--js-flags=--bar=2"))
    group_args = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_args), 1)
    group_a = FlagsGroupConfig.parse(("--js-flags='--bar=2 --foo=1'"))
    group_b = FlagsGroupConfig.parse("--js-flags='--bar=2 --foo=1'")
    group_c = FlagsGroupConfig.parse(("--js-flags='--bar=2,--foo=1'"))
    self.assertEqual(group_args, group_a)
    self.assertEqual(group_args, group_b)
    self.assertEqual(group_args, group_c)

  def test_parse_args_extra_and_other_browser_args_conflict(self):
    args = self.mock_args(
        extra_browser_args=("--foo=1",), other_browser_args=("--foo=2"))
    with self.assertRaisesRegex(ValueError, "--foo"):
      FlagsGroupConfig.parse_args(args)

  def test_parse_args_extra_and_other_browser_args_conflict_2(self):
    args = self.mock_args(
        extra_browser_args=("--js-flags=--foo=1",),
        other_browser_args=("--js-flags=--foo=2"))
    with self.assertRaisesRegex(ValueError, "--foo"):
      FlagsGroupConfig.parse_args(args)

  def test_parse_args_features(self):
    args = self.mock_args(
        other_browser_args=("--foo=1", "--bar"),
        enable_features="Feature1",
        disable_features="Feature2")
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 1)
    raw_flags = ("--foo=1 --bar"
                 " --enable-features=Feature1 --disable-features=Feature2")
    group_a = FlagsGroupConfig.parse((raw_flags,))
    group_b = FlagsGroupConfig.parse(raw_flags)
    self.assertEqual(group_inline, group_a)
    self.assertEqual(group_inline, group_b)

  def test_parse_args_enable_field_trials(self):
    args = self.mock_args(enable_field_trial_config=True)
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 1)
    raw_flags = "--enable-field-trial-config"
    group_a = FlagsGroupConfig.parse((raw_flags,))
    group_b = FlagsGroupConfig.parse(raw_flags)
    self.assertEqual(group_inline, group_a)
    self.assertEqual(group_inline, group_b)

  def test_parse_args_disable_field_trials(self):
    args = self.mock_args(enable_field_trial_config=False)
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 1)
    raw_flags = "--disable-field-trial-config"
    group_a = FlagsGroupConfig.parse((raw_flags,))
    group_b = FlagsGroupConfig.parse(raw_flags)
    self.assertEqual(group_inline, group_a)
    self.assertEqual(group_inline, group_b)

  def test_parse_args_js_flags_1(self):
    args = self.mock_args(js_flags=["--max-opt=1,--log-all"])
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 1)
    raw_flags = "--js-flags='--max-opt=1,--log-all'"
    group_a = FlagsGroupConfig.parse((raw_flags,))
    group_b = FlagsGroupConfig.parse(raw_flags)
    self.assertEqual(group_inline, group_a)
    self.assertEqual(group_inline, group_b)

  def test_parse_args_js_flags_other_browser_args(self):
    args = self.mock_args(
        other_browser_args=["--js-flags=--max-opt=1,--log-all"])
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 1)
    self.assertEqual(
        str(group_inline[0].flags), "--js-flags=--max-opt=1,--log-all")
    raw_flags = "--js-flags='--max-opt=1,--log-all'"
    group = FlagsGroupConfig.parse(raw_flags)
    self.assertEqual(group_inline, group)

  def test_parse_args_js_flags_2(self):
    args = self.mock_args(js_flags=["--max-opt=1", "--log-all"])
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 2)
    group_a = FlagsGroupConfig.parse(
        ("--js-flags=--max-opt=1", "--js-flags=--log-all"))
    self.assertEqual(group_inline, group_a)

  def test_parse_args_js_flags_2_other_browser_args(self):
    args = self.mock_args(
        js_flags=["--max-opt=1", "--log-all"],
        other_browser_args=["--js-flags=--no-turbofan"])
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 2)
    self.assertEqual(
        str(group_inline[0].flags), "--js-flags=--max-opt=1,--no-turbofan")
    self.assertEqual(
        str(group_inline[1].flags), "--js-flags=--log-all,--no-turbofan")

  def test_parse_args_js_flags_2_with_empty(self):
    args = self.mock_args(js_flags=["", "--log-all"])
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 2)
    group_a = FlagsGroupConfig.parse(("--js-flags", "--js-flags=--log-all"))
    self.assertEqual(group_inline, group_a)

    args = self.mock_args(js_flags=[" ", "--log-all"])
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 2)
    self.assertEqual(group_inline, group_a)
    variant_a = group_inline[0]
    variant_b = group_inline[1]
    self.assertEqual(str(variant_a.flags), "")
    self.assertEqual(str(variant_b.flags), "--js-flags=--log-all")

  def test_parse_args_js_flags_2_with_empty_and_other_browser_args(self):
    args = self.mock_args(
        js_flags=["", "--log-all"],
        other_browser_args=["--js-flags=--no-turbofan"])
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 2)
    self.assertEqual(str(group_inline[0].flags), "--js-flags=--no-turbofan")
    self.assertEqual(
        str(group_inline[1].flags), "--js-flags=--log-all,--no-turbofan")

  def test_parse_args_js_flags_2_with_empty_and_other_browser_args_empty(self):
    args = self.mock_args(
        js_flags=["", "--log-all"], other_browser_args=["--js-flags"])
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 2)
    self.assertEqual(str(group_inline[0].flags), "")
    self.assertEqual(str(group_inline[1].flags), "--js-flags=--log-all")

  def test_parse_args_combined(self):
    args = self.mock_args(
        other_browser_args=("--bar"),
        enable_features="Feature1",
        js_flags=["--max-opt=1", "--log-all"])
    group_inline = FlagsGroupConfig.parse_args(args)
    self.assertEqual(len(group_inline), 2)
    group_a = FlagsGroupConfig.parse(
        ("--bar --enable-features=Feature1 --js-flags=--max-opt=1",
         "--bar --enable-features=Feature1 --js-flags=--log-all"))
    self.assertEqual(group_inline, group_a)

  def test_parse_args_product_js_flags(self):
    args_a = self.mock_args(js_flags=["--max-opt=1", "--log-all"])
    group_a = FlagsGroupConfig.parse_args(args_a)
    self.assertEqual(len(group_a), 2)
    args_b = self.mock_args(js_flags=["--no-turbofan"])
    group_b = FlagsGroupConfig.parse_args(args_b)
    self.assertEqual(len(group_b), 1)
    product = group_a.product(group_b)
    self.assertEqual(len(product), 2)
    self.assertEqual(
        str(product[0].flags), "--js-flags=--max-opt=1,--no-turbofan")
    self.assertEqual(
        str(product[1].flags), "--js-flags=--log-all,--no-turbofan")

  def test_parse_chrome_flags(self):
    args = self.mock_args(js_flags=["--no-opt"])
    group = FlagsGroupConfig.parse(args)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--js-flags=--no-opt")

    args = self.mock_args(sandbox=False)
    group = FlagsGroupConfig.parse(args)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--no-sandbox")

    args = self.mock_args(enable_features="Custom")
    group = FlagsGroupConfig.parse(args)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--enable-features=Custom")

    args = self.mock_args(disable_features="Custom")
    group = FlagsGroupConfig.parse(args)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--disable-features=Custom")

    args = self.mock_args(enable_field_trial_config=True)
    group = FlagsGroupConfig.parse(args)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--enable-field-trial-config")

    args = self.mock_args(enable_field_trial_config=False)
    group = FlagsGroupConfig.parse(args)
    self.assertEqual(len(group), 1)
    self.assertEqual(str(group[0].flags), "--disable-field-trial-config")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
