# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Selenium Test Script for testing Browser Connection.

This script connects to a remote ChromeOS instance and retrieves the
content of the `chrome://version` page, printing the browser's
command-line flags. This allows verification that remote debugging is
enabled and that other flags are correctly applied.

Prerequisites:
1. A CrOS device or VM setup for remote testing.
2. Chrome on the device must be launched with the following flag in
   /etc/chrome_dev.conf:
   - `--remote-debugging-port=<port>`
"""

import argparse
import logging
import sys

from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.chrome import options
from selenium.webdriver.chrome import service
from selenium.webdriver.common import by

# Configure logging.
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Constants for element IDs from chrome://version.
_VERSION_ID = "version"
_COMMAND_LINE_ID = "command_line"


def run_test(driver_path: str, port: int) -> bool:
    """Connects to a remote Chrome instance, scrapes version info and prints it.

    Args:
        driver_path: Path to the chromedriver executable.
        port: The remote-debugging-port flag value on the DUT.

    Returns:
        True on success, False on error.
    """
    debugger_addr = f"127.0.0.1:{port}"
    logging.info("Connecting to DUT via %s...", debugger_addr)

    # Critical: Attach to existing remote browser.
    chrome_opts = options.Options()
    chrome_opts.add_experimental_option("debuggerAddress", debugger_addr)

    chrome_svc = service.Service(executable_path=driver_path)

    data = {}
    try:
        # The webdriver.Chrome instance is a context manager.
        # It will automatically close the session (detach) when exiting.
        with webdriver.Chrome(service=chrome_svc,
                              options=chrome_opts) as driver:
            logging.info("Connected. Navigating to chrome://version...")
            driver.get("chrome://version")

            # Scrape data using native Selenium functions.
            data = {
                "Google Chrome":
                driver.find_element(by.By.ID, _VERSION_ID).text,
                "Command Line":
                driver.find_element(by.By.ID, _COMMAND_LINE_ID).text,
            }
    except exceptions.WebDriverException as e:
        logging.error("A WebDriver error occurred: %s", e)
        logging.error(
            "Please ensure Chrome is running on the device with "
            "--remote-debugging-port=%d enabled.",
            port,
        )
        return False

    # If data was successfully scraped, log it.
    if data:
        logging.info("--- ChromeOS DUT Report ---")
        for key, value in data.items():
            logging.info("%s: %s", key, value)
        logging.info("--- End Report ---")

    logging.info("Test complete.")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--driver-path",
        default="./chromedriver",
        help="Path to the chromedriver executable.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9222,
        help="Remote debugging port on the DUT.",
    )
    opts = parser.parse_args(argv)

    return 0 if run_test(opts.driver_path, opts.port) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
