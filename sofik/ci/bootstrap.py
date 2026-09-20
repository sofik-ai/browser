#!/usr/bin/env python3
# Copyright 2026 Sofik. All rights reserved.
"""Makes a fresh checkout of this tree buildable, toolchains only.

    python3 sofik/ci/bootstrap.py              # fetch what is missing
    python3 sofik/ci/bootstrap.py --check      # report only, non-zero if short
    python3 sofik/ci/bootstrap.py --platform win

The source is Sofik's own and lives in the repository: nothing here ever
fetches source, and `gclient sync` is never run. What the repository does not
carry are the toolchains -- clang, rust, node, gn, ninja, siso, the Linux
sysroot -- because they are downloadable binaries pinned by DEPS, not part of
the browser. On a developer machine they are already next to the tree; on a
fresh CI checkout none of them are, and this script puts them where `gn gen`
and `autoninja` expect them:

    third_party/depot_tools                 gn/ninja/siso/autoninja wrappers
    third_party/llvm-build/Release+Asserts  clang, lld, llvm-objdump
    third_party/rust-toolchain              rustc, std, bindgen
    third_party/node/<platform>             node binary for the WebUI toolchain
    third_party/node/node_modules           the npm tree that goes with it
    buildtools/{mac,linux64,win}            gn
    third_party/ninja, third_party/siso     the two build executors
    build/linux/debian_bullseye_amd64-sysroot   Linux only
    third_party/test_fonts/test_fonts       Linux only
    ui/gl/resources/angle-metal             macOS only

The pins come from DEPS itself, read as Python, so there is exactly one place
to update when the tree rolls. GCS objects carry a sha256 in DEPS and every
download is checked against it before it is moved into place; CIPD packages
are addressed by instance id, which is their hash, and the cipd client checks
them on its own. The Linux sysroot is installed by the tree's own
install-sysroot.py, which already verifies the sha256 from sysroots.json.

After a run, a build needs only:

    PATH=<src>/third_party/depot_tools:$PATH DEPOT_TOOLS_UPDATE=0 \\
        gn gen out/Release && autoninja -C out/Release <target>

The depot_tools wrappers find the tree by asking git for the top level and
looking for buildtools/ there, so no .gclient file is needed -- but the
checkout has to be a git checkout, not an unpacked tarball.
"""

import argparse
import hashlib
import json
import os
import platform as platform_module
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1]

# depot_tools is not in DEPS -- it is the bootstrap of the bootstrap -- so the
# pin lives here. It is the commit the browser was last built with; bump it
# deliberately, never by letting depot_tools update itself (hence
# DEPOT_TOOLS_UPDATE=0 and the .disable_auto_update file written below).
DEPOT_TOOLS_URL = "https://chromium.googlesource.com/chromium/tools/depot_tools.git"
DEPOT_TOOLS_COMMIT = "0306e4682b4ac35287c726fa35a983157a625902"

GCS_HOST = "https://storage.googleapis.com"

PLATFORMS = ("linux", "mac", "win")
# The runners we build on. --cpu overrides it; for the host platform the host's
# own cpu wins, so a developer on an Intel Mac gets the x64 packages.
DEFAULT_CPU = {"linux": "x64", "mac": "arm64", "win": "x64"}

# DEPS paths, by platform, in the order they are fetched. Kept explicit rather
# than derived from DEPS conditions: DEPS describes a full Chromium checkout
# (Android, ChromeOS, test data, the updater, skia gold), and a build of this
# browser needs a small corner of it. Every entry here is a directory some
# build step of ours actually reads.
GCS_DEPS = {
    "linux": [
        "src/third_party/llvm-build/Release+Asserts",
        "src/third_party/rust-toolchain",
        # node.gni feeds the Linux node binary to every node action on Linux.
        "src/third_party/node/linux",
        "src/third_party/node/node_modules",
        # Linked into the fontconfig-backed text stack the Linux build uses.
        "src/third_party/test_fonts/test_fonts",
    ],
    "mac": [
        "src/third_party/llvm-build/Release+Asserts",
        "src/third_party/rust-toolchain",
        # node.gni picks mac/ or mac_arm64/ by host_cpu, so only one is needed;
        # DEPS pulls both because Chromium cross-compiles between them.
        "src/third_party/node/mac_arm64",
        "src/third_party/node/node_modules",
    ],
    "win": [
        "src/third_party/llvm-build/Release+Asserts",
        "src/third_party/rust-toolchain",
        "src/third_party/node/win",
        "src/third_party/node/node_modules",
    ],
}
# On an Intel Mac node lives in mac/ instead; patched in by deps_for().
NODE_MAC_X64 = "src/third_party/node/mac"

