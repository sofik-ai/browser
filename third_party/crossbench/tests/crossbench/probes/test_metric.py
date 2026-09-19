# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import json
import pathlib
import sys
import unittest

from crossbench.probes.metric import CSVFormatter, Metric, MetricsMerger
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase


class FormatMetricTestCase(unittest.TestCase):

  def test_no_stdev(self):
    self.assertEqual(Metric.format(100), "100")
    self.assertEqual(Metric.format(0), "0")
    self.assertEqual(Metric.format(1.5), "1.5")
    self.assertEqual(Metric.format(100, 0), "100")
    self.assertEqual(Metric.format(0, 0), "0")
    self.assertEqual(Metric.format(1.5, 0), "1.5")

  def test_stdev(self):
    self.assertEqual(Metric.format(100, 10), "100 ± 10%")
    self.assertEqual(Metric.format(100, 1), "100.0 ± 1.0%")
    self.assertEqual(Metric.format(100, 1.5), "100.0 ± 1.5%")
    self.assertEqual(Metric.format(100, 0.1), "100.00 ± 0.10%")
    self.assertEqual(Metric.format(100, 0.12), "100.00 ± 0.12%")
    self.assertEqual(Metric.format(100, 0.125), "100.00 ± 0.12%")

  def test_round_stdev(self):
    value = 100.123456789
    percent = value / 100
    self.assertEqual(Metric.format(value, percent * 10.1234), "100 ± 10%")
    self.assertEqual(Metric.format(value, percent * 1.2345), "100.1 ± 1.2%")
    self.assertEqual(Metric.format(value, percent * 0.12345), "100.12 ± 0.12%")
    self.assertEqual(
        Metric.format(value, percent * 0.012345), "100.123 ± 0.012%")
    self.assertEqual(
        Metric.format(value, percent * 0.0012345), "100.1235 ± 0.0012%")
    self.assertEqual(
        Metric.format(value, percent * 0.00012345), "100.12346 ± 0.00012%")


class MetricTestCase(unittest.TestCase):

  def test_empty(self):
    values = Metric()
    self.assertTrue(values.is_numeric)
    self.assertEqual(len(values), 0)

  def test_is_numeric(self):
    values = Metric([1, 2, 3, 4])
    self.assertTrue(values.is_numeric)
    values.append(5)
    self.assertTrue(values.is_numeric)
    values.append("6")
    self.assertFalse(values.is_numeric)

    values = Metric([1, 2, 3, "4"])
    self.assertFalse(values.is_numeric)

  def test_to_json_empty(self):
    json_data = Metric().to_json()
    self.assertDictEqual(json_data, {"values": []})

  def test_to_json_any(self):
    json_data = Metric(["a", "b", "c"]).to_json()
    self.assertDictEqual(json_data, {"values": ["a", "b", "c"]})

  def test_to_json_repeated(self):
    json_data = Metric(["a", "a", "a"]).to_json()
    self.assertEqual(json_data, "a")

  def test_to_json_numeric_repeated(self):
    json_data = Metric([1, 1, 1]).to_json()
    self.assertListEqual(json_data["values"], [1, 1, 1])
    self.assertEqual(json_data["min"], 1)
    self.assertEqual(json_data["max"], 1)
    self.assertEqual(json_data["geomean"], 1)
    self.assertEqual(json_data["average"], 1)
    self.assertEqual(json_data["stddevPercent"], 0)

  def test_to_json_numeric_average_0(self):
    json_data = Metric([-1, 0, 1]).to_json()
    self.assertListEqual(json_data["values"], [-1, 0, 1])
    self.assertEqual(json_data["min"], -1)
    self.assertEqual(json_data["max"], 1)
    self.assertEqual(json_data["geomean"], 0)
    self.assertEqual(json_data["average"], 0)
    self.assertEqual(json_data["stddevPercent"], 0)

  def test_sum(self):
    metric = Metric([1, 3])
    self.assertEqual(metric.sum, 4)
    self.assertIsInstance(metric.sum, int)

  def test_average(self):
    metric = Metric([1, 3])
    average = metric.average
    self.assertEqual(average, 2.0)
    self.assertIsInstance(average, float)
    self.assertEqual(Metric([0, 0]).average, 0)
    self.assertEqual(Metric([-1, -1]).average, -1)

  def test_geomean(self):
    metric = Metric([1, 4])
    geomean = metric.geomean
    self.assertEqual(geomean, 2.0)
    self.assertIsInstance(geomean, float)

    metric = Metric([1.1, 4.1])
    self.assertLess(geomean, metric.geomean)
    self.assertIsInstance(metric.geomean, float)

    self.assertEqual(Metric([-1, -1]).geomean, 0)
    self.assertEqual(Metric().geomean, 0)

  def test_geomean_overflow(self):
    metric = Metric([sys.maxsize] * 20)
    self.assertLess(0, metric.geomean)
    self.assertLess(abs(metric.geomean - float(sys.maxsize)), 10**5)


