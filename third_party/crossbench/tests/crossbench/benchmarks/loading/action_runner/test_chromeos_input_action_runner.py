# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import annotations

import datetime as dt
import pathlib
import unittest
from typing import TYPE_CHECKING, Optional

from crossbench.action_runner.action.click import ClickAction
from crossbench.action_runner.action.position import PositionConfig
from crossbench.action_runner.action.scroll import ScrollAction
from crossbench.action_runner.chromeos_input_action_runner import \
    SCRIPTS_DIR, ChromeOSInputActionRunner, ChromeOSTouchEvent, \
    ChromeOSViewportInfo, TouchDevice
from crossbench.action_runner.display_rectangle import DisplayRectangle
from crossbench.action_runner.element_not_found_error import \
    ElementNotFoundError
from crossbench.benchmarks.loading.input_source import InputSource
from crossbench.benchmarks.loading.point import Point
from crossbench.browsers.settings import Settings
from crossbench.flags.base import Flags
from crossbench.runner.groups.session import BrowserSessionRunGroup
from tests import test_helper
from tests.crossbench.action_runner.action_runner_test_case import \
    ActionRunnerTestCase
from tests.crossbench.mock_browser import JsInvocation, MockChromeStable
from tests.crossbench.mock_helper import ChromeOsSshMockPlatform, \
    LinuxMockPlatform, MockFd, MockPopen
from tests.crossbench.runner.helper import MockRun, MockRunner

if TYPE_CHECKING:
  from crossbench.action_runner.action.action import Action


