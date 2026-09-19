# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING, Optional

from typing_extensions import override

from crossbench.browsers.chromium_based import helper as chromium_helper
from crossbench.browsers.version import BrowserVersionChannel
from crossbench.cli import ui
from crossbench.helper.path_finder import ChromiumCheckoutFinder
from crossbench.plt.arch import MachineArch
from crossbench.plt.base import SubprocessError
from crossbench.probes.cb_perfetto import traceconv
from crossbench.probes.profiling.system_profiling import ProfilingProbe
from crossbench.probes.trace_processor.context.base import \
    TraceProcessorProbeContext
from crossbench.probes.trace_processor.query_config import \
    TraceProcessorQueryConfig

if TYPE_CHECKING:
  from crossbench import path as pth
  from crossbench import plt
  from crossbench.browsers.browser import Browser
  from crossbench.probes.results import LocalProbeResult
  from crossbench.probes.trace_processor.trace_processor import \
      TraceProcessorProbe
  from crossbench.runner.run import Run

KB = 1024


class TraceProcessorSymbolizingProbeContext(TraceProcessorProbeContext):

  def __init__(self, probe: TraceProcessorProbe, run: Run) -> None:
    self._has_symbols: bool = False
    super().__init__(probe, run)

  @property
  def should_symbolize_profile(self) -> bool:
    if not self.probe.symbolize_profile:
      return False
    return self.run.has_probe_context(ProfilingProbe)

  @override
  def _merge_trace_files(self) -> LocalProbeResult:
    result = super()._merge_trace_files()
    if self.should_symbolize_profile:
      return self._symbolize_profile(result)
    return result

  @property
  @override
  def queries(self) -> tuple[TraceProcessorQueryConfig, ...]:
    queries = super().queries
    if self._has_symbols and not any(query.name == "pprof"
                                     for query in queries):
      logging.info("trace_processor probe: auto-adding pprof query")
      queries += (TraceProcessorQueryConfig.parse("pprof"),)
    return queries

  @property
  @override
  def needs_tp_run(self) -> bool:
    # TODO: fix and respect needs_btp_run, add pprof query earlier.
    if super().needs_tp_run:
      return True
    return self._has_symbols

  def _symbolize_profile(self, result: LocalProbeResult) -> LocalProbeResult:
    llvm_symbolizer_bin = self.probe.llvm_symbolizer_bin
    if not llvm_symbolizer_bin:
      logging.error("Could not find llvm-symbolizer binary")
      return result
    traceconv_bin = self.probe.traceconv_bin
    if not traceconv_bin:
      logging.error("Could not find traceconv binary")
      return result

    merged_file = result.get("zip")
    symbols_result = self.local_result_path / "symbols.pb"

    symbols_path = self.probe.perfetto_binary_path
    if not symbols_path:
      symbols_path = self._ensure_symbols()
    if not symbols_path:
      logging.error("Could not find any input symbol directories")
      return result

    env = {
        "PERFETTO_SYMBOLIZER_MODE": "index",
        "PERFETTO_BINARY_PATH": str(symbols_path),
        **self.host_platform.environ,
    }
    env["PATH"] = (os.pathsep).join(
        (str(llvm_symbolizer_bin.parent), env.get("PATH", "")))

    traceconv_log = self.local_result_path / "traceconv.log"
    has_traceconv_error = False
    with ui.spinner(title="traceconv symbolization"):
      try:
        with traceconv_log.open("w", encoding="utf-8") as log_file:
          self.host_platform.sh(
              traceconv_bin,
              "--verbose",
              "symbolize",
              merged_file,
              symbols_result,
              env=env,
              stdout=log_file,
              stderr=log_file)
      except SubprocessError as e:
        has_traceconv_error = True
        logging.error("Symbolization failed: %s", e)
        self._log_traceconv_error(traceconv_log)

    if not self.host_platform.exists(symbols_result) or (
        self.host_platform.file_size(symbols_result) < 100 * KB):
      self._traceconv_version_check(traceconv_bin)
      logging.error("Could not generate valid symbols file: %s.", symbols_path)
      if not has_traceconv_error:
        self._log_traceconv_error(traceconv_log)
      return result

    return self._maybe_symbolized_result(result, symbols_result)

  def _log_traceconv_error(self, log_path: pth.LocalPath) -> None:
    logging.error("See log: %s", log_path)
    if not self.host_platform.exists(log_path):
      return
    with log_path.open("r", encoding="utf-8") as log_file:
      lines = log_file.readlines()
      if not lines:
        return
      logging.error("  ...")
      for line in lines[-10:]:
        logging.error("  %s", line.strip())

  def _traceconv_version_check(self, traceconv_bin: pth.LocalPath) -> None:
    traceconv_version_str = self.host_platform.sh_stdout(
        traceconv_bin, "--version")
    traceconv_version = traceconv.PerfettoVersion.parse(traceconv_version_str)
    if traceconv_version < traceconv.MIN_VERSION:
      logging.error(
          "traceconv version is too old: %s\n"
          "Make sure you have traceconv version at least %s due to "
          "http://crbug.com/481290800.", traceconv_version,
          traceconv.MIN_VERSION.version_str)

  def _ensure_symbols(self) -> Optional[pth.LocalPath]:
    # If the user provided no perfetto_binary_path, the default value is
    # a guess that works for some dev-built binaries. Worst-case scenario,
    # symbolization fails but the unsymbolized trace is still available. For
    # official builds, an even better alternative would be to download from
    # the official archive.
    if self.browser.is_local_build:
      if path := chromium_helper.find_build_dir(self.browser.app_path,
                                                self.host_platform):
        return self.host_platform.local_path(path)
      return None

    if self.host_platform.is_macos:
      return _download_macos_symbols(self.host_platform, self.browser)
    # TODO: support more platforms
    return None

  def _maybe_symbolized_result(
      self, result: LocalProbeResult,
      symbols_result: pth.LocalPath) -> LocalProbeResult:
    self.write_zip_file(self._symbolized_trace_path,
                        (*result.perfetto_list, symbols_result))

    if (self.host_platform.file_size(self._symbolized_trace_path)
        < self.host_platform.file_size(self.merged_trace_path)):
      logging.error("Failed to generated symbolized trace file")
      return result

    # If we have a successfully symbolized trace file we can replace
    # the original merged_trace.zip.
    self.host_platform.rm(self.merged_trace_path)
    self.host_platform.rename(self._symbolized_trace_path,
                              self.merged_trace_path)
    self._has_symbols = True
    return self.local_result(perfetto=(self.merged_trace_path,))


