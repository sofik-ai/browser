# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import enum

from crossbench.config import ConfigEnum


@enum.unique
class StartTracingSequence(ConfigEnum):
  PROBE_START = ("probe_start", "Start tracing as soon as the probe starts.")
  STORY_SETUP = (
      "story_setup",
      "Start tracing immediately before the story setup workload is started.")
  STORY_RUN = (
      "story_run",
      "Start tracing immediately before the first iteration of the core story workload."
  )
