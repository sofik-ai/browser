# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import signal
import unittest

from typing_extensions import override

from crossbench import plt
from crossbench.plt.signals import LinuxSignals, MacOSSignals, \
    PosixBaseSignal, PosixSignals, WinSignals
from tests import test_helper


class SignalsTestCase(unittest.TestCase):

  @override
  def setUp(self):
    self.platform = plt.PLATFORM

  def signal_names(self, signals_obj):
    for signal_name in dir(signals_obj):
      if signal_name.startswith("SIG_"):
        continue
      if signal_name.startswith("SIG"):
        yield signal_name

  def test_plt_matches_python(self):
    for signal_name in self.signal_names(signal):
      plt_value = getattr(self.platform.signals, signal_name)
      py_value = getattr(signal, signal_name)
      self.assertEqual(plt_value, py_value, f"Signal {signal_name} mismatch")

  def test_python_matches_plt(self):
    for signal_name in self.signal_names(self.platform.signals):
      plt_value = getattr(self.platform.signals, signal_name)
      py_value = getattr(signal, signal_name)
      self.assertEqual(plt_value, py_value, f"Signal {signal_name} mismatch")

  def test_base_signals(self):
    base_names = {"SIGABRT", "SIGFPE", "SIGILL", "SIGINT", "SIGSEGV", "SIGTERM"}
    for posix_subclass in (PosixBaseSignal, PosixSignals, LinuxSignals,
                           MacOSSignals, WinSignals):
      subclass_names = set(self.signal_names(posix_subclass))
      # All BaseSignals must be present.
      self.assertFalse(base_names.difference(subclass_names))

  def test_posix_base_signals(self):
    posix_base_names = set(self.signal_names(PosixBaseSignal))
    for posix_subclass in (PosixSignals, LinuxSignals, MacOSSignals):
      posix_names = set(self.signal_names(posix_subclass))
      for signal_name in posix_base_names:
        # Both value and name must match for all PosixBaseSignal and its
        # subclasses.
        self.assertIn(signal_name, posix_names)
        self.assertEqual(PosixBaseSignal[signal_name],
                         posix_subclass[signal_name])

  def test_posix_signals(self):
    posix_names = set(self.signal_names(PosixSignals))
    linux_names = set(self.signal_names(LinuxSignals))
    for signal_name in posix_names:
      self.assertIn(signal_name, linux_names)
      self.assertEqual(PosixSignals[signal_name], LinuxSignals[signal_name])

  def test_posix_signal_names(self):
    posix_names = set(self.signal_names(PosixSignals))
    for posix_subclass in (LinuxSignals, MacOSSignals):
      posix_names = set(self.signal_names(posix_subclass))
      for signal_name in posix_names:
        # Subclasses must have all posix signal names, values might differ.
        self.assertIn(signal_name, posix_names)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
