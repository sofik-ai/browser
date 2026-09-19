# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import json
import pathlib
import unittest
from argparse import ArgumentTypeError

from crossbench import path as pth
from crossbench import plt
from crossbench.cli.config.probe_list import ProbeListConfig
from crossbench.exception import ArgumentTypeMultiException
from crossbench.probes.all import TraceProcessorProbe
from crossbench.probes.trace_processor.constants import QUERIES_DIR
from crossbench.probes.trace_processor.trace_processor import \
    TraceProcessorQueryConfig
from tests import test_helper
from tests.crossbench.base import BaseCrossbenchTestCase, \
    CrossbenchFakeFsTestCase


def read_query_sql(name: str) -> str:
  return (QUERIES_DIR / name).read_text("utf-8")


class TraceProcessorProbeTestCase(unittest.TestCase):

  @unittest.skipIf(not plt.PLATFORM.which("trace_processor"),
                   "trace_processor not available")
  def test_parse_example_config(self):
    config_file = (
        test_helper.config_dir() / "doc/probe/trace_processor.config.hjson")
    self.assertTrue(config_file.is_file())
    probes = ProbeListConfig.parse(config_file).probes
    self.assertEqual(len(probes), 2)
    probe = probes[0]
    self.assertIsInstance(probe, TraceProcessorProbe)
    assert isinstance(probe, TraceProcessorProbe)
    queries = probe.queries
    self.assertEqual(len(queries), 2)
    speedometer_cpu_time_sql = read_query_sql("speedometer_cpu_time.sql")
    self.assertEqual(queries[0].name, "speedometer_cpu_time")
    self.assertEqual(queries[0].sql, speedometer_cpu_time_sql)

    inline_name = "my_query"
    inline_sql = "select dur from slice where slice.name = 'my_slice'"
    self.assertEqual(queries[1].name, inline_name)
    self.assertEqual(queries[1].sql, inline_sql)

    self.assertEqual(len(probe.module_paths), 2)
    self.assertRegex(
        str(probe.module_paths[0]),
        r".*\/crossbench\/probes\/perfetto\/trace_processor\/modules\/ext")
    self.assertEqual(str(probe.module_paths[1]), "/my_project/modules/ext")

    metric_definitions = probe.metric_definitions
    self.assertEqual(len(metric_definitions), 2)
    self.assertTrue("file_textproto_metric" in metric_definitions[0])
    self.assertTrue("inline_textproto_metric" in metric_definitions[1])

    summary_metrics = probe.summary_metrics
    # Should contain everything in 'metrics' plus 'summary_metrics'
    self.assertListEqual(
        list(summary_metrics),
        ["trace_stats", "file_textproto_metric", "inline_textproto_metric"])

  def test_query_config_duplicate_name_raises(self):
    with self.assertRaisesRegex(ArgumentTypeError,
                                "Unexpected duplicates in query names"):
      TraceProcessorProbe.parse_dict({
          "queries": [
              "loadline/benchmark_score",
              {
                  "name": "loadline_benchmark_score",
                  "sql": "select * from slice where slice.name = 'comment'",
              },
          ],
      })


class TraceProcessorProbeFakeFsTestCase(CrossbenchFakeFsTestCase):

  def test_custom_trace_processor_path(self):
    trace_processor_dir = pathlib.Path("/path/to")
    trace_processor_path = trace_processor_dir / "trace_processor_shell"
    trace_processor_dir.mkdir(parents=True)
    trace_processor_path.touch()

    config = TraceProcessorProbe.parse_dict({
        "trace_processor_bin": str(trace_processor_path),
        "queries": [],
    })

    self.assertEqual(str(config.trace_processor_bin), str(trace_processor_path))


