#!/usr/bin/env python3
# Copyright 2026 Sofik. All rights reserved.
"""Fills in the few source dependencies the Mac checkout never had.

    python3 sofik/ci/restore_linux_deps.py           # fetch and flatten
    python3 sofik/ci/restore_linux_deps.py --check   # report only
    python3 sofik/ci/restore_linux_deps.py --only wayland fontconfig

This tree is Sofik's own copy of the browser's source and is never re-synced:
sofik/ci/bootstrap.py downloads toolchains and nothing else. But the tree was
first checked out on a Mac, with checkout_linux and checkout_win off, so seven
directories that a Linux or a Windows build compiles were never populated --
fontconfig, wayland, the wayland protocol XML, libdrm, libsync and, for
Windows, the DirectX headers. They are source, not toolchain, which is why
they do not belong in bootstrap.py: they have to live in the repository like
the rest of the browser.

So this script runs once, by a developer, and then the result is committed. It
fetches each dependency at exactly the revision DEPS pins, shallow (one commit,
no history), and then deletes the nested .git so what is left is plain source
owned by this tree -- the same thing the rest of third_party/ already is. The
revisions are read from DEPS rather than repeated here, so a roll of DEPS and
a re-run stay in step.

One manual step remains afterwards. These paths are still listed in
.gitmodules and recorded in the index as gitlinks, so git will ignore the files
until the gitlink is dropped:

    git rm --cached third_party/fontconfig/src        # and the others
    git config -f .gitmodules --remove-section submodule.third_party/fontconfig/src
    git add third_party/fontconfig/src

Nothing here reaches upstream Chromium for the browser's own source: only these
seven third_party repositories, each at its pinned commit.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1]

# DEPS keys, in the order they are restored. Everything but the DirectX headers
# is Linux-only; microsoft_dxheaders is checkout_win and was missing for the
# same reason, so it rides along rather than waiting for a second script.
DEPENDENCIES = [
    # (nickname, DEPS key, what the build wants from it)
    # Windows only, like DirectX-Headers below: a Mac checkout skips what
    # DEPS marks checkout_win just as it skips what it marks checkout_linux.
    ("gperf", "src/third_party/gperf",
     "bin/gperf.exe, which generates Blink's lookup tables on Windows"),
    # Found by listing every git dependency DEPS gives Linux or Windows and
    # not the Mac, and keeping the ones living sources include from.
    ("cros_system_api", "src/third_party/cros_system_api",
     "D-Bus service constants; device/bluetooth and others include them"),
    ("minigbm", "src/third_party/minigbm/src",
     "gbm.h, for Ozone's GPU buffers on Linux"),
    ("webauthn", "src/third_party/microsoft_webauthn/src",
     "webauthn.h, for device/fido on Windows"),
    ("lss", "src/third_party/lss",
     "linux_syscall_support.h, which base, sandbox and crashpad include"),
    ("fontconfig", "src/third_party/fontconfig/src",
     "fontconfig's C sources and the fc-fontations Rust bridge"),
    ("wayland", "src/third_party/wayland/src",
     "libwayland client, cursor and the protocol scanner"),
    ("wayland-protocols", "src/third_party/wayland-protocols/src",
     "the stable, staging and unstable protocol XML"),
    ("wayland-protocols-kde", "src/third_party/wayland-protocols/kde",
     "the KDE appmenu and idle protocol XML"),
    ("libdrm", "src/third_party/libdrm/src",
     "xf86drm and the DRM fourcc table"),
    ("libsync", "src/third_party/libsync/src",
     "sync.c, the Android fence wrapper"),
    ("dxheaders", "src/third_party/microsoft_dxheaders/src",
     "dxguids.cpp -- Windows only"),
]


class Problem(Exception):
    pass


def log(*words) -> None:
    print(*words, flush=True)


def read_deps(root: Path) -> dict:
    """DEPS is Python; executing it is how gclient reads it too."""
    scope = {"Str": str}
    scope["Var"] = lambda name: scope["vars"][name]
    exec(compile((root / "DEPS").read_text(), str(root / "DEPS"), "exec"),
         scope)  # noqa: S102
    return scope


def pin(scope: dict, deps_path: str) -> tuple:
    """A DEPS source entry is either a 'url@rev' string or a dict with one."""
    entry = scope["deps"][deps_path]
    spec = entry if isinstance(entry, str) else entry["url"]
    url, _, revision = spec.rpartition("@")
    if not url or len(revision) != 40:
        raise Problem(f"{deps_path}: cannot read a pinned revision from {spec}")
    return url, revision


def tree_path(root: Path, deps_path: str) -> Path:
    assert deps_path.startswith("src/"), deps_path
    return root.joinpath(*deps_path[len("src/"):].split("/"))


def remove_tree(path: Path) -> None:
    """rmtree that survives git's read-only object files on Windows."""
    def relent(func, name, _):
        os.chmod(name, 0o700)
        func(name)

    shutil.rmtree(path, onexc=relent) if sys.version_info >= (3, 12) else \
        shutil.rmtree(path, onerror=relent)


