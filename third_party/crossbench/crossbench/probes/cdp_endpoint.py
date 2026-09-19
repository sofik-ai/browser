# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, ClassVar, Type

from typing_extensions import override

from crossbench.probes.probe import Probe, ProbeContext

if TYPE_CHECKING:
  from crossbench.probes.results import ProbeResult


class CDPEndpointProbe(Probe):
  """
  Probe to extract the CDP WebSocket endpoint of a chromium-based browser
  and write it to a file. This can be used to control a browser externally
  e.g. via an agent or other automation infrastructure while keeping the
  crossbench harness for probes and flag management.
  """
  NAME: ClassVar = "cdp_endpoint"
  FILE_NAME: ClassVar[str] = "cdp_ws_endpoint.txt"

  @property
  @override
  def result_path_name(self) -> str:
    return self.FILE_NAME

  @override
  def get_context_cls(self) -> Type[CDPEndpointProbeContext]:
    return CDPEndpointProbeContext


class CDPEndpointProbeContext(ProbeContext[CDPEndpointProbe]):

  @override
  def start(self) -> None:
    try:
      endpoint = self.run.browser.ws_endpoint
      logging.info("CROSSBENCH SESSION PID: %s", os.getpid())
      logging.info("CDP WS ENDPOINT: %s", endpoint)
      self.host_platform.write_text(self.local_result_path, endpoint)
    except NotImplementedError:
      logging.info("CDP WS ENDPOINT: Not supported for %s",
                   self.run.browser.unique_name)

  @override
  def stop(self) -> None:
    pass

  @override
  def teardown(self) -> ProbeResult:
    if self.host_platform.exists(self.local_result_path):
      return self.local_result(file=(self.local_result_path,))
    return self.empty_result()
