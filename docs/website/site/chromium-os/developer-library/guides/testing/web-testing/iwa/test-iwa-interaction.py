# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Selenium Test Script for Kitchen Sink IWA Interaction.

This script connects to a remote ChromeOS instance, installs the
Kitchen Sink Isolated Web App (IWA) from its web bundle, then
launches it, and interacts with its UI to simulate sending and
receiving messages via direct sockets.

Prerequisites:
1. A CrOS device or VM setup for remote testing.
2. Chrome on the device must be launched with the following flags in
   /etc/chrome_dev.conf:
   - `--remote-debugging-port=<port>`
   - `--enable-devtools-pwa-handler`
   - `--enable-features=IsolatedWebAppDevMode`
"""

import argparse
import logging
import sys
import time

from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.chrome import options
from selenium.webdriver.chrome import service
from selenium.webdriver.common import by
from selenium.webdriver.remote import webelement
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support import ui

# Configure logging.
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# IWA specific constants.
_WEB_BUNDLE_ID = "aiv4bxauvcu3zvbu6r5yynoh4atkzqqaoeof5mwz54b4zfywcrjuoaacai"
_IWA_VERSION = "0.18.0"
_WEB_BUNDLE_URL = ("https://github.com/chromeos/iwa-sink/releases/download/"
                   f"v{_IWA_VERSION}/iwa-sink.swbn")
_MANIFEST_ID = f"isolated-app://{_WEB_BUNDLE_ID}/"

_MSG_LEFT = "Sing me a song!"
_MSG_RIGHT = "Hello from the right side!"


def get_shadow_root(driver: webdriver.Chrome,
                    host_element: webelement.WebElement) -> object:
    """Retrieves the shadow root of a given web element."""
    return driver.execute_script("return arguments[0].shadowRoot", host_element)


def run_iwa_interaction_test(driver_path: str, port: int) -> bool:
    """Installs and tests the Kitchen Sink IWA.

    Args:
        driver_path: Path to the chromedriver executable.
        port: The remote-debugging-port flag value on the DUT.

    Returns:
        True on success, False on error.
    """
    debugger_addr = f"127.0.0.1:{port}"
    logging.info("Connecting to browser at %s...", debugger_addr)

    chrome_opts = options.Options()
    chrome_opts.add_experimental_option("debuggerAddress", debugger_addr)
    chrome_svc = service.Service(executable_path=driver_path)

    try:
        with webdriver.Chrome(service=chrome_svc,
                              options=chrome_opts) as driver:
            logging.info("Successfully connected to the browser.")
            original_window = driver.current_window_handle

            # Install IWA.
            logging.info("Installing IWA from URL: %s", _WEB_BUNDLE_URL)
            driver.execute_cdp_cmd(
                "PWA.install",
                {
                    "manifestId": _MANIFEST_ID,
                    "installUrlOrBundleUrl": _WEB_BUNDLE_URL,
                },
            )
            # Allow time for installation to propagate.
            time.sleep(5)

            # Launch IWA.
            logging.info("Launching IWA with manifest ID: %s", _MANIFEST_ID)
            driver.execute_cdp_cmd("PWA.launch", {"manifestId": _MANIFEST_ID})

            # Wait for window switch.
            wait = ui.WebDriverWait(driver, 15)
            wait.until(lambda d: len(d.window_handles) > 1)

            # Switch to IWA window.
            iwa_window_handle = [
                h for h in driver.window_handles if h != original_window
            ][0]
            driver.switch_to.window(iwa_window_handle)
            logging.info("Switched to IWA window: '%s'", driver.title)

            # --- UI Interaction ---
            wait_long = ui.WebDriverWait(driver, 30)

            logging.info("Waiting for 'Create new socket connection' button...")
            add_socket_button = wait_long.until(
                expected_conditions.presence_of_element_located(
                    (by.By.ID, "addSocketButton")))
            add_socket_button.click()
            logging.info("Clicked 'Create new socket connection' button.")

            # Interact with Shadow DOM.
            left_comp = wait_long.until(
                expected_conditions.presence_of_element_located(
                    (by.By.TAG_NAME, "socket-connection")))
            right_comp = wait_long.until(
                expected_conditions.presence_of_element_located(
                    (by.By.TAG_NAME, "socket-server")))

            left_root = get_shadow_root(driver, left_comp)
            right_root = get_shadow_root(driver, right_comp)

            # Message: Left -> Right.
            logging.info("Sending message from Left to Right...")
            left_input = left_root.find_element(by.By.CSS_SELECTOR,
                                                "input#messageInput")
            left_send_btn = left_root.find_element(by.By.CSS_SELECTOR,
                                                   "button#sendButton")

            left_input.send_keys(_MSG_LEFT)
            left_send_btn.click()

            wait.until(lambda d: _MSG_LEFT in right_root.find_element(
                by.By.CSS_SELECTOR, "#log").text)
            logging.info("Verified '%s' appeared on the right side.", _MSG_LEFT)

            # Message: Right -> Left.
            logging.info("Sending message from Right to Left...")
            right_input = right_root.find_element(by.By.CSS_SELECTOR,
                                                  "input#messageInput")
            right_send_btn = right_root.find_element(by.By.CSS_SELECTOR,
                                                     "button#sendButton")

            right_input.send_keys(_MSG_RIGHT)
            right_send_btn.click()

            wait.until(lambda d: _MSG_RIGHT in left_root.find_element(
                by.By.CSS_SELECTOR, "#log").text)
            logging.info("Verified '%s' appeared on the left side.", _MSG_RIGHT)

            # Cleanup within the context.
            try:
                logging.info("Uninstalling IWA: %s", _MANIFEST_ID)
                driver.execute_cdp_cmd("PWA.uninstall",
                                       {"manifestId": _MANIFEST_ID})
            except exceptions.WebDriverException as e:
                logging.warning("Could not uninstall IWA during cleanup: %s", e)

            logging.info("IWA test successful.")
            return True

    except exceptions.WebDriverException as e:
        logging.error("An error occurred during IWA interaction test: %s",
                      e,
                      exc_info=True)
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver-path", default="./chromedriver")
    parser.add_argument("--port", type=int, default=9222)
    opts = parser.parse_args(argv)

    return 0 if run_iwa_interaction_test(opts.driver_path, opts.port) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
