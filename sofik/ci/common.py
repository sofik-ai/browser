#!/usr/bin/env python3
# Copyright 2026 Sofik. All rights reserved.
"""What the CI scripts share: where the tree is, what each platform is called,
and how to run a command with depot_tools on PATH.

Every path is derived from this file's location. A CI script that knew a
checkout location would work on exactly one machine, and these run on three
operating systems in Actions and on whatever a developer has locally.

Nothing here fetches Chromium. The tree is Sofik's browser, not a mirror of
upstream; the only thing CI downloads is toolchains, and that is
sofik/ci/bootstrap.py's job.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

# sofik/ci/common.py -> sofik/ci -> sofik -> src
SRC = Path(__file__).resolve().parents[2]

# bootstrap.py installs depot_tools here, inside the tree, rather than beside
# it: a sibling directory is one more thing a checkout has to be told about,
# and Actions gives a job nothing but the workspace.
DEPOT_TOOLS = SRC / "third_party" / "depot_tools"

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


def target_cpu() -> str:
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return "arm64"
    return "x64"


def platform_tag() -> str:
    """The tag the artifact is published and looked up under.

    The same names third/download.cmake and cef_artifact.json use in the
    espacial repository, and the same ones cef/tools/make_distrib.py puts in
    the distribution's directory name -- which is what lets `package` find
    what it just built.
    """
    if IS_MAC:
        return "macosarm64" if target_cpu() == "arm64" else "macosx64"
    if IS_WINDOWS:
        return "windows64"
    return "linux64"


def chromium_version() -> str:
    """149.0.7827.201, from the file the build itself reads."""
    fields = dict(
        line.split("=") for line in (SRC / "chrome" / "VERSION").read_text().split()
    )
    return "{MAJOR}.{MINOR}.{BUILD}.{PATCH}".format(**fields)


def slug(version: str) -> str:
    """A version safe in a URL and in a file name.

    CEF versions carry '+' (149.0.6+g0d0eeb6+chromium-149.0.7827.201), which
    has to be percent-encoded in a URL and reads badly everywhere else. The
    full version stays in the manifest, where it is data.
    """
    return version.replace("+", "-")


def build_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(DEPOT_TOOLS), env.get("PATH", "")])
    # Both are about not phoning home mid-build: depot_tools would otherwise
    # update itself, and CEF's scripts would look for a GYP build.
    env["DEPOT_TOOLS_UPDATE"] = "0"
    env["CEF_USE_GN"] = "1"
    # Windows: build against the Visual Studio the runner has, not against a
    # Google-internal toolchain package no outside machine can download.
    env["DEPOT_TOOLS_WIN_TOOLCHAIN"] = "0"
    env.update(extra or {})
    return env


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"--> {printable}", flush=True)
    # shell=True on Windows so the .bat wrappers (autoninja.bat, gn.bat)
    # resolve; the same call fails outright without it.
    result = subprocess.run(
        command if not IS_WINDOWS else printable,
        cwd=str(cwd),
        env=env or build_env(),
        shell=IS_WINDOWS,
    )
    if result.returncode != 0:
        raise SystemExit(f"failed ({result.returncode}): {printable}")


def require_tree() -> None:
    if not (SRC / "chrome" / "VERSION").is_file():
        raise SystemExit(f"{SRC} does not look like the Chromium source root")


def set_output(name: str, value: str) -> None:
    """Hands a value to the workflow, and prints it for a local run."""
    print(f"--> {name}={value}", flush=True)
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def set_env(name: str, value: str) -> None:
    """Hands a value to every later step of the job."""
    print(f"--> {name}={value}", flush=True)
    path = os.environ.get("GITHUB_ENV")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    os.environ[name] = value


def human(size: float) -> str:
    return f"{size / 1e9:.1f} GB" if size >= 1e9 else f"{size / 1e6:.0f} MB"


def sha256_of(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main_guard() -> None:
    if sys.version_info < (3, 9):
        raise SystemExit("python 3.9 or newer is required")
