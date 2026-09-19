# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import inspect

import crossbench.path as pth
from crossbench.cli.config.probe_list import ProbeListConfig
from crossbench.probes.all import CONFIGURABLE_INTERNAL_PROBES, \
    DEFAULT_INTERNAL_PROBES, GENERAL_PURPOSE_PROBES, INTERNAL_PROBES, \
    NON_CONFIGURABLE_INTERNAL_PROBES, OPTIONAL_INTERNAL_PROBES
from crossbench.probes.cb_perfetto.perfetto import PerfettoProbe, TraceConfig
from crossbench.probes.cb_perfetto.tracing import TracingProbe
from crossbench.probes.chrome_histograms import ChromeHistogramsProbe
from crossbench.probes.chromium_pgo import ChromiumPgoProbe
from crossbench.probes.chromium_probe import ChromiumProbe
from crossbench.probes.debugger import DebuggerProbe
from crossbench.probes.downloads import DownloadsProbe
from crossbench.probes.dtrace import DTraceProbe
from crossbench.probes.dump_heap import DumpHeapProbe
from crossbench.probes.dump_html import DumpHtmlProbe
from crossbench.probes.embedder import WebviewEmbedderProbe
from crossbench.probes.env_modifier import EnvModifier
from crossbench.probes.etm import EtmProbe
from crossbench.probes.frequency import FrequencyProbe
from crossbench.probes.js import JSProbe
from crossbench.probes.json import JsonResultProbe
from crossbench.probes.performance_entries import PerformanceEntriesProbe
from crossbench.probes.polling import PollingShellProbe
from crossbench.probes.power_sampler import PowerSamplerProbe
from crossbench.probes.powermetrics import PowerMetricsProbe
from crossbench.probes.probe import Probe, ProbeKeyT, ProbePriority
from crossbench.probes.profiling.browser_profiling import BrowserProfilingProbe
from crossbench.probes.profiling.system_profiling import ProfilingProbe
from crossbench.probes.screenshot import ScreenshotProbe
from crossbench.probes.shell import ShellProbe
from crossbench.probes.system_stats import SystemStatsProbe
from crossbench.probes.trace_processor.trace_processor import \
    TraceProcessorProbe
from crossbench.probes.v8.builtins_pgo import V8BuiltinsPGOProbe
from crossbench.probes.v8.log import V8LogProbe
from crossbench.probes.v8.rcs import V8RCSProbe
from crossbench.probes.v8.turbolizer import V8TurbolizerProbe
from crossbench.probes.video import VideoProbe
from crossbench.probes.web_page_replay.recorder import WebPageReplayProbe
from tests import test_helper
from tests.crossbench.base import CrossbenchConfigTestMixin, \
    CrossbenchFakeFsTestCase


class ProbeListConfigTestCase(CrossbenchFakeFsTestCase):

  def test_invalid_empty(self):
    with self.assertRaises(ValueError) as cm:
      ProbeListConfig.parse({"probes": ""})
    self.assertIn("str", str(cm.exception).lower())
    with self.assertRaises(ValueError) as cm:
      ProbeListConfig.parse({"browsers": {}})
    self.assertIn("probes", str(cm.exception).lower())

  def test_empty(self):
    probe_list = ProbeListConfig.parse({"probes": []})
    self.assertEqual(probe_list.probes, ())
    probe_list = ProbeListConfig.parse({"probes": {}})
    self.assertEqual(probe_list.probes, ())


