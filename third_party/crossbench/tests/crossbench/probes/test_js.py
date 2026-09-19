# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

from typing import Final
from unittest import mock

from crossbench import path as pth
from crossbench.benchmarks.loading.config.blocks import ActionBlock
from crossbench.benchmarks.loading.page.live import InteractivePage, LivePage
from crossbench.cli.config.probe_list import ProbeListConfig
from crossbench.probes.js import JSProbe, JSProbeContext
from crossbench.probes.results import EmptyProbeResult
from crossbench.runner.run import Run
from tests import test_helper
from tests.crossbench.probes.helper import GenericProbeTestCase

JS_PROBE_EXAMPLE_CONFIG: Final = test_helper.config_dir(
) / "doc/probe/js.config.hjson"


class JSProbeTestCase(GenericProbeTestCase):

  def test_parse_example_config(self):
    # Wrap in pyfakefs path again
    config_file = pth.LocalPath(JS_PROBE_EXAMPLE_CONFIG)
    self.fs.add_real_file(config_file)
    self.assertTrue(config_file.is_file())
    probes = ProbeListConfig.parse(config_file).probes
    self.assertEqual(len(probes), 1)
    probe = probes[0]
    self.assertIsInstance(probe, JSProbe)
    assert isinstance(probe, JSProbe)
    self.assertTrue(probe.metric_js)

  def test_help_items(self):
    self.fs.add_real_file(JS_PROBE_EXAMPLE_CONFIG)
    help_text_items = JSProbe.config_parser().help_text_items
    help = "\n".join(map(str, help_text_items))
    self.assertIn(JSProbe.NAME, help)
    self.assertIn("example config", help)
    self.assertIn(str(JS_PROBE_EXAMPLE_CONFIG), help)

  def test_parse_config(self):
    config = {
        "setup": "globalThis.metrics = {};",
        "js": "return globalThis.metrics;",
    }
    probe = JSProbe.parse_dict(config)
    self.assertIsInstance(probe, JSProbe)
    self.assertEqual(probe.setup_js, "globalThis.metrics = {};")
    self.assertEqual(probe.metric_js, "return globalThis.metrics;")

  def test_parse_str(self):
    probe = JSProbe.parse_str("return globalThis.metrics2;")
    self.assertIsNone(probe.setup_js)
    self.assertEqual(probe.metric_js, "return globalThis.metrics2;")

  def test_simple_loading_case(self):
    config = {
        "setup": "globalThis.metrics = {};",
        "js": "return globalThis.metrics;",
    }
    probe = JSProbe.parse_dict(config)
    stories = [
        LivePage("google", "https://google.com"),
        LivePage("amazon", "https://amazon.com")
    ]
    repetitions = 2
    runner = self.create_runner(
        stories,
        js_side_effects=[
            # setup:
            None,
            # js:
            {
                "metric1": 1.1,
                "metric2": 2.2
            }
        ],
        repetitions=repetitions,
        separate=True,
        throw=True)
    runner.attach_probe(probe)
    runner.run()
    self.assertTrue(runner.is_success)
    js_result_files = list(runner.out_dir.glob(f"**/{probe.name}.json"))
    # One file per story repetition
    result_count = len(self.browsers) * len(stories) * repetitions
    # One merged result per story
    result_count += len(self.browsers) * len(stories)
    # One merged results per browser
    result_count += len(self.browsers)
    # One top-level
    result_count += 1
    self.assertEqual(len(js_result_files), result_count)

    (story_data, repetitions_data, stories_data,
     browsers_data) = self.get_non_empty_json_results(runner, probe)
    self.assertIsInstance(story_data, dict)
    self.assertIsInstance(repetitions_data, dict)
    self.assertIsInstance(stories_data, dict)
    self.assertIsInstance(browsers_data, dict)
    # TODO: check probe result contents

  def test_merge_with_missing_results(self):
    config = {
        "setup": "globalThis.metrics = {};",
        "js": "return globalThis.metrics;",
    }
    probe = JSProbe.parse_dict(config)
    stories = [
        LivePage("google", "https://google.com"),
        LivePage("amazon", "https://amazon.com")
    ]
    repetitions = 2
    runner = self.create_runner(
        stories,
        js_side_effects=[
            # setup:
            None,
            # js:
            {
                "metric1": 1.1,
                "metric2": 2.2
            }
        ],
        repetitions=repetitions,
        separate=True,
        throw=True)
    with mock.patch.object(JSProbeContext, "teardown") as mock_teardown:
      mock_teardown.side_effect = EmptyProbeResult
      runner.attach_probe(probe)
      runner.run()

    self.assertTrue(runner.is_success)
    js_result_files = list(runner.out_dir.glob(f"**/{probe.name}.json"))
    # All results per story repetition are missing
    result_count = 0
    # One merged result per story
    result_count += len(self.browsers) * len(stories)
    # One merged results per browser
    result_count += len(self.browsers)
    # One top-level
    result_count += 1
    self.assertEqual(len(js_result_files), result_count)

  def test_invoke(self):
    config = {
        "js": "return {'finalValue': 2};",
    }
    probe = JSProbe.parse_dict(config)
    blocks = (ActionBlock.parse_sequence([{
        "action": "probe",
        "probe": "js",
        "kwargs": {
            "js": "return {'intermediateValue': 1};"
        }
    }]),)
    page = InteractivePage(
        name="test_page",
        blocks=blocks,
    )
    stories = [page]
    runner = self.create_runner(
        stories,
        js_side_effects=[
            # probe invoke js:
            {
                "intermediateValue": 1
            },
            # probe teardown js:
            {
                "finalValue": 2
            }
        ],
        repetitions=1,
        throw=True)
    runner.attach_probe(probe)
    runner.run()
    self.assertTrue(runner.is_success)

    (story_data, repetitions_data, stories_data,
     browsers_data) = self.get_non_empty_json_results(runner, probe)
    self.assertEqual(story_data, {"intermediateValue": 1, "finalValue": 2})

  def test_update_metrics(self):
    probe = JSProbe.config_parser().parse({})
    mock_run = mock.MagicMock(spec=Run)
    context = JSProbeContext(probe, mock_run)

    context._update_metrics({"a": 1})
    self.assertDictEqual(context._json_data, {"a": 1})

    context._update_metrics({"b": 2})
    self.assertDictEqual(context._json_data, {"a": 1, "b": 2})

    with mock.patch("logging.debug") as logging_mock:
      context._update_metrics({"a": 3})
    logging_mock.assert_called_once()
    self.assertDictEqual(context._json_data, {"a": 3, "b": 2})


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