class ChromeOSTouchEventTestCase(unittest.TestCase):

  _FAKE_TOUCH_DEVICE: TouchDevice = TouchDevice("/dev/input/event0", 200, 100)

  def test_zero_duration_tap(self):
    expected_playback: str = """E: 1.000000 0003 0039 0
E: 1.000000 0003 0035 200
E: 1.000000 0003 0036 100
E: 1.000000 0001 014a 1
E: 1.000000 0003 0000 200
E: 1.000000 0003 0001 100
E: 1.000000 0000 0000 0
E: 1.000000 0003 0039 -1
E: 1.000000 0001 014a 0
E: 1.000000 0000 0000 0
"""

    tap_event: ChromeOSTouchEvent = ChromeOSTouchEvent(
        self._FAKE_TOUCH_DEVICE, DisplayRectangle(Point(0, 0), 200, 100),
        Point(200, 100))

    playback = str(tap_event)

    self.assertEqual(playback, expected_playback)

  def test_long_tap(self):
    expected_playback: str = """E: 1.000000 0003 0039 0
E: 1.000000 0003 0035 200
E: 1.000000 0003 0036 100
E: 1.000000 0001 014a 1
E: 1.000000 0003 0000 200
E: 1.000000 0003 0001 100
E: 1.000000 0000 0000 0
E: 5.000000 0003 0039 -1
E: 5.000000 0001 014a 0
E: 5.000000 0000 0000 0
"""

    tap_event: ChromeOSTouchEvent = ChromeOSTouchEvent(
        self._FAKE_TOUCH_DEVICE, DisplayRectangle(Point(0, 0), 200, 100),
        Point(200, 100), None, dt.timedelta(seconds=4))

    playback = str(tap_event)

    self.assertEqual(playback, expected_playback)

  def test_out_of_bounds_tap_raises(self):
    tap_event: ChromeOSTouchEvent = ChromeOSTouchEvent(
        self._FAKE_TOUCH_DEVICE, DisplayRectangle(Point(0, 0), 200, 100),
        Point(201, 101))

    with self.assertRaisesRegex(ValueError, "out of bounds"):
      str(tap_event)

  def test_reference_coordinates(self):
    tap_event: ChromeOSTouchEvent = ChromeOSTouchEvent(
        self._FAKE_TOUCH_DEVICE, DisplayRectangle(Point(0, 0), 600, 300),
        Point(53, 53))

    expected_playback: str = """E: 1.000000 0003 0039 0
E: 1.000000 0003 0035 18
E: 1.000000 0003 0036 18
E: 1.000000 0001 014a 1
E: 1.000000 0003 0000 18
E: 1.000000 0003 0001 18
E: 1.000000 0000 0000 0
E: 1.000000 0003 0039 -1
E: 1.000000 0001 014a 0
E: 1.000000 0000 0000 0
"""
    playback = str(tap_event)
    self.assertEqual(playback, expected_playback)

  def test_minimum_swipe(self):
    expected_playback: str = """E: 1.000000 0003 0039 0
E: 1.000000 0003 0035 100
E: 1.000000 0003 0036 50
E: 1.000000 0001 014a 1
E: 1.000000 0003 0000 100
E: 1.000000 0003 0001 50
E: 1.000000 0000 0000 0
E: 1.016667 0003 0035 200
E: 1.016667 0003 0036 100
E: 1.016667 0003 0000 200
E: 1.016667 0003 0001 100
E: 1.016667 0000 0000 0
E: 1.016667 0003 0039 -1
E: 1.016667 0001 014a 0
E: 1.016667 0000 0000 0
"""

    swipe_event: ChromeOSTouchEvent = ChromeOSTouchEvent(
        self._FAKE_TOUCH_DEVICE, DisplayRectangle(Point(0, 0), 200, 100),
        Point(100, 50), Point(200, 100), dt.timedelta(seconds=0.016))

    playback = str(swipe_event)

    self.assertEqual(playback, expected_playback)

  def test_multi_step_swipe(self):
    expected_playback: str = """E: 1.000000 0003 0039 0
E: 1.000000 0003 0035 100
E: 1.000000 0003 0036 50
E: 1.000000 0001 014a 1
E: 1.000000 0003 0000 100
E: 1.000000 0003 0001 50
E: 1.000000 0000 0000 0
E: 1.016667 0003 0035 110
E: 1.016667 0003 0036 60
E: 1.016667 0003 0000 110
E: 1.016667 0003 0001 60
E: 1.016667 0000 0000 0
E: 1.033333 0003 0035 120
E: 1.033333 0003 0036 70
E: 1.033333 0003 0000 120
E: 1.033333 0003 0001 70
E: 1.033333 0000 0000 0
E: 1.050000 0003 0035 130
E: 1.050000 0003 0036 80
E: 1.050000 0003 0000 130
E: 1.050000 0003 0001 80
E: 1.050000 0000 0000 0
E: 1.066667 0003 0035 140
E: 1.066667 0003 0036 90
E: 1.066667 0003 0000 140
E: 1.066667 0003 0001 90
E: 1.066667 0000 0000 0
E: 1.066667 0003 0039 -1
E: 1.066667 0001 014a 0
E: 1.066667 0000 0000 0
"""

    swipe_event: ChromeOSTouchEvent = ChromeOSTouchEvent(
        self._FAKE_TOUCH_DEVICE, DisplayRectangle(Point(0, 0), 200, 100),
        Point(100, 50), Point(140, 90), dt.timedelta(seconds=0.064))

    playback = str(swipe_event)

    self.assertEqual(playback, expected_playback)


