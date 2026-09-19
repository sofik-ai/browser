# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

from typing import Final

from crossbench.benchmarks.loading.page.live import LivePage
from crossbench.probes.v8.rcs import V8RCSProbe
from tests import test_helper
from tests.crossbench.probes.helper import GenericProbeTestCase

EXAMPLE_RCS_DATA: Final[str] = """
                      Runtime Function/C++ Builtin        Time             Count
========================================================================================
                                  FunctionCallback     94.96ms  38.47%     65908  29.19%
                                      JS_Execution     19.37ms   7.85%       976   0.43%
          PreParseBackgroundWithVariableResolution     14.49ms   5.87%      5175   2.29%
                              ParseFunctionLiteral     10.25ms   4.15%      2209   0.98%
                                   CompileIgnition      9.30ms   3.77%      2236   0.99%
"""


class V8RCSProbeTestCase(GenericProbeTestCase):

  def test_simple_loading_case(self):
    probe = V8RCSProbe()
    stories = [
        LivePage("google", "https://google.com"),
        LivePage("amazon", "https://amazon.com")
    ]
    repetitions = 2

    runner = self.create_runner(
        stories,
        js_side_effects=[EXAMPLE_RCS_DATA],
        repetitions=repetitions,
        separate=True,
        throw=True)
    runner.attach_probe(probe)
    runner.run()
    self.assertTrue(runner.is_success)

    for run in runner.runs:
      self.assertIn("--runtime-call-stats", run.browser.js_flags)

    # One file per story repetition
    result_count = len(self.browsers) * len(stories) * repetitions
    # One merged result per story
    result_count += len(self.browsers) * len(stories)
    # One merged results per browser
    result_count += len(self.browsers)
    # Symlinked summary files:
    rcs_result_files = list(runner.out_dir.glob(f"**/{probe.name}.txt"))
    self.assertEqual(len(rcs_result_files), result_count)
    # Cache-temperatures files
    rcs_result_files = list(runner.out_dir.glob(f"**/{probe.name}/*.rcs.txt"))
    self.assertEqual(len(rcs_result_files), result_count)

    (story_data, reps_data, stories_data, _) = self.get_non_empty_results_str(
        runner, probe, "txt", has_browsers_data=False)

    self.assertEqual(story_data.count(EXAMPLE_RCS_DATA), 1)
    self.assertEqual(reps_data.count(EXAMPLE_RCS_DATA), repetitions)
    self.assertEqual(
        stories_data.count(EXAMPLE_RCS_DATA),
        len(stories) * repetitions)

    self.assertEqual(story_data.count("== Page: "), 0)
    self.assertEqual(reps_data.count("== Page: "), 1)
    self.assertEqual(stories_data.count("== Page: "), len(stories))

  def validate_cache_temperatures_files(self, probe, group, cache_temperatures):
    rcs_result_files = list(group.path.glob(f"{probe.name}/*.rcs.txt"))
    self.assertEqual(len(rcs_result_files), len(cache_temperatures) + 1)
    self.assertTrue((group.path / f"{probe.name}.txt").is_file())
    for index, cache_temperature in enumerate(cache_temperatures):
      path = group.path / probe.name / f"{index}_{cache_temperature}.rcs.txt"
      self.assertTrue(path.is_file(), f"{path} does not exist")

  def test_simple_loading_case_cache_temperatures(self):
    probe = V8RCSProbe()
    stories = [
        LivePage("google", "https://google.com"),
        LivePage("amazon", "https://amazon.com")
    ]
    repetitions = 2
    cache_temperatures = ("cold", "warm")
    runner = self.create_runner(
        stories,
        js_side_effects=[EXAMPLE_RCS_DATA, EXAMPLE_RCS_DATA],
        repetitions=repetitions,
        cache_temperatures=cache_temperatures,
        separate=True,
        throw=True)
    runner.attach_probe(probe)
    runner.run()
    self.assertTrue(runner.is_success)

    repetition_group = runner.repetitions_groups[0]
    self.validate_cache_temperatures_files(probe, repetition_group,
                                           cache_temperatures)
    story_group = runner.story_groups[0]
    self.validate_cache_temperatures_files(probe, story_group,
                                           cache_temperatures)

    rcs_result_files = list(runner.out_dir.glob(f"**/{probe.name}.txt"))
    # One merged file for each story and cache temp + all.rcs.txt:
    result_count = len(self.browsers) * len(stories) * (
        len(cache_temperatures) + 1)
    # One merged results per browser and cache temp + all.rcs.txt
    result_count += len(self.browsers) * (len(cache_temperatures) + 1)
    # One merged results per browser
    result_count += len(self.browsers)
    # Without symlinked summary files:
    rcs_result_files = list(runner.out_dir.glob(f"**/{probe.name}/*.rcs.txt"))
    self.assertEqual(len(rcs_result_files), result_count)

    top_level_rcs_files = list((runner.out_dir / probe.name).iterdir())
    self.assertEqual(len(top_level_rcs_files), len(self.browsers))

    with self.assertLogs() as cm:
      probe.log_browsers_result(runner.browser_group)
    log_output = "\n".join(cm.output)
    for top_level_rcs_file in top_level_rcs_files:
      self.assertIn(str(top_level_rcs_file), log_output)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
