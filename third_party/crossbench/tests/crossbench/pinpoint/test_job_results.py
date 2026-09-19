# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import pathlib
import unittest
from typing import Final
from unittest import mock

from crossbench.pinpoint.job_results import PinpointAttemptResults, \
    PinpointJobResults, PinpointVariantResults, download_results
from tests import test_helper
from tests.crossbench.base import CrossbenchFakeFsTestCase

_JOB_ID: Final[str] = "1234567890"
_RESULTS_URL: Final[
    str] = f"https://storage.cloud.google.com/results2-public/{_JOB_ID}.html"


class JobResultsTest(CrossbenchFakeFsTestCase):

  def get_tmp_dir(self):
    path = pathlib.Path("/tmp/test_results")
    return path.resolve()

  def setUp(self):
    super().setUp()
    self.mock_fetch = self.enterContext(
        mock.patch("crossbench.pinpoint.job_results.fetch_job_config"))
    self.mock_sh = self.enterContext(mock.patch("crossbench.plt.PLATFORM.sh"))
    self.mock_which = self.enterContext(
        mock.patch("crossbench.plt.PLATFORM.which"))
    self.mock_which.return_value = "/usr/bin/cas"
    self.mock_storage_client = self.enterContext(
        mock.patch("crossbench.pinpoint.job_results.gcloud_storage.Client"))

    # Setup mock bucket and blob
    self.mock_bucket = mock.MagicMock()
    self.mock_blob = mock.MagicMock()
    self.mock_storage_client.return_value.bucket.return_value = self.mock_bucket
    self.mock_bucket.blob.return_value = self.mock_blob

    # Mock download_to_filename to create a dummy file
    def side_effect(filename):
      with pathlib.Path(filename).open("wb") as f:
        f.write(b"fake_content")

    self.mock_blob.download_to_filename.side_effect = side_effect

  def test_download_html_results(self):
    self.mock_fetch.return_value = {
        "results_url": _RESULTS_URL,
        "status": "Completed",
        "state": [],
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "linux-perf",
        }
    }
    out_dir = self.get_tmp_dir()

    download_results(_JOB_ID, out_dir)

    self.mock_fetch.assert_called_once_with(_JOB_ID, full=True)

    self.mock_storage_client.assert_called_once()
    self.mock_storage_client.return_value.bucket.assert_called_with(
        "results2-public")
    self.mock_bucket.blob.assert_called_with(f"{_JOB_ID}.html")
    self.mock_blob.download_to_filename.assert_called_with(
        str(out_dir / f"{_JOB_ID}.html"))

    self.assertTrue((out_dir / f"{_JOB_ID}.html").exists())

  def test_download_results_incomplete_job(self):
    self.mock_fetch.return_value = {
        "job_id": _JOB_ID,
        "configuration": "linux-perf",
        "results_url": _RESULTS_URL,
        "status": "Running",
        "state": [],
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "linux-perf",
        }
    }
    out_dir = self.get_tmp_dir()

    with self.assertRaisesRegex(ValueError, "Job is not completed"):
      download_results(_JOB_ID, out_dir)

  def test_download_results(self):
    self.mock_fetch.return_value = {
        "configuration":
            "mac-intel-perf",
        "results_url":
            _RESULTS_URL,
        "status":
            "Completed",
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "mac-intel-perf",
        },
        "state": [{
            "change": {
                "commits": [{
                    "repository": "chromium",
                    "commit_position": 111,
                }],
                "label": "base",
            },
            "attempts": [{
                "executions": [
                    {  # 0: build
                    },
                    {  # 1: test
                        "details": [{
                            "key": "isolate",
                            "value": "123abc",
                        }]
                    },
                    {  # 2: values
                        "details": [{
                            "key":
                                "trace",
                            "value":
                                "trace.pb",
                            "url":
                                "https://storage.cloud.google.com/res/trace.pb"
                        }]
                    }
                ]
            }]
        }]
    }

    out_dir = self.get_tmp_dir()
    download_results(_JOB_ID, out_dir)

    self.mock_sh.assert_called_once()
    cmd = self.mock_sh.call_args[0]
    self.assertEqual(str(cmd[0]), "/usr/bin/cas")
    self.assertEqual(cmd[1], "download")
    self.assertIn("123abc", cmd)
    self.assertIn("-dir", cmd)
    self.assertEqual(cmd[cmd.index("-dir") + 1], out_dir / "base" / "1")

    # Verify trace download
    self.mock_storage_client.return_value.bucket.assert_any_call("res")
    self.mock_bucket.blob.assert_any_call("trace.pb")
    self.mock_blob.download_to_filename.assert_any_call(
        str(out_dir / "base" / "1" / "trace.pb"))

    self.assertTrue((out_dir / "base" / "1" / "trace.pb").exists())

  def test_download_results_no_label(self):
    self.mock_fetch.return_value = {
        "configuration":
            "linux-perf",
        "results_url":
            _RESULTS_URL,
        "status":
            "Completed",
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "linux-perf",
        },
        "state": [{
            "change": {
                "commits": [{
                    "repository": "chromium",
                    "commit_position": 123,
                }, {
                    "repository": "v8",
                    "commit_position": 456,
                }],
            },
            "attempts": [{
                "executions": []
            }]
        }]
    }

    out_dir = self.get_tmp_dir()
    download_results(_JOB_ID, out_dir)

    self.assertTrue((out_dir / "chromium_123_v8_456").exists())

  def test_download_results_no_label_no_commits(self):
    self.mock_fetch.return_value = {
        "configuration": "linux-perf",
        "results_url": _RESULTS_URL,
        "status": "Completed",
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "linux-perf",
        },
        "state": [{
            "change": {},
            "attempts": [{
                "executions": []
            }]
        }]
    }

    out_dir = self.get_tmp_dir()
    download_results(_JOB_ID, out_dir)

    self.assertTrue((out_dir / "variant_0").exists())

  def test_download_results_missing_cas(self):
    self.mock_which.return_value = None
    self.mock_fetch.return_value = {
        "configuration": "linux-perf",
        "results_url": _RESULTS_URL,
        "status": "Completed",
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "linux-perf",
        },
        "state": []
    }
    out_dir = self.get_tmp_dir()

    with self.assertRaisesRegex(FileNotFoundError, "Missing binaries.*cas"):
      download_results(_JOB_ID, out_dir)

  def test_download_results_install_cas(self):

    def which_side_effect(binary):
      if binary == "cas":
        return None
      if binary == "cipd":
        return pathlib.Path("/usr/bin/cipd")
      return None

    self.mock_which.side_effect = which_side_effect

    self.mock_fetch.return_value = {
        "configuration": "linux-perf",
        "results_url": _RESULTS_URL,
        "status": "Completed",
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "linux-perf",
        },
        "state": []
    }
    out_dir = self.get_tmp_dir()

    download_results(_JOB_ID, out_dir)

    self.assertEqual(self.mock_sh.call_count, 2)

    init_args = self.mock_sh.call_args_list[0][0]
    self.assertEqual(init_args[0], "cipd")
    self.assertEqual(init_args[1], "init")
    self.assertEqual(init_args[2], "-force")

    install_args = self.mock_sh.call_args_list[1][0]
    self.assertEqual(install_args[0], "cipd")
    self.assertEqual(install_args[1], "install")
    self.assertIn("infra/tools/luci/cas/${platform}", install_args)

  def test_download_results_no_cipd(self):
    self.mock_which.return_value = None

    self.mock_fetch.return_value = {
        "configuration": "linux-perf",
        "results_url": _RESULTS_URL,
        "status": "Completed",
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "linux-perf",
        },
        "state": []
    }
    out_dir = self.get_tmp_dir()

    with self.assertRaises(FileNotFoundError):
      download_results(_JOB_ID, out_dir)

  def test_download_results_use_cas_from_cache(self):
    self.mock_which.return_value = None
    cache_dir = self.get_tmp_dir() / "cache" / "cipd"
    (cache_dir / "cas").mkdir(parents=True)
    # Fake cas executable file.
    (cache_dir / "cas" / "cas").open("a").close()

    with mock.patch(
        "crossbench.plt.PLATFORM.local_cache_dir", return_value=cache_dir):
      self.mock_fetch.return_value = {
          "configuration":
              "linux-perf",
          "results_url":
              _RESULTS_URL,
          "status":
              "Completed",
          "arguments": {
              "benchmark": "speedometer3",
              "configuration": "linux-perf",
          },
          "state": [{
              "change": {},
              "attempts": [{
                  "executions": [
                      {  # 0: build
                      },
                      {  # 1: test
                          "details": [{
                              "key": "isolate",
                              "value": "123abc_cached",
                          }]
                      },
                  ]
              }]
          }]
      }
      out_dir = self.get_tmp_dir() / "out"
      download_results(_JOB_ID, out_dir)

    args = self.mock_sh.call_args[0]
    self.assertEqual(args[0], cache_dir / "cas" / "cas")
    self.assertIn("123abc_cached", args)

  def test_download_results_file_exists_no_force(self):
    self.mock_fetch.return_value = {
        "configuration": "linux-perf",
        "results_url": _RESULTS_URL,
        "status": "Completed",
        "state": [],
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "linux-perf",
        }
    }
    out_dir = self.get_tmp_dir()
    out_dir.mkdir(parents=True)

    with self.assertRaises(FileExistsError):
      download_results(_JOB_ID, out_dir)

  def test_download_results_file_exists_with_force(self):
    self.mock_fetch.return_value = {
        "configuration": "linux-perf",
        "results_url": _RESULTS_URL,
        "status": "Completed",
        "state": [],
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "linux-perf",
        }
    }
    out_dir = self.get_tmp_dir()
    out_dir.mkdir(parents=True)

    download_results(_JOB_ID, out_dir, force=True)

    self.mock_fetch.assert_called_once_with(_JOB_ID, full=True)
    self.assertTrue((out_dir / f"{_JOB_ID}.html").exists())


