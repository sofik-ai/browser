# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import argparse
import contextlib
import pathlib
from unittest import mock

from typing_extensions import override

from crossbench.network.live import LiveNetwork
from crossbench.network.traffic_shaping.ts_proxy import TsProxyProcess, \
    TsProxyServer, TsProxyTrafficShaper
from crossbench.runner.groups.session import BrowserSessionRunGroup
from tests import test_helper
from tests.crossbench.base import BaseCrossbenchTestCase


class TsProxyBaseTestCase(BaseCrossbenchTestCase):

  @override
  def setUp(self) -> None:
    super().setUp()
    self.ts_proxy_path = pathlib.Path("/chrome/tsproxy/tsproxy.py")
    self.fs.create_file(self.ts_proxy_path, st_size=100)
    # Avoid dealing with fcntl for testing.
    patcher = mock.patch.object(
        TsProxyProcess, "_setup_non_blocking_io", return_value=None)
    self.addCleanup(patcher.stop)
    patcher.start()

  @contextlib.contextmanager
  def startup_process_mock(self):
    proc = mock.Mock()
    proc.configure_mock(**{
        "poll.return_value": None,
        "communicate.return_value": (None, None)
    })
    proc.stdout = mock.Mock()
    proc.stdout.configure_mock(**{
        "readline.return_value":
            "Started Socks5 proxy server on 127.0.0.1:43210"
    })
    proc.stderr = mock.Mock()

    def popen_mock(cmd, *args, **kwargs):
      self.assertEqual(cmd[1], self.ts_proxy_path)
      self.assertEqual(cmd[2], "--port=0")
      del args, kwargs
      return proc

    with mock.patch("subprocess.Popen", side_effect=popen_mock) as mock_popen:
      with mock.patch.object(self.platform,
                             "terminate_gracefully") as terminate_gracefully:
        yield proc
    mock_popen.assert_called_once()
    terminate_gracefully.assert_called_once()


class TsProxyTrafficShaperTestCase(TsProxyBaseTestCase):

  def create_session(self):
    return mock.Mock(
        spec=BrowserSessionRunGroup, browser_platform=self.platform)

  def test_ts_proxy_traffic_shaper_no_tsproxy(self):
    with self.assertRaises(RuntimeError):
      TsProxyTrafficShaper(self.platform)

  def test_ts_proxy_traffic_shaper_default(self):
    ts_proxy = TsProxyTrafficShaper(self.platform, self.ts_proxy_path)
    self.assertFalse(ts_proxy.is_running)

  def test_ts_proxy_open(self):
    ts_proxy = TsProxyTrafficShaper(self.platform, self.ts_proxy_path)
    network = LiveNetwork(ts_proxy, self.platform)
    session = self.create_session()

    with self.startup_process_mock() as proc:
      with ts_proxy.open(network, session):
        self.assertTrue(ts_proxy.is_running)
        self.assertEqual(proc.stdout.readline.call_count, 1)
        proc.stdout.readline.return_value = "OK"
    proc.stdin.write.assert_called_with("exit\n")
    self.assertEqual(proc.stdout.readline.call_count, 2)

  def test_ts_proxy_pause(self):
    ts_proxy = TsProxyTrafficShaper(self.platform, self.ts_proxy_path)
    network = LiveNetwork(ts_proxy, self.platform)
    session = self.create_session()

    with self.startup_process_mock() as proc:
      with ts_proxy.open(network, session):
        self.assertTrue(ts_proxy.is_running)
        self.assertEqual(proc.stdout.readline.call_count, 1)
        # All setting updates are "OK"
        proc.stdout.readline.return_value = "OK"
        with ts_proxy.pause():
          self.assertEqual(proc.stdout.readline.call_count, 4)
          self.assertTrue(ts_proxy.is_running)
        self.assertTrue(ts_proxy.is_running)
        # Default settings are already set.
        self.assertEqual(proc.stdout.readline.call_count, 4)
    self.assertEqual(proc.stdout.readline.call_count, 5)
    proc.stdin.write.assert_called_with("exit\n")

  def test_ts_proxy_pause_custom(self):
    ts_proxy = TsProxyTrafficShaper(
        self.platform,
        self.ts_proxy_path,
        rtt_ms=101,
        in_kbps=102,
        out_kbps=103)
    network = LiveNetwork(ts_proxy, self.platform)
    session = self.create_session()

    with self.startup_process_mock() as proc:
      with ts_proxy.open(network, session):
        stdout_readline = proc.stdout.readline
        stdin_write = proc.stdin.write

        self.assertTrue(ts_proxy.is_running)
        self.assertEqual(stdout_readline.call_count, 1)
        stdout_readline.reset_mock()
        # All setting updates are "OK"
        stdout_readline.return_value = "OK"

        with ts_proxy.pause():
          self.assertEqual(stdout_readline.call_count, 3)
          stdin_write.assert_any_call("set rtt 0\n")
          stdin_write.assert_any_call("set inkbps 0\n")
          stdin_write.assert_any_call("set outkbps 0\n")
          self.assertTrue(ts_proxy.is_running)

        self.assertEqual(stdout_readline.call_count, 6)
        stdin_write.assert_any_call("set rtt 101\n")
        stdin_write.assert_any_call("set inkbps 102\n")
        stdin_write.assert_any_call("set outkbps 103\n")
        stdout_readline.reset_mock()
        stdin_write.reset_mock()
    stdout_readline.assert_called_once()
    stdin_write.assert_called_once_with("exit\n")


class TsProxyServerTestCase(TsProxyBaseTestCase):

  def test_construct_invalid(self):
    with self.assertRaises(argparse.ArgumentTypeError):
      TsProxyServer(self.platform, pathlib.Path("does/not/exist"))

  def test_basic_instance(self):
    server = TsProxyServer(self.platform, self.ts_proxy_path)
    self.assertFalse(server.is_running)

    with self.assertRaises(AssertionError):
      server.set_traffic_settings()
    with self.assertRaises(AssertionError):
      _ = server.socks_proxy_port
    self.assertIsNone(server.stop())

  def test_basic_instance_http_port(self):
    server = TsProxyServer(self.platform, self.ts_proxy_path, http_port=8080)
    self.assertFalse(server.is_running)
    with self.assertRaises(AssertionError):
      _ = server.socks_proxy_port
    self.assertIsNone(server.stop())

  def test_ports(self):
    with self.assertRaises(ValueError):
      TsProxyServer(self.platform, self.ts_proxy_path, https_port=400)
    with self.assertRaises(ValueError):
      TsProxyServer(
          self.platform, self.ts_proxy_path, http_port=400, https_port=400)
    with self.assertRaises(argparse.ArgumentTypeError):
      TsProxyServer(
          self.platform, self.ts_proxy_path, http_port=-400, https_port=400)
    with self.assertRaises(argparse.ArgumentTypeError):
      TsProxyServer(
          self.platform, self.ts_proxy_path, http_port=400, https_port=-400)

  def test_start_server(self):
    server = TsProxyServer(self.platform, self.ts_proxy_path)
    with self.startup_process_mock() as proc:
      self.assertFalse(server.is_running)
      with server:
        self.assertTrue(server.is_running)
        self.assertEqual(server.socks_proxy_port, 43210)
        proc.stdout.readline.assert_called_once()
        # Set return value for exit command.
        proc.stdout.readline.return_value = "OK"
      self.assertFalse(server.is_running)
    proc.stdin.write.assert_called_with("exit\n")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
