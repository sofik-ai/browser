#!/usr/bin/env python3
# Copyright 2026 Sofik. All rights reserved.
"""Whether a platform's build for this release is already settled.

    sofik/ci/status.py check --tag v149... --platform linux64
    sofik/ci/status.py fail  --tag v149... --platform linux64 --stage 3

The stages of one platform are a chain of jobs, and every one of them has to
answer the same question before it does anything expensive: is there still
work to do? Two answers mean there is not.

  published  the release already carries artifact-<platform>.json, so the
             build finished in an earlier stage. Later stages exist for the
             platforms that needed them; this one is a few seconds of API
             call.
  failed     an earlier stage stopped for a reason that was not the deadline.
             Without this the remaining stages would each spend hours
             reaching the same broken edge. The marker names the release, so
             the next run starts clean.

Both are answered before the checkout, which on this tree is several minutes
and several gigabytes on its own.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cache import CACHE_RELEASE, gh, repo_of  # noqa: E402
from common import set_output  # noqa: E402


def marker(tag: str, platform: str) -> str:
    return f"failed-{tag}-{platform}.txt"


def assets(repo: str, release: str) -> list[str]:
    result = gh("release", "view", release, "--repo", repo,
                "--json", "assets", "-q", ".assets[].name", check=False)
    # A release that does not exist yet is the normal case for the first
    # stage of the first run, not an error.
    return result.stdout.split() if result.returncode == 0 else []


def cmd_check(args: argparse.Namespace) -> None:
    repo = repo_of(args)
    if f"artifact-{args.platform}.json" in assets(repo, args.tag):
        print(f"--> {args.platform} is already published in {args.tag}")
        return set_output("settled", "published")
    if marker(args.tag, args.platform) in assets(repo, CACHE_RELEASE):
        print(f"--> {args.platform} failed earlier in {args.tag}")
        return set_output("settled", "failed")
    set_output("settled", "")


def cmd_fail(args: argparse.Namespace) -> None:
    repo = repo_of(args)
    name = marker(args.tag, args.platform)
    path = Path(name)
    path.write_text(
        f"{args.platform} stopped in stage {args.stage} of {args.tag} for a "
        "reason that was not the deadline.\n",
        encoding="utf-8",
    )
    gh("release", "create", CACHE_RELEASE, "--repo", repo, "--title",
       "build cache", "--prerelease", "--notes", "Build state, not downloads.",
       check=False)
    gh("release", "upload", CACHE_RELEASE, str(path), "--repo", repo,
       "--clobber", check=False)
    path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("check", cmd_check), ("fail", cmd_fail)):
        command = sub.add_parser(name)
        command.add_argument("--tag", required=True, help="the release tag")
        command.add_argument("--platform", required=True)
        command.add_argument("--repo", help="owner/name; GH_REPO by default")
        command.add_argument("--stage", default="?")
        command.set_defaults(handler=handler)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
