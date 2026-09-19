# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Python CDP Test Script for an IWA in Kiosk Mode.

This script connects to a remote ChromeOS instance running in Kiosk
mode, finds the target for the launched Isolated Web App (IWA), and
interacts with its UI using low-level Chrome DevTools Protocol (CDP)
commands via raw WebSockets.

Prerequisites:
1. A CrOS device or VM set up for remote testing and configured for
   Kiosk mode.
2. The device must have policies set to auto-launch the IWA in Kiosk
   mode.
3. Chrome on the device must be launched with ALL of the following
   flags:
   - `--remote-debugging-port=<port>` (default 9222)
   - `--remote-debugging-address=0.0.0.0`
   - `--force-devtools-available`
"""

import argparse
import datetime
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from typing import Any

try:
    import websocket
except ImportError:
    sys.exit("Error: This script requires 'websocket-client'.\n"
             "Please install it: pip install websocket-client")

# Configure logging.
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Color constants for console output.
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

# Timeout settings (seconds).
DEFAULT_TIMEOUT = 15

# The specific Bundle ID for the test IWA.
IWA_WEB_BUNDLE_ID = "aiv4bxauvcu3zvbu6r5yynoh4atkzqqaoeof5mwz54b4zfywcrjuoaacai"
IWA_URL_PATTERN = f"isolated-app://{IWA_WEB_BUNDLE_ID}"


class FlatCdpSession:
    """Manage a Flat CDP session via a raw WebSocket.

    Commands are sent with 'sessionId' property, results return directly.
    """

    def __init__(self, ws: websocket.WebSocket, session_id: str):
        self.ws = ws
        self.session_id = session_id
        self._msg_id = 0

    def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Sends a CDP command and waits for the result."""
        if params is None:
            params = {}
        self._msg_id += 1
        msg_id = self._msg_id

        # In Flat Mode, sessionId is a top-level property.
        message = json.dumps({
            "id": msg_id,
            "method": method,
            "params": params,
            "sessionId": self.session_id,
        })

        self.ws.send(message)

        # Wait for the direct response matching our ID.
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=DEFAULT_TIMEOUT)
        while datetime.datetime.now() < end_time:
            try:
                # We rely on the socket timeout set in run_test to
                # prevent blocking forever.
                resp_str = self.ws.recv()
                resp = json.loads(resp_str)
            except (websocket.WebSocketTimeoutException, json.JSONDecodeError):
                continue

            # Check if this is the response to our specific command.
            if resp.get("id") == msg_id:
                if "error" in resp:
                    raise Exception(f"{method} failed: {resp['error']}")
                return resp.get("result")

        raise TimeoutError(f"Timeout waiting for command {method}")


def click_element(session: FlatCdpSession, node_id: int) -> None:
    """Calculates the center of a node and dispatches a mouse click."""
    model = session.send("DOM.getBoxModel", {"nodeId": node_id})["model"]
    c = model["content"]
    # Box model content is [x1, y1, x2, y2, x3, y3, x4, y4].
    x = (c[0] + c[2]) / 2
    y = (c[1] + c[5]) / 2

    # Dispatch mousePressed and mouseReleased to simulate a click.
    for event_type in ("mousePressed", "mouseReleased"):
        session.send(
            "Input.dispatchMouseEvent",
            {
                "type": event_type,
                "button": "left",
                "x": x,
                "y": y,
                "clickCount": 1,
            },
        )


def type_text(session: FlatCdpSession, node_id: int, text: str) -> None:
    """Focuses a node and sends character keys."""
    session.send("DOM.focus", {"nodeId": node_id})
    for char in text:
        session.send("Input.dispatchKeyEvent", {"type": "char", "text": char})


def wait_for_condition(
    session: FlatCdpSession,
    selector: str,
    text: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """Polls the DOM (including Shadow Root) for a specific string."""
    # JS checks if the element exists, has a shadow root, and contains the text.
    js = (f"(function() {{ "
          f"  const r = document.querySelector('{selector}'); "
          f"  return r && r.shadowRoot && "
          f"r.shadowRoot.innerHTML.includes('{text}'); "
          f"}})()")

    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(seconds=timeout)
    while datetime.datetime.now() < end_time:
        res = session.send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True
        })
        if res and res["result"].get("value") is True:
            return
        time.sleep(0.5)
    raise TimeoutError(f"Timeout waiting for '{text}' in '{selector}'")


