# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Selenium test script for end-to-end file download and verification.

This script uses a robust UI automation approach to control the Files
app and the Media App.

Prerequisites:
1. A CrOS device or VM setup for remote testing.
2. Chrome on the device must be launched with the following flags in
   /etc/chrome_dev.conf:
   - `--remote-debugging-port=<port>`
   - `--enable-devtools-pwa-handler`
"""

import argparse
import logging
import sys
import time
from urllib import parse

from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.chrome import service
from selenium.webdriver.common import action_chains
from selenium.webdriver.common import by
from selenium.webdriver.common import keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support import ui

# Configure logging.
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Javascript Helpers.
_JS_FIND_DOWNLOADS_FOLDER = """
    const tree = document.querySelector('#directory-tree');
    if (!tree) return null;
    const items = tree.querySelectorAll('xf-tree-item');
    for (const item of items) {
        // Shadow DOM traversal to find the label
        const label = item.shadowRoot?.querySelector('span#tree-label');
        if (label?.textContent.trim() === 'Downloads') {
            return item;
        }
    }
    return null;
"""

_JS_VERIFY_CONTENT = """
    const callback = arguments[arguments.length - 1];
    const timeoutMs = 20000;
    const startTime = Date.now();

    function poll() {
        try {
            // Check CodeMirror editor (Files App / Media App text editor)
            const editorDom = document.querySelector('.cm-editor');
            if (editorDom && editorDom.cmView && editorDom.cmView.view) {
                const text = editorDom.cmView.view.state.doc.toString();
                if (text && text.trim().length > 0) {
                    callback(text);
                    return;
                }
            }
            // Fallback: Check standard content node
            const contentNode = document.querySelector('.cm-content');
            if (contentNode) {
                const text = contentNode.innerText;
                if (text && text.trim().length > 0) {
                    callback(text);
                    return;
                }
            }
        } catch (e) {
            // Suppress DOM errors during polling
        }

        if (Date.now() - startTime > timeoutMs) {
            callback({error: 'Timed out verifying content'});
            return;
        }
        setTimeout(poll, 500);
    }
    poll();
"""

# Test Configuration.
_FILE_CONTENT = "Hello, ChromeOS E2E Testing!"
_FILE_NAME = "test-download.txt"
_ENCODED_CONTENT = parse.quote(_FILE_CONTENT)
_DOWNLOAD_PAGE_URL = (
    f'data:text/html,<a id="downloadLink" '
    f'href="data:text/plain;charset=utf-8,{_ENCODED_CONTENT}" '
    f'download="{_FILE_NAME}">Download Test File</a>')
_FILES_APP_URL = "chrome://file-manager"
_TIMEOUT = 20


def run_file_download_test(driver_path: str, port: int) -> bool:
    """Runs the file download and verification test.

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
            logging.info("Successfully connected.")
            original_window = driver.current_window_handle
            wait = ui.WebDriverWait(driver, _TIMEOUT)

            # Step 1: Download the file.
            logging.info("Navigating to test page to download file...")
            driver.get(_DOWNLOAD_PAGE_URL)

            wait.until(
                expected_conditions.element_to_be_clickable(
                    (by.By.ID, "downloadLink"))).click()
            logging.info('Clicked download link for "%s".', _FILE_NAME)
            # Short wait for download to start.
            time.sleep(2)

            # Step 2: Launch Files App.
            logging.info("Launching Files app...")
            driver.execute_cdp_cmd("PWA.launch", {"manifestId": _FILES_APP_URL})

            # Wait for Files App window.
            wait.until(lambda d: len(d.window_handles) > 1)

            files_app_window = [
                h for h in driver.window_handles if h != original_window
            ][0]
            driver.switch_to.window(files_app_window)
            logging.info("Switched to Files App window.")

            # Find and click "Downloads" folder.
            downloads_folder = wait.until(
                lambda d: d.execute_script(_JS_FIND_DOWNLOADS_FOLDER))
            downloads_folder.click()
            logging.info('Clicked "Downloads" folder.')

            file_selector = (
                by.By.CSS_SELECTOR,
                f'li.table-row[file-name="{_FILE_NAME}"]',
            )
            file_element = wait.until(
                expected_conditions.presence_of_element_located(file_selector))
            logging.info('Found "%s" in Files app.', _FILE_NAME)

            # Step 3: Open file and verify content.
            logging.info("Double-clicking file to open Text/Media app...")
            action_chains.ActionChains(driver).double_click(
                file_element).perform()

            # Wait for Media App window.
            wait.until(lambda d: len(d.window_handles) > 2)

            media_app_window = [
                h for h in driver.window_handles
                if h not in [original_window, files_app_window]
            ][0]
            driver.switch_to.window(media_app_window)
            logging.info("Switched to Media App window.")

            # Verify content using the constant script.
            content = driver.execute_async_script(_JS_VERIFY_CONTENT)

            if isinstance(content, dict) and "error" in content:
                raise RuntimeError(content["error"])

            if content.strip() != _FILE_CONTENT:
                raise ValueError(
                    f'File content mismatch! Expected "{_FILE_CONTENT}", '
                    f'got "{content.strip()}"')
            logging.info("File content verified successfully.")

            # Step 4: Cleanup.
            driver.close()
            driver.switch_to.window(files_app_window)
            logging.info('Cleaning up: Deleting "%s"...', _FILE_NAME)

            file_to_del = wait.until(
                expected_conditions.presence_of_element_located(file_selector))
            action_chains.ActionChains(driver).click(file_to_del).key_down(
                keys.Keys.DELETE).key_up(keys.Keys.DELETE).perform()

            try:
                confirm_btn = ui.WebDriverWait(driver, 3).until(
                    expected_conditions.element_to_be_clickable(
                        (by.By.CSS_SELECTOR, ".cr-dialog-ok")))
                confirm_btn.click()
                logging.info("Confirmation dialog clicked.")
            except Exception:
                logging.info(
                    "No confirmation dialog (moved to Trash directly).")

            wait.until(
                expected_conditions.invisibility_of_element_located(
                    file_selector))
            logging.info("File deletion confirmed. Test passed!")
            return True

    except Exception as e:
        logging.error("An error occurred during file download test: %s",
                      e,
                      exc_info=True)
        return False


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

    return 0 if run_file_download_test(opts.driver_path, opts.port) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
