#!/usr/bin/env python3
# Copyright 2026 Sofik. All rights reserved.
"""Builds and packages Sofik's browser in CI, one time-boxed stage at a time.

    sofik/ci/build.py runner-setup        make a hosted runner big enough
    sofik/ci/build.py gen                 generate the build directory
    sofik/ci/build.py build --deadline M  compile for at most M minutes
    sofik/ci/build.py package --dest DIR  make the release asset and its digest
    sofik/ci/build.py manifest            merge the per-platform sidecars

Two products, chosen with --config:

  cef      the CEF minimal binary distribution the espacial repository's
           third_party/webview_cef/third/download.cmake consumes. Windows and
           Linux.
  engine   SofikEngine.framework, what the Browser Card runs on macOS.

The reason this is a script and not a few lines of YAML is that it has to run
identically on three operating systems and on a developer's machine. A shell
step would be two implementations that drift, and a developer could not run
either of them to reproduce what CI did.

It is a sibling of tool/chromium/chromium.py in the espacial repository, which
does the same things interactively. The GN arguments below are copied from it
verbatim: each one was validated by a full build, and inventing one here would
produce a different browser that still compiles.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    IS_LINUX,
    IS_MAC,
    IS_WINDOWS,
    SRC,
    build_env,
    chromium_version,
    human,
    platform_tag,
    require_tree,
    run,
    set_env,
    set_output,
    sha256_of,
    slug,
    target_cpu,
)

# GN arguments, all of them measured rather than assumed. Copied from
# tool/chromium/chromium.py in the espacial repository; the comments there
# explain each one, and the short version is that `gn gen` accepts arguments
# that do not exist, so a flag nobody compiled with proves nothing.
GN_ARGS: dict[str, str] = {
    # Not the CEF default. Without it CEF produces an ordinary release with
    # dcheck_always_on, which aborts where a shipping build continues, and the
    # framework goes from 215 MB to 527 MB.
    "is_official_build": "true",
    "dcheck_always_on": "false",
    # Required alongside is_official_build: it turns on chrome_pgo_phase=2,
    # which needs profile data this checkout does not fetch.
    "chrome_pgo_phase": "0",
    "symbol_level": "0",
    "blink_symbol_level": "0",
    # Parity with the prebuilt CEF this replaced: a browser that cannot play
    # ordinary video is anomalous, so this is a fingerprint requirement as much
    # as a feature one.
    "proprietary_codecs": "true",
    "ffmpeg_branding": '"Chrome"',
    # Reporting, mDNS and service discovery all emit traffic this browser has
    # no reason to emit.
    "enable_reporting": "false",
    "enable_mdns": "false",
    "enable_service_discovery": "false",
    "enable_captive_portal_detection": "false",
    # The software rasteriser. A page that reads "SwiftShader" as the WebGL
    # renderer knows it is talking to something without a GPU.
    "enable_swiftshader": "false",
    # PDF stays: agents meet PDFs constantly.
    "enable_pdf": "true",
    # SwiftShader only goes when ANGLE and Dawn agree it is gone.
    "angle_enable_swiftshader": "false",
    "enable_swiftshader_vulkan": "false",
    "dawn_use_swiftshader": "false",
    # Vulkan debugging aids, not the Vulkan backend.
    "dawn_enable_vulkan_validation_layers": "false",
    "dawn_enable_spirv_validation": "false",
    "angle_has_frame_capture": "false",
    # On-device LLM service; the web-facing objects stay and report the model
    # as unavailable, which is what a real Chrome without the download does.
    "use_on_device_model_service": "false",
    "enable_hosted_apps": "false",
    "enable_remoting": "false",
    "enable_paint_preview": "false",
    "enterprise_local_content_analysis": "false",
    "enterprise_telomere_reporting": "false",
}

# macOS renders through Metal; ANGLE's Vulkan backend is only there to host
# SwiftShader. On Linux it is a real backend, so this one is not global.
MAC_GN_ARGS: dict[str, str] = {
    "angle_enable_vulkan": "false",
}

# CEF's gn_args.py turns the sysroot OFF on Linux ("recommended for local
# builds"), which makes the build read the host's headers and libraries: gn
# then runs the host's cups-config, pkg-config for GTK, NSS, X11 and the rest,
# and a machine needs some forty -dev packages before it can even generate.
# The first Linux run stopped there. The sysroot bootstrap.py fetches is the
# one DEPS pins, so with it on the build is the same wherever it runs and the
# binaries are linked against the old glibc a distribution should target.
LINUX_GN_ARGS: dict[str, str] = {
    "use_sysroot": "true",
}

# What CEF's own configuration adds, and what the engine has to repeat.
#
# The engine does not use CEF, but it is built in a tree CEF has patched, and
# those patches put //cef/libcef/features on the path of every graph: //content
# reaches it, so //sofik/engine reaches it, so //cef/BUILD.gn is evaluated even
# under --root-target=//sofik/engine:sofik. Its asserts then fail one by one --
# enable_widevine, enable_rlz -- and `gn gen` refuses.
#
# Rather than argue with them, the engine takes the same values CEF's
# tools/gn_args.py writes for a Release configuration, which is also what the
# macOS engine has always been built with. Verified by generating: without
# these, gn stops at cef/BUILD.gn:258; with them it makes 29,860 targets.
CEF_REQUIRED_ARGS: dict[str, str] = {
    "enable_widevine": "true",
    "enable_cdm_host_verification": "true",
    "enable_cdm_storage_id": "true",
    "alternate_cdm_storage_id_key": '"968b476909da4373b08903c28e859454"',
    "enable_rlz": "true",
    "enable_background_mode": "false",
    "enable_downgrade_processing": "false",
    "enable_resource_allowlist_generation": "false",
    "forbid_non_component_debug_builds": "false",
    "optimize_webui": "true",
    "disable_fieldtrial_testing_config": "true",
    "clang_use_chrome_plugins": "false",
}

# The compiler cache, and the whole reason a build that does not fit in a
# six-hour job can be finished by several of them.
#
#  - use_clang_modules has to be off. With modules on, sccache classes every
#    call as non-cacheable (-fmodules, and -Xclang flags it does not know) and
#    caches nothing while looking perfectly healthy.
#  - the working directory is part of sccache's key, so the build directory
#    name is fixed per configuration below and the workspace path has to stay
#    the same between stages. On GitHub-hosted runners it does
#    (/home/runner/work/<repo>/<repo>, D:\a\<repo>\<repo>); a self-hosted
#    runner that checks out somewhere else starts from a cold cache once.
SCCACHE_GN_ARGS: dict[str, str] = {
    "cc_wrapper": '"sccache"',
    "use_clang_modules": "false",
}

# The shipping targets, by the names the generated build.ninja gives them.
# Label form throughout: the short aliases GN also writes only exist when the
# name happens to be unique, and `cefclient` and `chrome_sandbox` are not
# unique on Linux. Derived from what cef/tools/make_distrib.py copies in
# minimal mode. Not cefclient: the sample application is in no minimal
# distribution, and on Linux it wants GTK headers the sysroot does not carry --
# the first Linux build compiled all of libcef and failed on it alone.
CEF_TARGETS: dict[str, list[str]] = {
    "windows64": [
        "cef:libcef",
        "cef:libcef_dll_wrapper",
        "chrome/chrome_elf:chrome_elf",
        "cef:bootstrap",
        "cef:bootstrapc",
        "cef:cef_sandbox",
    ],
    "linux64": [
        "cef:libcef",
        "cef:libcef_dll_wrapper",
        "sandbox/linux:chrome_sandbox",
    ],
    # macOS publishes the engine, not CEF. Kept so a developer can still run
    # this script locally for a CEF build: make_distrib takes the framework
    # out of cefclient.app rather than from the top of the output directory,
    # which is why cefclient is in the list at all.
    "macosarm64": [
        "cef:cef_framework",
        "cef:libcef_dll_wrapper",
        "cef:cefclient",
    ],
}

ENGINE_TARGET = "sofik/engine:sofik"


def out_dir(config: str) -> str:
    """One stable name per configuration -- see SCCACHE_GN_ARGS."""
    if config == "engine":
        return f"out/Engine_{target_cpu()}"
    # CEF's own naming scheme, from GetAllPlatformConfigs in cef/tools/gn_args.py.
    return f"out/Release_GN_{target_cpu()}"


def gn_args_for(config: str) -> dict[str, str]:
    args = {**GN_ARGS, **(MAC_GN_ARGS if IS_MAC else {}),
            **(LINUX_GN_ARGS if IS_LINUX else {})}
    if config == "engine":
        # CEF's script adds these itself for the CEF configuration; a plain
        # `gn gen` has to carry them.
        args.update(CEF_REQUIRED_ARGS)
        args.update({
            "is_debug": "false",
            "is_component_build": "false",
            "target_cpu": f'"{target_cpu()}"',
        })
    if shutil.which("sccache"):
        args.update(SCCACHE_GN_ARGS)
    return args


# ---- make room -------------------------------------------------------------

# What a hosted runner ships with that no Chromium build reads. The checkout is
# about 7 GB, the toolchains another 3, and a CEF output directory 11: none of
# the three platforms fits in what a runner offers untouched.
#
# Every entry is skipped when it is not there, so the same list serves every
# runner image, and nothing outside these names is touched.
JUNK = {
    "Linux": [
        "/usr/share/dotnet",
        "/usr/local/lib/android",
        "/opt/ghc",
        "/usr/local/share/boost",
        "/usr/local/share/powershell",
        "/usr/share/swift",
        "/usr/local/lib/node_modules",
        "/opt/hostedtoolcache/CodeQL",
        "/opt/hostedtoolcache/Ruby",
        "/opt/hostedtoolcache/go",
        "/opt/hostedtoolcache/node",
    ],
    "Windows": [
        r"C:\Android",
        r"C:\Miniconda",
        r"C:\Strawberry",
        r"C:\Program Files (x86)\Android",
        r"C:\Program Files\MongoDB",
        r"C:\Program Files\PostgreSQL",
        r"C:\Program Files\dotnet",
        r"C:\hostedtoolcache\windows\CodeQL",
        r"C:\hostedtoolcache\windows\Ruby",
        r"C:\hostedtoolcache\windows\go",
        r"C:\hostedtoolcache\windows\node",
        # Not Python: the job runs on the interpreter that lives under
        # hostedtoolcache, and so does this script.
    ],
    "Darwin": [
        "/Users/runner/Library/Developer/CoreSimulator",
        "/Users/runner/Library/Android",
        "/Users/runner/.dotnet",
        "/Users/runner/hostedtoolcache/Ruby",
        "/Users/runner/hostedtoolcache/go",
        "/Users/runner/hostedtoolcache/node",
    ],
}


def free_space(path: str | Path = "/") -> int:
    try:
        return shutil.disk_usage(str(path)).free
    except OSError:
        return 0


def remove(path: Path) -> None:
    """Deletes a directory, with sudo where the runner user does not own it."""
    if not path.exists():
        return
    try:
        shutil.rmtree(path, ignore_errors=False)
    except (PermissionError, OSError):
        if IS_WINDOWS:
            subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(path)])
        else:
            subprocess.run(["sudo", "rm", "-rf", str(path)])


def workspace() -> Path:
    return Path(os.environ.get("GITHUB_WORKSPACE") or os.getcwd())


def roomiest_volume() -> Path:
    """The volume with the most free space, which on Windows is not the one
    the job was given.

    A hosted Windows runner puts the workspace on D:, a 14 GB scratch disk,
    while C: is the 80 GB system disk with room to spare once the preinstalled
    SDKs are gone. The checkout alone is 7 GB, the output directory 11, so the
    build has to happen on C: -- see relocate() for how it gets there. Every
    other platform has one volume and this returns it.
    """
    here = workspace().anchor or "/"
    if not IS_WINDOWS:
        return Path(here)
    candidates = [Path(here)] + [Path(f"{letter}:\\") for letter in "CD"]
    return max(candidates, key=free_space)


def relocate(target_root: Path) -> None:
    """Moves the workspace onto another volume, invisibly.

    The workspace path is baked into a hundred places -- GITHUB_WORKSPACE, the
    default working directory, and sccache's cache key, which is the working
    directory the compiler ran in -- so the directory has to keep its name. A
    junction keeps the name and moves the bytes: everything still writes to
    D:\\a\\<repo>\\<repo>, and everything lands on C:.

    Called before the real checkout, when the workspace holds nothing but the
    sparse copy of these scripts.
    """
    here = workspace()
    if not IS_WINDOWS or (here.anchor or "/").upper() == str(target_root).upper():
        return
    target = target_root / "sofik-work"
    target.mkdir(parents=True, exist_ok=True)
    print(f"--> {here} -> {target} (junction)", flush=True)
    remove(here)
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(here), str(target)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # The checkout would land on the small disk and run out halfway, which
        # is a much worse way to find out.
        here.mkdir(parents=True, exist_ok=True)
        raise SystemExit(f"could not relocate the workspace: {result.stderr}")


def cmd_runner_setup(_: argparse.Namespace) -> None:
    """Makes a hosted runner big enough to build a browser on.

    Three things, in this order, all before the real checkout: delete what the
    image ships that this build has no use for, move the workspace to the
    volume with room on it, and put the compiler cache somewhere the checkout
    will not wipe.
    """
    # A developer's machine has the same directory names as a runner and none
    # of the same expectations about them.
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("runner-setup deletes preinstalled SDKs; CI only")
    import platform as platform_module

    volume = workspace().anchor or "/"
    before = free_space(volume)
    for name in JUNK.get(platform_module.system(), []):
        path = Path(name)
        if path.exists():
            print(f"--> removing {path}", flush=True)
            remove(path)
    if platform_module.system() == "Linux":
        # The image carries a few GB of pulled container images that nothing in
        # this build has any use for.
        subprocess.run(["docker", "system", "prune", "--all", "--force"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if IS_WINDOWS:
        # Every compile reads hundreds of headers and writes an object, and
        # the real-time scanner looks at each of them. The runner is ours for
        # the hour, and it is a build machine.
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Set-MpPreference -DisableRealtimeMonitoring $true"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    roomiest = roomiest_volume()
    for candidate in {volume, str(roomiest)}:
        print(f"--> free on {candidate}: {human(free_space(candidate))}", flush=True)
    relocate(roomiest)

    # Outside the workspace, because the checkout clears it, and on the volume
    # that has room, because it grows to several GB.
    # On Windows that is the root of the roomy drive. Elsewhere there is one
    # volume and its root is not the job's to write to -- on macOS it is
    # read-only outright -- so the home directory, which is on it.
    scratch = (roomiest if IS_WINDOWS else Path.home()) / "sofik-ci"
    (scratch / "sccache").mkdir(parents=True, exist_ok=True)
    set_env("SCCACHE_DIR", str(scratch / "sccache"))
    set_env("SOFIK_CI_SCRATCH", str(scratch))
    print(f"--> free: {human(before)} -> {human(free_space(str(roomiest)))}",
          flush=True)


# There is deliberately no command that deletes the checkout's .git to save
# the gigabyte it costs. depot_tools finds the tree by asking git for its top
# level -- see the note at the end of sofik/ci/bootstrap.py -- so a checkout
# without history is a checkout where `gn` and `autoninja` do not work.


# ---- generate --------------------------------------------------------------


def cmd_gen(args: argparse.Namespace) -> None:
    require_tree()
    directory = out_dir(args.config)
    if getattr(args, "if_needed", False) and (SRC / directory / "args.gn").is_file() \
            and (SRC / directory / "build.ninja").is_file():
        # A carried output directory (see the workflow's carry_out_dir):
        # already generated by an earlier stage of this same release run, for
        # the same commit and the same args -- the directory name is scoped to
        # both. Regenerating anyway is not wrong, only pointless: it rewrites
        # build.ninja with a new timestamp, and siso then re-verifies every
        # action against it rather than trusting what carried over. On the
        # Windows runner that alone cost four and a half hours for zero new
        # compiles -- the deadline gone to reconfirming, not building.
        print(f"--> {directory} is already generated; skipping", flush=True)
        return
    gn_args = gn_args_for(args.config)
    if "cc_wrapper" in gn_args:
        print("--> compiler cache: sccache", flush=True)

    if args.config == "engine":
        # Plain `gn gen`: cef_create_projects exists to apply CEF's patches and
        # to add CEF's own arguments, and the engine needs neither.
        # --root-target keeps the graph to what //sofik/engine reaches, which
        # is what makes it a third smaller than the CEF build of this tree.
        joined = " ".join(f"{k}={v}" for k, v in sorted(gn_args.items()))
        run(
            ["gn", "gen", directory, f"--root-target=//{ENGINE_TARGET}",
             f"--args={joined}"],
            SRC,
        )
        return

    if platform_tag() == "linux64":
        # gn_args.py only offers a configuration whose sysroot is installed,
        # and CEF would then raise "No supported architectures" -- which reads
        # like an unsupported CPU rather than a missing download.
        sysroot = SRC / "build" / "linux" / "debian_bullseye_amd64-sysroot"
        if not sysroot.is_dir():
            raise SystemExit(
                f"no Linux sysroot at {sysroot}\n"
                "It is part of the toolchain, so sofik/ci/bootstrap.py installs "
                "it; nothing here fetches anything."
            )

    env = build_env({
        "GN_DEFINES": " ".join(f"{k}={v}" for k, v in gn_args.items()),
        # Without this, gclient_hook.py also generates Debug (and on Windows
        # x86), which is three more `gn gen` runs of a 50,000-target graph for
        # configurations nothing builds.
        "GN_OUT_CONFIGS": Path(directory).name,
        # Only what //cef:cef reaches. A plain `gn gen` evaluates every
        # BUILD.gn in the tree, including tools nothing here builds, and one of
        # them fails on Linux with the arguments this browser is built with:
        # //chrome/tools/service_discovery_sniffer asserts
        # enable_service_discovery, which is off. It is also the graph the
        # prune lists were taken from.
        "GN_ARGUMENTS": "--root-target=//cef:cef",
    })
    script = "cef_create_projects.bat" if IS_WINDOWS else "./cef_create_projects.sh"
    run([script], SRC / "cef", env=env)


# ---- compile ---------------------------------------------------------------


def ninja_command(config: str) -> list[str]:
    targets = (
        [ENGINE_TARGET] if config == "engine" else CEF_TARGETS[platform_tag()]
    )
    # -k 0: keep going after a failure instead of stopping the world. A stage
    # that hits one broken edge should still spend its remaining hours filling
    # the cache with the other 40,000.
    return ["autoninja", "-C", out_dir(config), "-k", "0", *targets]


def missing_inputs(config: str, env) -> list[str]:
    """Every source file the graph names and the tree does not have.

    The tree was pruned against lists taken on a Mac, where the Windows and
    Linux graphs could be generated but not run: what their *host* tools read,
    and what a configuration generated slightly differently reads, was in
    nobody's list. A build finds such a file the hard way -- the scheduler
    stops at the first one, the stage fails, and the next run finds the second.
    (A dry run does no better: -n -k 0 still stops at the first.)

    `siso query inputs` prints every declared input of the targets without
    building anything, which is how the prune lists were made in the first
    place; whatever it names that is neither in the tree nor something the
    build itself produces is missing, and all of them come out at once.
    """
    directory = out_dir(config)
    targets = ninja_command(config)[5:]
    command = ["siso", "query", "inputs", "-C", directory, *targets]
    result = subprocess.run(
        " ".join(command) if IS_WINDOWS else command, cwd=str(SRC), env=env,
        shell=IS_WINDOWS, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        print(f"--> siso query inputs failed ({result.returncode}); "
              "skipping the check", flush=True)
        print(result.stderr[-2000:], flush=True)
        return []
    out_root = (SRC / directory).resolve()
    missing = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        path = (out_root / line).resolve()
        # Inside the output directory: generated, not there yet, not missing.
        if out_root == path or out_root in path.parents:
            continue
        if not path.exists():
            try:
                missing.add(path.relative_to(SRC.resolve()).as_posix())
            except ValueError:
                missing.add(str(path))
    return sorted(missing)


def run_with_deadline(command: list[str], cwd: Path, env, seconds: int) -> int | None:
    """Runs a command; returns its exit code, or None if the deadline passed.

    The deadline is the whole point of this file. A job is killed at six hours
    with no warning and no chance to save anything, so the build is stopped
    before that by us, on purpose, with time left to write the compiler cache
    where the next stage will find it.
    """
    printable = " ".join(str(part) for part in command)
    print(f"--> {printable}   (deadline {seconds // 60} min)", flush=True)
    kwargs: dict = {"cwd": str(cwd), "env": env}
    if IS_WINDOWS:
        kwargs["shell"] = True
        # A console child only hears Ctrl-Break, and only if it is in a group
        # of its own.
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        command = printable  # type: ignore[assignment]
    else:
        # autoninja is a wrapper around python around siso: signalling the
        # process alone leaves the compilers running.
        kwargs["start_new_session"] = True

    started = time.monotonic()
    process = subprocess.Popen(command, **kwargs)
    try:
        return process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        elapsed = int(time.monotonic() - started)
        print(f"--> deadline reached after {elapsed // 60} min; stopping",
              flush=True)
        try:
            if IS_WINDOWS:
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except (OSError, ValueError):
            pass
        try:
            process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        return None


# 2001-01-01. Older than any output, newer than nothing that matters.
OLD = 978307200


def make_sources_old() -> int:
    """Sets the modification time of everything outside out/ to OLD.

    siso, like ninja, decides that a step is stale when an input is newer than
    its output, and decides it by the clock, not by content: touching a header
    without changing a byte made a warm local build re-run 16,000 steps. A
    stage that restores the previous stage's output directory has fresh
    checkout, toolchain and generated files, all newer than every object in
    it, so without this all of it would be redone -- from the compiler cache,
    which is exactly the replay that does not fit in a stage on Windows.

    Only the timestamps change. A commit that differs from the one the output
    directory was built at must not reach this point with that directory; the
    workflow names the carried directory after the run for that reason.
    """
    count = 0
    stack = [SRC]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if directory == SRC and entry.name in ("out", ".git"):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                    try:
                        os.utime(entry.path, (OLD, OLD), follow_symlinks=False)
                    except NotImplementedError:
                        os.utime(entry.path, (OLD, OLD))
                    count += 1
                except OSError:
                    continue
    return count


def checkpoint(args: argparse.Namespace) -> None:
    """Uploads the compiler cache as it stands, mid-stage."""
    print("--> checkpoint: saving the compiler cache", flush=True)
    # Stopped so that the directory is whole while it is archived; the next
    # compile starts another server.
    subprocess.run(["sccache", "--stop-server"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(Path(__file__).with_name("cache.py")),
                    "save", "--name", args.cache_name, "--dir", args.cache_dir])


def compile_in_segments(args: argparse.Namespace, env) -> int | None:
    """The deadline, cut into pieces with the cache saved between them.

    A hosted runner can vanish -- "lost communication with the server", three
    and a half hours into a Windows stage -- and then nothing after Compile
    runs, the save included: the next stage started from where the previous
    one had. Stopping the build costs the compiles in flight and restarting
    it a few minutes, which is cheap against losing a stage.
    """
    total = args.deadline * 60
    segment = args.checkpoint * 60 if args.checkpoint and args.cache_dir else total
    started = time.monotonic()
    while True:
        left = total - (time.monotonic() - started)
        # A last piece too short to be worth a restart joins the one before.
        last = left <= segment * 1.5
        code = run_with_deadline(
            ninja_command(args.config), SRC, env, int(left if last else segment)
        )
        if code is not None or last:
            return code
        checkpoint(args)


def cmd_build(args: argparse.Namespace) -> None:
    require_tree()
    if not (SRC / out_dir(args.config) / "args.gn").is_file():
        raise SystemExit(f"no build directory: run `gen --config {args.config}`")

    env = build_env()
    missing = missing_inputs(args.config, env)
    if missing:
        print(f"--> {len(missing)} files the build reads are not in the tree:",
              flush=True)
        for path in missing:
            print(f"    MISSING {path}", flush=True)
        set_output("complete", "false")
        raise SystemExit("the tree is incomplete for this platform; "
                         "restore the files above (they are in quarantine)")
    # Always, not only when an output directory was carried in: siso decides
    # an input changed when its recorded metadata (from whichever stage last
    # wrote to .siso_fs_state) does not match what it now sees, in either
    # direction -- not "is it newer". A first stage that leaves sources at
    # today's real mtime and a second that then set them to a fixed one would
    # itself look like 300,000 changed inputs to the state carried between
    # them; every stage has to record the same value for a later one carrying
    # its output directory to see nothing changed at all.
    started = time.monotonic()
    count = make_sources_old()
    print(f"--> {count} sources set to a fixed mtime, "
          f"{int(time.monotonic() - started)}s", flush=True)
    code = compile_in_segments(args, env)

    if shutil.which("sccache"):
        # Printed whatever happened: hit rate is how a stage is judged, and a
        # rate near zero means the build is not actually being cached (see
        # use_clang_modules in SCCACHE_GN_ARGS).
        subprocess.run(["sccache", "--show-stats"])
        # The server holds nothing back, but stopping it makes "the cache
        # directory is now final" true rather than probably true.
        subprocess.run(["sccache", "--stop-server"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if code is None:
        set_output("complete", "false")
        print("--> incomplete: the next stage continues from the cache")
        return
    if code != 0:
        # Not a deadline: something is actually broken, and every further stage
        # would break the same way for five hours each.
        raise SystemExit(f"build failed ({code})")
    set_output("complete", "true")
    print("--> complete")


# ---- package ---------------------------------------------------------------


def tar_gz(source: Path, archive: Path, arcname: str) -> None:
    """Packs a directory, symbolic links and all.

    The engine framework *is* its symbolic links (Versions/Current, and the
    four at the top), so they are stored as links rather than followed;
    tarfile does that by default, and it is the reason this is not a zip.
    """
    print(f"--> packing {source.name}", flush=True)
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source, arcname=arcname)


def strip_elf(directory: Path) -> None:
    """Drops the symbol tables of what ships.

    CEF hands out libcef.so with them and tells the consumer to strip it. With
    symbol_level=0 there is no debug information to lose, only names: the
    first Linux libcef.so was 488 MB, 204 MB of it .symtab and .strtab that
    nothing reads at run time. The dynamic symbols -- the cef_* API -- stay.
    """
    strip = SRC / "third_party" / "llvm-build" / "Release+Asserts" / "bin" / "llvm-strip"
    if not strip.is_file():
        strip = Path(shutil.which("strip") or "strip")
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("rb") as handle:
            if handle.read(4) != b"\x7fELF":
                continue
        before = path.stat().st_size
        run([str(strip), "--strip-unneeded", str(path)], directory)
        print(f"--> stripped {path.name}: {before >> 20} MB -> "
              f"{path.stat().st_size >> 20} MB", flush=True)


def package_cef(dest: Path) -> tuple[Path, str]:
    distrib = dest / "distrib"
    distrib.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "make_distrib.py",
            f"--output-dir={distrib}",
            "--ninja-build",
            # Required on macOS too, despite the help text saying "(Linux
            # only)": without it the arch suffix defaults to _GN_x86 and it
            # looks for an output directory that does not exist.
            f"--{target_cpu()}-build",
            # Keeps include/, cmake/ and libcef_dll/ -- all three are
            # mandatory, because the consumer compiles libcef_dll_wrapper with
            # its own toolchain.
            "--minimal",
            "--no-archive",
            "--no-docs",
            "--no-symbols",
        ],
        SRC / "cef" / "tools",
    )
    built = sorted(p for p in distrib.glob("cef_binary_*_minimal") if p.is_dir())
    if not built:
        raise SystemExit(f"make_distrib produced nothing in {distrib}")
    distribution = built[-1]
    if IS_LINUX:
        strip_elf(distribution / "Release")
    version = distribution.name.removeprefix("cef_binary_").removesuffix(
        f"_{platform_tag()}_minimal"
    )
    archive = dest / f"cef_{platform_tag()}_{slug(version)}.tar.gz"
    tar_gz(distribution, archive, distribution.name)
    return archive, version


def package_engine(dest: Path) -> tuple[Path, str]:
    if not IS_MAC:
        raise SystemExit("the engine ships on macOS only so far")
    staging = dest / "engine"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    run(
        [sys.executable, str(SRC / "sofik" / "engine" / "package_mac.py"),
         "--out-dir", out_dir("engine"), "--dest", str(staging)],
        SRC,
    )
    framework = staging / "SofikEngine.framework"
    version = chromium_version()
    archive = dest / f"sofik_engine_{platform_tag()}_{version}.tar.gz"
    tar_gz(framework, archive, framework.name)
    return archive, version


def used_inputs(config: str, env) -> list[str]:
    """Every file of the tree this build read, as the build itself tells it.

    This is what lets the tree shrink. It was pruned against lists taken on a
    Mac, where the Linux and Windows graphs could be generated but never
    compiled, so nobody knew which headers those platforms include -- and
    every header was kept: 62,000 of them that no build is known to read. A
    finished build knows. Three sources, as in tool/chromium/inputs.py:

      siso query inputs   what the build files declare
      siso query deps     the headers the compiler really opened
      **/*.d              depfiles of actions (grit alone reads 11,000 files)
    """
    import re
    directory = out_dir(config)
    out_root = str((SRC / directory).resolve())
    src_root = str(SRC.resolve())
    # Raw spellings first, resolved once each at the end. The deps query
    # names every header of every object -- tens of millions of lines, almost
    # all repeats -- and resolving each against the disk, which is what
    # Path.resolve does on Windows, held the first finished Windows build in
    # this function for five hours, until the job's time ran out.
    raw: set[str] = set()

    def keep(path) -> None:
        raw.add(str(path))

    targets = ninja_command(config)[5:]
    for query, args in (("inputs", targets), ("deps", [])):
        command = ["siso", "query", query, "-C", directory, *args]
        result = subprocess.run(
            " ".join(command) if IS_WINDOWS else command, cwd=str(SRC),
            env=env, shell=IS_WINDOWS, capture_output=True, text=True,
            errors="replace")
        for line in result.stdout.splitlines():
            # `deps` prints "target: ..." then its inputs indented.
            if query == "deps" and not line.startswith((" ", "\t")):
                continue
            line = line.strip()
            if line:
                keep(os.path.join(out_root, line))
    for depfile in Path(out_root).rglob("*.d"):
        try:
            text = depfile.read_text(errors="replace")
        except OSError:
            continue
        _, _, deps = text.replace("\\\n", " ").partition(":")
        for token in re.findall(r"(?:\\ |\S)+", deps):
            token = token.replace("\\ ", " ")
            if token.endswith(":"):
                continue
            keep(token if os.path.isabs(token) else os.path.join(out_root, token))
    found: set[str] = set()
    inside = os.path.normcase(out_root) + os.sep
    for path in raw:
        path = os.path.normpath(path)
        if os.path.normcase(path).startswith(inside) \
                or os.path.normcase(path) == os.path.normcase(out_root):
            continue
        relative = os.path.relpath(path, src_root)
        if relative.startswith(".."):
            continue
        found.add(relative.replace(os.sep, "/"))
    return sorted(found)


def cmd_package(args: argparse.Namespace) -> None:
    require_tree()
    dest = Path(args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    if args.config == "engine":
        archive, version = package_engine(dest)
    else:
        archive, version = package_cef(dest)

    # What this platform's build read, published beside what it built. Never
    # worth failing a release over: the browser is the product, the list is
    # how the next prune is measured.
    try:
        import gzip
        used = used_inputs(args.config, build_env())
        listing = dest / f"inputs-{platform_tag()}.txt.gz"
        with gzip.open(listing, "wt") as out:
            out.write("\n".join(used) + "\n")
        print(f"--> {len(used)} files read by this build -> {listing.name}",
              flush=True)
    except Exception as error:  # noqa: BLE001
        print(f"--> could not list the build's inputs: {error}", flush=True)

    digest = sha256_of(archive)
    # The sidecar every consumer checks the download against. Written next to
    # the archive and uploaded with it, in the shape `sha256sum -c` reads.
    (dest / f"{archive.name}.sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    # And a description of the asset, for the job that assembles
    # artifacts.json once every platform has finished. It travels as a release
    # asset because that is the only place all three platforms can write to
    # and the manifest job can read from.
    sidecar = dest / f"artifact-{platform_tag()}.json"
    sidecar.write_text(
        json.dumps(
            {
                "tag": platform_tag(),
                "file": archive.name,
                "sha256": digest,
                "version": version,
                "chromium": chromium_version(),
                "product": "engine" if args.config == "engine" else "cef",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    size = archive.stat().st_size
    print(f"--> {archive}  ({human(size)})")
    print(f"--> sha256 {digest}")
    set_output("archive", str(archive))
    set_output("sha256", digest)
    set_output("version", version)


# ---- manifest --------------------------------------------------------------

MANIFEST_COMMENT = [
    "The Sofik browser builds the espacial repository installs, published from",
    "sofik-ai/browser by .github/workflows/release.yml.",
    "",
    "Copy this file over third_party/webview_cef/cef_artifact.json to move the",
    "app to this build. The sha256 is the point of it: without one, installing",
    "from a URL is the failure mode the CDN path had -- some server hands us a",
    "browser and nothing checks whether it is OUR browser.",
    "",
    "On Windows and Linux the artifact is a CEF minimal binary distribution.",
    "On macOS it is SofikEngine.framework: the Browser Card there runs on the",
    "Sofik engine, not on CEF.",
]


def cmd_manifest(args: argparse.Namespace) -> None:
    sidecars = sorted(Path(args.inputs).glob("artifact-*.json"))
    if not sidecars:
        raise SystemExit(f"no artifact-*.json under {args.inputs}")

    artifacts: dict[str, dict] = {}
    cef_version = None
    for path in sidecars:
        entry = json.loads(path.read_text())
        base = f"https://github.com/{args.repo}/releases/download/{args.tag}"
        artifacts[entry["tag"]] = {
            "url": f"{base}/{entry['file']}",
            "sha256": entry["sha256"],
            "version": entry["version"],
            "product": entry["product"],
        }
        if entry["product"] == "cef":
            cef_version = entry["version"]

    manifest = {
        "_comment": MANIFEST_COMMENT,
        # cef_artifact.json's consumers read `version` as the CEF version, so
        # that is what it is whenever a CEF distribution was published at all;
        # a macOS-only run has none, and Chromium's own version is the honest
        # answer there.
        "version": cef_version or chromium_version(),
        "chromium": chromium_version(),
        "release": args.tag,
        "artifacts": dict(sorted(artifacts.items())),
    }
    out = Path(args.out)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(out.read_text())

    missing = [t for t in ("windows64", "linux64", "macosarm64") if t not in artifacts]
    if missing:
        # Not an error. A release with two of three platforms is worth having,
        # and saying which one is absent is worth more than failing the job.
        print(f"--> no artifact for: {', '.join(missing)}", flush=True)


# ---- version ---------------------------------------------------------------


def cmd_tag(args: argparse.Namespace) -> None:
    version = chromium_version()
    set_output("chromium", version)
    set_output("tag", f"v{version}-sofik.{args.run_number}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def with_config(p):
        p.add_argument("--config", choices=("cef", "engine"), required=True)
        return p

    sub.add_parser(
        "runner-setup", help="make room and place the caches (CI only)"
    ).set_defaults(handler=cmd_runner_setup)
    gen = with_config(sub.add_parser("gen", help="generate the build directory"))
    gen.add_argument(
        "--if-needed", action="store_true",
        help="skip when the directory is already generated (args.gn, build.ninja exist)",
    )
    gen.set_defaults(handler=cmd_gen)

    build = with_config(sub.add_parser("build", help="compile, time-boxed"))
    build.add_argument(
        "--deadline", type=int, required=True,
        help="minutes to compile for before stopping cleanly",
    )
    build.add_argument(
        "--checkpoint", type=int, default=0,
        help="minutes between saves of the compiler cache during the build",
    )
    build.add_argument("--cache-name", help="the cache to checkpoint")
    build.add_argument("--cache-dir", help="its directory; none, no checkpoints")
    build.set_defaults(handler=cmd_build)

    package = with_config(sub.add_parser("package", help="make the release asset"))
    package.add_argument("--dest", required=True)
    package.set_defaults(handler=cmd_package)

    manifest = sub.add_parser("manifest", help="merge the per-platform sidecars")
    manifest.add_argument("--inputs", required=True)
    manifest.add_argument("--out", required=True)
    manifest.add_argument("--tag", required=True)
    manifest.add_argument("--repo", required=True)
    manifest.set_defaults(handler=cmd_manifest)

    tag = sub.add_parser("tag", help="the release tag for this run")
    tag.add_argument("--run-number", required=True)
    tag.set_defaults(handler=cmd_tag)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