_MACOS_SYMBOL_ARCH_LOOKUP = {
    MachineArch.ARM_64: "arm64",
    MachineArch.X64: "x86_64",
}


def _download_macos_symbols(host_platform: plt.Platform,
                            browser: Browser) -> Optional[pth.LocalPath]:
  checkout_path = ChromiumCheckoutFinder(host_platform).path
  if not checkout_path:
    logging.debug("Could not find chromium checkout to download symbols.")
    return None

  download_script = checkout_path / "tools/mac/download_symbols.py"
  if not host_platform.exists(download_script):
    logging.debug("Could not find download_symbols.py at %s", download_script)
    return None

  version = browser.version
  if version.is_unknown or version.channel == BrowserVersionChannel.ANY or (
      not version.parts_str):
    logging.warning("Could not determine browser version for symbol download.")
    return None

  version_str = browser.version.parts_str
  channel_name = browser.version.channel_name
  arch_str = _MACOS_SYMBOL_ARCH_LOOKUP[browser.platform.machine]

  symbols_cache = host_platform.local_cache_dir("symbols")
  output_dir = symbols_cache / f"{version_str}_{channel_name}_{arch_str}"
  host_platform.mkdir(output_dir, exist_ok=True)

  if list(host_platform.iterdir(output_dir)):
    logging.debug("Found existing symbols: %s", output_dir)
    return output_dir

  with ui.spinner(title="Downloading symbols"):
    try:
      host_platform.sh(sys.executable, download_script, "--version",
                       version_str, "--arch", arch_str, "--out", output_dir,
                       "--channel", channel_name)
    except SubprocessError as e:
      logging.error("Failed to download symbols: %s", e)
      return None

  result_files = list(host_platform.iterdir(output_dir))
  if len(result_files) == 1 and host_platform.is_dir(result_files[0]):
    download_dir = result_files[0]
    for symbol_file in host_platform.iterdir(download_dir):
      host_platform.rename(symbol_file, output_dir / symbol_file.name)
    host_platform.rm(download_dir, dir=True)

  return output_dir