class ProbeTestCase(CrossbenchConfigTestMixin, CrossbenchFakeFsTestCase):

  def probe_instances(self):
    yield from self.internal_probe_instances()
    yield from self.general_purpose_probe_instances()

  def internal_probe_instances(self):
    for probe_cls in INTERNAL_PROBES:
      yield probe_cls()

  def general_purpose_probe_instances(self):
    yield BrowserProfilingProbe()
    yield ChromiumPgoProbe()
    yield DTraceProbe(pth.LocalPath("script.dtrace"))
    yield DebuggerProbe(pth.LocalPath("debugger.bin"))
    yield DownloadsProbe()
    yield DumpHtmlProbe()
    yield DumpHeapProbe()
    yield FrequencyProbe.parse_dict({})
    yield PerfettoProbe(enabled_tags=["v8"])
    yield PerformanceEntriesProbe()
    yield PowerMetricsProbe()
    yield PowerSamplerProbe()
    yield ProfilingProbe()
    yield ScreenshotProbe()
    yield PollingShellProbe(cmd=["ls"])
    yield SystemStatsProbe()
    yield TracingProbe()
    yield V8BuiltinsPGOProbe()
    yield V8LogProbe()
    yield V8RCSProbe()
    yield V8TurbolizerProbe()
    yield VideoProbe()
    yield WebPageReplayProbe(wpr_go_bin=self.create_file("wpr.go"))

  def probe_classes(self):
    yield from INTERNAL_PROBES
    yield from GENERAL_PURPOSE_PROBES

  def test_general_purpose_probe_order(self):
    sorted_probe_classes = sorted(GENERAL_PURPOSE_PROBES, key=lambda x: x.NAME)
    self.assertSequenceEqual(GENERAL_PURPOSE_PROBES, sorted_probe_classes)

  def all_probe_subclasses(self, probe_cls=Probe):
    for probe_sub_cls in probe_cls.__subclasses__():
      if "Mock" in str(probe_sub_cls):
        continue
      # Filter out abstract helper classes.
      if probe_sub_cls in (ChromiumProbe, EnvModifier, JsonResultProbe):
        continue
      if not inspect.isabstract(probe_sub_cls):
        yield probe_sub_cls
      yield from self.all_probe_subclasses(probe_sub_cls)
    yield from OPTIONAL_INTERNAL_PROBES

  def test_properties(self):
    for probe_cls in INTERNAL_PROBES:
      with self.subTest(probe_cls=str(probe_cls)):
        self.assertFalse(probe_cls.IS_GENERAL_PURPOSE)

    for probe_cls in GENERAL_PURPOSE_PROBES:
      with self.subTest(probe_cls=str(probe_cls)):
        self.assertTrue(probe_cls.IS_GENERAL_PURPOSE)

    for probe_cls in self.probe_classes():
      with self.subTest(probe_cls=str(probe_cls)):
        self.assertTrue(probe_cls.NAME)

  def test_default_lists(self):
    count = 0
    for probe_cls in self.all_probe_subclasses():
      count += 1
      if probe_cls.IS_GENERAL_PURPOSE:
        self.assertIn(probe_cls, GENERAL_PURPOSE_PROBES)
    self.assertGreater(
        count,
        len(GENERAL_PURPOSE_PROBES) + len(DEFAULT_INTERNAL_PROBES))
    self.assertFalse(
        set(NON_CONFIGURABLE_INTERNAL_PROBES).intersection(
            set(CONFIGURABLE_INTERNAL_PROBES)))
    self.assertFalse(
        set(NON_CONFIGURABLE_INTERNAL_PROBES).intersection(
            set(OPTIONAL_INTERNAL_PROBES)))
    self.assertFalse(
        set(CONFIGURABLE_INTERNAL_PROBES).intersection(
            set(OPTIONAL_INTERNAL_PROBES)))

  def test_help(self):
    TraceConfig.presets.cache_clear()
    self.setup_perfetto_config_presets()
    for probe_cls in self.probe_classes():
      help_text = probe_cls.help_text()
      self.assertTrue(help_text)
      summary = probe_cls.summary_text()
      self.assertTrue(summary)
      self.assertIn(summary, help_text)

  def test_config_parser(self):
    for probe_cls in self.probe_classes():
      config_parser = probe_cls.config_parser()
      self.assertEqual(config_parser.probe_cls, probe_cls)
      self.assertIn(probe_cls.NAME, config_parser.title)

  def test_config_parser_defaults(self):
    # If possible all probes should define a sane default so they can easily
    # be experimented with and make it more accessible to explore.
    # TODO(crbug.com/383572680): provide more default settings
    requires_configuration = {
        ChromeHistogramsProbe,
        DTraceProbe,
        # Reason: missing lldb binary on some platforms
        DebuggerProbe,
        # TODO: provide default settings
        JSProbe,
        # TODO: auto-download perfetto bin from storage
        PerfettoProbe,
        # TODO: provide default settings
        PollingShellProbe,
        # TODO: provide default settings
        ShellProbe,
        # TODO: missing wpr, download precompiled wpr from storage
        WebPageReplayProbe,
        WebviewEmbedderProbe,
        EtmProbe,
    }
    for probe_cls in GENERAL_PURPOSE_PROBES:
      if probe_cls in requires_configuration:
        continue
      config_parser = probe_cls.config_parser()
      probe = config_parser.parse({})
      self.assertIsInstance(probe, probe_cls)

  def test_basic_probe_instances(self):
    keys: set[ProbeKeyT] = set()
    names: set[str] = set()
    for probe_instance in self.probe_instances():
      _ = hash(probe_instance)
      key = probe_instance.key
      self.assertIsInstance(key, tuple)
      self.assertNotIn(key, keys)
      keys.add(key)
      self.assertTrue(probe_instance.name)
      self.assertNotIn(probe_instance.name, names)
      names.add(probe_instance.name)

  def test_is_internal(self):
    for probe_instance in self.internal_probe_instances():
      with self.subTest(probe_cls=str(type(probe_instance))):
        self.assertTrue(probe_instance.is_internal)
        self.assertEqual(probe_instance.PRIORITY, ProbePriority.INTERNAL)

    for probe_instance in self.general_purpose_probe_instances():
      with self.subTest(probe_cls=str(type(probe_instance))):
        self.assertFalse(probe_instance.is_internal)

  def test_is_attached(self):
    for probe_instance in self.general_purpose_probe_instances():
      with self.subTest(probe_cls=str(type(probe_instance))):
        self.assertFalse(probe_instance.is_attached)

  def test_probe_priority(self):
    for probe_cls in INTERNAL_PROBES:
      self.assertEqual(probe_cls.PRIORITY, ProbePriority.INTERNAL)

    for probe_cls in GENERAL_PURPOSE_PROBES:
      with self.subTest(probe_cls=str(probe_cls)):
        if probe_cls == TraceProcessorProbe:
          self.assertEqual(probe_cls.PRIORITY, ProbePriority.TRACE_PROCESSOR)
        elif probe_cls == ChromeHistogramsProbe:
          self.assertEqual(probe_cls.PRIORITY, ProbePriority.PRE_USER)
        else:
          self.assertEqual(probe_cls.PRIORITY, ProbePriority.USER)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
