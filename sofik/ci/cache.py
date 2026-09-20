#!/usr/bin/env python3
# Copyright 2026 Sofik. All rights reserved.
"""Carries the compiler cache from one build stage to the next.

    sofik/ci/cache.py restore --name sccache-linux64 --dir DIR
    sofik/ci/cache.py save    --name sccache-linux64 --dir DIR

A cold build of this tree is about 47,000 compiles, which is more than a
six-hour job on four cores can do. Several jobs can, but only if what the last
one learned survives, and on GitHub the obvious place for that does not fit:
the Actions cache is 10 GB for the whole repository, and three platforms want
five or six each, so they would evict one another every run and every stage
would start cold.

So the cache travels as assets of a release of its own, `build-cache`:

  <name>.index    JSON: the parts, in order, each with its sha256
  <name>.partNN   the tar stream, split because a release asset stops at 2 GB

Release assets have no repository-wide quota, they are not evicted, they are
readable from any branch, and GITHUB_TOKEN can write them -- which is the
whole list of things the Actions cache could not give us. They are also
public, like the rest of the repository; a compiler cache is derived from
published source and holds nothing that the released binaries do not.

Three details earn their code:

  - the index is uploaded last, after every part. An upload that dies halfway
    leaves the old index pointing at parts that no longer match, so the digests
    in it will not verify and the next stage starts cold instead of extracting
    a torn cache.
  - parts are downloaded, extracted and deleted one at a time. Holding the
    whole archive and the whole cache at once needs twice the disk, and disk is
    what these runners have least of.
  - nothing here fails a build. A cache is an optimisation; if any of it goes
    wrong the stage compiles from scratch and says so.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import human  # noqa: E402

CACHE_RELEASE = "build-cache"
# GitHub refuses a release asset over 2 GiB. Below it with room to spare, so a
# part that grows by a few bytes of tar padding is still accepted.
PART_SIZE = 1900 * 1024 * 1024


def gh(*args: str, check: bool = True, capture: bool = True):
    command = ["gh", *args]
    result = subprocess.run(
        command, capture_output=capture, text=True, errors="replace"
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"gh {' '.join(args[:3])} failed ({result.returncode}): "
            f"{(result.stderr or '')[-500:]}"
        )
    return result


def repo_of(args) -> str:
    repo = args.repo or os.environ.get("GH_REPO")
    if not repo:
        raise SystemExit("--repo, or GH_REPO in the environment")
    return repo


def directory_size(path: Path) -> int:
    total = 0
    for root, _, names in os.walk(path):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


# ---- the tar stream, split into parts --------------------------------------


class PartWriter:
    """A file object that writes a byte stream as a series of part files.

    The split is by bytes, not by tar member: the parts are meaningless alone
    and only ever concatenated, so there is nothing to be gained by aligning
    them to anything.
    """

    def __init__(self, directory: Path, name: str, on_part):
        self.directory = directory
        self.name = name
        self.on_part = on_part
        self.index: list[dict] = []
        self._handle = None
        self._digest = None
        self._written = 0

    def _open(self) -> None:
        part = f"{self.name}.part{len(self.index):02d}"
        self._path = self.directory / part
        self._handle = self._path.open("wb")
        self._digest = hashlib.sha256()
        self._written = 0

    def write(self, data: bytes) -> int:
        view = memoryview(data)
        while view:
            if self._handle is None:
                self._open()
            room = PART_SIZE - self._written
            chunk, view = view[:room], view[room:]
            self._handle.write(chunk)
            self._digest.update(chunk)
            self._written += len(chunk)
            if self._written >= PART_SIZE:
                self._finish()
        return len(data)

    def _finish(self) -> None:
        if self._handle is None:
            return
        self._handle.close()
        self._handle = None
        self.index.append({
            "name": self._path.name,
            "sha256": self._digest.hexdigest(),
            "size": self._written,
        })
        # Uploaded and deleted immediately: the alternative is keeping the
        # whole archive on a disk that does not have room for it.
        self.on_part(self._path)
        self._path.unlink(missing_ok=True)

    def close(self) -> None:
        self._finish()


class PartReader:
    """A read-only file object over parts fetched one at a time."""

    def __init__(self, parts: list[dict], fetch):
        self.parts = parts
        self.fetch = fetch
        self.position = 0
        self._handle = None
        self._digest = None
        self._path = None

    def _next(self) -> bool:
        if self.position >= len(self.parts):
            return False
        entry = self.parts[self.position]
        self.position += 1
        self._path = self.fetch(entry["name"])
        self._handle = self._path.open("rb")
        self._digest = hashlib.sha256()
        self._expected = entry["sha256"]
        return True

    def _close_current(self) -> None:
        self._handle.close()
        self._handle = None
        got = self._digest.hexdigest()
        self._path.unlink(missing_ok=True)
        if got != self._expected:
            raise ValueError(f"{self._path.name}: digest does not match")

    def read(self, size: int = -1) -> bytes:
        out = bytearray()
        while size < 0 or len(out) < size:
            if self._handle is None and not self._next():
                break
            want = -1 if size < 0 else size - len(out)
            chunk = self._handle.read(want)
            if not chunk:
                self._close_current()
                continue
            self._digest.update(chunk)
            out += chunk
        return bytes(out)

    def finish(self) -> None:
        """Drains what tarfile did not read, which is where the digests are.

        A tar stream ends at its end-of-archive marker, so the last part is
        never read to the end and its digest is never completed -- and the
        part file is still on disk. Reading the remaining padding closes,
        verifies and removes every part that is left.
        """
        while self.read(4 * 1024 * 1024):
            pass


# ---- restore ---------------------------------------------------------------


def cmd_restore(args: argparse.Namespace) -> None:
    repo = repo_of(args)
    directory = Path(args.dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    staging = Path(args.staging or directory.parent / f"{args.name}.parts")
    staging.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    def cold(why: str) -> None:
        print(f"--> cold cache: {why}", flush=True)
        shutil.rmtree(staging, ignore_errors=True)
        stamp(directory, args.name, 0)

    try:
        result = gh(
            "release", "download", CACHE_RELEASE, "--repo", repo,
            "--pattern", f"{args.name}.index", "--dir", str(staging),
            "--clobber", check=False,
        )
        index_path = staging / f"{args.name}.index"
        if result.returncode != 0 or not index_path.is_file():
            return cold(f"no {args.name}.index in the {CACHE_RELEASE} release")
        parts = json.loads(index_path.read_text())["parts"]
        index_path.unlink()

        def fetch(part_name: str) -> Path:
            gh("release", "download", CACHE_RELEASE, "--repo", repo,
               "--pattern", part_name, "--dir", str(staging), "--clobber")
            return staging / part_name

        reader = PartReader(parts, fetch)
        with tarfile.open(fileobj=reader, mode="r|") as tar:
            # The `tar` filter keeps the mode and the timestamp and drops the
            # owner, which is what restoring build output into a different
            # runner's account needs. Absent before 3.12, where extractall
            # behaves this way anyway.
            try:
                tar.extractall(directory, filter="tar")
            except TypeError:
                tar.extractall(directory)
        reader.finish()
    except Exception as error:  # noqa: BLE001 -- a cache never fails a build
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)
        return cold(str(error))

    shutil.rmtree(staging, ignore_errors=True)
    size = directory_size(directory)
    stamp(directory, args.name, size)
    print(f"--> restored {human(size)} in {int(time.monotonic() - started)}s "
          f"from {len(parts)} part(s)", flush=True)


# ---- save ------------------------------------------------------------------


def stamp_path(directory: Path, name: str) -> Path:
    # Beside the cache, not inside it: anything inside would be archived.
    return directory.parent / f"{name}.restored"


def stamp(directory: Path, name: str, size: int) -> None:
    stamp_path(directory, name).write_text(str(size), encoding="utf-8")


def restored_size(directory: Path, name: str) -> int:
    path = stamp_path(directory, name)
    try:
        return int(path.read_text())
    except (OSError, ValueError):
        return 0


def cmd_save(args: argparse.Namespace) -> None:
    repo = repo_of(args)
    directory = Path(args.dir).resolve()
    if not directory.is_dir():
        print(f"--> nothing to save: {directory} does not exist", flush=True)
        return
    # An unset --dir resolves to the working directory, and the working
    # directory is a seven gigabyte checkout. Uploading that as a "cache" would
    # take an hour and publish the tree twice.
    if (directory / ".git").exists() or directory == Path.cwd():
        raise SystemExit(f"refusing to archive a source checkout: {directory}")

    size = directory_size(directory)
    before = restored_size(directory, args.name)
    # A stage that only replayed the cache has nothing to add, and re-uploading
    # several GB to say so costs minutes on every platform, every stage.
    if size <= before:
        print(f"--> unchanged at {human(size)}; nothing to upload", flush=True)
        return

    staging = Path(args.staging or directory.parent / f"{args.name}.parts")
    staging.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    # `|| true` on the create, as elsewhere: the release exists from the
    # second run onwards, and that is not an error.
    gh("release", "create", CACHE_RELEASE, "--repo", repo,
       "--title", "build cache", "--prerelease", "--notes",
       "Compiler caches for .github/workflows/release.yml. Not a download: "
       "these are build inputs, rewritten by every run.", check=False)

    def upload(path: Path) -> None:
        print(f"--> uploading {path.name} ({human(path.stat().st_size)})",
              flush=True)
        gh("release", "upload", CACHE_RELEASE, str(path), "--repo", repo,
           "--clobber")

    writer = PartWriter(staging, args.name, upload)
    try:
        # Uncompressed: sccache already stores every entry compressed, so a
        # second pass costs CPU on a four-core runner and saves almost nothing.
        with tarfile.open(fileobj=writer, mode="w|") as tar:
            tar.add(directory, arcname=".")
        writer.close()

        index = staging / f"{args.name}.index"
        index.write_text(
            json.dumps({"parts": writer.index, "bytes": size}, indent=2),
            encoding="utf-8",
        )
        # Last, always: until this lands, the old index still describes a
        # complete set of parts, and any reader either gets the old cache or
        # gets a digest mismatch and starts cold.
        upload(index)
        index.unlink()
    except Exception as error:  # noqa: BLE001
        print(f"--> could not save the cache: {error}", flush=True)
        return
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    prune_stale_parts(repo, args.name, len(writer.index))
    print(f"--> saved {human(size)} as {len(writer.index)} part(s) in "
          f"{int(time.monotonic() - started)}s", flush=True)


def prune_stale_parts(repo: str, name: str, kept: int) -> None:
    """Deletes parts a smaller cache left behind.

    An index that names four parts while a fifth from a bigger run is still
    attached is harmless -- nothing reads it -- but it is several GB of
    confusion sitting in the release for ever.
    """
    result = gh("release", "view", CACHE_RELEASE, "--repo", repo,
                "--json", "assets", "-q", ".assets[].name", check=False)
    if result.returncode != 0:
        return
    for asset in result.stdout.split():
        if not asset.startswith(f"{name}.part"):
            continue
        try:
            number = int(asset.rsplit("part", 1)[1])
        except ValueError:
            continue
        if number >= kept:
            print(f"--> removing stale {asset}", flush=True)
            gh("release", "delete-asset", CACHE_RELEASE, asset,
               "--repo", repo, "--yes", check=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("restore", cmd_restore), ("save", cmd_save)):
        command = sub.add_parser(name)
        command.add_argument("--name", required=True,
                             help="asset base name, e.g. sccache-linux64")
        command.add_argument("--dir", required=True, help="the cache directory")
        command.add_argument("--repo", help="owner/name; GH_REPO by default")
        command.add_argument("--staging", help="where parts are written")
        command.set_defaults(handler=handler)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
