# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
import pathlib
import unittest.mock

from crossbench.cli.config.extension import ExtensionConfig
from tests import test_helper
from tests.crossbench.cli.config.base import BaseConfigTestCase


class ExtensionConfigTestCase(BaseConfigTestCase):

  def test_crx(self):
    crx_file = pathlib.Path("/extension.crx")
    with self.assertRaisesRegex(argparse.ArgumentTypeError, "extension.crx"):
      ExtensionConfig.parse(crx_file)
    self.fs.create_file(crx_file, st_size=501)
    config = ExtensionConfig.parse(str(crx_file))
    self.assertEqual(config.crx, crx_file)
    self.assertEqual(config.id, None)
    self.assertEqual(config.unpacked, None)
    config_2 = ExtensionConfig.parse(crx_file)
    self.assertEqual(config, config_2)
    config_3 = ExtensionConfig.parse("extension.crx")
    self.assertEqual(config, config_3)

  def test_id(self):
    config = ExtensionConfig.parse("abcdefghijklmnopabcdefghijklmnop")
    self.assertEqual(config.crx, None)
    self.assertEqual(config.id, "abcdefghijklmnopabcdefghijklmnop")
    self.assertEqual(config.unpacked, None)

  def test_unpacked(self):
    manifest_file = pathlib.Path("/dir/manifest.json")
    self.fs.create_file(manifest_file, st_size=501)
    unpacked_dir = manifest_file.parent
    config = ExtensionConfig.parse(str(unpacked_dir))
    self.assertEqual(config.crx, None)
    self.assertEqual(config.id, None)
    self.assertEqual(config.unpacked, unpacked_dir)
    config = ExtensionConfig.parse(unpacked_dir)
    self.assertEqual(config.crx, None)
    self.assertEqual(config.id, None)
    self.assertEqual(config.unpacked, unpacked_dir)

  def test_does_not_exist(self):
    with self.assertRaises(argparse.ArgumentTypeError):
      ExtensionConfig.parse(str(pathlib.Path("does/not/exist")))
    with self.assertRaises(argparse.ArgumentTypeError):
      ExtensionConfig.parse(pathlib.Path("does/not/exist"))

  def test_exists_but_not_crx(self):
    cry_file = pathlib.Path("extension.cry")
    self.fs.create_file(cry_file, st_size=501)
    with self.assertRaises(argparse.ArgumentTypeError):
      ExtensionConfig.parse(str(cry_file))
    with self.assertRaises(argparse.ArgumentTypeError):
      ExtensionConfig.parse(cry_file)

  def test_unpacked_missing_manifest(self):
    unpacked_dir = pathlib.Path("dir")
    self.fs.create_dir(unpacked_dir)
    with self.assertRaises(argparse.ArgumentTypeError):
      ExtensionConfig.parse(str(unpacked_dir))
    with self.assertRaises(argparse.ArgumentTypeError):
      ExtensionConfig.parse(unpacked_dir)

  def test_parse_path_with_comma(self):
    path_with_comma = pathlib.Path("/path,with,comma.crx")
    self.fs.create_file(path_with_comma, st_size=501)
    with self.assertRaisesRegex(argparse.ArgumentTypeError, "','"):
      ExtensionConfig.parse(str(path_with_comma))
    with self.assertRaisesRegex(argparse.ArgumentTypeError, "','"):
      ExtensionConfig.parse(path_with_comma)

  def test_get_unpacked_unpacked(self):
    manifest_file = pathlib.Path("/dir/manifest.json")
    self.fs.create_file(manifest_file, st_size=501)
    unpacked_dir = manifest_file.parent
    config = ExtensionConfig.parse(unpacked_dir)

    mock_platform = unittest.mock.MagicMock()
    tmp_dir = pathlib.Path("/tmp")

    result = config.get_unpacked("1.0", tmp_dir, mock_platform)
    self.assertEqual(result, unpacked_dir)

  def test_get_unpacked_crx(self):
    crx_file = pathlib.Path("/extension.crx")
    self.fs.create_file(crx_file, st_size=501)

    config = ExtensionConfig.parse(crx_file)
    mock_platform = unittest.mock.MagicMock()
    tmp_dir = pathlib.Path("/tmp")

    with unittest.mock.patch("zipfile.ZipFile") as mock_zip:
      result = config.get_unpacked("1.0", tmp_dir, mock_platform)
      mock_zip.assert_called_once_with(crx_file)
      self.assertEqual(result, tmp_dir / "extension")

  def test_get_unpacked_id(self):
    config = ExtensionConfig.parse("abcdefghijklmnopabcdefghijklmnop")
    mock_platform = unittest.mock.MagicMock()
    cache_dir = pathlib.Path("/cache")
    self.fs.create_dir(cache_dir)
    mock_platform.local_cache_dir.return_value = cache_dir

    tmp_dir = pathlib.Path("/tmp")

    with unittest.mock.patch("crossbench.helper.url_helper.get") as mock_get, \
         unittest.mock.patch("zipfile.ZipFile") as mock_zip:

      mock_response = unittest.mock.MagicMock()
      mock_response.content = b"fake crx content"
      mock_get.return_value = mock_response

      result = config.get_unpacked("1.0", tmp_dir, mock_platform)

      mock_get.assert_called_once()
      cache_file = cache_dir / "1.0.crx"
      self.assertTrue(self.fs.exists(cache_file))
      self.assertEqual(cache_file.read_bytes(), b"fake crx content")

      mock_zip.assert_called_once_with(cache_file)
      self.assertEqual(result, tmp_dir / "abcdefghijklmnopabcdefghijklmnop")

  def test_validate_invalid(self):
    with self.assertRaisesRegex(ValueError, "crx, id, unpacked"):
      ExtensionConfig(crx=None, id=None, unpacked=None).validate()
    with self.assertRaisesRegex(ValueError, "crx, id, unpacked"):
      ExtensionConfig(
          crx=pathlib.Path("foo.crx"),
          id="abcdefghijklmnopabcdefghijklmnop").validate()

  def test_get_unpacked_id_cached(self):
    config = ExtensionConfig.parse("abcdefghijklmnopabcdefghijklmnop")
    mock_platform = unittest.mock.MagicMock()
    cache_dir = pathlib.Path("/cache")
    self.fs.create_dir(cache_dir)
    mock_platform.local_cache_dir.return_value = cache_dir

    tmp_dir = pathlib.Path("/tmp")

    cache_file = cache_dir / "1.0.crx"
    self.fs.create_file(cache_file, st_size=501)

    with unittest.mock.patch("zipfile.ZipFile") as mock_zip:
      result = config.get_unpacked("1.0", tmp_dir, mock_platform)

      mock_zip.assert_called_once_with(cache_file)
      self.assertEqual(result, tmp_dir / "abcdefghijklmnopabcdefghijklmnop")

  def test_get_unpacked_unsupported(self):
    config = ExtensionConfig(
        crx=None, id="abcdefghijklmnopabcdefghijklmnop", unpacked=None)
    object.__setattr__(config, "id", None)
    mock_platform = unittest.mock.MagicMock()
    tmp_dir = pathlib.Path("/tmp")

    with self.assertRaisesRegex(RuntimeError,
                                "Unsupported ExtensionConfig type"):
      config.get_unpacked("1.0", tmp_dir, mock_platform)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