CIPD_DEPS = {
    "linux": [
        "src/buildtools/linux64",
        "src/third_party/ninja",
        "src/third_party/siso/cipd",
        # Blink's generated lookup tables (CSS properties, HTML entities). macOS
        # and Windows find a gperf elsewhere; on Linux the build names this one.
        "src/third_party/gperf/cipd",
    ],
    "mac": [
        "src/buildtools/mac",
        "src/third_party/ninja",
        "src/third_party/siso/cipd",
        # The prebuilt Metal shader libraries the GPU process loads.
        "src/ui/gl/resources/angle-metal",
    ],
    "win": [
        "src/buildtools/win",
        "src/third_party/ninja",
        "src/third_party/siso/cipd",
    ],
}

# The DevTools front end is a checkout inside the checkout, with a DEPS of its
# own, and the tools that bundle it are pinned there rather than in the root
# DEPS. Both are host binaries: esbuild is an executable and rollup_libs a
# native node module. A tree that carries the Mac's copies builds on a Mac and
# nowhere else -- on Linux the file is there, has the right name, and is a
# Mach-O -- so they are fetched for the host like any other tool.
DEVTOOLS_DIR = "third_party/devtools-frontend/src"
DEVTOOLS_CIPD_DEPS = [
    "third_party/esbuild",
    "third_party/rollup_libs",
]

# cipd's ${{platform}} / ${{arch}}, which we expand ourselves instead of
# letting cipd do it: --platform win on a Mac must ask for windows packages.
CIPD_PLATFORM = {
    ("linux", "x64"): "linux-amd64",
    ("linux", "arm64"): "linux-arm64",
    ("mac", "x64"): "mac-amd64",
    ("mac", "arm64"): "mac-arm64",
    ("win", "x64"): "windows-amd64",
    ("win", "arm64"): "windows-arm64",
}
CIPD_ARCH = {"x64": "amd64", "arm64": "arm64"}

# The sysroot is a Linux-only affair and the only 32-bit-capable one we skip:
# the runners are x86-64 and we do not ship a 32-bit browser.
SYSROOT_ARCH = "x64"
SYSROOT_DIR = "build/linux/debian_bullseye_amd64-sysroot"


class Problem(Exception):
    pass


def log(*words) -> None:
    print(*words, flush=True)


def human(size: int) -> str:
    return (f"{size / 1_000_000:.0f} MB" if size >= 1_000_000
            else f"{size / 1_000:.0f} kB")


def remove_tree(path: Path) -> None:
    """rmtree that survives git's read-only object files on Windows."""
    def relent(func, name, _):
        os.chmod(name, 0o700)
        func(name)

    shutil.rmtree(path, onexc=relent) if sys.version_info >= (3, 12) else \
        shutil.rmtree(path, onerror=relent)


# ---------------------------------------------------------------- DEPS pins


class Namespace(dict):
    """A DEPS condition namespace where an unknown name is simply false.

    DEPS conditions mention variables that only exist once gclient has merged
    custom_vars from a .gclient file we deliberately do not have. Anything we
    did not set is a feature we are not checking out."""

    def __missing__(self, key):
        return False


def read_deps(root: Path) -> dict:
    """DEPS is Python; executing it is how gclient reads it too."""
    scope = {"Str": str}
    scope["Var"] = lambda name: scope["vars"][name]
    source = (root / "DEPS").read_text()
    exec(compile(source, str(root / "DEPS"), "exec"), scope)  # noqa: S102
    return scope


def fetch_devtools_tools(root: Path, plat: str, cpu: str, check: bool) -> bool:
    devtools = root.joinpath(*DEVTOOLS_DIR.split("/"))
    if not (devtools / "DEPS").is_file():
        return True
    scope = read_deps(devtools)
    ok = True
    for deps_path in DEVTOOLS_CIPD_DEPS:
        # fetch_cipd wants a path as the root DEPS writes them: "src/...".
        ok &= fetch_cipd(root, f"src/{DEVTOOLS_DIR}/{deps_path}",
                         scope["deps"][deps_path], plat, cpu, check)
    if ok and not check and plat == host_platform():
        # rollup loads its native half as the npm package
        # @rollup/rollup-<platform>, from node_modules. Upstream puts it there
        # with a gclient hook after every sync; nothing here runs gclient, and
        # without it every rollup action fails with "Cannot find module
        # @rollup/rollup-linux-x64-gnu" -- an hour into the build.
        sync = devtools / "scripts" / "deps" / "sync_rollup_libs.py"
        if sync.is_file():
            log("  sync rollup's native module into node_modules")
            subprocess.run([sys.executable, str(sync)], cwd=str(devtools),
                           check=True)
    return ok


