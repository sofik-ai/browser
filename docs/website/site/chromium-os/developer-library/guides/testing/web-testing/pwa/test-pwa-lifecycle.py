# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Selenium Test Script for a Standard PWA Lifecycle.

This script connects to a remote Chrome instance, installs a standard
PWA using the `PWA` Chrome DevTools Protocol (CDP) domain. It then
launches the PWA, checks its state, and finally uninstalls it.

Prerequisites:
1. A CrOS device or VM setup for remote testing as described in the
   guide:
   https://www.chromium.org/chromium-os/developer-library/guides/testing/web-testing/
2. Chrome on the device must be launched with the following flags in
   /etc/chrome_dev.conf:
   - `--remote-debugging-port=<port>`
   - `--enable-devtools-pwa-handler`
"""

import argparse
import logging
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.chrome import service
from selenium.webdriver.support import ui

# Configure logging.
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# PWA specific constants.
_MANIFEST_ID = "https://developer.chrome.com/"


def run_pwa_lifecycle_test(driver_path: str, port: int) -> bool:
    """Connects to a remote browser, installs, launches, and inspects a PWA.

    Args:
        driver_path: Path to the chromedriver binary.
        port: The remote-debugging-port flag value on the DUT.

    Returns:
        True on success, False on error.
    """
    debugger_addr = f"127.0.0.1:{port}"
    logging.info("Attempting to connect to browser at %s...", debugger_addr)

    chrome_opts = options.Options()
    chrome_opts.add_experimental_option("debuggerAddress", debugger_addr)

    chrome_svc = service.Service(executable_path=driver_path)

    try:
        with webdriver.Chrome(service=chrome_svc,
                              options=chrome_opts) as driver:
            logging.info("Successfully connected to the browser.")
            original_window = driver.current_window_handle
            wait = ui.WebDriverWait(driver, 15)

            # Install PWA.
            logging.info("Installing PWA from manifest: %s", _MANIFEST_ID)
            driver.execute_cdp_cmd(
                "PWA.install",
                {
                    "manifestId": _MANIFEST_ID,
                    "installUrlOrBundleUrl": _MANIFEST_ID,
                },
            )
            # Allow time for installation to propagate.
            time.sleep(5)

            # Launch PWA.
            logging.info("Launching PWA with manifest ID: %s", _MANIFEST_ID)
            driver.execute_cdp_cmd("PWA.launch", {"manifestId": _MANIFEST_ID})

            # Wait for the PWA window to open.
            logging.info("Waiting for PWA window to open...")
            wait.until(lambda d: len(d.window_handles) > 1)

            # Find new handle.
            pwa_window_handle = next(
                (h for h in driver.window_handles if h != original_window),
                None)

            if not pwa_window_handle:
                raise RuntimeError("PWA window handle not found.")

            driver.switch_to.window(pwa_window_handle)
            # Ensure we are on the right URL (sometimes launch opens blank).
            driver.get(_MANIFEST_ID)
            logging.info("PWA launched successfully and window is focused.")

            # Inspect state.
            logging.info("Inspecting PWA's OS state and manifest...")
            os_app_state = driver.execute_cdp_cmd("PWA.getOsAppState",
                                                  {"manifestId": _MANIFEST_ID})
            logging.info("PWA OS App State: %s", os_app_state)

            manifest = driver.execute_cdp_cmd("Page.getAppManifest", {})
            logging.info("PWA Manifest: %s", manifest)

            # Test opening current page.
            logging.info("Testing 'openCurrentPageInApp' command...")
            driver.execute_cdp_cmd("PWA.openCurrentPageInApp",
                                   {"manifestId": _MANIFEST_ID})

            # Cleanup.
            try:
                logging.info("Uninstalling PWA: %s", _MANIFEST_ID)
                driver.execute_cdp_cmd("PWA.uninstall",
                                       {"manifestId": _MANIFEST_ID})
            except Exception as e:
                logging.warning("Failed to uninstall PWA during cleanup: %s", e)

            logging.info("Test complete.")
            return True

    except Exception as e:
        logging.error("An error occurred during the test: %s", e)
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--driver-path",
        default="./chromedriver",
        help="Path to the chromedriver binary.",
    )
    parser.add_argument("--port",
                        type=int,
                        default=9222,
                        help="Remote debugging port.")
    opts = parser.parse_args(argv)

    return 0 if run_pwa_lifecycle_test(opts.driver_path, opts.port) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
