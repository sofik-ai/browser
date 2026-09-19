# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import logging
import re
import shutil
from typing import TYPE_CHECKING

import pytest

from crossbench import plt
from crossbench.browsers.chrome.downloader import ChromeDownloader
from crossbench.browsers.chrome.webdriver import ChromeWebDriver
from crossbench.browsers.chromium.driver_finder import ChromeDriverFinder, \
    DriverNotFoundError
from crossbench.browsers.settings import Settings
from tests import test_helper
from tests.end2end.desktop.browser.helper import tmp_platform_cache_dir

if TYPE_CHECKING:
  import pathlib

  from tests.test_helper import TestEnv


def check_gsutil_access():
  gsutil_path = plt.PLATFORM.which("gsutil")
  if not gsutil_path:
    pytest.skip("Could not find gsutil")
  try:
    plt.PLATFORM.sh_stdout(
        gsutil_path, "ls",
        "gs://chrome-signed/desktop-5c0tCh/111.0.5563.19/linux64")
  except plt.SubprocessError as e:
    logging.info("Could not access chrome bucket with gsutil: %s", e)
    if "does not have storage.objects.list access" in str(e):
      pytest.skip(
          "gsutil likely has no access to gs://chrome-signed/desktop-5c0tCh")
    raise e


def _load_and_check_version(output_dir: pathlib.Path, archive_dir: pathlib.Path,
                            version_or_archive: str | pathlib.Path,
                            version_str: str) -> pathlib.Path:
  check_gsutil_access()
  with tmp_platform_cache_dir(output_dir):
    app_path: pathlib.Path = ChromeDownloader.load(version_or_archive,
                                                   plt.PLATFORM)
    assert app_path.is_relative_to(output_dir)
    assert archive_dir.exists()
    assert app_path.exists()
    assert version_str in plt.PLATFORM.app_version(app_path)
    archives = list(archive_dir.iterdir())
    assert len(archives) == 1
    assert app_path.exists()
    chrome = ChromeWebDriver(
        "test-chrome", app_path, settings=Settings(platform=plt.PLATFORM))
    assert version_str in str(chrome.version)
    _load_and_check_chromedriver(output_dir, chrome)
    return app_path


def _load_and_check_chromedriver(output_dir, chrome: ChromeWebDriver) -> None:
  chromedriver_binaries_dir = output_dir / "chromedriver-binaries"
  assert not chromedriver_binaries_dir.exists()
  with tmp_platform_cache_dir(chromedriver_binaries_dir):
    finder = ChromeDriverFinder(chrome)
    driver_dir = chromedriver_binaries_dir / "driver"
    assert not list(driver_dir.iterdir())
    with pytest.raises(DriverNotFoundError):
      finder.find_local_build()
    driver_path: pathlib.Path = finder.download()
    assert list(driver_dir.iterdir()) == [driver_path]
    assert driver_path.is_file()
    # Downloading again should use the cache-version
    driver_path = finder.download()
    assert list(driver_dir.iterdir()) == [driver_path]
    assert driver_path.is_file()
    # Restore output dir state.
    driver_path.unlink()
    driver_dir.rmdir()
  chromedriver_binaries_dir.rmdir()


def _delete_extracted_app(output_dir: pathlib.Path, app_version: str) -> None:
  browser_bin = output_dir / "browser_bin"
  pattern = re.compile(app_version)
  for extracted_app_path in list(browser_bin.iterdir()):
    if pattern.search(str(extracted_app_path)):
      shutil.rmtree(str(extracted_app_path))


@pytest.mark.skipif(
    plt.PLATFORM.is_linux, reason="No canary versions on linux.")
def test_download_pre_115_canary(test_env: TestEnv) -> None:
  test_env.assert_empty_output_dir()
  _load_and_check_version(test_env.output_dir, test_env.archive_dir,
                          "chrome-114.0.5734.0 canary", "114.0.5734.0")


def test_download_major_version_milestone(test_env: TestEnv) -> None:
  test_env.assert_empty_output_dir()
  _load_and_check_version(
      test_env.output_dir,
      test_env.archive_dir,
      "chrome-M111",
      "111",
  )

  # Re-downloading should reuse the extracted app.
  app_path = _load_and_check_version(
      test_env.output_dir,
      test_env.archive_dir,
      "chrome-M111",
      "111",
  )

  _delete_extracted_app(test_env.output_dir, "M111")
  assert not app_path.exists()
  _load_and_check_version(
      test_env.output_dir,
      test_env.archive_dir,
      "chrome-M111",
      "111",
  )


def test_download_any_channel_milestone(test_env: TestEnv) -> None:
  test_env.assert_empty_output_dir()
  _load_and_check_version(
      test_env.output_dir,
      test_env.archive_dir,
      "chrome-M136-any",
      "136",
  )

  # Re-downloading should reuse the extracted app.
  app_path = _load_and_check_version(
      test_env.output_dir,
      test_env.archive_dir,
      "chrome-M136-any",
      "136",
  )

  _delete_extracted_app(test_env.output_dir, "M136.any")
  assert not app_path.exists()
  _load_and_check_version(
      test_env.output_dir,
      test_env.archive_dir,
      "chrome-M136-any",
      "136",
  )


def test_download_major_version_chrome_for_testing(test_env: TestEnv) -> None:
  # Post M114 we're relying on the new chrome-for-testing download
  test_env.assert_empty_output_dir()
  _load_and_check_version(
      test_env.output_dir,
      test_env.archive_dir,
      "chrome-M115",
      "115",
  )

  # Re-downloading should reuse the extracted app.
  app_path = _load_and_check_version(
      test_env.output_dir,
      test_env.archive_dir,
      "chrome-M115",
      "115",
  )

  _delete_extracted_app(test_env.output_dir, "M115")
  assert not app_path.exists()
  _load_and_check_version(
      test_env.output_dir,
      test_env.archive_dir,
      "chrome-M115",
      "115",
  )


def test_download_specific_version_pre_115_stable(test_env: TestEnv) -> None:
  test_env.assert_empty_output_dir()
  version_str = "111.0.5563.146"
  _load_and_check_version(test_env.output_dir, test_env.archive_dir,
                          f"chrome-{version_str}", version_str)

  # Re-downloading should work as well and hit the extracted app.
  app_path = _load_and_check_version(test_env.output_dir, test_env.archive_dir,
                                     f"chrome-{version_str}", version_str)

  _delete_extracted_app(test_env.output_dir, version_str)
  assert not app_path.exists()
  app_path = _load_and_check_version(test_env.output_dir, test_env.archive_dir,
                                     f"chrome-{version_str}", version_str)

  _delete_extracted_app(test_env.output_dir, version_str)
  assert not app_path.exists()
  archives = list(test_env.archive_dir.iterdir())
  assert len(archives) == 1
  archive = archives[0]
  app_path = _load_and_check_version(test_env.output_dir, test_env.archive_dir,
                                     archive, version_str)
  assert list(test_env.archive_dir.iterdir()) == [archive]


def test_download_old_major_version(test_env: TestEnv) -> None:
  if plt.PLATFORM.is_macos and plt.PLATFORM.is_arm64:
    # Old versions only supported on intel machines.
    return
  test_env.assert_empty_output_dir()
  _load_and_check_version(test_env.output_dir, test_env.archive_dir,
                          "chrome-M68", "68")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