class MetricsMergerTestCase(CrossbenchFakeFsTestCase):

  def test_empty(self):
    merger = MetricsMerger()
    self.assertDictEqual(merger.to_json(), {})
    self.assertListEqual(CSVFormatter(merger).table, [])

  def test_add_flat(self):
    input_data = {"a": 1, "b": 2}
    merger = MetricsMerger()
    merger.add(input_data)
    data = merger.data
    self.assertEqual(len(data), 2)
    self.assertIsInstance(data["a"], Metric)
    self.assertIsInstance(data["b"], Metric)
    self.assertListEqual(data["a"].values, [1])
    self.assertListEqual(data["b"].values, [2])

    merger.add(input_data)
    data = merger.data
    self.assertEqual(len(data), 2)
    self.assertListEqual(data["a"].values, [1, 1])
    self.assertListEqual(data["b"].values, [2, 2])

  def test_add_hierarchical(self):
    input_data = {
        "a": {
            "a": {
                "a": 1,
                "b": 2
            }
        },
        "b": 2,
    }
    merger = MetricsMerger()
    merger.add(input_data)
    data = merger.data
    self.assertListEqual(list(data.keys()), ["a/a/a", "a/a/b", "b"])
    self.assertIsInstance(data["a/a/a"], Metric)
    self.assertIsInstance(data["a/a/b"], Metric)
    self.assertIsInstance(data["b"], Metric)

  def test_repeated_numeric(self):
    merger = MetricsMerger()
    input_data = {
        "a": {
            "aa": 1,
            "ab": 2
        },
        "b": 3,
        "c": {
            "cc": {
                "ccc": 4
            }
        },
    }
    merger.add(input_data)
    merger.add(input_data)
    data = merger.data
    self.assertEqual(len(data), 4)
    self.assertListEqual(data["a/aa"].values, [1, 1])
    self.assertListEqual(data["a/ab"].values, [2, 2])
    self.assertListEqual(data["b"].values, [3, 3])
    self.assertListEqual(data["c/cc/ccc"].values, [4, 4])
    json_data = merger.to_json()
    self.assertListEqual(json_data["a/aa"]["values"], [1, 1])
    self.assertListEqual(json_data["a/ab"]["values"], [2, 2])
    self.assertListEqual(json_data["b"]["values"], [3, 3])
    self.assertListEqual(json_data["c/cc/ccc"]["values"], [4, 4])

  def test_repeated_non_numeric(self):
    merger = MetricsMerger()
    input_data = {"a": {"aa": "a.aa", "ab": "a.ab"}}
    merger.add(input_data)
    merger.add(input_data)
    data = merger.data
    self.assertEqual(len(data), 2)
    self.assertListEqual(data["a/aa"].values, ["a.aa", "a.aa"])
    self.assertListEqual(data["a/ab"].values, ["a.ab", "a.ab"])
    json_data = merger.to_json()
    self.assertDictEqual(json_data, {"a/aa": "a.aa", "a/ab": "a.ab"})

  def test_repeated_non_numeric_nested(self):
    merger = MetricsMerger()
    input_data = {"a": {"aa": "a.aa", "ab": {"cccA": "cccA", "cccB": "cccB"}}}
    merger.add(input_data)
    merger.add(input_data)
    data = merger.data
    self.assertEqual(len(data), 3)
    self.assertListEqual(data["a/aa"].values, ["a.aa", "a.aa"])
    self.assertListEqual(data["a/ab/cccA"].values, ["cccA", "cccA"])
    self.assertListEqual(data["a/ab/cccB"].values, ["cccB", "cccB"])
    json_data = merger.to_json()
    self.assertDictEqual(json_data, {
        "a/aa": "a.aa",
        "a/ab/cccA": "cccA",
        "a/ab/cccB": "cccB"
    })

  BASIC_NESTED_DATA = {
      "a": {
          "a": {
              "a": 1,
              "b": 2
          }
      },
      "b": 3,
  }

  def test_custom_key_fn(self):

    def under_join(segments):
      return "_".join(segments)

    merger = MetricsMerger(key_fn=under_join)
    merger.add(self.BASIC_NESTED_DATA)
    data = merger.data
    self.assertListEqual(list(data.keys()), ["a_a_a", "a_a_b", "b"])

  def test_merge_serialized_same(self):
    merger = MetricsMerger()
    merger.add(self.BASIC_NESTED_DATA)
    self.assertListEqual(list(merger.data.keys()), ["a/a/a", "a/a/b", "b"])
    path_a = pathlib.Path("merged_a.json")
    path_b = pathlib.Path("merged_b.json")
    with path_a.open("w", encoding="utf-8") as f:
      json.dump(merger.to_json(), f)
    with path_b.open("w", encoding="utf-8") as f:
      json.dump(merger.to_json(), f)

    merger = MetricsMerger.merge_json_list([path_a, path_b],
                                           merge_duplicate_paths=True)
    data = merger.data
    self.assertListEqual(list(data.keys()), ["a/a/a", "a/a/b", "b"])
    self.assertListEqual(data["a/a/a"].values, [1, 1])
    self.assertListEqual(data["a/a/b"].values, [2, 2])
    self.assertListEqual(data["b"].values, [3, 3])

    # All duplicate entries are ignored
    merger = MetricsMerger.merge_json_list([path_a, path_b],
                                           merge_duplicate_paths=False)
    self.assertListEqual(list(merger.data.keys()), [])

  def test_merge_serialized_different_data(self):
    merger_a = MetricsMerger({"a": {"a": 1}})
    merger_b = MetricsMerger({"a": {"b": 2}})
    path_a = pathlib.Path("merged_a.json")
    path_b = pathlib.Path("merged_b.json")
    with path_a.open("w", encoding="utf-8") as f:
      json.dump(merger_a.to_json(), f)
    with path_b.open("w", encoding="utf-8") as f:
      json.dump(merger_b.to_json(), f)

    merger = MetricsMerger.merge_json_list([path_a, path_b],
                                           merge_duplicate_paths=True)
    data = merger.data
    self.assertListEqual(list(data.keys()), ["a/a", "a/b"])
    self.assertListEqual(data["a/a"].values, [1])
    self.assertListEqual(data["a/b"].values, [2])

    merger = MetricsMerger.merge_json_list([path_a, path_b],
                                           merge_duplicate_paths=False)
    data = merger.data
    self.assertListEqual(list(data.keys()), ["a/a", "a/b"])

  def test_to_csv_no_path(self) -> None:
    merger = MetricsMerger()
    merger.add(self.BASIC_NESTED_DATA)
    csv = CSVFormatter(
        merger, lambda metric: round(metric.geomean, 10),
        include_parts=False).table
    self.assertListEqual(csv, [
        ("a/a/a", 1.0),
        ("a/a/b", 2.0),
        ("b", 3.0),
    ])

  def test_to_csv_path(self) -> None:
    merger = MetricsMerger()
    merger.add(self.BASIC_NESTED_DATA)
    csv = CSVFormatter(
        merger, lambda metric: round(metric.geomean, 10),
        include_parts=True).table
    self.assertListEqual(csv, [
        ("a/a/a", "a", "a", "a", 1.0),
        ("a/a/b", "a", "a", "b", 2.0),
        ("b", "b", "", "", 3.0),
    ])

  def test_to_csv_header(self) -> None:
    merger = MetricsMerger()
    merger.add({"a/b/c": 1, "d": 2})
    headers = [
        ("a", "custom", "header", "line"),
        (1, 2, 3, 4, 5),
    ]
    csv = CSVFormatter(
        merger,
        lambda metric: metric.geomean,
        headers=headers,
        include_parts=True).table
    self.assertListEqual(csv, [
        ("a", "", "", "", "custom", "header", "line"),
        (1, "", "", "", 2, 3, 4, 5),
        ("a/b/c", "a", "b", "c", 1.0),
        ("d", "d", "", "", 2.0),
    ])


class CSVFormatterTestCase(unittest.TestCase):

  def test_format(self):
    metrics = MetricsMerger({
        "Total/average": 10,
        "Total/score": 20,
        "cdjs/average": 30,
        "cdjs/score": 40,
    })
    table = CSVFormatter(metrics,
                         lambda metric: round(metric.geomean, 10)).table
    self.assertSequenceEqual(table, [
        ("Total/average", "Total", "average", 10.0),
        ("Total/score", "Total", "score", 20.0),
        ("cdjs/average", "cdjs", "average", 30.0),
        ("cdjs/score", "cdjs", "score", 40.0),
    ])


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
