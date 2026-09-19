# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import json
import unittest
from typing import MutableSet

from ordered_set import OrderedSet

from crossbench.runner.run_annotation import RunAnnotation, WarnLevel
from tests import test_helper


class RunAnnotationTestCase(unittest.TestCase):

  def test_fatal(self):
    message = "FATAL custom message"
    annotation = RunAnnotation.fatal(message)
    self.assertEqual(annotation.message, message)
    self.assertEqual(annotation.level, WarnLevel.FATAL)
    self.assertTrue(json.dumps(annotation.to_json()))
    with self.assertLogs(level="FATAL") as cm:
      annotation.log()
    self.assertIn(message, "\n".join(cm.output))

  def test_error(self):
    message = "ERROR custom message"
    annotation = RunAnnotation.error(message)
    self.assertEqual(annotation.message, message)
    self.assertEqual(annotation.level, WarnLevel.ERROR)
    self.assertTrue(json.dumps(annotation.to_json()))
    with self.assertLogs(level="ERROR") as cm:
      annotation.log()
    self.assertIn(message, "\n".join(cm.output))
    with self.assertNoLogs(level="FATAL"):
      annotation.log()

  def test_warning(self):
    message = "WARNING custom message"
    annotation = RunAnnotation.warning(message)
    self.assertEqual(annotation.message, message)
    self.assertEqual(annotation.level, WarnLevel.WARNING)
    self.assertTrue(json.dumps(annotation.to_json()))
    with self.assertLogs(level="WARNING") as cm:
      annotation.log()
    self.assertIn(message, "\n".join(cm.output))
    with self.assertNoLogs(level="ERROR"):
      annotation.log()

  def test_info(self):
    message = "INFO custom message"
    annotation = RunAnnotation.info(message)
    self.assertEqual(annotation.message, message)
    self.assertEqual(annotation.level, WarnLevel.INFO)
    self.assertTrue(json.dumps(annotation.to_json()))
    with self.assertLogs(level="INFO") as cm:
      annotation.log()
    self.assertIn(message, "\n".join(cm.output))
    with self.assertNoLogs(level="WARNING"):
      annotation.log()

  def test_log_all(self):
    annotations: MutableSet[RunAnnotation] = OrderedSet()
    for level in WarnLevel:
      for i in range(10):
        annotations.add(RunAnnotation(f"Annotation {level.name} {i}", level))
    with self.assertLogs(level="INFO") as cm:
      RunAnnotation.log_all(annotations, limit=5)
    output = "\n".join(cm.output)
    for level in WarnLevel:
      for i in range(5):
        message = f"Annotation {level.name} {i}"
        self.assertIn(message, output)
      for i in range(5, 10):
        message = f"Annotation {level.name} {i}"
        self.assertNotIn(message, output)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