def condition_namespace(scope: dict, plat: str, cpu: str) -> Namespace:
    ns = Namespace(scope.get("vars", {}))
    ns.update(
        host_os=plat,
        host_cpu=cpu,
        target_os=plat,
        target_cpu=cpu,
        checkout_linux=plat == "linux",
        checkout_mac=plat == "mac",
        checkout_win=plat == "win",
        checkout_android=False,
        checkout_ios=False,
        checkout_chromeos=False,
        checkout_fuchsia=False,
        checkout_src_internal=False,
        checkout_x64=cpu == "x64",
        checkout_arm64=cpu == "arm64",
        checkout_x86=False,
        checkout_arm=False,
        # Not a git submodule checkout: gclient's flag for "fetch the binaries".
        non_git_source=True,
        llvm_force_head_revision=False,
        rust_force_head_revision=False,
        # Editor and coverage extras nobody needs to compile the browser.
        checkout_clang_tidy=False,
        checkout_clangd=False,
        checkout_clang_coverage_tools=False,
    )
    return ns


def applies(condition, ns: Namespace) -> bool:
    if not condition:
        return True
    return bool(eval(condition, {"__builtins__": {}}, ns))  # noqa: S307


def deps_for(plat: str, cpu: str) -> tuple:
    gcs = list(GCS_DEPS[plat])
    if plat == "mac" and cpu == "x64":
        gcs[gcs.index("src/third_party/node/mac_arm64")] = NODE_MAC_X64
    return gcs, list(CIPD_DEPS[plat])


def rel(deps_path: str) -> str:
    """DEPS keys are rooted at the gclient solution; our root is that solution."""
    assert deps_path.startswith("src/"), deps_path
    return deps_path[len("src/"):]


def tree_path(root: Path, deps_path: str) -> Path:
    return root.joinpath(*rel(deps_path).split("/"))


# ------------------------------------------------------------ GCS downloads


def gcs_stamp(target: Path, object_name: str) -> Path:
    """The marker gclient leaves for a first-class GCS dep.

    Written in gclient's own spelling so that a tree populated by either one
    looks up to date to the other, and so a developer's existing checkout is
    recognised instead of re-downloaded."""
    flat = object_name.replace("/", "_").replace(".", "_")
    return target / f".{flat}_hash"