def run(command: list) -> None:
    result = subprocess.run(command)
    if result.returncode != 0:
        raise Problem(f"{command[0]} failed ({result.returncode})")


def populated(target: Path) -> bool:
    """Empty or absent means the submodule was never checked out."""
    return target.is_dir() and any(
        child.name != ".git" for child in target.iterdir())


def measure(target: Path) -> tuple:
    files = 0
    size = 0
    for path in target.rglob("*"):
        if path.is_file() and not path.is_symlink():
            files += 1
            size += path.stat().st_size
    return files, size


def restore(root: Path, deps_path: str, url: str, revision: str) -> None:
    target = tree_path(root, deps_path)
    # Fetch in place rather than cloning to a temporary directory: the path
    # already exists as an empty submodule mount point, and working inside it
    # keeps the whole operation on one filesystem.
    target.mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(target)]
    run(git + ["init", "--quiet"])
    run(git + ["remote", "add", "origin", url])
    try:
        # chromium.googlesource.com serves any reachable commit, so one commit
        # is all that comes down -- no history, no other branches.
        run(git + ["fetch", "--quiet", "--depth", "1", "origin", revision])
    except Problem:
        # A mirror that refuses a commit-ish want; take the branches instead.
        run(git + ["fetch", "--quiet", "origin"])
    run(git + ["checkout", "--quiet", "--detach", revision])
    # And now it stops being a repository. The files belong to this tree from
    # here on: no submodule, no upstream, nothing left to re-sync.
    remove_tree(target / ".git")


def main(argv) -> int:
    parser = argparse.ArgumentParser(
        description="Restore the source dependencies a Mac checkout skipped.")
    parser.add_argument("--check", action="store_true",
                        help="report what is empty, fetch nothing")
    parser.add_argument("--only", nargs="+", metavar="NAME",
                        help="restore just these, by nickname")
    # Undocumented: run against a copy of the tree, which is how this script
    # is tested without touching a working checkout.
    parser.add_argument("--root", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else SRC
    scope = read_deps(root)
    chosen = [d for d in DEPENDENCIES
              if not args.only or d[0] in args.only]
    if args.only:
        unknown = set(args.only) - {d[0] for d in DEPENDENCIES}
        if unknown:
            raise Problem(f"unknown dependency: {', '.join(sorted(unknown))}")

    log(f"sofik restore: {len(chosen)} source dependencies in {root}")
    missing = 0
    for name, deps_path, why in chosen:
        target = tree_path(root, deps_path)
        url, revision = pin(scope, deps_path)
        label = deps_path[len("src/"):]
        if populated(target):
            files, size = measure(target)
            log(f"  have {label} ({files} files, {size / 1e6:.1f} MB)")
            continue
        missing += 1
        if args.check:
            log(f"  MISS {label} <- {url}@{revision[:12]} -- {why}")
            continue
        log(f"  get  {label} <- {url}@{revision[:12]}")
        restore(root, deps_path, url, revision)
        files, size = measure(target)
        log(f"       {files} files, {size / 1e6:.1f} MB, no .git")

    if args.check:
        log("complete" if not missing else f"{missing} missing")
        return 0 if not missing else 1
    log("restored -- now drop the gitlinks (see the docstring) and commit")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Problem as problem:
        sys.stderr.write(f"restore_linux_deps: {problem}\n")
        sys.exit(1)
