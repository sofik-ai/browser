# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import datetime as dt
import logging
from unittest import mock

from tests.crossbench.base import CrossbenchFakeFsTestCase, \
    CrossbenchMockArgsMixin


class ActionRunnerTestCase(CrossbenchMockArgsMixin, CrossbenchFakeFsTestCase):

  def setUp(self) -> None:
    super().setUp()

    init_time = dt.datetime.now()
    datetime_patcher = mock.patch("datetime.datetime", spec=dt.datetime)
    self.datetime_mock = datetime_patcher.start()
    self.addCleanup(datetime_patcher.stop)
    self.datetime_mock.now.return_value = init_time

    def sleep_side_effect(seconds):
      self.datetime_mock.now.return_value += dt.timedelta(seconds=seconds)
      logging.debug("mocked time advanced %fs to %s", seconds,
                    self.datetime_mock.now.return_value)

    self.sleep_mock.side_effect = sleep_side_effect

  def tearDown(self):
    expected_sh_cmds = self.platform.expected_sh_cmds
    if expected_sh_cmds is not None:
      self.assertListEqual(expected_sh_cmds, [],
                           "Got additional unused shell cmds.")

    expected_js = self.browser.expected_js
    if expected_js is not None:
      self.assertListEqual(expected_js, [],
                           "Got additional unused expected JS.")