class TraceProcessorQueryConfigTestCase(unittest.TestCase):

  def test_invalid_name_raises(self):
    with self.assertRaisesRegex(ArgumentTypeMultiException,
                                "sql query path does not exist"):
      TraceProcessorQueryConfig.parse("not_an_actual_query")

  def test_file_query(self):
    query = TraceProcessorQueryConfig.parse("speedometer_cpu_time")
    self.assertEqual(query.name, "speedometer_cpu_time")
    self.assertEqual(query.sql, read_query_sql("speedometer_cpu_time.sql"))

  def test_file_query_path(self):
    query = TraceProcessorQueryConfig.parse(
        pth.LocalPath("speedometer_cpu_time"))
    self.assertEqual(query.name, "speedometer_cpu_time")
    self.assertEqual(query.sql, read_query_sql("speedometer_cpu_time.sql"))

  def test_file_query_sql_suffix(self):
    query = TraceProcessorQueryConfig.parse("speedometer_cpu_time.sql")
    self.assertEqual(query.name, "speedometer_cpu_time")
    self.assertEqual(query.sql, read_query_sql("speedometer_cpu_time.sql"))

  def test_file_query_name_escaped(self):
    query = TraceProcessorQueryConfig.parse("loadline/benchmark_score")
    self.assertEqual(query.name, "loadline_benchmark_score")
    self.assertEqual(query.sql, read_query_sql("loadline/benchmark_score.sql"))

  def test_file_query_name_escaped_sql_suffix(self):
    query = TraceProcessorQueryConfig.parse("loadline/benchmark_score.sql")
    self.assertEqual(query.name, "loadline_benchmark_score")
    self.assertEqual(query.sql, read_query_sql("loadline/benchmark_score.sql"))

  def test_inline_query(self):
    query = TraceProcessorQueryConfig.parse({
        "name": "comment",
        "sql": "select * from slice where slice.name = 'comment'",
    })
    self.assertEqual(query.name, "comment")
    self.assertEqual(query.sql,
                     "select * from slice where slice.name = 'comment'")

  def test_inline_query_name_escaped(self):
    query = TraceProcessorQueryConfig.parse({
        "name": "//comment//",
        "sql": "select * from slice where slice.name = 'comment'",
    })
    self.assertEqual(query.name, "__comment__")
    self.assertEqual(query.sql,
                     "select * from slice where slice.name = 'comment'")

  def test_query_with_replacements(self):
    query = TraceProcessorQueryConfig.parse({
        "name": "comment",
        "sql": "'replace me'",
        "replacements": {
            "replace me": "new value"
        }
    })
    self.assertEqual(query.name, "comment")
    self.assertEqual(query.sql, "'new value'")


class TraceProcessorResultTestCase(BaseCrossbenchTestCase):

  def test_merge_browsers(self):
    probe: TraceProcessorProbe = TraceProcessorProbe.parse_dict({})

    browser = unittest.mock.MagicMock()
    browser.label = "browser"
    browser.unique_name = "browser"

    story = unittest.mock.MagicMock()
    story.name = "story"

    result1 = unittest.mock.MagicMock()
    csv1 = self.create_file("run1/query.csv", contents="foo,bar\n1,2\n")
    json1 = self.create_file(
        "run1/metric.json", contents=json.dumps({"foo": {
            "bar": 7
        }}))
    result1.csv_list = [csv1]
    result1.json_list = [json1]

    run1 = unittest.mock.MagicMock()
    run1.repetition = 0
    run1.results = {probe: result1}
    run1.browser = browser
    run1.story = story
    run1.temperature = "default"

    result2 = unittest.mock.MagicMock()
    csv2 = self.create_file("run2/query.csv", contents="foo,bar\n3,4\n")
    json2 = self.create_file(
        "run2/metric.json", contents=json.dumps({"foo": {
            "bar": 9
        }}))
    result2.csv_list = [csv2]
    result2.json_list = [json2]

    run2 = unittest.mock.MagicMock()
    run2.repetition = 1
    run2.results = {probe: result2}
    run2.browser = browser
    run2.story = story
    run2.temperature = "default"

    rep_group = unittest.mock.MagicMock()
    rep_group.story = story
    rep_group.runs = [run1, run2]

    story_group = unittest.mock.MagicMock()
    story_group.browser = browser
    story_group.repetitions_groups = [rep_group]

    browsers_run_group = unittest.mock.MagicMock()
    browsers_run_group.get_local_probe_result_path = unittest.mock.MagicMock(
        return_value=pth.LocalPath("result/"))
    browsers_run_group.story_groups = [story_group]
    browsers_run_group.runs = [run1, run2]

    merged_result = probe.merge_browsers(browsers_run_group)
    self.assertEqual(len(merged_result.csv_list), 1)
    self.assertEqual(len(merged_result.json_list), 1)

    expected_csv = ("foo,bar,cb_browser,cb_story,cb_temperature,cb_run\n"
                    "1,2,browser,story,default,0\n"
                    "3,4,browser,story,default,1\n")
    with merged_result.csv.open("r") as f:
      self.assertEqual(f.read(), expected_csv)

    with merged_result.json.open("r") as f:
      metrics = json.load(f)
    self.assertTrue("foo/bar" in metrics)
    self.assertTrue("values" in metrics["foo/bar"])
    self.assertEqual([7, 9], metrics["foo/bar"]["values"])


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
