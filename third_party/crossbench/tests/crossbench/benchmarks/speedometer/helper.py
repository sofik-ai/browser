# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import abc
import argparse
import copy
import csv
import datetime as dt
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Sequence, Type
from unittest import mock

from typing_extensions import override

from crossbench.benchmarks.speedometer.speedometer_3 import MeasurementMethod
from crossbench.browsers.viewport import Viewport
from crossbench.env.runner_env import EnvConfig, ValidationMode
from crossbench.runner.runner import Runner
from tests.crossbench.benchmarks import helper

if TYPE_CHECKING:
  from crossbench.action_runner.config import ActionRunnerConfig
  from crossbench.benchmarks.speedometer.speedometer import \
      SpeedometerBenchmark, SpeedometerProbe, SpeedometerProbeContext, \
      SpeedometerStory
  from crossbench.stories.story import Story
  from crossbench.types import Json
  from tests.crossbench.mock_browser import MockBrowser


class SpeedometerBaseTestCase(
    helper.PressBaseBenchmarkTestCase, metaclass=abc.ABCMeta):

  @property
  @abc.abstractmethod
  @override
  def benchmark_cls(self) -> Type[SpeedometerBenchmark]:
    pass

  @property
  @abc.abstractmethod
  @override
  def story_cls(self) -> Type[SpeedometerStory]:
    pass

  @property
  @abc.abstractmethod
  def probe_cls(self) -> Type[SpeedometerProbe]:
    pass

  @property
  @abc.abstractmethod
  def probe_context_cls(self) -> Type[SpeedometerProbeContext]:
    pass

  @property
  @abc.abstractmethod
  def name(self) -> str:
    pass

  @property
  def name_all(self) -> str:
    # Override if default() != all() stories.
    return self.name

  @dataclass
  class Namespace(argparse.Namespace):
    stories = "default"
    iterations: int = 10
    separate: bool = False
    custom_benchmark_url: str | None = None
    action_runner_config: ActionRunnerConfig | None = None

  def test_iterations_kwargs(self):
    args = self.Namespace()
    self.benchmark_cls.from_cli_args(args)
    with self.assertRaises(argparse.ArgumentTypeError):
      args.iterations = "-10"
      self.benchmark_cls.from_cli_args(args)
    with self.assertRaises(argparse.ArgumentTypeError):
      args.iterations = "1234"
      benchmark = self.benchmark_cls.from_cli_args(args)
    args.iterations = 1234
    benchmark = self.benchmark_cls.from_cli_args(args)
    for story in benchmark.stories:
      assert isinstance(story, self.story_cls)
      self.assertEqual(story.iterations, 1234)

  def test_story_filtering_cli_args_all_separate(self):
    stories = self.story_cls.all(separate=True)
    args = self.Namespace()
    args.stories = "all"
    args.separate = True
    stories_all = self.benchmark_cls.stories_from_cli_args(args)
    self.assertListEqual(
        [story.name for story in stories],
        [story.name for story in stories_all],
    )

  def test_story_filtering_cli_args_all(self):
    stories = self.story_cls.all(separate=False)
    args = self.Namespace()
    args.stories = "all"
    args.custom_benchmark_url = self.story_cls.URL_LOCAL
    args.separate = False
    args.iterations = 503
    stories_all = self.benchmark_cls.stories_from_cli_args(args)
    self.assertEqual(len(stories), 1)
    self.assertEqual(len(stories_all), 1)
    story = stories[0]
    assert isinstance(story, self.story_cls)
    self.assertEqual(story.name, self.name_all)
    story = stories_all[0]
    assert isinstance(story, self.story_cls)
    self.assertEqual(story.name, self.name_all)
    self.assertEqual(story.url, self.story_cls.URL_LOCAL)
    self.assertEqual(story.iterations, 503)

    args.custom_benchmark_url = None
    args.separate = False
    args.iterations = 701
    stories_all = self.benchmark_cls.stories_from_cli_args(args)
    self.assertEqual(len(stories_all), 1)
    story = stories_all[0]
    assert isinstance(story, self.story_cls)
    self.assertEqual(story.name, self.name_all)
    self.assertEqual(story.url, self.story_cls.URL)
    self.assertEqual(story.iterations, 701)

  def test_story_filtering(self):
    with self.assertRaises(ValueError):
      self.story_cls.from_names([])
    stories = self.story_cls.default(separate=False)
    self.assertEqual(len(stories), 1)

    with self.assertRaises(ValueError):
      self.story_cls.from_names([], separate=True)
    stories = self.story_cls.default(separate=True)
    self.assertEqual(len(stories), len(self.story_cls.default_story_names()))

  def test_story_filtering_regexp_invalid(self):
    with self.assertRaises(ValueError):
      _ = self.story_filter(".*", separate=True).stories

  def test_story_filtering_regexp(self):
    stories = self.story_cls.all(separate=True)
    stories_b = self.story_filter([".*"], separate=True).stories
    self.assertListEqual(
        [story.name for story in stories],
        [story.name for story in stories_b],
    )

  def _test_run(self,
                story_names: Optional[Sequence[str]] = None,
                separate: bool = False,
                iterations: int = 2,
                repetitions: int = 3,
                warmup_repetitions: int = 0,
                custom_url: Optional[str] = None,
                throw: bool = True) -> Runner:
    if story_names is None:
      default_story_name = self.story_cls.SUBSTORIES[0]
      self.assertTrue(default_story_name)
      story_names = [default_story_name]
    stories = self.story_cls.from_names(
        story_names, separate=separate, url=custom_url, iterations=iterations)

    # The order should match Runner.get_runs
    for _ in range(warmup_repetitions + repetitions):
      for story in stories:
        speedometer_probe_results = self._generate_test_probe_results(
            iterations, story)

        for browser in self.browsers:
          self._setup_run_js_expect(browser, speedometer_probe_results)
    for browser in self.browsers:
      browser.expected_js = copy.deepcopy(browser.expected_js)

    benchmark: SpeedometerBenchmark = self.benchmark_cls(
        stories, custom_url=custom_url)
    self.assertTrue(len(benchmark.describe()) > 0)
    runner = Runner(
        self.out_dir,
        self.browsers,
        benchmark,
        env_config=EnvConfig(),
        env_validation_mode=ValidationMode.SKIP,
        platform=self.platform,
        repetitions=repetitions,
        warmup_repetitions=warmup_repetitions,
        throw=throw,
        in_memory_result_db=True)
    with mock.patch.object(self.benchmark_cls, "validate_url") as cm:
      runner.run()
    cm.assert_called_once()
    return runner

  def _setup_run_js_expect(self, browser: MockBrowser,
                           speedometer_probe_results: Json) -> None:
    # Page is ready
    browser.expect_js(result=True)
    # _setup_substories
    browser.expect_js()
    # _setup_benchmark_client
    browser.expect_js()
    # _run_stories
    browser.expect_js()
    # Wait until done
    browser.expect_js(result=True)
    browser.expect_js(result=json.dumps(speedometer_probe_results))

  @abc.abstractmethod
  def _generate_test_probe_results(self, iterations, story):
    pass

  def _verify_results(
      self,
      runner: Runner,
      expected_num_urls: Optional[int] = None) -> list[dict[str, str]]:
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      if expected_num_urls is not None:
        self.assertEqual(len(urls), expected_num_urls)
      self.assertTrue(browser.was_js_invoked(self.probe_context_cls.JS))
      self.assertListEqual(browser.expected_js, [])

    with self.assertLogs(level="INFO") as cm:
      for probe in runner.probes:
        for run in runner.runs:
          probe.log_run_result(run)
    output = "\n".join(cm.output)
    self.assertIn("Speedometer results", output)

    with self.assertLogs(level="INFO") as cm:
      for probe in runner.probes:
        probe.log_browsers_result(runner.browser_group)
    output = "\n".join(cm.output)
    self.assertIn("Speedometer results", output)
    self.assertIn("102.22.33.44", output)
    self.assertIn("100.22.33.44", output)

    csv_files = list(runner.out_dir.glob("speedometer*.csv"))
    self.assertEqual(len(csv_files), 1)
    csv_file = self.out_dir / f"{self.probe_cls.NAME}.csv"
    rows: list[dict[str, str]] = [{}]
    with csv_file.open(encoding="utf-8") as f:
      reader = csv.DictReader(f, delimiter="\t")
      rows = list(reader)
    self.assertListEqual(list(rows[0].keys()), ["label", "", "dev", "stable"])
    self.assertDictEqual(
        rows[1],
        {
            "label": "version",
            "dev": "102.22.33.44",
            "stable": "100.22.33.44",
            # Padding element after "label":
            "": ""
        })
    return rows

  def test_run_throw(self):
    runner = self._test_run(throw=True)
    self._verify_results(runner)

  def test_run_default(self):
    runner = self._test_run(iterations=10)
    self._verify_results(runner)
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertIn(self.story_cls.URL, urls)
      self.assertNotIn(self.story_cls.URL_LOCAL, urls)

  def test_run_warmups(self):
    runner = self._test_run(iterations=10, warmup_repetitions=1)
    self._verify_results(runner)
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertIn(self.story_cls.URL, urls)
      self.assertNotIn(self.story_cls.URL_LOCAL, urls)

  def test_run_custom_url(self):
    custom_url = "http://test.example.com/speedometer"
    runner = self._test_run(custom_url=custom_url, iterations=10)
    self._verify_results(runner)
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertIn(custom_url, urls)
      self.assertNotIn(self.story_cls.URL, urls)
      self.assertNotIn(self.story_cls.URL_LOCAL, urls)

  def test_run_custom_iterations(self):
    runner = self._test_run(iterations=7)
    self._verify_results(runner)
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertIn(f"{self.story_cls.URL}?iterationCount=7", urls)
      self.assertNotIn(self.story_cls.URL, urls)
      self.assertNotIn(f"{self.story_cls.URL_LOCAL}?iterationCount=7", urls)
      self.assertNotIn(self.story_cls.URL_LOCAL, urls)

  def _verify_results_stories(self, rows, story_names, label_suffix):
    labels = [row["label"] for row in rows]
    story_name_str = "_".join(story_names)
    self.assertNotIn(f"{self.benchmark_cls.NAME}_{story_name_str}", labels)
    for story_name in story_names:
      self.assertIn(f"{story_name}{label_suffix}", labels)

  def _run_combined(self, story_names: Sequence[str], label_suffix: str = ""):
    runner = self._test_run(story_names=story_names, separate=False)
    rows = self._verify_results(runner, expected_num_urls=3)
    self._verify_results_stories(rows, story_names, label_suffix)

  def _run_separate(self, story_names: Sequence[str], label_suffix: str = ""):
    runner = self._test_run(story_names=story_names, separate=True)
    rows = self._verify_results(runner, expected_num_urls=6)
    self._verify_results_stories(rows, story_names, label_suffix)

  def test_run_combined(self):
    self._run_combined(["VanillaJS-TodoMVC", "Elm-TodoMVC"])

  def test_run_separate(self):
    self._run_separate(["VanillaJS-TodoMVC", "Elm-TodoMVC"])


