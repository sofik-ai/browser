# Copyright 2022 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import csv
import pathlib
import unittest
from typing import Optional

from crossbench.probes import helper
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase


class TestMergeCSV(CrossbenchFakeFsTestCase):

  def merge(self,
            *args,
            delimiter: str = "\t",
            headers: Optional[list[str]] = None,
            row_header_len: int = 1):
    csv_files = []
    for index, content in enumerate(args):
      csv_file = pathlib.Path(f"test.{index}.csv")
      with csv_file.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter=delimiter).writerows(content)
      csv_files.append(csv_file)
    return helper.merge_csv(
        csv_files,
        delimiter=delimiter,
        headers=headers,
        row_header_len=row_header_len)

  def test_merge_single(self):
    data = [
        ["Metric", "Run1"],
        ["Total", "200"],
    ]
    for delimiter in ["\t", ","]:
      merged = self.merge(data, delimiter=delimiter)
      self.assertListEqual(merged, data)

  def test_merge_single_padding(self):
    data = [
        ["Metric", "Run1", "Run2"],
        ["marker"],
        ["Total", "200", "300"],
    ]
    merged = self.merge(data, headers=None)
    self.assertListEqual(merged, [
        ["Metric", "Run1", "Run2"],
        ["marker", None, None],
        ["Total", "200", "300"],
    ])

  def test_merge_single_file_header(self):
    data = [
        ["Total", "200"],
    ]
    for delimiter in ["\t", ","]:
      merged = self.merge(data, delimiter=delimiter, headers=["custom"])
      self.assertListEqual(merged, [
          [None, "custom"],
          ["Total", "200"],
      ])

  def test_merge_two_padding(self):
    data_1 = [
        ["marker"],
        ["Total", "101", "102"],
    ]
    data_2 = [
        ["marker"],
        ["Total", "201"],
    ]
    merged = self.merge(data_1, data_2, headers=["col_1", "col_2"])
    self.assertListEqual(merged, [
        [None, "col_1", None, "col_2"],
        ["marker", None, None, None],
        ["Total", "101", "102", "201"],
    ])

  def test_merge_two_long_row_header(self):
    data_1 = [
        ["full-marker", "marker"],
        ["Full/Total", "Total", "101", "102"],
    ]
    data_2 = [
        ["full-marker", "marker"],
        ["Full/Total", "Total", "201"],
    ]
    merged = self.merge(
        data_1, data_2, headers=["col_1", "col_2"], row_header_len=2)
    self.assertListEqual(merged, [
        [None, None, "col_1", None, "col_2"],
        ["full-marker", "marker", None, None, None],
        ["Full/Total", "Total", "101", "102", "201"],
    ])

  def test_merge_two_disjoint_consecutive(self):
    data_1 = [
        ["marker"],
        ["A", "101", "102"],
        ["B", "101", "102"],
    ]
    data_2 = [
        ["marker"],
        ["C", "201"],
        ["D", "201"],
    ]
    merged = self.merge(data_1, data_2)
    self.assertListEqual(merged, [
        ["marker", None, None, None],
        ["A", "101", "102", None],
        ["B", "101", "102", None],
        ["C", None, None, "201"],
        ["D", None, None, "201"],
    ])

  def test_merge_two_disjoint_interleaved(self):
    data_1 = [
        ["marker"],
        ["B", "101", "102"],
        ["C", "201"],
    ]
    data_2 = [
        ["marker"],
        ["A", "101", "102"],
        ["D", "201"],
    ]
    merged = self.merge(data_1, data_2)
    self.assertListEqual(merged, [
        ["marker", None, None, None, None],
        ["A", None, None, "101", "102"],
        ["B", "101", "102", None, None],
        ["C", "201", None, None, None],
        ["D", None, None, "201", None],
    ])

  def test_merge_two_missing(self):
    data_1 = [
        ["marker"],
        ["Total-A0"],
        ["Total-A1", "101"],
        ["Total-A2", "111", "112"],
        ["Total-A3", "301", "302"],
        ["Total-B", "01"],
        ["Total-X", "201", "202"],
    ]
    data_2 = [
        ["marker"],
        ["Total-B", "02"],
        ["Total-C1", "401", "402"],
        ["Total-C2", "501"],
        ["Total-C3", "601", "602"],
        ["Total-C4", "701"],
        ["Total-X", "203"],
    ]
    merged = self.merge(data_1, data_2, headers=["col_1", "col_2"])
    self.assertListEqual(merged, [
        [None, "col_1", None, "col_2", None],
        ["marker", None, None, None, None],
        ["Total-A0", None, None, None, None],
        ["Total-A1", "101", None, None, None],
        ["Total-A2", "111", "112", None, None],
        ["Total-A3", "301", "302", None, None],
        ["Total-B", "01", None, "02", None],
        ["Total-C1", None, None, "401", "402"],
        ["Total-C2", None, None, "501", None],
        ["Total-C3", None, None, "601", "602"],
        ["Total-C4", None, None, "701", None],
        ["Total-X", "201", "202", "203", None],
    ])

  def test_merge_two_duplicate(self):
    data_1 = [
        ["A", "101"],
        ["A", "201"],
    ]
    data_2 = [
        ["A", "301"],
        ["A", "401"],
    ]
    merged = self.merge(data_1, data_2)
    self.assertListEqual(merged, [
        ["A", "101", "301"],
        ["A", "201", "401"],
    ])

  def test_merge_two_partial_duplicate(self):
    data_1 = [
        ["marker"],
        ["A", "101"],
        ["A", "201"],
        ["B", "B01"],
    ]
    data_2 = [
        ["marker"],
        ["A", "301"],
        ["A", "401"],
        ["C", "C01"],
    ]
    merged = self.merge(data_1, data_2)
    self.assertListEqual(merged, [
        ["marker", None, None],
        ["A", "101", "301"],
        ["A", "201", "401"],
        ["B", "B01", None],
        ["C", None, "C01"],
    ])


