# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import json
from typing import Any

from crossbench.benchmarks.loading.config.blocks import ActionBlock
from crossbench.benchmarks.loading.page.live import InteractivePage
from crossbench.benchmarks.loading.playback_controller import \
    PlaybackController
from crossbench.probes.meminfo import MeminfoProbe
from tests import test_helper
from tests.crossbench.probes.helper import GenericProbeTestCase


def mock_meminfo(info_stack: list[str],
                 name: str,
                 title: str | None = None,
                 system: bool = False) -> dict[str, Any]:
  meminfo = {
      "info_stack":
          info_stack,
      "processes": [
          {
              "name": name,
              "pid": 1,
              "pss_total": 2,
              "rss_total": 3,
              "swap_total": 4,
          },
          {
              "name": name,
              "pid": 2,
              "pss_total": 3,
              "rss_total": 4,
              "swap_total": 5,
          },
      ],
  }
  if title is not None:
    meminfo["title"] = title
  if system:
    meminfo["system"] = {
        "total_ram_kb": 5,
        "cached_pss_kb": 4,
        "cached_kernel_kb": 3,
        "free_kb": 2,
    }
  return meminfo


class TestMeminfoProbe(GenericProbeTestCase):

  def test_meminfo_dumped(self):
    probe = MeminfoProbe.config_parser().parse({})
    setup = ActionBlock.parse_sequence([{
        "action": "meminfo",
        "title": "test",
    }])
    blocks = (ActionBlock.parse_sequence([{
        "action": "get",
        "url": "https://google.com"
    }, {
        "action": "meminfo",
        "title": "test",
        "system": True,
    }]),)
    teardown = ActionBlock.parse_sequence([{
        "action": "meminfo",
        "system": True,
    }])
    playback = PlaybackController.repeat(3)

    page = InteractivePage(
        name="google",
        setup=setup,
        blocks=blocks,
        teardown=teardown,
        playback=playback)
    stories = [page]
    runner = self.create_runner(
        stories,
        js_side_effects=[
            # setup:
            None,
            # wait for ready state
            True,
        ],
        repetitions=1)
    runner.attach_probe(probe)

    runner.run()
    self.assertTrue(runner.is_success)
    meminfo_result_files = list(runner.out_dir.glob(f"**/{probe.name}/*.json"))

    # 5 files per browser: 1 setup, 3 iterations, 1 teardown.
    self.assertEqual(len(meminfo_result_files), 5 * len(self.browsers))

    for browser in self.browsers:
      mock_json = [
          mock_meminfo(["setup", "block_0", "action_1"],
                       str(browser.path),
                       title="test"),
          mock_meminfo(["playback_0", "block_0", "action_2"],
                       str(browser.path),
                       title="test",
                       system=True),
          mock_meminfo(["playback_1", "block_0", "action_2"],
                       str(browser.path),
                       title="test",
                       system=True),
          mock_meminfo(["playback_2", "block_0", "action_2"],
                       str(browser.path),
                       title="test",
                       system=True),
          mock_meminfo(["teardown", "block_0", "action_1"],
                       str(browser.path),
                       system=True),
      ]

      # Check that there are 5 json dump files.
      files = [
          file for file in meminfo_result_files
          if browser.unique_name in file.parts
      ]
      self.assertListEqual([file.name for file in files], [
          "test.setup_block_0_action_1.json",
          "test.playback_0_block_0_action_2.json",
          "test.playback_1_block_0_action_2.json",
          "test.playback_2_block_0_action_2.json",
          "teardown_block_0_action_1.json",
      ])
      self.assertListEqual(
          [json.loads(file.read_text(encoding="utf-8")) for file in files],
          mock_json)

      # Check that there are 5 performance marks all with the correct JSON.
      details = [
          browser.performance_marks_details[i]
          for i, mark in enumerate(browser.performance_marks)
          if mark == "crossbench-meminfo"
      ]
      self.assertListEqual(details, mock_json)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