class Speedometer2BaseTestCase(SpeedometerBaseTestCase, metaclass=abc.ABCMeta):

  EXAMPLE_STORY_DATA = {
      "tests": {
          "Adding100Items": {
              "tests": {
                  "Sync": 74.6000000089407,
                  "Async": 6.299999997019768
              },
              "total": 80.90000000596046
          },
          "CompletingAllItems": {
              "tests": {
                  "Sync": 22.600000008940697,
                  "Async": 5.899999991059303
              },
              "total": 28.5
          },
          "DeletingItems": {
              "tests": {
                  "Sync": 11.800000011920929,
                  "Async": 0.19999998807907104
              },
              "total": 12
          }
      },
      "total": 121.40000000596046
  }

  @override
  def _generate_test_probe_results(self, iterations: int, story: Story) -> Json:
    return [{
        "tests": {
            substory_name: copy.deepcopy(self.EXAMPLE_STORY_DATA)
            for substory_name in story.substories
        },
        "total": 1000,
        "mean": 2000,
        "geomean": 3000,
        "score": 10
    }
            for _ in range(iterations)]

  def test_s2_probe_results(self):
    story_names = ("VanillaJS-TodoMVC", "React-TodoMVC")
    self.browsers = [self.browsers[0]]
    runner = self._test_run(
        story_names=story_names, separate=False, repetitions=2)
    run_1, run_2 = runner.runs
    probe_file = f"{self.probe_cls.NAME}.json"
    with (run_1.out_dir / probe_file).open() as f:
      data_1 = json.load(f)
    with (run_2.out_dir / probe_file).open() as f:
      data_2 = json.load(f)
    keys_1 = tuple(data_1.keys())
    keys_2 = tuple(data_2.keys())
    self.assertTupleEqual(keys_1, keys_2)
    # Make sure the aggregate metrics are at the end
    self.assertTupleEqual(keys_1[-2:], ("Geomean", "Score"))

    with (runner.story_groups[0].path / probe_file).open() as f:
      stories_data = json.load(f)
    self.assertTupleEqual(tuple(stories_data.keys())[-2:], ("Geomean", "Score"))

  def test_run_combined(self):
    self._run_combined(["VanillaJS-TodoMVC", "Elm-TodoMVC"],
                       label_suffix="/total")

  def test_run_separate(self):
    self._run_separate(["VanillaJS-TodoMVC", "Elm-TodoMVC"],
                       label_suffix="/total")


