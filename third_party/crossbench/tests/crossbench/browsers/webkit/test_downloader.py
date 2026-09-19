# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import abc
import pathlib

from typing_extensions import override

from crossbench.browsers.webkit.downloader import WebKitDownloader, \
    WebKitDownloaderMacOS
from tests import test_helper
from tests.crossbench.browsers.downloader_helper import \
    AbstractDownloaderTestCase


class AbstractWebKitDownloaderTestCase(
    AbstractDownloaderTestCase, metaclass=abc.ABCMeta):
  __test__ = False

  def test_name(self):
    self.assertEqual(WebKitDownloader.name(), "WebKit-Nightly")

  def test_wrong_versions(self) -> None:
    with self.assertRaises(ValueError):
      WebKitDownloader.load("", self.platform)
    with self.assertRaises(ValueError):
      WebKitDownloader.load("M", self.platform)
    with self.assertRaises(ValueError):
      WebKitDownloader.load("Webkit Dev", self.platform)
    with self.assertRaises(ValueError):
      WebKitDownloader.load("Safari", self.platform)

  def test_empty_path(self) -> None:
    with self.assertRaises(ValueError):
      WebKitDownloader.load(pathlib.Path("custom"), self.platform)


class BasicWebKitDownloaderTestCaseLinux(AbstractWebKitDownloaderTestCase):
  __test__ = True

  @override
  def setUp(self) -> None:
    super().setUp()
    self.platform.is_linux = True

  # TODO: Add linux support


class BasicWebKitDownloaderTestCaseMacOS(AbstractWebKitDownloaderTestCase):
  __test__ = True

  @override
  def setUp(self) -> None:
    super().setUp()
    self.platform.is_macos = True

  def test_is_valid_archive(self) -> None:
    path = pathlib.Path("download/archive.zip")
    self.fs.create_file(path)
    self.assertTrue(WebKitDownloader.is_valid(path, self.platform))
    self.assertTrue(WebKitDownloaderMacOS.is_valid(path, self.platform))

  def test_is_valid_strings(self) -> None:
    self.assertFalse(WebKitDownloader.is_valid("", self.platform))
    self.assertFalse(WebKitDownloader.is_valid("webkit-nightly", self.platform))
    self.assertTrue(
        WebKitDownloader.is_valid("webkit-nightly-12356", self.platform))
    self.assertTrue(
        WebKitDownloader.is_valid("webkit-nightly 12356", self.platform))
    self.assertTrue(
        WebKitDownloader.is_valid("webkit nightly 12356", self.platform))
    self.assertTrue(
        WebKitDownloader.is_valid("webkit-nightly-12356@main", self.platform))
    self.assertTrue(
        WebKitDownloader.is_valid("webkit-nightly 12356@main", self.platform))
    self.assertTrue(
        WebKitDownloader.is_valid("webkit nightly 12356@main", self.platform))

    self.assertTrue(WebKitDownloader.is_valid("webkit-12356", self.platform))
    self.assertTrue(WebKitDownloader.is_valid("webkit 12356", self.platform))
    self.assertTrue(
        WebKitDownloader.is_valid("webkit-12356@main", self.platform))
    self.assertTrue(
        WebKitDownloader.is_valid("webkit 12356@main", self.platform))


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