class ChromeOSViewportInfoTestCase(unittest.TestCase):

  def test_element_rect_no_element(self) -> None:
    viewport_info = ChromeOSViewportInfo(
        device_pixel_ratio=1,
        window_outer_width=1920,
        window_inner_width=1920,
        window_inner_height=1080,
        screen_width=1920,
        screen_height=1080,
        screen_avail_width=1920,
        screen_avail_height=1080,
        window_offset_x=0,
        window_offset_y=0,
        element_rect=None)

    self.assertFalse(viewport_info.element_rect)

  _NO_RATIO_NO_OFFSET = ChromeOSViewportInfo(
      device_pixel_ratio=1,
      window_outer_width=1920,
      window_inner_width=1920,
      window_inner_height=1080,
      screen_width=1920,
      screen_height=1080,
      screen_avail_width=1920,
      screen_avail_height=1080,
      window_offset_x=0,
      window_offset_y=0,
      element_rect=DisplayRectangle(Point(1, 2), 3, 4))

  def test_browser_viewable_no_ratios_no_offset(self) -> None:
    self.assertEqual(self._NO_RATIO_NO_OFFSET.browser_viewable,
                     DisplayRectangle(Point(0, 0), 1920, 1080))

  def test_css_to_native_no_ratio(self) -> None:
    self.assertEqual(
        self._NO_RATIO_NO_OFFSET.css_to_native_distance(1234), 1234)

  def test_element_rect_no_ratio_no_offset(self) -> None:
    self.assertEqual(self._NO_RATIO_NO_OFFSET.element_rect,
                     DisplayRectangle(Point(1, 2), 3, 4))

  _DOUBLE_RATIO_NO_OFFSET = ChromeOSViewportInfo(
      device_pixel_ratio=2,
      window_outer_width=1920,
      window_inner_width=1920,
      window_inner_height=1080,
      screen_width=1920,
      screen_height=1080,
      screen_avail_width=1920,
      screen_avail_height=1080,
      window_offset_x=0,
      window_offset_y=0,
      element_rect=DisplayRectangle(Point(1, 2), 3, 4))

  def test_css_to_native_double_ratio(self) -> None:
    viewport_info = self._DOUBLE_RATIO_NO_OFFSET

    self.assertEqual(viewport_info.css_to_native_distance(100), 200)

  def test_browser_viewable_double_ratio(self) -> None:
    viewport_info = self._DOUBLE_RATIO_NO_OFFSET

    self.assertEqual(viewport_info.browser_viewable,
                     DisplayRectangle(Point(0, 0), 3840, 2160))

  def test_element_rect_double_ratio(self) -> None:
    viewport_info = self._DOUBLE_RATIO_NO_OFFSET

    self.assertEqual(viewport_info.element_rect,
                     DisplayRectangle(Point(2, 4), 6, 8))

  def test_browser_viewable_no_ratios_with_browser_window_offset(self) -> None:
    viewport_info = ChromeOSViewportInfo(
        device_pixel_ratio=1,
        window_outer_width=1920,
        window_inner_width=1920,
        window_inner_height=1080,
        screen_width=1920,
        screen_height=1080,
        screen_avail_width=1920,
        screen_avail_height=1080,
        window_offset_x=10,
        window_offset_y=20,
        element_rect=None)

    self.assertEqual(viewport_info.browser_viewable,
                     DisplayRectangle(Point(10, 20), 1910, 1060))

  def test_element_rect_no_ratios_with_browser_window_offset(self) -> None:
    viewport_info = ChromeOSViewportInfo(
        device_pixel_ratio=1,
        window_outer_width=1920,
        window_inner_width=1920,
        window_inner_height=1080,
        screen_width=1920,
        screen_height=1080,
        screen_avail_width=1920,
        screen_avail_height=1080,
        window_offset_x=10,
        window_offset_y=20,
        element_rect=DisplayRectangle(Point(1, 2), 3, 4))

    self.assertEqual(viewport_info.element_rect,
                     DisplayRectangle(Point(11, 22), 3, 4))

  def test_element_rect_no_ratios_with_browser_window_offset_2(self) -> None:
    viewport_info = ChromeOSViewportInfo(
        device_pixel_ratio=1,
        window_outer_width=1920,
        window_inner_width=1920,
        window_inner_height=900,
        screen_width=1920,
        screen_height=1080,
        screen_avail_width=1920,
        screen_avail_height=1080,
        window_offset_x=10,
        window_offset_y=20,
        element_rect=None)

    self.assertEqual(viewport_info.browser_viewable,
                     DisplayRectangle(Point(10, 200), 1910, 880))

  def test_element_rect_no_ratios_with_browser_window_offset_3(self) -> None:
    viewport_info = ChromeOSViewportInfo(
        device_pixel_ratio=1,
        window_outer_width=1920,
        window_inner_width=1920,
        window_inner_height=900,
        screen_width=1920,
        screen_height=1080,
        screen_avail_width=1920,
        screen_avail_height=1080,
        window_offset_x=10,
        window_offset_y=20,
        element_rect=DisplayRectangle(Point(1, 2), 3, 4))

    self.assertEqual(viewport_info.element_rect,
                     DisplayRectangle(Point(11, 202), 3, 4))


