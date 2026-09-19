# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import contextlib
import pathlib
import tempfile
import unittest
from typing import Iterator
from unittest import mock

from sqlalchemy.exc import IntegrityError

from crossbench import plt
from crossbench.results_db.db import ResultsDB
from crossbench.results_db.records.browser import BrowserRecord
from crossbench.results_db.records.platform import PlatformRecord
from crossbench.results_db.records.run import RunRecord
from tests import test_helper
from tests.crossbench.base import BaseCrossbenchTestCase


class OpenResultDBMixin:

  @contextlib.contextmanager
  def open_results_db(self, in_memory: bool = False) -> Iterator[ResultsDB]:
    with tempfile.TemporaryDirectory() as tmp_dir:
      if in_memory:
        db = ResultsDB()
      else:
        db_file = pathlib.Path(tmp_dir) / "results.db"
        db = ResultsDB(db_file)
      yield db


class ResultsDBTestCase(OpenResultDBMixin, unittest.TestCase):

  def test_init_in_memory(self):
    db = ResultsDB()
    self.assertTrue(db.is_in_memory)
    with self.assertRaises(RuntimeError):
      _ = db.db_file

  def test_init_in_file(self):
    with self.open_results_db() as db:
      self.assertTrue(db.db_file.exists())

  def test_add_platforms(self):
    with self.open_results_db() as db:
      with db.session() as session:
        self.assertEqual(session.query(PlatformRecord).count(), 0)
      db.add_platforms([plt.PLATFORM])
      with db.session() as session:
        self.assertEqual(session.query(PlatformRecord).count(), 1)

  def test_add_platforms_in_memory(self):
    with self.open_results_db(in_memory=True) as db:
      with db.session() as session:
        self.assertEqual(session.query(PlatformRecord).count(), 0)
      db.add_platforms([plt.PLATFORM])
      with db.session() as session:
        self.assertEqual(session.query(PlatformRecord).count(), 1)

  def test_add_duplicate_platforms(self):
    with self.open_results_db() as db:
      with db.session() as session:
        self.assertEqual(session.query(PlatformRecord).count(), 0)
      # Auto deduped.
      db.add_platforms([plt.PLATFORM, plt.PLATFORM])
      with db.session() as session:
        self.assertEqual(session.query(PlatformRecord).count(), 1)


class ResultDBMockTestCase(OpenResultDBMixin, BaseCrossbenchTestCase):

  def test_add_browser(self):
    with self.open_results_db(in_memory=True) as db:
      with self.assertRaisesRegex(IntegrityError, "platform"):
        db.add_browsers(self.browsers)
      with db.session() as session:
        self.assertEqual(session.query(BrowserRecord).count(), 0)
      db.add_platforms([browser.platform for browser in self.browsers])
      db.add_browsers(self.browsers)
      with db.session() as session:
        self.assertEqual(session.query(BrowserRecord).count(), 2)

  def test_setup_runs(self):
    mock_story = mock.Mock()
    mock_story.name = "story_a"
    mock_runs = [
        mock.Mock(
            index=0,
            repetition=0,
            temperature="cold",
            story=mock_story,
            browser=self.browsers[0],
            browser_platform=self.browsers[0].platform),
        mock.Mock(
            index=1,
            repetition=0,
            temperature="cold",
            story=mock_story,
            browser=self.browsers[1],
            browser_platform=self.browsers[1].platform),
    ]
    mock_runs[0].name = "run_0_story_a"
    mock_runs[1].name = "run_1_story_a"
    with self.open_results_db(in_memory=True) as db:
      db.setup_runs(mock_runs)
      with db.session() as session:
        self.assertEqual(session.query(RunRecord).count(), 2)
      with db.session() as session:
        run_0 = session.query(RunRecord).filter_by(index=0).one()
        run_1 = session.query(RunRecord).filter_by(index=1).one()
        self.assertEqual(run_0.name, "run_0_story_a")
        self.assertEqual(run_1.name, "run_1_story_a")
        self.assertEqual(run_0.browser.label, self.browsers[0].label)
        self.assertEqual(run_1.browser.label, self.browsers[1].label)
        self.assertEqual(run_0.browser.platform.label,
                         str(self.browsers[0].platform))
        self.assertEqual(run_1.browser.platform.label,
                         str(self.browsers[1].platform))
      with self.assertRaises(IntegrityError):
        db.setup_runs(mock_runs)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
