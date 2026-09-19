# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse

from typing_extensions import override

from crossbench.flags.chrome import ChromeFlags, ChromePreM139Flags
from crossbench.flags.chrome_extensions import ChromeExtensions
from crossbench.flags.known_chrome_flags import KNOWN_CHROME_FLAGS
from crossbench.flags.known_js_flags import KNOWN_JS_FLAGS
from tests import test_helper
from tests.crossbench.flags.test_flags import TestFlags


class TestChromeFlags(TestFlags):
  CLASS = ChromeFlags

  def test_for_milestone(self):
    flags = self.CLASS.for_milestone()
    self.assertEqual(type(flags), ChromeFlags)

    flags = self.CLASS.for_milestone(milestone=0)
    self.assertEqual(type(flags), ChromeFlags)

    for milestone in range(80, 139):
      flags = self.CLASS.for_milestone({}, milestone)
      self.assertEqual(type(flags), ChromePreM139Flags)

    flags = self.CLASS.for_milestone({}, 138)
    self.assertEqual(type(flags), ChromePreM139Flags)
    flags = self.CLASS.for_milestone({}, 139)
    self.assertEqual(type(flags), ChromeFlags)

    for milestone in range(140, 150):
      flags = ChromeFlags.for_milestone({}, milestone)
      self.assertEqual(type(flags), ChromeFlags)

  def test_js_flags(self):
    flags = self.CLASS({
        "--foo": None,
        "--bar": "v1",
    })
    self.assertIsNone(flags["--foo"])
    self.assertEqual(flags["--bar"], "v1")
    self.assertTrue(flags)
    self.assertFalse(flags.js_flags)
    self.assertNotIn("--js-flags", flags)
    with self.assertRaises(ValueError):
      flags["--js-flags"] = "--js-foo, --no-js-foo"
    flags["--js-flags"] = "--js-foo=v3, --no-js-bar"
    with self.assertRaises(ValueError):
      flags["--js-flags"] = "--js-foo=v4, --no-js-bar"
    js_flags = flags.js_flags
    self.assertTrue(js_flags)
    self.assertNotIn(flags["--js-flags"], js_flags)
    self.assertEqual(js_flags["--js-foo"], "v3")
    self.assertIsNone(js_flags["--no-js-bar"])

  def test_set_empty_js_flags(self):
    flags = self.CLASS({
        "--foo": None,
        "--bar": "v1",
    })
    self.assertNotIn("--js-flags", flags)
    self.assertTrue(flags)
    flags["--js-flags"] = None
    self.assertNotIn("--js-flags", flags)
    self.assertFalse(flags.js_flags)
    flags["--js-flags"] = ""
    self.assertNotIn("--js-flags", flags)
    self.assertFalse(flags.js_flags)
    flags["--js-flags"] = "  "
    self.assertNotIn("--js-flags", flags)
    self.assertFalse(flags.js_flags)

  def test_reset_js_flags(self):
    flags = self.CLASS()
    flags["--js-flags"] = "--js-foo=v3, --no-js-bar"
    js_flags = flags.js_flags
    self.assertTrue(js_flags)
    flags["--js-flags"] = None
    self.assertFalse(js_flags)

  def test_set_js_flags_invalid(self):
    flags = self.CLASS()
    for invalid in ("-foo", "--bar'f'", "--", "-8", "--8"):
      with self.subTest(js_flag=invalid):
        with self.assertRaises(ValueError) as cm:
          flags["--js-flags"] = invalid
        self.assertNotIn("--js-flags", flags)
        self.assertIn(invalid, str(cm.exception))
    for invalid in ("--foo=", "--foo,--bar=,--baz", "---foo", "--foo,--,--bar",
                    "--foo;;;,;;;--bar"):
      with self.subTest(js_flag=invalid):
        with self.assertRaises(ValueError) as cm:
          flags["--js-flags"] = invalid
        self.assertNotIn("--js-flags", flags)

  def test_js_flags_initial_data(self):
    flags = self.CLASS({
        "--js-flags": "--foo=v1,--no-bar",
    })
    js_flags = flags.js_flags
    self.assertEqual(js_flags["--foo"], "v1")
    self.assertIsNone(js_flags["--no-bar"])
    self.assertTrue(flags)
    self.assertTrue(flags.js_flags)

  def test_features(self):
    flags = self.CLASS()
    features = flags.features
    self.assertFalse(flags)
    self.assertFalse(flags.features)
    self.assertTrue(features.is_empty)
    flags["--enable-features"] = "F1,F2"
    self.assertTrue(flags)
    self.assertTrue(flags.features)
    with self.assertRaises(ValueError):
      flags["--disable-features"] = "F1,F2"
    with self.assertRaises(ValueError):
      flags["--disable-features"] = "F2,F1"
    flags["--disable-features"] = "F3,F4"
    self.assertEqual(features.enabled, {"F1": None, "F2": None})
    self.assertEqual(flags["--enable-features"], "F1,F2")
    self.assertEqual(features.disabled, {"F3", "F4"})
    self.assertEqual(flags["--disable-features"], "F3,F4")
    self.assertTrue(flags)
    self.assertTrue(flags.features)

  def test_features_rename(self):
    flags = self.CLASS()
    flags["--enable-feature"] = "F1"
    self.assertEqual(str(flags), "--enable-features=F1")
    self.assertEqual(flags.features.enabled_str(), "F1")
    flags = self.CLASS()
    flags["--disable-feature"] = "F1"
    self.assertEqual(str(flags), "--disable-features=F1")
    self.assertEqual(flags.features.disabled_str(), "F1")

  def test_blink_features(self):
    flags = self.CLASS()
    features = flags.blink_features
    self.assertFalse(flags)
    self.assertFalse(flags.blink_features)
    self.assertTrue(features.is_empty)
    flags["--enable-blink-features"] = "F1,F2"
    self.assertTrue(flags)
    self.assertTrue(flags.blink_features)
    with self.assertRaises(ValueError):
      flags["--disable-blink-features"] = "F1,F2"
    with self.assertRaises(ValueError):
      flags["--disable-blink-features"] = "F2,F1"
    flags["--disable-blink-features"] = "F3,F4"
    self.assertEqual(features.enabled, {"F1": None, "F2": None})
    self.assertEqual(flags["--enable-blink-features"], "F1,F2")
    self.assertEqual(features.disabled, {"F3", "F4"})
    self.assertEqual(flags["--disable-blink-features"], "F3,F4")

  def test_features_none(self):
    flags = self.CLASS()
    features = flags.features
    self.assertFalse(features)
    self.assertTrue(features.is_empty)
    flags["--disable-features"] = None
    self.assertFalse(features)
    self.assertTrue(features.is_empty)
    flags["--enable-features"] = None
    self.assertFalse(features)
    self.assertTrue(features.is_empty)

  def test_features_reset_none(self):
    flags = self.CLASS()
    features = flags.features
    flags["--enable-features"] = "F1,F2"
    flags["--disable-features"] = "F3,F4"
    self.assertEqual(features.enabled, {"F1": None, "F2": None})
    self.assertEqual(features.disabled, {"F3", "F4"})

    flags["--enable-features"] = None
    self.assertFalse(features.enabled)
    self.assertEqual(features.disabled, {"F3", "F4"})

    flags["--disable-features"] = None
    self.assertFalse(features)

  def test_blink_features_none(self):
    flags = self.CLASS()
    features = flags.blink_features
    self.assertTrue(features.is_empty)
    flags["--disable-blink-features"] = None
    self.assertTrue(features.is_empty)
    flags["--enable-blink-features"] = None
    self.assertNotIn("--enable-blink-features", flags)
    self.assertTrue(features.is_empty)

  def test_blink_features_rename(self):
    flags = self.CLASS()
    flags["--enable-blink-feature"] = "F1"
    self.assertEqual(str(flags), "--enable-blink-features=F1")
    self.assertEqual(flags.blink_features.enabled_str(), "F1")
    flags = self.CLASS()
    flags["--disable-blink-feature"] = "F1"
    self.assertEqual(str(flags), "--disable-blink-features=F1")
    self.assertEqual(flags.blink_features.disabled_str(), "F1")

  def test_user_data_dir(self):
    flags = self.CLASS()
    for invalid in (None, "", "  "):
      with self.subTest(user_dat_dir=invalid):
        with self.assertRaises(ValueError) as cm:
          flags["--user-data-dir"] = invalid
        self.assertIn("empty string", str(cm.exception))

  def test_get_list(self):
    flags = self.CLASS()
    flags["--user-data-dir"] = "/test/user-data"
    flags.set("--single-process")
    flags["--js-flags"] = "--js-foo=v3, --no-js-bar"
    flags["--enable-features"] = "F1,F2"
    flags["--disable-features"] = "F3,F4"
    flags["--enable-blink-features"] = "BLINK_F1,BLINK_F2"
    flags["--disable-blink-features"] = "BLINK_F3,BLINK_F4"
    flags_list = list(flags)
    self.assertListEqual(flags_list, [
        "--user-data-dir=/test/user-data",
        "--single-process",
        "--js-flags=--js-foo=v3,--no-js-bar",
        "--enable-features=F1,F2",
        "--disable-features=F3,F4",
        "--enable-blink-features=BLINK_F1,BLINK_F2",
        "--disable-blink-features=BLINK_F3,BLINK_F4",
    ])

  def test_to_dict(self):
    flags = self.CLASS()
    flags["--user-data-dir"] = "/test/user-data"
    flags.set("--single-process")
    flags["--js-flags"] = "--js-foo=v3, --no-js-bar"
    flags["--enable-features"] = "F1,F2"
    flags["--disable-features"] = "F3,F4"
    flags["--enable-blink-features"] = "BLINK_F1,BLINK_F2"
    flags["--disable-blink-features"] = "BLINK_F3,BLINK_F4"
    self.assertDictEqual(
        flags.to_dict(), {
            "--user-data-dir": "/test/user-data",
            "--single-process": None,
            "--js-flags": "--js-foo=v3,--no-js-bar",
            "--enable-features": "F1,F2",
            "--disable-features": "F3,F4",
            "--enable-blink-features": "BLINK_F1,BLINK_F2",
            "--disable-blink-features": "BLINK_F3,BLINK_F4",
        })

  def test_initial_data_empty(self):
    flags = self.CLASS()
    flags_copy = self.CLASS(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertFalse(flags_copy)
    flags_copy = self.CLASS()
    flags_copy.update(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertFalse(flags_copy)

  def test_initial_data_simple(self):
    flags = self.CLASS()
    flags["--no-sandbox"] = None
    flags_copy = self.CLASS(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertTrue(flags_copy)
    flags_copy = self.CLASS()
    flags_copy.update(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertTrue(flags_copy)

  def test_initial_data_js_flags(self):
    flags = self.CLASS()
    flags["--js-flags"] = "--js-foo=v3, --no-js-bar"
    flags_copy = self.CLASS(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertTrue(flags_copy)
    flags_copy = self.CLASS()
    flags_copy.update(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertTrue(flags_copy)

  def test_initial_data_features(self):
    flags = self.CLASS()
    flags["--enable-features"] = "F1,F2"
    flags["--disable-features"] = "F3,F4"
    flags_copy = self.CLASS(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertTrue(flags_copy)
    flags_copy = self.CLASS()
    flags_copy.update(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertTrue(flags_copy)

  def test_initial_data_blink_features(self):
    flags = self.CLASS()
    flags["--enable-blink-features"] = "BLINK_F1,BLINK_F2"
    flags["--disable-blink-features"] = "BLINK_F3,BLINK_F4"
    flags_copy = self.CLASS(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertTrue(flags_copy)
    flags_copy = self.CLASS()
    flags_copy.update(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertTrue(flags_copy)

  def test_initial_data_all(self):
    flags = self.CLASS()
    flags["--no-sandbox"] = None
    flags["--js-flags"] = "--js-foo=v3, --no-js-bar"
    flags["--enable-features"] = "F1,F2"
    flags["--disable-features"] = "F3,F4"
    flags["--enable-blink-features"] = "BLINK_F1,BLINK_F2"
    flags["--disable-blink-features"] = "BLINK_F3,BLINK_F4"
    flags_copy = self.CLASS(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertTrue(flags_copy)
    flags_copy = self.CLASS()
    flags_copy.update(flags)
    self.assertListEqual(list(flags), list(flags_copy))
    self.assertTrue(flags_copy)

  def test_set_js_flags(self):
    flags = self.CLASS()
    flags["--js-flags"] = "--foo=a/b/c-d-e.log,--bar=a--b/c ,--no-baz"
    self.assertEqual(flags.js_flags["--foo"], "a/b/c-d-e.log")
    self.assertEqual(flags.js_flags["--bar"], "a--b/c")
    self.assertEqual(flags.js_flags["--no-baz"], None)

  def test_js_flags_separators(self):
    flags_1 = self.CLASS()
    flags_1["--js-flags"] = "--f-one=1,--no-f-two,--f-three=3"
    flags_2 = self.CLASS()
    flags_2["--js-flags"] = "--f-one=1 --no-f-two --f-three=3"
    flags_3 = self.CLASS()
    flags_3["--js-flags"] = "--f-one='1',--no-f-two,--f-three=\"3\""
    flags_4 = self.CLASS()
    flags_4["--js-flags"] = "--f-one='1' --no-f-two, --f-three=\"3\""

    list_1 = list(flags_1.js_flags)
    list_2 = list(flags_2.js_flags)
    self.assertListEqual(list_1, list_2)
    list_3 = list(flags_3.js_flags)
    self.assertListEqual(list_1, list_3)
    list_4 = list(flags_4.js_flags)
    self.assertListEqual(list_1, list_4)

    for flags in (flags_1, flags_2, flags_3):
      self.assertEqual(flags.js_flags["--f-one"], "1")
      self.assertEqual(flags.js_flags["--no-f-two"], None)
      self.assertEqual(flags.js_flags["--f-three"], "3")

  def test_set_invalid_js_flags(self):
    flags = self.CLASS()
    flags["--js-flags"] = "--foo=1--bar"
    for invalid in ("--bar,=", "-bar=1", "--bar,,", "--", "-", "a=b",
                    "--bar==1", "--bar==--bar", "--bar='1\", --foo=1",
                    "--foo='1'--bar", "--bar='a b c'"):
      with self.subTest(invalid=invalid):
        with self.assertRaises(ValueError):
          flags["--js-flags"] = invalid

  def test_merge(self):
    flags = self.CLASS({
        "--foo": "v1",
        "--bar": None,
        "--js-flags": "--log-maps,--log-ic",
        "--enable-features": "feature_1,feature_2",
        "--disable-features": "feature_3",
        "--enable-blink-features": "blink_feature_1,blink_feature_2",
        "--disable-blink-features": "blink_feature_3"
    })
    with self.assertRaises(ValueError):
      flags.merge({"--bar": "v2"})
    with self.assertRaises(ValueError):
      flags.merge({"--js-flags": "--no-log-maps"})
    with self.assertRaises(ValueError):
      flags.merge({"--disable-features": "feature_1,"})
    with self.assertRaises(ValueError):
      flags.merge({"--enable-features": "feature_3"})
    with self.assertRaises(ValueError):
      flags.merge({"--enable-blink-features": "blink_feature_3"})
    flags.merge({
        "--js-flags": "--log-all",
        "--enable-features": "feature_x",
        "--disable-features": "feature_y,feature_z",
        "--enable-blink-features": "blink_feature_x",
        "--disable-blink-features": "blink_feature_y,blink_feature_z"
    })
    self.assertListEqual(
        list(flags.js_flags), ["--log-maps", "--log-ic", "--log-all"])
    self.assertListEqual(
        list(flags.features), [
            "--enable-features=feature_1,feature_2,feature_x",
            "--disable-features=feature_3,feature_y,feature_z"
        ])
    self.assertListEqual(
        list(flags.blink_features), [
            "--enable-blink-features="
            "blink_feature_1,blink_feature_2,blink_feature_x",
            "--disable-blink-features="
            "blink_feature_3,blink_feature_y,blink_feature_z"
        ])

  def test_flag_typos_enable_features(self):
    # Check misspelled flags warnings
    for invalid_flag in ("--enable-feature", "--enabled-feature",
                         "--enabled-features"):
      with self.assertLogs(level="ERROR") as cm:
        self.CLASS({invalid_flag: "feature_1"})
      output = "\n".join(cm.output)
      self.assertIn(invalid_flag, output)
      self.assertIn("--enable-features", output)

    for invalid_flag in ("--disable-feature", "--disabled-feature",
                         "--disabled-features"):
      with self.assertLogs(level="ERROR") as cm:
        self.CLASS({invalid_flag: "feature_1"})
      output = "\n".join(cm.output)
      self.assertIn(invalid_flag, output)
      self.assertIn("--disable-features", output)

    for invalid_flag in ("--enable-blink-feature", "--enabled-blink-feature",
                         "--enabled-blink-features"):
      with self.assertLogs(level="ERROR") as cm:
        self.CLASS({invalid_flag: "feature_1"})
      output = "\n".join(cm.output)
      self.assertIn(invalid_flag, output)
      self.assertIn("--enable-blink-features", output)

    for invalid_flag in ("--disable-blink-feature", "--disabled-blink-feature",
                         "--disabled-blink-features"):
      with self.assertLogs(level="ERROR") as cm:
        self.CLASS({invalid_flag: "feature_1"})
      output = "\n".join(cm.output)
      self.assertIn(invalid_flag, output)
      self.assertIn("--disable-blink-features", output)

    for invalid_flag in ("--enable-field-trials",
                         "--enable-field-trials-config"):
      with self.assertLogs(level="ERROR") as cm:
        self.CLASS({invalid_flag: ""})
      output = "\n".join(cm.output)
      self.assertIn(invalid_flag, output)
      self.assertIn("--enable-field-trial-config", output)

  def test_flag_typos_enable_blink_features(self):
    for invalid_flag in ("--enable-blink-feature", "--enabled-blink-feature",
                         "--enabled-blink-features"):
      with self.assertLogs(level="ERROR") as cm:
        self.CLASS({invalid_flag: "feature_1"})
      output = "\n".join(cm.output)
      self.assertIn(invalid_flag, output)
      self.assertIn("--enable-blink-features", output)

    for invalid_flag in ("--disable-blink-feature", "--disabled-blink-feature",
                         "--disabled-blink-features"):
      with self.assertLogs(level="ERROR") as cm:
        self.CLASS({invalid_flag: "feature_1"})
      output = "\n".join(cm.output)
      self.assertIn(invalid_flag, output)
      self.assertIn("--disable-blink-features", output)

  def test_flag_js_flags_as_chrome_flags(self):
    for invalid_flag in ("--no-maglev", "--maglev"):
      flags = self.CLASS()
      with self.assertLogs(level="ERROR") as cm:
        flags.set(invalid_flag)
      self.assertIn(invalid_flag, str(cm.output))
      self.assertIn(invalid_flag, flags)
      self.assertNotIn(invalid_flag, flags.js_flags)

  def test_known_flags(self):
    for chrome_flag in KNOWN_CHROME_FLAGS:
      self.assertNotIn("=", chrome_flag, "Only allow names, no values")

  def test_known_flags_chrome_overlap(self):
    for chrome_flag in KNOWN_CHROME_FLAGS:
      self.assertNotIn(chrome_flag, KNOWN_JS_FLAGS)

  def test_field_trial_flags(self):
    empty = self.CLASS()
    self.assertFalse(empty.field_trial_enable_flags)
    some_flags = self.CLASS(("--foo", "--bar"))
    self.assertFalse(some_flags.field_trial_enable_flags)
    field_trials = self.CLASS(("--enable-field-trial-config", "--foo"))
    self.assertEqual(
        str(field_trials.field_trial_enable_flags),
        "--enable-field-trial-config")
    # Post M139 --enable-benchmarking does not affect field trials.
    field_trials.set("--enable-benchmarking")
    self.assertEqual(
        str(field_trials.field_trial_enable_flags),
        "--enable-field-trial-config")
    field_trials.set("--enable-benchmarking", should_override=True)
    self.assertEqual(
        str(field_trials.field_trial_enable_flags),
        "--enable-field-trial-config")

  def test_disable_field_trials_flags(self):
    empty = self.CLASS()
    self.assertFalse(empty.field_trial_disable_flags)
    some_flags = self.CLASS(("--foo", "--bar"))
    self.assertFalse(some_flags.field_trial_disable_flags)
    field_trials = self.CLASS(("--disable-field-trial-config", "--foo"))
    self.assertEqual(
        str(field_trials.field_trial_disable_flags),
        "--disable-field-trial-config")
    field_trials.set("--enable-benchmarking")
    self.assertEqual(
        str(field_trials.field_trial_disable_flags),
        "--disable-field-trial-config")
    field_trials.set("--enable-benchmarking", should_override=True)
    self.assertEqual(
        str(field_trials.field_trial_disable_flags),
        "--disable-field-trial-config")

  def test_set_enable_benchmarking_extension(self):
    flags = self.CLASS()
    flags.enable_benchmarking_api()
    self.assertEqual(str(flags), "--enable-benchmarking-api")

    flags = self.CLASS.parse("--foo")
    flags.enable_benchmarking_api()
    self.assertEqual(str(flags), "--foo --enable-benchmarking-api")

    flags = self.CLASS.parse("--enable-benchmarking-api")
    flags.enable_benchmarking_api()
    self.assertEqual(str(flags), "--enable-benchmarking-api")

    flags = self.CLASS.parse("--enable-benchmarking=enable-field-trial-config")
    flags.enable_benchmarking_api()
    self.assertEqual(
        str(flags), ("--enable-benchmarking=enable-field-trial-config "
                     "--enable-benchmarking-api"))

    flags = self.CLASS.parse("--enable-field-trial-config")
    flags.enable_benchmarking_api()
    self.assertEqual(
        str(flags), "--enable-field-trial-config "
        "--enable-benchmarking-api")

    flags = self.CLASS.parse("--foo --enable-field-trial-config --bar")
    flags.enable_benchmarking_api()
    self.assertEqual(
        str(flags), "--foo --enable-field-trial-config --bar "
        "--enable-benchmarking-api")

  def test_load_extensions(self):
    flags = self.CLASS()
    flags["--load-extensions"] = "a,b"
    self.assertEqual(flags.extensions.extensions, ("a", "b"))
    self.assertEqual(str(flags), "--load-extension=a,b")

    flags = self.CLASS()
    flags["--load-extension"] = "a,b"
    self.assertEqual(flags.extensions.extensions, ("a", "b"))
    self.assertEqual(str(flags), "--load-extension=a,b")

  def test_extensions_disabled(self):
    flags = self.CLASS()
    self.assertFalse(flags.extensions.enabled)
    self.assertFalse(flags.extensions.disabled)
    flags.set("--disable-extensions")
    self.assertFalse(flags.extensions.enabled)
    self.assertTrue(flags.extensions.disabled)
    self.assertEqual(str(flags), "--disable-extensions")

    flags = self.CLASS()
    flags["--disable-extensions-except"] = "foo"
    self.assertTrue(flags.extensions.enabled)
    self.assertFalse(flags.extensions.disabled)
    self.assertEqual(str(flags), "--disable-extensions-except=foo")

  def test_extensions_conflicts_enable(self):
    flags = self.CLASS()
    flags.set("--disable-extensions")
    for enable_flag in ChromeExtensions.ENABLE_FLAGS:
      with self.assertRaisesRegex(ValueError, enable_flag):
        flags[enable_flag] = "foo"

  def test_extensions_conflicts_disable(self):
    for enable_flag in ChromeExtensions.ENABLE_FLAGS:
      flags = self.CLASS()
      flags[enable_flag] = "foo"
      with self.assertRaisesRegex(ValueError, "--disable-extensions"):
        flags.set("--disable-extensions")

  def test_extensions_conflict_enable(self):
    flags = self.CLASS()
    flags["--load-extension"] = "extension_a,extension_b"
    self.assertEqual(str(flags), "--load-extension=extension_a,extension_b")
    self.assertEqual(
        str(flags.extensions), "--load-extension=extension_a,extension_b")
    # setting the same twice is allowed
    flags["--load-extension"] = "extension_a,extension_b"
    # Switching modes is not allowed.
    with self.assertRaisesRegex(ValueError, "extension_a"):
      flags["--disable-extensions-except"] = "extension_a,extension_b"
    # Overriding is not allowed.
    with self.assertRaisesRegex(ValueError, "extension_c"):
      flags["--load-extension"] = "extension_c"
    with self.assertRaisesRegex(ValueError, "extension_c"):
      flags["--disable-extensions-except"] = "extension_c"

  def test_merge_extensions(self):
    flags_a = self.CLASS()
    flags_a["--load-extension"] = "extension_a"
    flags_b = self.CLASS()
    flags_b["--load-extension"] = "extension_b,extension_c"
    flags_a.merge(flags_b)
    self.assertEqual(
        str(flags_a), "--load-extension=extension_a,extension_b,extension_c")

  def test_extensions_invalid_empty(self):
    flags = self.CLASS()
    with self.assertRaisesRegex(ValueError, "load-extension"):
      flags["--load-extension"] = ""
    with self.assertRaisesRegex(ValueError, "disable-extensions-except"):
      flags["--disable-extensions-except"] = ""
    with self.assertRaisesRegex(ValueError, "disable-extensions"):
      flags["--disable-extensions"] = "asdfasdfasd"

  def test_conflict_field_trials(self):
    flags = self.CLASS()
    flags.set("--enable-field-trial-config")
    flags.set("--disable-field-trial-config")
    with self.assertRaisesRegex(argparse.ArgumentTypeError, "field-trial"):
      flags.validate()

  def test_conflict_field_trials_enable_benchmarking(self):
    flags = self.CLASS()
    flags.set("--enable-field-trial-config")
    flags.set("--enable-benchmarking")
    flags.validate()
    flags.set(
        "--enable-benchmarking",
        "enable-field-trial-config",
        should_override=True)
    flags.validate()


class TestChromePreM139Flags(TestChromeFlags):
  CLASS = ChromePreM139Flags

  @override
  def test_disable_field_trials_flags(self):
    empty = self.CLASS()
    self.assertFalse(empty.field_trial_disable_flags)
    some_flags = self.CLASS(("--foo", "--bar"))
    self.assertFalse(some_flags.field_trial_disable_flags)
    field_trials = self.CLASS(("--disable-field-trial-config", "--foo"))
    self.assertEqual(
        str(field_trials.field_trial_disable_flags),
        "--disable-field-trial-config")
    field_trials.set("--enable-benchmarking")
    self.assertEqual(
        str(field_trials.field_trial_disable_flags),
        "--disable-field-trial-config --enable-benchmarking")
    field_trials.set(
        "--enable-benchmarking",
        "enable-field-trial-config",
        should_override=True)
    self.assertEqual(
        str(field_trials.field_trial_disable_flags),
        "--disable-field-trial-config")

  @override
  def test_set_enable_benchmarking_extension(self):
    flags = self.CLASS()
    flags.enable_benchmarking_api()
    self.assertEqual(str(flags), "--enable-benchmarking")

    flags = self.CLASS.parse("--foo")
    flags.enable_benchmarking_api()
    self.assertEqual(str(flags), "--foo --enable-benchmarking")

    flags = self.CLASS.parse("--enable-benchmarking")
    flags.enable_benchmarking_api()
    self.assertEqual(str(flags), "--enable-benchmarking")

    flags = self.CLASS.parse("--enable-benchmarking=enable-field-trial-config")
    flags.enable_benchmarking_api()
    self.assertEqual(
        str(flags), "--enable-benchmarking=enable-field-trial-config")

    flags = self.CLASS.parse("--enable-field-trial-config")
    flags.enable_benchmarking_api()
    self.assertEqual(
        str(flags), "--enable-field-trial-config "
        "--enable-benchmarking=enable-field-trial-config")

    flags = self.CLASS.parse("--foo --enable-field-trial-config --bar")
    flags.enable_benchmarking_api()
    self.assertEqual(
        str(flags), "--foo --enable-field-trial-config --bar "
        "--enable-benchmarking=enable-field-trial-config")

  @override
  def test_field_trial_flags(self):
    empty = self.CLASS()
    self.assertFalse(empty.field_trial_enable_flags)
    some_flags = self.CLASS(("--foo", "--bar"))
    self.assertFalse(some_flags.field_trial_enable_flags)
    field_trials = self.CLASS(("--enable-field-trial-config", "--foo"))
    self.assertEqual(
        str(field_trials.field_trial_enable_flags),
        "--enable-field-trial-config")
    field_trials.set("--enable-benchmarking")
    self.assertEqual(
        str(field_trials.field_trial_enable_flags),
        "--enable-field-trial-config")
    field_trials.set(
        "--enable-benchmarking",
        "enable-field-trial-config",
        should_override=True)
    self.assertEqual(
        str(field_trials.field_trial_enable_flags),
        "--enable-field-trial-config "
        "--enable-benchmarking=enable-field-trial-config")

  @override
  def test_conflict_field_trials_enable_benchmarking(self):
    flags = self.CLASS()
    flags.set("--enable-field-trial-config")
    flags.set("--enable-benchmarking")
    with self.assertRaisesRegex(argparse.ArgumentTypeError, "field-trial"):
      flags.validate()
    flags.set(
        "--enable-benchmarking",
        "enable-field-trial-config",
        should_override=True)
    flags.validate()


del TestFlags

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
