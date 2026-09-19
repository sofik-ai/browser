# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse
import unittest

import hjson
import pytest

from crossbench.cli.config.probe_list import ProbeListConfig
from crossbench.probes.chrome_histograms import ChromeHistogramMetric, \
    ChromeHistogramSample, ChromeHistogramsProbe, parse_histogram_metrics
from tests import test_helper
from tests.crossbench.probes.helper import GenericProbeTestCase


class ChromeHistogramProbeTestCase(GenericProbeTestCase):
  HISTOGRAM_NAME = "test"

  BASELINE_HEADER = (
      "Histogram: test recorded 50 samples, mean = 57.4 (flags = 0x41)")

  BASELINE_BODY = """0  -----O                     (5 = 10.0%) {0.0%}
10 ... 
20 -----O                     (5 = 10.0%) {10.0%}
30 -------O                   (7 = 14.0%) {20.0%}
40 -----O                     (5 = 10.0%) {34.0%}
50 -----O                     (5 = 10.0%) {44.0%}
60 -----O                     (5 = 10.0%) {54.0%}
70 ----O                      (4 = 8.0%) {64.0%}
80 --O                        (2 = 4.0%) {72.0%}
90 ------------O              (12 = 24.0%) {76.0%}
"""  # noqa: W291

  DELTA_HEADER = (
      "Histogram: test recorded 100 samples, mean = 52.11 (flags = 0x41)")
  DELTA_BODY = """0  ------------O              (12 = 12.0%) {0.0%}
10 -------O                   (7 = 7.0%) {12.0%}
20 -----------O               (11 = 11.0%) {19.0%}
30 ---------O                 (9 = 9.0%) {30.0%}
40 --------------O            (14 = 14.0%) {39.0%}
50 ------O                    (6 = 6.0%) {53.0%}
60 --------O                  (8 = 8.0%) {59.0%}
70 --------O                  (8 = 8.0%) {67.0%}
80 -------O                   (7 = 7.0%) {75.0%}
90 ------------------O        (18 = 18.0%) {82.0%}
"""

  def _sample_json(self, name: str, header: str, body: str) -> dict:
    return {
        "name": name,
        "header": header,
        "body": body,
    }

  def _baseline(self) -> ChromeHistogramSample:
    json = self._sample_json(self.HISTOGRAM_NAME, self.BASELINE_HEADER,
                             self.BASELINE_BODY)
    return ChromeHistogramSample.from_json(json)

  def _delta(self) -> ChromeHistogramSample:
    json = self._sample_json(self.HISTOGRAM_NAME, self.DELTA_HEADER,
                             self.DELTA_BODY)
    return ChromeHistogramSample.from_json(json)

  def test_parse_histogram_metrics_invalid(self):
    with self.assertRaisesRegex(argparse.ArgumentTypeError,
                                "'invalid.metric' 'foo' is not a valid metric"):
      parse_histogram_metrics({"invalid.metric": ["foo"]})
    with self.assertRaisesRegex(
        argparse.ArgumentTypeError,
        "'invalid.metric' 'p101' is not a valid percentile"):
      parse_histogram_metrics({"invalid.metric": ["p101"]})

  def _parse_one_metric(self, histogram_name: str,
                        metric_type: str) -> ChromeHistogramMetric:
    metrics = parse_histogram_metrics({histogram_name: [metric_type]})
    if len(metrics) != 1:
      raise ValueError(f"expected exactly 1 metric, got {len(metrics)}")
    return metrics[0]

  def test_count(self):
    metric = self._parse_one_metric(self.HISTOGRAM_NAME, "count")
    value = metric.compute(self._delta(), self._baseline())
    self.assertEqual(50, value)

  def test_mean(self):
    metric = self._parse_one_metric(self.HISTOGRAM_NAME, "mean")
    value = metric.compute(self._delta(), self._baseline())
    self.assertEqual(value, 46.82)

  def test_mean_no_baseline(self):
    metric = self._parse_one_metric(self.HISTOGRAM_NAME, "mean")
    value = metric.compute(self._delta(),
                           ChromeHistogramSample(self.HISTOGRAM_NAME))
    self.assertEqual(value, 52.11)

  def test_percentile(self):
    metrics = parse_histogram_metrics(
        {self.HISTOGRAM_NAME: ["p25", "p50", "p75", "p90", "p99"]})
    values = [m.compute(self._delta(), self._baseline()) for m in metrics]
    self.assertListEqual([16.875, 43, 75, 90, 90], values)

  def test_sample_invalid_header(self):
    with pytest.raises(
        argparse.ArgumentTypeError,
        match="test histogram header has invalid data: foo"):
      ChromeHistogramSample.from_json(
          self._sample_json("test", "foo", self.BASELINE_BODY))

  def test_sample_invalid_body(self):
    with pytest.raises(
        argparse.ArgumentTypeError,
        match="test histogram body line 11 has invalid data: bar"):
      ChromeHistogramSample.from_json(
          self._sample_json("test", self.BASELINE_HEADER,
                            self.BASELINE_BODY + "bar\n"))

  def test_sample_no_flags_in_header(self):
    no_flags_sample = ChromeHistogramSample.from_json(
        self._sample_json("test",
                          "Histogram: test recorded 50 samples, mean = 57.4",
                          self.BASELINE_BODY))
    self.assertEqual(0, no_flags_sample.flags)

  def test_sample_count_header_body_mismatch(self):
    with pytest.raises(
        Exception,
        match="Histogram test has 50 total samples, but buckets add to 100"):
      ChromeHistogramSample.from_json(
          self._sample_json("test", self.BASELINE_HEADER, self.DELTA_BODY))

  def test_sample_bucket_max(self):
    self.assertEqual(10, self._delta().bucket_max(0))
    self.assertEqual(20, self._delta().bucket_max(10))
    self.assertEqual(None, self._delta().bucket_max(90))

  def test_sample_diff_percentile_invalid(self):
    with pytest.raises(Exception, match="-1 is not a valid percentile"):
      self._delta().diff_percentile(self._baseline(), -1)

    with pytest.raises(
        Exception, match="test can not compute percentile without any samples"):
      self._delta().diff_percentile(self._delta(), 50)

  def test_sample_diff_mean_invalid(self):
    with pytest.raises(
        Exception, match="test can not compute mean without any samples"):
      self._delta().diff_mean(self._delta())

    no_mean = ChromeHistogramSample.from_json(
        self._sample_json("test",
                          "Histogram: test recorded 50 samples (flags = 0x41)",
                          self.BASELINE_BODY))
    with pytest.raises(
        Exception, match="test has no mean reported, is it an enum histogram?"):
      self._delta().diff_mean(no_mean)

  def test_sample_name(self):
    self.assertEqual(self.HISTOGRAM_NAME, self._delta().name)

  @unittest.skipIf(hjson.__name__ != "hjson", "hjson not available")
  def test_parse_example_config(self):
    config_file = (
        test_helper.config_dir() / "doc/probe/chrome_histograms.hjson")
    self.fs.add_real_file(config_file)
    self.assertTrue(config_file.is_file())
    probes = ProbeListConfig.parse(config_file).probes
    self.assertEqual(len(probes), 1)
    probe = probes[0]
    self.assertIsInstance(probe, ChromeHistogramsProbe)
    isinstance(probe, ChromeHistogramsProbe)
    self.assertListEqual([metric.name for metric in probe.metrics], [
        "WebVitals.FirstContentfulPaint3_count",
        "WebVitals.FirstContentfulPaint3_mean",
        "WebVitals.FirstContentfulPaint3_p50",
        "WebVitals.FirstContentfulPaint3_p90",
        "Startup.FirstWebContents.NonEmptyPaint3_count",
        "Startup.FirstWebContents.NonEmptyPaint3_mean",
        "Startup.FirstWebContents.NonEmptyPaint3_p50",
        "Startup.FirstWebContents.NonEmptyPaint3_p90",
    ])
    self.assertEqual(probe.use_baseline, True)

  def test_parse_config(self):
    probe: ChromeHistogramsProbe = ChromeHistogramsProbe.parse_dict({
        "metrics": {
            "PageLoad.PaintTiming.NavigationToFirstContentfulPaint": ["mean"]
        },
        "baseline": False,
    })
    self.assertListEqual([metric.name for metric in probe.metrics], [
        "PageLoad.PaintTiming.NavigationToFirstContentfulPaint_mean",
    ])
    self.assertEqual(probe.use_baseline, False)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