class ChromeOSInputActionRunnerTestCase(ActionRunnerTestCase):
  _FAKE_TOUCH_DEVICE: TouchDevice = TouchDevice("/dev/input/event0", 1920, 1080)

  _NO_ELEMENT_JS_RESULT: JsInvocation = JsInvocation(result=[
      False,  # Found element
      1,  # pixel ratio
      1920,  # window outer width
      1920,  # window inner width
      1080,  # window inner height
      1920,  # screen width
      1080,  # screen height
      1920,  # screen avail width
      1080,  # screen avail height
      0,  # screenX
      0,  # screenY
      0,  # element left
      0,  # element top
      0,  # element width
      0,  # element height
  ])

  def setUp(self) -> None:
    super().setUp()
    self.host_platform = LinuxMockPlatform()
    self.platform = ChromeOsSshMockPlatform(
        host_platform=self.host_platform,
        host="1.1.1.1",
        port="1234",
        ssh_port="22",
        ssh_user="root")

    self.platform.expect_sh("[", "-e", "/usr/bin/google-chrome", "]", result="")
    self.platform.expect_sh("[", "-f", "/usr/bin/google-chrome", "]", result="")

    self.browser = MockChromeStable(
        "mock browser", settings=Settings(platform=self.platform))
    self.runner = MockRunner()
    self.root_dir = pathlib.Path()
    self.session = BrowserSessionRunGroup(self.runner.env,
                                          self.runner.probes, self.browser,
                                          Flags(), 1, self.root_dir, True, True)
    self.action_runner = ChromeOSInputActionRunner()
    self.run = MockRun(self.runner, self.session, "run 1", self.action_runner)

  def run_action(self, action: Action) -> None:
    action.run_with(self.run, self.action_runner)

  def expect_touch_setup(self, expected_js: JsInvocation, touch_count: int = 1):

    path = SCRIPTS_DIR / "query_touch_device.py"
    self.fs.create_file(path, contents="query_touch_device")

    path = SCRIPTS_DIR / "get_window_positions.js"
    self.fs.create_file(path, contents="get_window_positions")

    # Query touch device response
    self.platform.expect_sh(
        "python3",
        "-",
        result=f"Performing autotest_lib import\n{self._FAKE_TOUCH_DEVICE}")

    self.browser.expect_js(expected_js=expected_js)

    for _ in range(touch_count):
      self.platform.expect_sh(
          "mktemp",
          "/usr/local/tmp/XXXXXXXXXXX",
          result="/usr/local/tmp/RANDOM")
      self.platform.expect_sh("evemu-play --insert-slot0 /dev/input/event0 <"
                              " /usr/local/tmp/RANDOM")
      self.platform.expect_sh("[", "-e", "/usr/local/tmp/RANDOM", "]")
      self.platform.expect_sh("rm", "/usr/local/tmp/RANDOM")

  def expect_mouse_click(
      self,
      expected_js: JsInvocation,
      clicked_coordinates: Optional[Point],
      click_duration: dt.timedelta = dt.timedelta(seconds=0)):

    path = SCRIPTS_DIR / "get_window_positions.js"
    self.fs.create_file(path, contents="get_window_positions")

    self.browser.expect_js(expected_js=expected_js)

    path = SCRIPTS_DIR / "mouse.py"
    self.fs.create_file(path, contents="mouse")

    self.platform.expect_sh(
        "mktemp", "/usr/local/tmp/XXXXXXXXXXX", result="/usr/local/tmp/RANDOM")
    self.platform.expect_sh("python3", "/usr/local/tmp/RANDOM", "1920", "1080")
    self.platform.expect_sh("[", "-e", "/usr/local/tmp/RANDOM", "]")
    self.platform.expect_sh("rm", "/usr/local/tmp/RANDOM")

    mouse_process_stdin: MockFd = MockFd()
    mouse_process_stdout: MockFd = MockFd()

    mouse_process_stdout.read_returns.append("0\n".encode("utf-8"))

    if clicked_coordinates:
      mouse_process_stdin.expected_writes.append(
          f"{click_duration.total_seconds()}\n"
          f"{clicked_coordinates.x}\n{clicked_coordinates.y}\n".encode("utf-8"))
      mouse_process_stdout.read_returns.append("0\n".encode("utf-8"))

    mock_mouse_process: MockPopen = MockPopen(mouse_process_stdout,
                                              mouse_process_stdin)
    self.platform.popens.append(mock_mouse_process)

  def assert_coordinates_touched(
      self,
      start_coordinates: Point,
      end_coordinates: Optional[Point] = None,
      duration: dt.timedelta = dt.timedelta()
  ) -> None:

    expected_event: ChromeOSTouchEvent = ChromeOSTouchEvent(
        self._FAKE_TOUCH_DEVICE, DisplayRectangle(Point(0, 0), 1920, 1080),
        start_coordinates, end_coordinates, duration)

    pushed_files = self.platform.file_contents
    self.assertEqual(len(pushed_files), 1)

    actual_playback_history = list(pushed_files.values())[0]

    actual_playback = actual_playback_history.pop(0)

    self.assertEqual(actual_playback, str(expected_event))

  def test_click_touch_coordinates(self):
    click_action = ClickAction(
        InputSource.TOUCH, position=PositionConfig.from_coordinates(x=50, y=50))

    self.expect_touch_setup(expected_js=self._NO_ELEMENT_JS_RESULT)

    self.run_action(click_action)

    self.assert_coordinates_touched(Point(50, 50))

  def test_click_mouse_coordinates(self):
    click_action = ClickAction(
        InputSource.MOUSE, position=PositionConfig.from_coordinates(x=50, y=50))

    self.expect_mouse_click(
        expected_js=self._NO_ELEMENT_JS_RESULT,
        clicked_coordinates=Point(50, 50))

    self.run_action(click_action)

  def test_click_touch_coordinates_duration(self):
    click_duration = dt.timedelta(seconds=100)

    click_action = ClickAction(
        InputSource.TOUCH,
        position=PositionConfig.from_coordinates(x=50, y=50),
        duration=click_duration)

    self.expect_touch_setup(expected_js=self._NO_ELEMENT_JS_RESULT)

    self.run_action(click_action)

    self.assert_coordinates_touched(Point(50, 50), duration=click_duration)

  def test_click_mouse_coordinates_duration(self):
    click_duration = dt.timedelta(seconds=100)

    click_action = ClickAction(
        InputSource.MOUSE,
        position=PositionConfig.from_coordinates(x=50, y=50),
        duration=click_duration)

    self.expect_mouse_click(
        expected_js=self._NO_ELEMENT_JS_RESULT,
        clicked_coordinates=Point(50, 50),
        click_duration=click_duration)

    self.run_action(click_action)

  def test_click_touch_selector_non_existent_element_raises(self):
    click_action = ClickAction(
        InputSource.TOUCH,
        position=PositionConfig.from_selector(selector="div[]", required=True))

    self.expect_touch_setup(
        touch_count=0, expected_js=self._NO_ELEMENT_JS_RESULT)

    with self.assertRaisesRegex(ElementNotFoundError, "matching DOM"):
      self.run_action(click_action)

  def test_click_mouse_selector_non_existent_element_raises(self):
    click_action = ClickAction(
        InputSource.MOUSE,
        position=PositionConfig.from_selector(selector="div[]", required=True))

    path = SCRIPTS_DIR / "get_window_positions.js"
    self.fs.create_file(path, contents="get_window_positions")

    self.browser.expect_js(expected_js=self._NO_ELEMENT_JS_RESULT)

    with self.assertRaisesRegex(ElementNotFoundError, "matching DOM"):
      self.run_action(click_action)

  def test_click_touch_selector_non_required_element_success(self):
    click_action = ClickAction(
        InputSource.TOUCH,
        position=PositionConfig.from_selector(selector="div[]", required=False))

    self.expect_touch_setup(
        touch_count=0, expected_js=self._NO_ELEMENT_JS_RESULT)

    self.run_action(click_action)

  def test_click_mouse_selector_non_required_element_success(self):
    click_action = ClickAction(
        InputSource.MOUSE,
        position=PositionConfig.from_selector(selector="div[]", required=False))

    self.expect_mouse_click(
        expected_js=self._NO_ELEMENT_JS_RESULT, clicked_coordinates=None)

    self.run_action(click_action)

  def test_click_touch_selector_success(self):

    click_action = ClickAction(
        InputSource.TOUCH,
        position=PositionConfig.from_selector(selector="div[]", required=True))

    self.expect_touch_setup(
        expected_js=JsInvocation(result=[
            True,  # Found element
            1,  # pixel ratio
            1920,  # window outer width
            1920,  # window inner width
            1080,  # window inner height
            1920,  # screen width
            1080,  # screen height
            1920,  # screen avail width
            1080,  # screen avail height
            0,  # screenX
            0,  # screenY
            5,  # element left
            6,  # element top
            7,  # element width
            8,  # element height
        ]))

    self.run_action(click_action)

    self.assert_coordinates_touched(Point(8, 10))

  def test_click_mouse_selector_success(self):

    click_action = ClickAction(
        InputSource.MOUSE,
        position=PositionConfig.from_selector(selector="div[]", required=True))

    self.expect_mouse_click(
        expected_js=JsInvocation(result=[
            True,  # Found element
            1,  # pixel ratio
            1920,  # window outer width
            1920,  # window inner width
            1080,  # window inner height
            1920,  # screen width
            1080,  # screen height
            1920,  # screen avail width
            1080,  # screen avail height
            0,  # screenX
            0,  # screenY
            5,  # element left
            6,  # element top
            7,  # element width
            8,  # element height
        ]),
        clicked_coordinates=Point(8, 10))

    self.run_action(click_action)

  def test_click_wait_timeout_required(self):
    click_action = ClickAction(
        InputSource.TOUCH,
        position=PositionConfig.from_selector(
            selector="#selector", required=True, wait=True),
        # Set timeout to 0.1 to timeout after 1 call to wait_for_element_impl.
        timeout=dt.timedelta(seconds=0.1))

    self.expect_touch_setup(
        touch_count=0, expected_js=self._NO_ELEMENT_JS_RESULT)

    with self.assertRaises(TimeoutError):
      self.run_action(click_action)

  def test_click_wait_timeout_unrequired(self):
    click_action = ClickAction(
        InputSource.TOUCH,
        position=PositionConfig.from_selector(
            selector="#selector", required=False, wait=True),
        # Set timeout to 0.1 to timeout after 1 call to wait_for_element_impl.
        timeout=dt.timedelta(seconds=0.1))

    self.expect_touch_setup(
        touch_count=0, expected_js=self._NO_ELEMENT_JS_RESULT)
    self.browser.expect_js(self._NO_ELEMENT_JS_RESULT)

    self.run_action(click_action)

  def test_scroll_touch_window_success(self):

    scroll_duration: dt.timedelta = dt.timedelta(seconds=2)

    scroll_action = ScrollAction(
        InputSource.TOUCH, distance=100, duration=scroll_duration)

    self.expect_touch_setup(
        expected_js=JsInvocation(result=[
            False,  # Found element
            1,  # pixel ratio
            1920,  # window outer width
            1920,  # window inner width
            1080,  # window inner height
            1920,  # screen width
            1080,  # screen height
            1920,  # screen avail width
            1080,  # screen avail height
            0,  # screenX
            0,  # screenY
            0,  # element left
            0,  # element top
            0,  # element width
            0,  # element height
        ]))

    self.run_action(scroll_action)

    self.assert_coordinates_touched(
        Point(960, 972), Point(960, 872), scroll_duration)

  def test_scroll_touch_window_multi_step_success(self):

    scroll_duration: dt.timedelta = dt.timedelta(seconds=2)

    scroll_action = ScrollAction(
        InputSource.TOUCH, distance=1600, duration=scroll_duration)

    self.expect_touch_setup(
        expected_js=JsInvocation(result=[
            False,  # Found element
            1,  # pixel ratio
            1920,  # window outer width
            1920,  # window inner width
            1080,  # window inner height
            1920,  # screen width
            1080,  # screen height
            1920,  # screen avail width
            1080,  # screen avail height
            0,  # screenX
            0,  # screenY
            0,  # element left
            0,  # element top
            0,  # element width
            0,  # element height
        ]),
        touch_count=2)

    self.run_action(scroll_action)

    self.assert_coordinates_touched(
        Point(960, 972), Point(960, 172), scroll_duration * 0.5)
    self.assert_coordinates_touched(
        Point(960, 972), Point(960, 172), scroll_duration * 0.5)

  def test_scroll_touch_selector_required_not_found_raises(self):
    scroll_action = ScrollAction(
        InputSource.TOUCH,
        distance=100,
        duration=dt.timedelta(seconds=2),
        selector="div[]",
        required=True)

    self.expect_touch_setup(
        expected_js=JsInvocation(result=[
            False,  # Found element
            1,  # pixel ratio
            1920,  # window outer width
            1920,  # window inner width
            1080,  # window inner height
            1920,  # screen width
            1080,  # screen height
            1920,  # screen avail width
            1080,  # screen avail height
            0,  # screenX
            0,  # screenY
            0,  # element left
            0,  # element top
            0,  # element width
            0,  # element height
        ]),
        touch_count=0)

    with self.assertRaisesRegex(ElementNotFoundError, "matching DOM"):
      self.run_action(scroll_action)

  def test_scroll_touch_selector_not_found_does_nothing(self):
    scroll_action = ScrollAction(
        InputSource.TOUCH,
        distance=100,
        duration=dt.timedelta(seconds=2),
        selector="div[]",
        required=False)

    self.expect_touch_setup(
        expected_js=JsInvocation(result=[
            False,  # Found element
            1,  # pixel ratio
            1920,  # window outer width
            1920,  # window inner width
            1080,  # window inner height
            1920,  # screen width
            1080,  # screen height
            1920,  # screen avail width
            1080,  # screen avail height
            0,  # screenX
            0,  # screenY
            0,  # element left
            0,  # element top
            0,  # element width
            0,  # element height
        ]),
        touch_count=0)

    self.run_action(scroll_action)

    pushed_files = self.platform.file_contents
    self.assertEqual(len(pushed_files), 0)

  def test_scroll_touch_selector_success(self):
    scroll_duration: dt.timedelta = dt.timedelta(seconds=0.5)

    scroll_action = ScrollAction(
        InputSource.TOUCH,
        distance=100,
        duration=scroll_duration,
        selector="div[]",
        required=True)

    self.expect_touch_setup(
        expected_js=JsInvocation(result=[
            True,  # Found element
            1,  # pixel ratio
            1920,  # window outer width
            1920,  # window inner width
            1080,  # window inner height
            1920,  # screen width
            1080,  # screen height
            1920,  # screen avail width
            1080,  # screen avail height
            0,  # screenX
            0,  # screenY
            10,  # element left
            20,  # element top
            50,  # element width
            600,  # element height
        ]))

    self.run_action(scroll_action)

    self.assert_coordinates_touched(
        Point(35, 560), Point(35, 460), scroll_duration)


if __name__ == "__main__":
  test_helper.run_pytest(__file__)
