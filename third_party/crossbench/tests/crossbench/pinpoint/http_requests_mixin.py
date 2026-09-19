# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from unittest import mock
from tests.crossbench.base import BaseCrossbenchTestCase


class MockHttpRequestsMixin(BaseCrossbenchTestCase):
  """Mixin to mock the http_requests.get and http_requests.post functions."""

  def setUp(self):
    super().setUp()
    self.mock_get = self.enterContext(
        mock.patch("crossbench.pinpoint.http_requests.get"))
    self.mock_get.return_value.raise_for_status.return_value = None
    self.mock_post = self.enterContext(
        mock.patch("crossbench.pinpoint.http_requests.post"))
    self.mock_post.return_value.raise_for_status.return_value = None
