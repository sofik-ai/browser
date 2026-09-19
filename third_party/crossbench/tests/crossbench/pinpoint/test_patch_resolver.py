# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing import Final
from unittest import mock

from crossbench.pinpoint import patch_resolver
from tests import test_helper
from tests.crossbench.pinpoint.http_requests_mixin import MockHttpRequestsMixin

_TEST_PATCH: Final[
    str] = "https://chromium-review.googlesource.com/c/chromium/src/+/12345"

_TEST_PATCH_WITH_PATCHSET: Final[str] = _TEST_PATCH + "/6"


class PatchResolverTest(MockHttpRequestsMixin):

  def setUp(self):
    super().setUp()

    def mock_get_side_effect(url, **kwargs):
      self.assertTrue(
          url.startswith(
              "https://chromium-review.googlesource.com/changes/12345"))

      mock_response = mock.Mock()
      mock_response.text = ")]}'\n{\"project\": \"chromium/src\"}"
      mock_response.raise_for_status.return_value = None
      return mock_response

    self.mock_get.side_effect = mock_get_side_effect

  def test_resolve_patch(self):
    for protocol in ["", "https://"]:
      for path in ["crrev/", "crrev.com/"]:
        for c in ["", "c/"]:
          patch = protocol + path + c + "12345"
          self.assertEqual(patch_resolver.resolve_patch(patch), _TEST_PATCH)
          self.assertEqual(
              patch_resolver.resolve_patch(patch + "/6"),
              _TEST_PATCH_WITH_PATCHSET)

  def test_resolve_patch_invalid(self):
    with self.assertRaises(ValueError):
      patch_resolver.resolve_patch("invalid")
    with self.assertRaises(ValueError):
      patch_resolver.resolve_patch("i/12345")
    with self.assertRaises(ValueError):
      patch_resolver.resolve_patch("12345/6/7")


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
