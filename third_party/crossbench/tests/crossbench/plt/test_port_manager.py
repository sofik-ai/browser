# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import unittest
from typing import cast

from crossbench.plt.port_manager import PortForwardException, PortManager
from tests import test_helper
from tests.crossbench.mock_helper import LinuxMockPlatform, \
    MockRemotePortManager


class FakePortLinuxMockPlatform(LinuxMockPlatform):

  def _create_port_manager(self) -> PortManager:
    return MockRemotePortManager(self)


class PortManagerTestCase(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.platform = FakePortLinuxMockPlatform()
    self.port_scope = self.platform.ports
    self.port_manager: MockRemotePortManager = cast(MockRemotePortManager,
                                                    self.platform.port_manager)
    self.assertIsInstance(self.port_manager, MockRemotePortManager)

  def tearDown(self):
    self.assertFalse(self.port_manager.forwarded_ports)
    self.assertFalse(self.port_manager.reverse_forwarded_ports)
    self.assertTrue(self.port_scope.is_empty)
    super().tearDown()

  def test_default(self):
    self.assertTrue(self.port_scope.is_empty)
    self.assertFalse(self.port_manager.has_nested_scopes)

  def test_nested(self):
    self.assertTrue(self.port_scope.is_empty)
    with self.port_scope.nested() as scope:
      self.assertFalse(self.port_manager.is_empty)
      self.assertTrue(self.port_scope.is_empty)
      self.assertTrue(scope.is_empty)
      self.assertTrue(self.port_manager.has_nested_scopes)
    self.assertTrue(self.port_scope.is_empty)

  def test_stop(self):
    self.port_manager.stop()
    self.assertTrue(self.port_scope.is_empty)
    self.assertFalse(self.port_manager.has_nested_scopes)

  def test_forward_port(self):
    with self.port_scope.nested() as port_scope:
      returned_local_port = port_scope.forward(12345, 8080)
      self.assertEqual(returned_local_port, 12345)
      self.assertIn(12345, self.port_manager.forwarded_ports)
      self.assertEqual(self.port_manager.forwarded_ports[12345], 8080)
      self.assertFalse(port_scope.is_empty)
    self.assertFalse(self.port_manager.forwarded_ports)
    self.assertTrue(port_scope.is_empty)

  def test_forward_port_auto_assign(self):
    with self.port_scope.nested() as port_scope:
      returned_local_port = port_scope.forward(0, 8080)
      self.assertEqual(returned_local_port, 60001)
      self.assertIn(60001, self.port_manager.forwarded_ports)

  def test_stop_forward_port(self):
    with self.port_scope.nested() as port_scope:
      port_scope.forward(12345, 8080)
      port_scope.stop_forward(12345)
      self.assertNotIn(12345, self.port_manager.forwarded_ports)

  def test_forward_port_conflict(self):
    with self.port_scope.nested() as port_scope:
      port_scope.forward(12345, 8080)
      with self.assertRaises(PortForwardException):
        # Try to forward same local port
        port_scope.forward(12345, 8081)

  def test_stop_forward_port_not_forwarded(self):
    with self.port_scope.nested() as port_scope:
      with self.assertRaises(PortForwardException):
        port_scope.stop_forward(12345)

  def test_reverse_forward_port(self):
    with self.port_scope.nested() as port_scope:
      returned_remote_port = port_scope.reverse_forward(54321, 8081)
      self.assertEqual(returned_remote_port, 54321)
      self.assertIn(54321, self.port_manager.reverse_forwarded_ports)
      self.assertEqual(self.port_manager.reverse_forwarded_ports[54321], 8081)
      self.assertFalse(port_scope.is_empty)

  def test_reverse_forward_port_auto_assign(self):
    with self.port_scope.nested() as port_scope:
      returned_remote_port = port_scope.reverse_forward(0, 8081)
      self.assertEqual(returned_remote_port, 60001)
      self.assertIn(60001, self.port_manager.reverse_forwarded_ports)

  def test_stop_reverse_forward_port(self):
    with self.port_scope.nested() as port_scope:
      port_scope.reverse_forward(54321, 8081)
      port_scope.stop_reverse_forward(54321)
      self.assertNotIn(54321, self.port_manager.reverse_forwarded_ports)

  def test_reverse_forward_port_conflict(self):
    with self.port_scope.nested() as port_scope:
      port_scope.reverse_forward(54321, 8081)
      with self.assertRaises(PortForwardException):
        # Try to reverse forward same remote port
        port_scope.reverse_forward(54321, 8082)

  def test_stop_reverse_forward_port_not_forwarded(self):
    with self.port_scope.nested() as port_scope:
      with self.assertRaises(PortForwardException):
        port_scope.stop_reverse_forward(54321)

  def test_nested_cleanup(self):
    self.port_scope.forward(1111, 2222)
    with self.port_scope.nested() as port_scope:
      port_scope.forward(3333, 4444)
    self.assertIn(1111, self.port_manager.forwarded_ports)
    self.assertNotIn(3333, self.port_manager.forwarded_ports)
    self.assertFalse(self.port_manager.has_nested_scopes)
    self.port_manager.stop()
    self.assertTrue(self.port_scope.is_empty)
    self.assertNotIn(1111, self.port_manager.forwarded_ports)
    self.assertNotIn(3333, self.port_manager.forwarded_ports)

  def test_forward_nested_cleanup_stop_outer(self):
    self.port_scope.forward(1111, 2222)
    with self.port_scope.nested() as port_scope:
      port_scope.forward(3333, 4444)
      port_scope.stop_forward(3333)
      with self.assertRaisesRegex(PortForwardException, "1111"):
        port_scope.stop_forward(1111)
    self.port_scope.stop_forward(1111)

  def test_reverse_forward_nested_cleanup_stop_outer(self):
    self.port_scope.reverse_forward(1111, 2222)
    with self.port_scope.nested() as port_scope:
      port_scope.reverse_forward(3333, 4444)
      port_scope.stop_reverse_forward(3333)
      with self.assertRaisesRegex(PortForwardException, "1111"):
        port_scope.stop_reverse_forward(1111)
    self.port_scope.stop_reverse_forward(1111)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