def gcs_present(target: Path, obj: dict) -> bool:
    stamp = gcs_stamp(target, obj["object_name"])
    try:
        return stamp.read_text().strip() == obj["sha256sum"]
    except OSError:
        return False


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    """Fetch to a temporary name in the destination's directory.

    Same filesystem as the final name, so the move at the end is atomic and an
    interrupted run leaves a .part file rather than a truncated toolchain."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    try:
        with urllib.request.urlopen(url) as response, open(part, "wb") as out:
            shutil.copyfileobj(response, out, 1024 * 1024)
        part.replace(destination)
    finally:
        part.unlink(missing_ok=True)


def unpack(archive: Path, target: Path) -> None:
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
        return
    with tarfile.open(archive) as tf:
        # These archives are Google's own, pinned, and verified by sha256 a few
        # lines above, and they contain relative symlinks (clang++ -> clang,
        # the rust sysroot) that the "data" filter rejects. Nothing untrusted
        # reaches this call.
        if hasattr(tarfile, "fully_trusted_filter"):
            tf.extractall(target, filter=tarfile.fully_trusted_filter)
        else:
            tf.extractall(target)


def fetch_gcs(root: Path, deps_path: str, entry: dict, ns: Namespace,
              check: bool) -> bool:
    """Returns True when the dep is (or was made) up to date."""
    target = tree_path(root, deps_path)
    bucket = entry["bucket"]
    ok = True
    for obj in entry["objects"]:
        if not applies(obj.get("condition"), ns):
            continue
        name = obj["object_name"]
        if gcs_present(target, obj):
            log(f"  have {rel(deps_path)} <- {name}")
            continue
        if check:
            log(f"  MISS {rel(deps_path)} <- {name}")
            ok = False
            continue
        log(f"  get  {rel(deps_path)} <- {name} ({human(obj['size_bytes'])})")
        # output_file is what gclient calls the downloaded file; without one
        # the object's basename is used and the object is an archive.
        filename = obj.get("output_file") or name.rsplit("/", 1)[-1]
        target.mkdir(parents=True, exist_ok=True)
        blob = target / filename
        download(f"{GCS_HOST}/{bucket}/{name}", blob)
        digest = sha256_of(blob)
        if digest != obj["sha256sum"]:
            blob.unlink(missing_ok=True)
            raise Problem(
                f"{name}: sha256 {digest}, DEPS says {obj['sha256sum']}")
        if filename.endswith((".tar.gz", ".tgz", ".tar.xz", ".zip")):
            unpack(blob, target)
            # gclient keeps the archive when DEPS named it and drops it
            # otherwise; node's .tar.gz stays next to the unpacked tree.
            if not obj.get("output_file"):
                blob.unlink()
        gcs_stamp(target, name).write_text(obj["sha256sum"] + "\n")
    return ok


# ---------------------------------------------------------- CIPD  packages


def cipd_stamp(target: Path) -> Path:
    return target / ".sofik_cipd"


def cipd_wanted(entry: dict, plat: str, cpu: str) -> list:
    out = []
    for package in entry["packages"]:
        name = (package["package"]
                .replace("${{platform}}", CIPD_PLATFORM[(plat, cpu)])
                .replace("${{arch}}", CIPD_ARCH[cpu]))
        out.append(f"{name} {package['version']}")
    return out


def cipd_present(target: Path, wanted: list) -> bool:
    try:
        return cipd_stamp(target).read_text().split("\n") == wanted + [""]
    except OSError:
        return False


def cipd_binary(root: Path) -> Path:
    tools = depot_tools_dir(root)
    return tools / ("cipd.bat" if os.name == "nt" else "cipd")


def fetch_cipd(root: Path, deps_path: str, entry: dict, plat: str, cpu: str,
               check: bool) -> bool:
    target = tree_path(root, deps_path)
    wanted = cipd_wanted(entry, plat, cpu)
    if cipd_present(target, wanted):
        log(f"  have {rel(deps_path)} <- {', '.join(wanted)}")
        return True
    if check:
        log(f"  MISS {rel(deps_path)} <- {', '.join(wanted)}")
        return False
    log(f"  get  {rel(deps_path)} <- {', '.join(wanted)}")
    target.mkdir(parents=True, exist_ok=True)
    # One cipd root per dep instead of gclient's single root with @Subdir
    # stanzas: it keeps cipd's .cipd state inside the directory it belongs to
    # rather than at the top of the source tree, and it lets each dep be
    # checked on its own.
    ensure = "\n".join(wanted) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".ensure", delete=False) as f:
        f.write(ensure)
        ensure_file = f.name
    try:
        # -log-level warning: cipd narrates every byte otherwise, and the
        # point of this script's output is one line per dependency.
        run([str(cipd_binary(root)), "ensure", "-log-level", "warning",
             "-root", str(target), "-ensure-file", ensure_file])
    finally:
        os.unlink(ensure_file)
    cipd_stamp(target).write_text(ensure)
    return True


# ----------------------------------------------------------- depot_tools


def depot_tools_dir(root: Path) -> Path:
    return root / "third_party" / "depot_tools"


def depot_tools_head(tools: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(tools), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def depot_tools_ready(tools: Path) -> bool:
    """Whether depot_tools has bootstrapped itself.

    Its wrappers -- gn, autoninja, siso -- are Python run by a Python of its
    own, fetched over CIPD the first time gclient runs. Nothing here runs
    gclient, so a fresh clone refuses every command with "python3_bin_reldir.txt
    not found", which is how the first CI run ended.
    """
    return (tools / "python3_bin_reldir.txt").is_file()


def bootstrap_depot_tools(tools: Path) -> None:
    log("  init third_party/depot_tools (its own python, over CIPD)")
    env = dict(os.environ, DEPOT_TOOLS_UPDATE="0")
    if os.name == "nt":
        # On Windows the same job is win_tools.bat's, which ensure_bootstrap
        # leaves alone.
        command = ["cmd", "/c", str(tools / "bootstrap" / "win_tools.bat")]
    else:
        command = ["bash", str(tools / "ensure_bootstrap")]
    result = subprocess.run(command, cwd=str(tools), env=env)
    if result.returncode != 0 or not depot_tools_ready(tools):
        raise Problem("depot_tools did not bootstrap itself")


def fetch_depot_tools(root: Path, check: bool) -> bool:
    tools = depot_tools_dir(root)
    if depot_tools_head(tools) == DEPOT_TOOLS_COMMIT:
        if depot_tools_ready(tools):
            log(f"  have third_party/depot_tools <- {DEPOT_TOOLS_COMMIT[:12]}")
            return True
        if check:
            log("  MISS third_party/depot_tools (cloned, not initialised)")
            return False
        bootstrap_depot_tools(tools)
        return True
    if check:
        log(f"  MISS third_party/depot_tools <- {DEPOT_TOOLS_COMMIT[:12]}")
        return False
    log(f"  get  third_party/depot_tools <- {DEPOT_TOOLS_COMMIT[:12]}")
    if tools.exists():
        remove_tree(tools)
    tools.mkdir(parents=True)
    run(["git", "-C", str(tools), "init", "--quiet"])
    run(["git", "-C", str(tools), "remote", "add", "origin", DEPOT_TOOLS_URL])
    try:
        # googlesource serves arbitrary reachable commits, so one shallow
        # fetch of the pin is enough; fall back for mirrors that do not.
        run(["git", "-C", str(tools), "fetch", "--quiet", "--depth", "1",
             "origin", DEPOT_TOOLS_COMMIT])
    except Problem:
        run(["git", "-C", str(tools), "fetch", "--quiet", "origin"])
    run(["git", "-C", str(tools), "checkout", "--quiet", DEPOT_TOOLS_COMMIT])
    # Belt and braces with DEPOT_TOOLS_UPDATE=0: a wrapper invoked without that
    # variable would otherwise roll depot_tools off the pin mid-build.
    (tools / ".disable_auto_update").write_text("pinned by sofik/ci/bootstrap.py\n")
    bootstrap_depot_tools(tools)
    return True


# -------------------------------------------------------------- sysroot


def sysroot_url(root: Path) -> str:
    path = root / "build" / "linux" / "sysroot_scripts" / "sysroots.json"
    entry = json.loads(path.read_text())["bullseye_amd64"]
    return f"{entry['URL']}/{entry['Sha256Sum']}"


def fetch_sysroot(root: Path, check: bool) -> bool:
    script = root / "build" / "linux" / "sysroot_scripts" / "install-sysroot.py"
    want = sysroot_url(root)
    stamp = root / SYSROOT_DIR / ".stamp"
    try:
        if stamp.read_text() == want:
            log(f"  have {SYSROOT_DIR}")
            return True
    except OSError:
        pass
    if check:
        log(f"  MISS {SYSROOT_DIR}")
        return False
    log(f"  get  {SYSROOT_DIR}")
    # The tree's own script: it knows the layout, verifies the pinned sha256
    # and writes the .stamp a later checkout reads. It needs no gclient.
    run([sys.executable, str(script), f"--arch={SYSROOT_ARCH}"])
    return True


# ----------------------------------------------------------------- driver


def run(command: list) -> None:
    result = subprocess.run(command)
    if result.returncode != 0:
        raise Problem(f"{command[0]} failed ({result.returncode})")


def host_platform() -> str:
    return {"darwin": "mac", "win32": "win", "cygwin": "win"}.get(
        sys.platform, "linux")


def host_cpu() -> str:
    machine = platform_module.machine().lower()
    return "arm64" if machine in ("arm64", "aarch64") else "x64"


def main(argv) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch the toolchains this tree pins.")
    parser.add_argument("--check", action="store_true",
                        help="report what is missing, download nothing")
    parser.add_argument("--platform", choices=PLATFORMS,
                        default=host_platform(),
                        help="target platform (default: the host)")
    parser.add_argument("--cpu", choices=("x64", "arm64"),
                        help="host cpu of that platform (default: per runner)")
    # Undocumented: run the whole thing against a copy of the tree, which is
    # how this script is tested without touching a working checkout.
    parser.add_argument("--root", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else SRC
    plat = args.platform
    cpu = args.cpu or (host_cpu() if plat == host_platform()
                       else DEFAULT_CPU[plat])

    log(f"sofik bootstrap: {plat}-{cpu} in {root}")
    scope = read_deps(root)
    ns = condition_namespace(scope, plat, cpu)
    gcs_paths, cipd_paths = deps_for(plat, cpu)

    ok = fetch_depot_tools(root, args.check)
    for deps_path in gcs_paths:
        entry = scope["deps"][deps_path]
        ok &= fetch_gcs(root, deps_path, entry, ns, args.check)
    for deps_path in cipd_paths:
        entry = scope["deps"][deps_path]
        ok &= fetch_cipd(root, deps_path, entry, plat, cpu, args.check)
    ok &= fetch_devtools_tools(root, plat, cpu, args.check)
    if plat == "linux":
        ok &= fetch_sysroot(root, args.check)

    if args.check:
        log("up to date" if ok else "incomplete")
        return 0 if ok else 1
    log("ready")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Problem as problem:
        sys.stderr.write(f"bootstrap: {problem}\n")
        sys.exit(1)
