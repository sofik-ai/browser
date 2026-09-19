# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from crossbench.probes import all as probes

if TYPE_CHECKING:
  from crossbench.probes.probe import Probe
  from crossbench.runner.runner import Runner


def get_extra_trace_processor(runner: Runner) -> Iterable[Probe]:
  if (runner.has_probe(probes.PerfettoProbe.NAME) and
      runner.has_probe(probes.ProfilingProbe.NAME) and
      not runner.has_probe(probes.TraceProcessorProbe.NAME)):
    # Install an additional TraceProcessorProbe to symbolize complex
    # traces with profiles data.
    return (probes.TraceProcessorProbe(),)
  return ()