class TestFlatten(unittest.TestCase):

  def flatten(self, *data, key_fn=None, sort: bool = True):
    return helper.Flatten(*data, key_fn=key_fn, sort=sort).data

  def test_single(self):
    data = {
        "a": 1,
        "b": 2,
    }
    flattened = self.flatten(data)
    self.assertDictEqual(flattened, data)

  def test_single_sort(self):
    data = {
        "b": 2,
        "a": 1,
    }
    flattened_keys = tuple(self.flatten(data, sort=True).keys())
    self.assertTupleEqual(flattened_keys, ("a", "b"))
    flattened_keys = tuple(self.flatten(data, sort=False).keys())
    self.assertTupleEqual(flattened_keys, ("b", "a"))

  def test_single_nested(self):
    data = {
        "a": 1,
        "b": {
            "a": 2,
            "b": 3
        },
    }
    flattened = self.flatten(data)
    self.assertDictEqual(flattened, {"a": 1, "b/a": 2, "b/b": 3})

  def test_single_key_fn(self):
    data = {
        "a": 1,
        "b": 2,
    }
    flattened = self.flatten(data, key_fn=lambda path: "prefix_" + path[0])
    self.assertDictEqual(flattened, {
        "prefix_a": 1,
        "prefix_b": 2,
    })

  def test_single_key_fn_filtering(self):
    data = {
        "a": 1,
        "b": 2,
    }
    flattened = self.flatten(
        data,
        key_fn=lambda path: None if path[0] == "a" else "prefix_" + path[0])
    self.assertDictEqual(flattened, {
        "prefix_b": 2,
    })

  def test_single_nested_key_fn(self):
    data = {
        "a": 1,
        "b": {
            "a": 2,
            "b": 3
        },
    }
    with self.assertRaises(ValueError):
      # Fail on duplicate entries
      self.flatten(data, key_fn=lambda path: "prefix_" + path[0])

    flattened = self.flatten(
        data, key_fn=lambda path: "prefix_" + "/".join(path))
    self.assertDictEqual(flattened, {
        "prefix_a": 1,
        "prefix_b/a": 2,
        "prefix_b/b": 3,
    })

  def test_single_nested_key_fn_filtering(self):
    data = {
        "a": 1,
        "b": {
            "a": 2,
            "b": 3
        },
    }
    flattened = self.flatten(
        data,
        key_fn=lambda path: None
        if path[-1] == "a" else "prefix_" + "/".join(path))
    self.assertDictEqual(flattened, {
        "prefix_b/b": 3,
    })

  def test_multiple_flat(self):
    data_1 = {
        "a": 1,
        "b": 2,
    }
    with self.assertRaises(ValueError):
      # duplicate entries
      self.flatten(data_1, data_1)
    data_2 = {
        "c": 3,
        "d": 4,
    }
    flattened = self.flatten(data_1, data_2)
    self.assertDictEqual(flattened, {
        "a": 1,
        "b": 2,
        "c": 3,
        "d": 4,
    })

  def test_null(self):
    data = {
        "a": 1,
        "b": None,
    }
    flattened = self.flatten(data)
    self.assertDictEqual(flattened, {
        "a": 1,
    })


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
