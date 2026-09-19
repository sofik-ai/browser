# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
import datetime as dt
import unittest
from unittest import mock

from crossbench.benchmarks.loading.playback_controller import \
    ForeverPlaybackController, PeriodicPlaybackController, \
    PlaybackController, RepeatPlaybackController, TimeoutPlaybackController
from tests import test_helper


class PlaybackControllerTestCase(unittest.TestCase):

  def test_parse_invalid(self):
    for invalid in [
        "11", "something", "1.5x", "4.3.h", "4.5.x", "-1x", "-1.4x", "-2h",
        "-2.1h", "1h30", "infx", "infh", "nanh", "nanx", "0s", "0"
    ]:
      with self.subTest(pattern=invalid):
        with self.assertRaises((argparse.ArgumentTypeError, ValueError)):
          PlaybackController.parse(invalid)

  def test_invalid_repeat(self):
    with self.assertRaises(argparse.ArgumentTypeError):
      PlaybackController.repeat(-1)

  def test_parse_repeat(self):
    playback = PlaybackController.parse("once")
    self.assertIsInstance(playback, RepeatPlaybackController)
    assert isinstance(playback, RepeatPlaybackController)
    self.assertEqual(playback.count, 1)
    self.assertEqual(len(list(playback)), 1)

    playback = PlaybackController.parse("1x")
    self.assertIsInstance(playback, RepeatPlaybackController)
    assert isinstance(playback, RepeatPlaybackController)
    self.assertEqual(playback.count, 1)
    self.assertEqual(len(list(playback)), 1)

    playback = PlaybackController.parse("11x")
    self.assertIsInstance(playback, RepeatPlaybackController)
    assert isinstance(playback, RepeatPlaybackController)
    self.assertEqual(playback.count, 11)
    self.assertEqual(len(list(playback)), 11)

  def test_parse_forever(self):
    playback = PlaybackController.parse("forever")
    self.assertIsInstance(playback, ForeverPlaybackController)
    playback = PlaybackController.parse("inf")
    self.assertIsInstance(playback, ForeverPlaybackController)
    playback = PlaybackController.parse("infinity")
    self.assertIsInstance(playback, ForeverPlaybackController)

  def test_parse_duration(self):
    playback = PlaybackController.parse("5s")
    self.assertIsInstance(playback, TimeoutPlaybackController)
    assert isinstance(playback, TimeoutPlaybackController)
    self.assertEqual(playback.duration, dt.timedelta(seconds=5))

    playback = PlaybackController.parse("5m")
    self.assertIsInstance(playback, TimeoutPlaybackController)
    assert isinstance(playback, TimeoutPlaybackController)
    self.assertEqual(playback.duration, dt.timedelta(minutes=5))

    playback = PlaybackController.parse("5.5m")
    self.assertIsInstance(playback, TimeoutPlaybackController)
    assert isinstance(playback, TimeoutPlaybackController)
    self.assertEqual(playback.duration, dt.timedelta(minutes=5.5))

    playback = PlaybackController.parse("5.5m")
    self.assertIsInstance(playback, TimeoutPlaybackController)
    assert isinstance(playback, TimeoutPlaybackController)
    self.assertEqual(playback.duration, dt.timedelta(minutes=5.5))

  def test_parse_periodic(self):
    playback = PlaybackController.parse("10x every 1m")
    self.assertIsInstance(playback, PeriodicPlaybackController)
    assert isinstance(playback, PeriodicPlaybackController)
    self.assertEqual(playback.period, dt.timedelta(minutes=1))
    self.assertEqual(playback.count, 10)

  def test_once(self):
    iterations = list(PlaybackController.once())
    self.assertListEqual(iterations, [0])
    iterations = list(PlaybackController.default())
    self.assertListEqual(iterations, [0])

  def test_repeat(self):
    iterations = list(PlaybackController.repeat(1))
    self.assertListEqual(iterations, [0])
    iterations = list(PlaybackController.repeat(11))
    self.assertListEqual(iterations, list(range(11)))

  def test_timeout(self):
    # Even 0-duration playback should run once
    iterations = list(PlaybackController.timeout(dt.timedelta()))
    self.assertListEqual(iterations, [0])
    iterations = list(
        PlaybackController.timeout(dt.timedelta(milliseconds=0.1)))
    self.assertListEqual(iterations, list(range(len(iterations))))

  def test_timeout_mocked(self):
    controller = PlaybackController.timeout(dt.timedelta(seconds=1))
    now = dt.datetime.now()
    with mock.patch(
        "crossbench.benchmarks.loading.playback_controller.dt") as mock_dt:
      mock_dt.datetime.now.return_value = now
      iterator = iter(controller)
      for _ in range(100):
        next(iterator)
      mock_dt.datetime.now.return_value = now + dt.timedelta(seconds=0.9)
      for _ in range(100):
        next(iterator)
      mock_dt.datetime.now.return_value = now + dt.timedelta(seconds=1)
      for _ in range(100):
        next(iterator)
      mock_dt.datetime.now.return_value = now + dt.timedelta(seconds=1.1)
      with self.assertRaises(StopIteration):
        next(iterator)

  def test_forever(self):
    for count, i in enumerate(PlaybackController.forever()):
      self.assertEqual(count, i)
      # Just run for some large-ish amount of iterations to get code coverage.
      if count > 100:
        break

  def test_periodic_mocked(self):
    controller = PlaybackController.periodic(
        period=dt.timedelta(seconds=1), count=2)
    now = dt.datetime.now()
    with mock.patch(
        "crossbench.benchmarks.loading.playback_controller.dt"
    ) as mock_dt, mock.patch(
        "crossbench.benchmarks.loading.playback_controller.time") as mock_time:
      mock_dt.datetime.now.return_value = now
      iterator = iter(controller)

      self.assertEqual(next(iterator), 0)
      mock_time.sleep.assert_not_called()

      mock_dt.datetime.now.return_value = now + dt.timedelta(seconds=0.5)
      self.assertEqual(next(iterator), 1)
      mock_time.sleep.assert_called_once_with(0.5)

      mock_dt.datetime.now.return_value = now + dt.timedelta(seconds=1.5)
      with self.assertRaises(StopIteration):
        next(iterator)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