class Speedometer3BaseTestCase(SpeedometerBaseTestCase):

  @property
  def name_all(self):
    return "all"

  def _setup_run_js_expect(self, browser: MockBrowser,
                           speedometer_probe_results: Json) -> None:
    # Page is ready
    browser.expect_js(result=True)
    # _setup_benchmark_client
    browser.expect_js()
    # _run_stories
    browser.expect_js()
    # Wait until done
    browser.expect_js(result=True)
    browser.expect_js(result=json.dumps(speedometer_probe_results))

  @dataclass
  class Namespace(SpeedometerBaseTestCase.Namespace):
    sync_wait = dt.timedelta(0)
    sync_warmup = dt.timedelta(0)
    measurement_method = MeasurementMethod.RAF
    story_viewport = None
    shuffle_seed = None
    detailed_metrics = False
    measure_prepare = None

  EXAMPLE_STORY_DATA: dict[str, Any] = {}

  def _generate_s3_metrics(self, name, values):
    return {
        "children": [],
        "delta": 0,
        "geomean": 39.20000000298023,
        "max": 39.20000000298023,
        "mean": 39.20000000298023,
        "min": 39.20000000298023,
        "name": name,
        "percentDelta": 0,
        "sum": 39.20000000298023,
        "unit": "ms",
        "values": values
    }

  @override
  def _generate_test_probe_results(self, iterations, story) -> Json:
    values = [21.3] * iterations
    probe_result = {}
    for substory_name in story.substories:
      probe_result[substory_name] = self._generate_s3_metrics(
          substory_name, values)

    for iteration in range(iterations):
      key = f"Iteration-{iteration}-Total"
      probe_result[key] = self._generate_s3_metrics(key, values)

    probe_result.update({
        "Geomean": self._generate_s3_metrics("Geomean", values),
        "Score": self._generate_s3_metrics("Score", values),
    })
    return probe_result

  def test_run_combined(self):
    self._run_combined(["TodoMVC-JavaScript-ES5", "TodoMVC-Backbone"])

  def test_run_separate(self):
    self._run_separate(["TodoMVC-JavaScript-ES5", "TodoMVC-Backbone"])

  def test_s3_probe_results(self):
    story_names = ("TodoMVC-JavaScript-ES5", "TodoMVC-Backbone")
    self.browsers = [self.browsers[0]]
    runner = self._test_run(
        story_names=story_names, separate=False, repetitions=2)
    self.assertEqual(len(runner.runs), 2)
    run_1 = runner.runs[0]
    run_2 = runner.runs[1]
    probe_file = f"{self.probe_cls.NAME}.json"
    with (run_1.out_dir / probe_file).open() as f:
      data_1 = json.load(f)
    with (run_2.out_dir / probe_file).open() as f:
      data_2 = json.load(f)
    keys_1 = tuple(data_1.keys())
    keys_2 = tuple(data_2.keys())
    self.assertTupleEqual(keys_1, keys_2)
    # Make sure the aggregate metrics are at the end
    expected_keys = story_names + ("Iteration-0-Total", "Iteration-1-Total",
                                   "Geomean", "Score")
    self.assertTupleEqual(keys_1, expected_keys)

    with (runner.story_groups[0].path / probe_file).open() as f:
      stories_data = json.load(f)
    self.assertTupleEqual(tuple(stories_data.keys()), expected_keys)

  def test_measurement_method_kwargs(self):
    args = self.Namespace()
    args.stories = "default"
    benchmark = self.benchmark_cls.from_cli_args(args)
    (story,) = benchmark.stories
    assert isinstance(story, self.story_cls)
    self.assertEqual(story.name, self.name)
    self.assertDictEqual(story.url_params, {})

    args.measurement_method = MeasurementMethod.TIMER
    benchmark = self.benchmark_cls.from_cli_args(args)
    (story,) = benchmark.stories
    assert isinstance(story, self.story_cls)
    self.assertEqual(story.name, self.name)
    self.assertDictEqual(story.url_params, {"measurementMethod": "timer"})

  def test_all_stories_kwargs_url_params(self):
    args = self.Namespace()
    args.stories = "all"
    benchmark = self.benchmark_cls.from_cli_args(args)
    (story,) = benchmark.stories
    assert isinstance(story, self.story_cls)
    self.assertEqual(story.name, "all")
    self.assertDictEqual(story.url_params,
                         {"suites": ",".join(story.SUBSTORIES)})

  def test_single_story_kwargs(self):
    args = self.Namespace()
    args.stories = "TodoMVC-jQuery"
    benchmark = self.benchmark_cls.from_cli_args(args)
    (story,) = benchmark.stories
    assert isinstance(story, self.story_cls)
    self.assertEqual(story.name, "TodoMVC-jQuery")
    self.assertDictEqual(story.url_params, {"suites": "TodoMVC-jQuery"})

  def test_iterations_kwargs(self):
    args = self.Namespace()
    args.stories = "default"
    benchmark = self.benchmark_cls.from_cli_args(args)
    (story,) = benchmark.stories
    assert isinstance(story, self.story_cls)
    self.assertEqual(story.iterations, 10)
    self.assertDictEqual(story.url_params, {})

    args.iterations = 10
    benchmark = self.benchmark_cls.from_cli_args(args)
    (story,) = benchmark.stories
    assert isinstance(story, self.story_cls)
    self.assertEqual(story.iterations, 10)
    self.assertDictEqual(story.url_params, {})

    args.iterations = 123
    benchmark = self.benchmark_cls.from_cli_args(args)
    (story,) = benchmark.stories
    assert isinstance(story, self.story_cls)
    self.assertEqual(story.iterations, 123)
    self.assertDictEqual(story.url_params, {"iterationCount": "123"})

  def test_sync_wait_kwargs(self):
    args = self.Namespace()
    benchmark = self.benchmark_cls.from_cli_args(args)
    for story in benchmark.stories:
      assert isinstance(story, self.story_cls)
      self.assertDictEqual(story.url_params, {})

    args.sync_wait = dt.timedelta(seconds=123.4)
    benchmark = self.benchmark_cls.from_cli_args(args)
    for story in benchmark.stories:
      assert isinstance(story, self.story_cls)
      self.assertDictEqual(story.url_params, {"waitBeforeSync": "123400"})

  def test_sync_warmup_kwargs(self):
    args = self.Namespace()
    benchmark = self.benchmark_cls.from_cli_args(args)
    for story in benchmark.stories:
      assert isinstance(story, self.story_cls)
      self.assertFalse(story.url_params)

    args.sync_warmup = dt.timedelta(seconds=123.4)
    benchmark = self.benchmark_cls.from_cli_args(args)
    for story in benchmark.stories:
      assert isinstance(story, self.story_cls)
      self.assertDictEqual(story.url_params, {"warmupBeforeSync": "123400"})

  def test_viewport_kwargs(self):
    args = self.Namespace()
    benchmark = self.benchmark_cls.from_cli_args(args)
    for story in benchmark.stories:
      assert isinstance(story, self.story_cls)
      self.assertFalse(story.url_params)

    args.story_viewport = Viewport(999, 888)
    benchmark = self.benchmark_cls.from_cli_args(args)
    for story in benchmark.stories:
      assert isinstance(story, self.story_cls)
      self.assertDictEqual(story.url_params, {"viewport": "999x888"})

  def test_shuffle_seed_kwargs(self):
    args = self.Namespace()
    benchmark = self.benchmark_cls.from_cli_args(args)
    for story in benchmark.stories:
      assert isinstance(story, self.story_cls)
      self.assertFalse(story.url_params)

    args.shuffle_seed = 1234
    benchmark = self.benchmark_cls.from_cli_args(args)
    for story in benchmark.stories:
      assert isinstance(story, self.story_cls)
      self.assertDictEqual(story.url_params, {"shuffleSeed": "1234"})

  def test_run_default(self):
    runner = self._test_run(iterations=10)
    self._verify_results(runner)
    default_story_name = self.story_cls.SUBSTORIES[0]
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertIn(f"{self.story_cls.URL}?suites={default_story_name}", urls)
      self.assertNotIn(
          f"{self.story_cls.URL_LOCAL}?suites={default_story_name}", urls)

  def test_run_warmups(self):
    runner = self._test_run(iterations=10, warmup_repetitions=1)
    self._verify_results(runner)
    default_story_name = self.story_cls.SUBSTORIES[0]
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertIn(f"{self.story_cls.URL}?suites={default_story_name}", urls)
      self.assertNotIn(
          f"{self.story_cls.URL_LOCAL}?suites={default_story_name}", urls)

  def test_run_custom_url(self):
    custom_url = "http://test.example.com/speedometer"
    runner = self._test_run(custom_url=custom_url, iterations=10)
    default_story_name = self.story_cls.SUBSTORIES[0]
    self._verify_results(runner)
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertIn(f"{custom_url}?suites={default_story_name}", urls)
      self.assertNotIn(f"{self.story_cls.URL}?suites={default_story_name}",
                       urls)
      self.assertNotIn(
          f"{self.story_cls.URL_LOCAL}?suites={default_story_name}", urls)

  def test_run_custom_iterations(self):
    runner = self._test_run(iterations=7)
    self._verify_results(runner)
    default_story_name = self.story_cls.SUBSTORIES[0]
    for browser in self.browsers:
      urls = self.filter_splashscreen_urls(browser.url_list)
      self.assertIn(
          f"{self.story_cls.URL}?iterationCount=7&suites={default_story_name}",
          urls)
      self.assertNotIn(self.story_cls.URL, urls)
      self.assertNotIn(
          f"{self.story_cls.URL_LOCAL}?iterationCount=7"
          f"&suites={default_story_name}", urls)
      self.assertNotIn(self.story_cls.URL_LOCAL, urls)