def run_test(port: int) -> bool:
    debugger_addr = f"127.0.0.1:{port}"
    ws = None

    try:
        # 1. Get WebSocket URL from the browser version endpoint.
        url = f"http://{debugger_addr}/json/version"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                browser_ws_url = json.load(response)["webSocketDebuggerUrl"]
        except Exception as e:
            raise Exception(f"Could not connect to Chrome at {url}. "
                            f"Is it running? Error: {e}")

        logging.info("Connecting to browser at %s...", debugger_addr)
        ws = websocket.create_connection(browser_ws_url, suppress_origin=True)
        # Set a socket timeout so we don't block indefinitely if Chrome hangs.
        ws.settimeout(DEFAULT_TIMEOUT)

        # 2. Find IWA Target.
        logging.info("Searching for IWA target...")
        ws.send(json.dumps({"id": 999, "method": "Target.getTargets"}))

        targets = []
        # Simple loop to wait for the target list response.
        start_find = datetime.datetime.now()
        end_find = start_find + datetime.timedelta(seconds=DEFAULT_TIMEOUT)
        while datetime.datetime.now() < end_find:
            resp_str = ws.recv()
            resp = json.loads(resp_str)
            if resp.get("id") == 999:
                targets = resp["result"]["targetInfos"]
                break

        iwa_target = next(
            (t for t in targets if t["url"].startswith(IWA_URL_PATTERN)
             and t["type"] in {"app", "page", "other"}),
            None,
        )

        if not iwa_target:
            visible = "\n".join(f"{t['type']}: {t['url']}" for t in targets)
            raise Exception(
                f"Could not find IWA target. Available targets:\n{visible}")

        logging.info("%sFound IWA Target: %s%s", GREEN, iwa_target['url'],
                     RESET)

        # 3. Attach (Flat Mode).
        # We assume the browser supports "flatten: true".
        attach_id = 1000
        ws.send(
            json.dumps({
                "id": attach_id,
                "method": "Target.attachToTarget",
                "params": {
                    "targetId": iwa_target["targetId"],
                    "flatten": True,
                },
            }))

        session_id = None
        start_attach = datetime.datetime.now()
        end_attach = start_attach + datetime.timedelta(seconds=DEFAULT_TIMEOUT)
        while datetime.datetime.now() < end_attach:
            resp = json.loads(ws.recv())
            if resp.get("id") == attach_id:
                if "error" in resp:
                    raise Exception(f"Attach failed: {resp['error']}")
                session_id = resp["result"]["sessionId"]
                break

        if not session_id:
            raise Exception("Failed to obtain a session ID.")

        logging.info("Attached to IWA via tunnelled session.")

        # 4. Initialize Session.
        session = FlatCdpSession(ws, session_id)
        session.send("Runtime.enable")
        session.send("DOM.enable")

        # Get the document root.
        root = session.send("DOM.getDocument")["root"]

        # 5. UI Interaction.
        logging.info("Waiting for 'Create new socket connection' button...")
        btn_id = 0
        # Retry loop to find the initial button.
        start_wait = datetime.datetime.now()
        end_wait = start_wait + datetime.timedelta(seconds=DEFAULT_TIMEOUT)
        while datetime.datetime.now() < end_wait:
            r = session.send(
                "DOM.querySelector",
                {
                    "nodeId": root["nodeId"],
                    "selector": "#addSocketButton",
                },
            )
            if r["nodeId"]:
                btn_id = r["nodeId"]
                break
            time.sleep(1)

        if not btn_id:
            raise Exception("Button '#addSocketButton' not found")

        click_element(session, btn_id)
        logging.info("Clicked '#addSocketButton'.")

        logging.info("Waiting for socket components to appear...")
        time.sleep(2)

        # Get Component References (assuming light DOM of main doc).
        left_id = session.send(
            "DOM.querySelector",
            {
                "nodeId": root["nodeId"],
                "selector": "socket-connection",
            },
        )["nodeId"]
        right_id = session.send(
            "DOM.querySelector",
            {
                "nodeId": root["nodeId"],
                "selector": "socket-server",
            },
        )["nodeId"]

        if not left_id or not right_id:
            raise Exception("Could not find <socket-connection> or "
                            "<socket-server> elements.")

        # Get Shadow Roots for internal access.
        left_shadow = session.send(
            "DOM.describeNode",
            {"nodeId": left_id})["node"]["shadowRoots"][0]["nodeId"]

        right_shadow = session.send(
            "DOM.describeNode",
            {"nodeId": right_id})["node"]["shadowRoots"][0]["nodeId"]

        logging.info("Found shadow roots for socket components.")

        # -- Scenario 1: Left -> Right --.
        logging.info("Sending message from LEFT to RIGHT...")
        l_in = session.send(
            "DOM.querySelector",
            {
                "nodeId": left_shadow,
                "selector": "input#messageInput",
            },
        )["nodeId"]
        l_btn = session.send(
            "DOM.querySelector",
            {
                "nodeId": left_shadow,
                "selector": "button#sendButton",
            },
        )["nodeId"]

        type_text(session, l_in, "Sing me a song!")
        click_element(session, l_btn)

        logging.info("Verifying message on RIGHT...")
        wait_for_condition(session, "socket-server", "Sing me a song!")
        logging.info("%sVerified 'Sing me a song!' on right.%s", GREEN, RESET)

        # -- Scenario 2: Right -> Left --.
        logging.info("Sending message from RIGHT to LEFT...")
        r_in = session.send(
            "DOM.querySelector",
            {
                "nodeId": right_shadow,
                "selector": "input#messageInput",
            },
        )["nodeId"]
        r_btn = session.send(
            "DOM.querySelector",
            {
                "nodeId": right_shadow,
                "selector": "button#sendButton",
            },
        )["nodeId"]

        type_text(session, r_in, "Hello from the right side!")
        click_element(session, r_btn)

        logging.info("Verifying message on LEFT...")
        wait_for_condition(session, "socket-connection",
                           "Hello from the right side!")
        logging.info("%sVerified 'Hello from the right side!' on left.%s",
                     GREEN, RESET)

        logging.info("%sTest finished successfully!%s", GREEN, RESET)
        return True

    except Exception as e:
        logging.error("%sTest Failed: %s%s", RED, e, RESET)
        return False
    finally:
        if ws:
            try:
                ws.close()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        type=int,
        default=9222,
        help="Remote debugging port (default: 9222)",
    )
    opts = parser.parse_args(argv)

    return 0 if run_test(opts.port) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