class PinpointJobResultsTestCase(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_fetch = self.enterContext(
        mock.patch("crossbench.pinpoint.job_results.fetch_job_config"))
    self.mock_fetch.return_value = {
        "results_url": "https://example.com/results.html",
        "status": "Completed",
        "created": "2024-01-01T12:00:00Z",
        "state": [],
        "arguments": {
            "benchmark": "speedometer3",
            "configuration": "linux-perf",
        }
    }

  def test_created_date_valid(self):
    job = PinpointJobResults(_JOB_ID)
    self.assertEqual(job.created_date, "2024-01-01_120000")

  def test_created_date_invalid(self):
    self.mock_fetch.return_value["created"] = "invalid-date"
    job = PinpointJobResults(_JOB_ID)
    with self.assertLogs(level="WARNING") as cm:
      self.assertEqual(job.created_date, "invalid-date")
    self.assertIn("Invalid created time", cm.output[0])

  def test_init_valid(self):
    job = PinpointJobResults(_JOB_ID)
    self.assertEqual(job.name, "pinpoint_speedometer3_linux-perf")
    self.assertEqual(job.benchmark, "speedometer3")
    self.assertEqual(job.bot, "linux-perf")
    self.assertEqual(job.status, "Completed")
    self.assertEqual(job.results_url, "https://example.com/results.html")

  def test_init_invalid_status(self):
    self.mock_fetch.return_value = {"status": "Running"}
    with self.assertRaisesRegex(ValueError, "Job is not completed"):
      PinpointJobResults(_JOB_ID)

  def test_variant_name_with_label(self):
    data = {"change": {"label": "test-label"}, "attempts": []}
    variant = PinpointVariantResults(data, 0)
    self.assertEqual(variant.name, "test-label")

  def test_variant_name_with_commits(self):
    data = {
        "change": {
            "commits": [{
                "repository": "chromium",
                "commit_position": 123
            }, {
                "repository": "v8",
                "commit_position": 456
            }]
        },
        "attempts": []
    }
    variant = PinpointVariantResults(data, 0)
    self.assertEqual(variant.name, "chromium_123_v8_456")

  def test_variant_name_fallback(self):
    data = {"change": {}, "attempts": []}
    variant = PinpointVariantResults(data, 5)
    self.assertEqual(variant.name, "variant_5")

  def test_find_isolate(self):
    data = {
        "executions": [
            {},  # 0: build
            {  # 1: test
                "details": [{
                    "key": "isolate",
                    "value": "123abchash"
                }]
            }
        ]
    }
    attempt = PinpointAttemptResults(data, 0)
    self.assertEqual(attempt.cas_isolate, "123abchash")

  def test_find_isolate_missing(self):
    data = {"executions": [{}, {}]}
    attempt = PinpointAttemptResults(data, 0)
    self.assertIsNone(attempt.cas_isolate)

  def test_find_trace(self):
    data = {
        "executions": [
            {},
            {},
            {  # 2: values
                "details": [{
                    "key": "trace",
                    "value": "trace.pb",
                    "url": "gs://bucket/trace.pb"
                }]
            }
        ]
    }
    attempt = PinpointAttemptResults(data, 0)
    self.assertEqual(attempt.perfetto_trace_url_by_name,
                     {"trace.pb": "gs://bucket/trace.pb"})

  def test_find_trace_missing(self):
    data = {"executions": [{}, {}, {}]}
    attempt = PinpointAttemptResults(data, 0)
    self.assertEqual(attempt.perfetto_trace_url_by_name, {})

  def test_find_multiple_traces(self):
    data = {
        "executions": [
            {},
            {},
            {  # 2: values
                "details": [{
                    "key": "trace",
                    "value": "trace1.pb",
                    "url": "gs://bucket/trace1.pb"
                }, {
                    "key": "trace",
                    "value": "trace2",
                    "url": "gs://bucket/trace2.pb"
                }]
            }
        ]
    }
    attempt = PinpointAttemptResults(data, 0)
    self.assertEqual(attempt.perfetto_trace_url_by_name, {
        "trace1.pb": "gs://bucket/trace1.pb",
        "trace2.pb": "gs://bucket/trace2.pb"
    })


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
