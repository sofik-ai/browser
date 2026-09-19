# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse
import pathlib
import unittest

from typing_extensions import override

from crossbench.browsers.settings import Settings
from crossbench.probes import all as all_probes
from crossbench.probes.profiling.context.android import \
    generate_simpleperf_command_line
from crossbench.probes.profiling.system_profiling import RENDERER_CMD_PATH, \
    CallGraphMode, CleanupMode, ProfilingProbe, TargetMode
from tests import test_helper
from tests.crossbench.mock_browser import MockChromeStable, MockFirefox, \
    MockSafari
from tests.crossbench.mock_helper import LinuxMockPlatform, MacOsMockPlatform
from tests.crossbench.probes.helper import GenericProbeTestCase


class SystemProfilingProbeTestCase(GenericProbeTestCase):

  @override
  def setUp(self):
    super().setUp()
    self.fs.add_real_file(RENDERER_CMD_PATH)

  def test_simpleperf_command_line_with_tid(self):
    output_path = pathlib.Path("simpleperf.perf.data")
    self.assertListEqual(
        generate_simpleperf_command_line(
            target=TargetMode.RENDERER_MAIN_ONLY,
            app_name="com.android.chrome",
            renderer_pid=1234,
            renderer_main_tid=5678,
            call_graph_mode=CallGraphMode.DWARF,
            frequency=None,
            count=None,
            cpus=(),
            events=(),
            grouped_events=(),
            add_counters=(),
            output_path=output_path), [
                "simpleperf", "record", "-t", "5678", "--call-graph", "dwarf",
                "--post-unwind=yes", "-o", output_path
            ])

  def test_simpleperf_command_line_with_pid(self):
    output_path = pathlib.Path("simpleperf.perf.data")
    self.assertListEqual(
        generate_simpleperf_command_line(
            target=TargetMode.RENDERER_PROCESS_ONLY,
            app_name="com.android.chrome",
            renderer_pid=1234,
            renderer_main_tid=5678,
            call_graph_mode=CallGraphMode.DWARF,
            frequency=None,
            count=None,
            cpus=(),
            events=(),
            grouped_events=(),
            add_counters=(),
            output_path=output_path), [
                "simpleperf", "record", "-p", "1234", "--call-graph", "dwarf",
                "--post-unwind=yes", "-o", output_path
            ])

  def test_simpleperf_command_line_with_app(self):
    output_path = pathlib.Path("simpleperf.perf.data")
    self.assertListEqual(
        generate_simpleperf_command_line(
            target=TargetMode.BROWSER_APP_ONLY,
            app_name="com.chrome.beta",
            renderer_pid=None,
            renderer_main_tid=None,
            call_graph_mode=CallGraphMode.DWARF,
            frequency=None,
            count=None,
            cpus=(),
            events=(),
            grouped_events=(),
            add_counters=(),
            output_path=output_path), [
                "simpleperf", "record", "--app", "com.chrome.beta",
                "--call-graph", "dwarf", "--post-unwind=yes", "-o", output_path
            ])

  def test_simpleperf_command_line_systemwide(self):
    output_path = pathlib.Path("simpleperf.perf.data")
    self.assertListEqual(
        generate_simpleperf_command_line(
            target=TargetMode.SYSTEM_WIDE,
            app_name="org.chromium.chrome",
            renderer_pid=None,
            renderer_main_tid=None,
            call_graph_mode=CallGraphMode.DWARF,
            frequency=None,
            count=None,
            cpus=(),
            events=(),
            grouped_events=(),
            add_counters=(),
            output_path=output_path), [
                "simpleperf", "record", "-a", "--call-graph", "dwarf",
                "--post-unwind=yes", "-o", output_path
            ])

  def test_simpleperf_command_line_with_frequency(self):
    output_path = pathlib.Path("simpleperf.perf.data")
    self.assertListEqual(
        generate_simpleperf_command_line(
            target=TargetMode.SYSTEM_WIDE,
            app_name="org.chromium.chrome",
            renderer_pid=None,
            renderer_main_tid=None,
            call_graph_mode=CallGraphMode.FRAME_POINTER,
            frequency=1234,
            count=None,
            cpus=(),
            events=(),
            grouped_events=(),
            add_counters=(),
            output_path=output_path), [
                "simpleperf", "record", "-a", "--call-graph", "fp", "-f",
                "1234", "-o", output_path
            ])

  def test_simpleperf_command_line_with_count(self):
    output_path = pathlib.Path("simpleperf.perf.data")
    self.assertListEqual(
        generate_simpleperf_command_line(
            target=TargetMode.SYSTEM_WIDE,
            app_name="org.chromium.chrome",
            renderer_pid=None,
            renderer_main_tid=None,
            call_graph_mode=CallGraphMode.FRAME_POINTER,
            frequency=None,
            count=5,
            cpus=(),
            events=(),
            grouped_events=(),
            add_counters=(),
            output_path=output_path), [
                "simpleperf", "record", "-a", "--call-graph", "fp", "-c", "5",
                "-o", output_path
            ])

  def test_simpleperf_command_line_with_cpu(self):
    output_path = pathlib.Path("simpleperf.perf.data")
    self.assertListEqual(
        generate_simpleperf_command_line(
            target=TargetMode.SYSTEM_WIDE,
            app_name="org.chromium.chrome",
            renderer_pid=None,
            renderer_main_tid=None,
            call_graph_mode=CallGraphMode.FRAME_POINTER,
            frequency=None,
            count=None,
            cpus=(
                0,
                1,
                2,
            ),
            events=(),
            grouped_events=(),
            add_counters=(),
            output_path=output_path), [
                "simpleperf", "record", "-a", "--call-graph", "fp", "--cpu",
                "0,1,2", "-o", output_path
            ])

  def test_simpleperf_command_line_with_events(self):
    output_path = pathlib.Path("simpleperf.perf.data")
    self.assertListEqual(
        generate_simpleperf_command_line(
            target=TargetMode.SYSTEM_WIDE,
            app_name="org.chromium.chrome",
            renderer_pid=None,
            renderer_main_tid=None,
            call_graph_mode=CallGraphMode.NO_CALL_GRAPH,
            frequency=1234,
            count=5,
            cpus=(),
            events=(
                "cpu-cycles",
                "instructions",
            ),
            grouped_events=(),
            add_counters=(),
            output_path=output_path), [
                "simpleperf", "record", "-a", "-f", "1234", "-c", "5", "-e",
                "cpu-cycles,instructions", "-o", output_path
            ])

  def test_simpleperf_command_line_with_grouped_events(self):
    output_path = pathlib.Path("simpleperf.perf.data")
    self.assertListEqual(
        generate_simpleperf_command_line(
            target=TargetMode.SYSTEM_WIDE,
            app_name="org.chromium.chrome",
            renderer_pid=None,
            renderer_main_tid=None,
            call_graph_mode=CallGraphMode.NO_CALL_GRAPH,
            frequency=1234,
            count=5,
            cpus=(),
            events=(),
            grouped_events=(
                "cpu-cycles",
                "instructions",
            ),
            add_counters=(),
            output_path=output_path), [
                "simpleperf", "record", "-a", "-f", "1234", "-c", "5",
                "--group", "cpu-cycles,instructions", "-o", output_path
            ])

  def test_simpleperf_command_line_with_add_counters(self):
    output_path = pathlib.Path("simpleperf.perf.data")
    self.assertListEqual(
        generate_simpleperf_command_line(
            target=TargetMode.SYSTEM_WIDE,
            app_name="org.chromium.chrome",
            renderer_pid=None,
            renderer_main_tid=None,
            call_graph_mode=CallGraphMode.NO_CALL_GRAPH,
            frequency=1234,
            count=5,
            cpus=(),
            events=("sched:sched_switch",),
            grouped_events=(),
            add_counters=(
                "cpu-cycles",
                "instructions",
            ),
            output_path=output_path), [
                "simpleperf", "record", "-a", "-f", "1234", "-c", "5", "-e",
                "sched:sched_switch", "--add-counter",
                "cpu-cycles,instructions", "--no-inherit", "-o", output_path
            ])

  def test_parse_target_preset(self):
    probe = ProfilingProbe()
    self.assertEqual(probe.target, TargetMode.AUTO)
    probe = ProfilingProbe.parse_str("browser_app_only")
    self.assertEqual(probe.target, TargetMode.BROWSER_APP_ONLY)
    probe = ProfilingProbe.parse_str("renderer_process_only")
    self.assertEqual(probe.target, TargetMode.RENDERER_PROCESS_ONLY)
    probe = ProfilingProbe.parse_str("renderer_main_only")
    self.assertEqual(probe.target, TargetMode.RENDERER_MAIN_ONLY)

  def test_resolve_target_mode(self):
    probe = ProfilingProbe()
    self.assertEqual(probe.target, TargetMode.AUTO)

    macos_platform = MacOsMockPlatform()
    MockChromeStable.setup_fs(self.fs, macos_platform)
    macos_browser = MockChromeStable(
        "macos_chrome", settings=Settings(platform=macos_platform))
    self.assertEqual(
        probe.resolve_target_mode(macos_browser),
        TargetMode.RENDERER_PROCESS_ONLY)

    linux_platform = LinuxMockPlatform()
    MockChromeStable.setup_fs(self.fs, linux_platform)
    linux_browser = MockChromeStable(
        "linux_chrome", settings=Settings(platform=linux_platform))
    self.assertEqual(
        probe.resolve_target_mode(linux_browser), TargetMode.BROWSER_APP_ONLY)

    # For explicitly set targets, it should always return that target
    probe = ProfilingProbe(target=TargetMode.SYSTEM_WIDE)
    self.assertEqual(
        probe.resolve_target_mode(macos_browser), TargetMode.SYSTEM_WIDE)
    self.assertEqual(
        probe.resolve_target_mode(linux_browser), TargetMode.SYSTEM_WIDE)

  def test_create_non_defaults(self):
    probe = ProfilingProbe.parse_dict({
        "js": False,
        "browser_process": True,
        "spare_renderer_process": True,
        "v8_interpreted_frames": False,
        "pprof": False,
        "cleanup": "never",
        "target": "renderer_process_only",
        "pin_renderer_main_core": 3,
        "call_graph_mode": "dwarf",
        "frequency": 1200,
        "count": 430,
        "cpu": [1, 2, 3],
        "events": ["instructions", "cache-misses"],
        "grouped_events": ["cache-references", "cache-misses"],
        "add_counters": ["aa", "bb"],
    })
    self.assertTrue(probe.key)
    self.assertFalse(probe.sample_js)
    self.assertTrue(probe.sample_browser_process)
    self.assertFalse(probe.run_pprof)
    self.assertTrue(probe.cleanup_mode, CleanupMode.NEVER)
    self.assertEqual(probe.target, TargetMode.RENDERER_PROCESS_ONLY)
    self.assertTrue(probe.start_profiling_after_setup(probe.target))
    self.assertEqual(probe.pin_renderer_main_core, 3)
    self.assertEqual(probe.call_graph_mode, CallGraphMode.DWARF)
    self.assertEqual(probe.frequency, 1200)
    self.assertEqual(probe.count, 430)
    self.assertEqual(probe.cpu, (1, 2, 3))
    self.assertEqual(probe.events, ("instructions", "cache-misses"))
    self.assertEqual(probe.grouped_events, ("cache-references", "cache-misses"))
    self.assertEqual(probe.add_counters, ("aa", "bb"))

  def test_create_custom_frequency(self):
    probe = ProfilingProbe.parse_dict({"freq": "max"})
    self.assertEqual(probe.frequency, "max")
    probe = ProfilingProbe.parse_dict({"freq": 333})
    self.assertEqual(probe.frequency, 333)

  def test_create_invalid_frequency(self):
    with self.assertRaisesRegex(argparse.ArgumentTypeError, "frequency"):
      _ = ProfilingProbe.parse_dict({"freq": -100})
    with self.assertRaisesRegex(argparse.ArgumentTypeError, "frequency"):
      _ = ProfilingProbe.parse_dict({"freq": "maaaaxxx"})

  def test_spare_renderer(self):
    browser_a = self.browsers[0]
    browser_b = self.browsers[0]

    probe_spare = ProfilingProbe(spare_renderer_process=True)
    browser_a.attach_probe(probe_spare)
    self.assertNotIn("SpareRendererForSitePerProcess",
                     browser_b.features.disabled)

    probe_no_spare = ProfilingProbe(spare_renderer_process=False)
    browser_b.attach_probe(probe_no_spare)
    self.assertIn("SpareRendererForSitePerProcess", browser_b.features.disabled)

  def test_attach_unsupported(self):
    probe = ProfilingProbe()

    macos_platform = MacOsMockPlatform()
    test_browsers = (MockSafari, MockFirefox, MockChromeStable)
    for browser_cls in test_browsers:
      browser_cls.setup_fs(self.fs, macos_platform)
      name = browser_cls.__name__
      browser_cls(
          name, settings=Settings(platform=macos_platform)).attach_probe(probe)

    linux_platform = LinuxMockPlatform()
    for browser_cls in test_browsers:
      browser_cls.setup_fs(self.fs, linux_platform)
    with self.assertRaises(AssertionError):
      MockFirefox(
          "firefox",
          settings=Settings(platform=linux_platform)).attach_probe(probe)
    MockChromeStable(
        "chrome",
        settings=Settings(platform=linux_platform)).attach_probe(probe)


class EnumTestCase(unittest.TestCase):

  def test_cleanup_mode(self):
    self.assertIs(CleanupMode(True), CleanupMode.ALWAYS)
    self.assertIs(CleanupMode(False), CleanupMode.NEVER)

    self.assertIs(CleanupMode("always"), CleanupMode.ALWAYS)
    self.assertIs(CleanupMode("never"), CleanupMode.NEVER)
    self.assertIs(CleanupMode("auto"), CleanupMode.AUTO)

  def test_target_mode(self):
    self.assertIs(
        TargetMode("renderer_main_only"), TargetMode.RENDERER_MAIN_ONLY)
    self.assertIs(
        TargetMode("RENDERER_MAIN_ONLY"), TargetMode.RENDERER_MAIN_ONLY)

  def test_call_graph_mode(self):
    self.assertIs(CallGraphMode("fp"), CallGraphMode.FRAME_POINTER)
    self.assertIs(CallGraphMode("FP"), CallGraphMode.FRAME_POINTER)

# Remove import that's used to avoid circular import issues.
del all_probes

if __name__ == "__main__":
  test_helper.run_pytest(__file__)
