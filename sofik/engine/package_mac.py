#!/usr/bin/env python3
# Copyright 2026 Sofik. All rights reserved.
"""Assembles the engine as a host application embeds it on macOS.

    package_mac.py --out-dir out/Engine_arm64 --dest DIR

DIR/SofikEngine.framework goes into <Host>.app/Contents/Frameworks:

    Versions/A/SofikEngine             the engine; Headers/sofik_engine.h
    Versions/A/libsofik_engine.dylib   -> SofikEngine, the name the helpers
                                       were linked against
    Versions/A/Resources/              Info.plist, icudtl.dat, *.pak, *.bin
    Versions/A/Libraries/              ANGLE: a bundled GPU process loads it
                                       from the framework's Libraries/
    Versions/A/Helpers/<Helper>.app    renderer, GPU and utility processes
    Versions/A/Helpers/<Helper> (Renderer).app
    Versions/A/Helpers/<Helper> (GPU).app

Inside the main bundle, because the sandbox lets a child process read the main
bundle and nothing else. A framework, because everything under
Contents/Frameworks is code to codesign: loose resources there fail the
application's signature, while a framework seals its own. Three helper
bundles, because the content layer picks one per process type as soon as the
host is a bundle -- a renderer that finds no "(Renderer)" variant fails to
launch -- and because that is where the renderer's JIT entitlement goes when
the application is signed for distribution. They are copies of one executable;
signing tells them apart.
"""

import argparse
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

FRAMEWORK = "SofikEngine"
LIBRARY = "libsofik_engine.dylib"
HELPER = "Sofik Engine Helper"
BUNDLE_ID = "ai.sofik.engine"
# (name suffix, bundle id suffix), as content/public/app/mac_helpers.gni.
VARIANTS = [("", ""), (" (Renderer)", ".renderer"), (" (GPU)", "")]

ANGLE = ["libEGL.dylib", "libGLESv2.dylib"]
RESOURCES = ["icudtl.dat", "headless_lib_data.pak", "headless_lib_strings.pak",
             "snapshot_blob.bin"]
HERE = Path(__file__).resolve().parent


def version() -> str:
    fields = dict(line.split("=") for line in
                  (HERE.parents[1] / "chrome" / "VERSION").read_text().split())
    return "{MAJOR}.{MINOR}.{BUILD}.{PATCH}".format(**fields)


def info_plist(path: Path, executable: str, name: str, identifier: str,
               package_type: str, extra: dict) -> None:
    with open(path, "wb") as plist:
        plistlib.dump({
            "CFBundleExecutable": executable,
            "CFBundleIdentifier": identifier,
            "CFBundleName": name,
            "CFBundlePackageType": package_type,
            "CFBundleInfoDictionaryVersion": "6.0",
            "CFBundleShortVersionString": version(),
            "CFBundleVersion": version(),
            "LSMinimumSystemVersion": "12.0",
            **extra,
        }, plist)


def helper_bundle(out_dir: Path, helpers: Path, suffix: str, id_suffix: str):
    name = HELPER + suffix
    contents = helpers / f"{name}.app" / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    shutil.copy2(out_dir / "sofik_engine_helper", contents / "MacOS" / name)
    info_plist(contents / "Info.plist", name, name,
               f"{BUNDLE_ID}.helper{id_suffix}", "APPL", {
                   # No Dock icon, no menu bar: these are not applications.
                   "LSUIElement": True,
                   "NSSupportsAutomaticGraphicsSwitching": True,
               })


def sign(path: Path) -> None:
    # Ad-hoc, so the bundles are valid on Apple silicon as they are. A host
    # that ships re-signs everything with its own identity and entitlements.
    subprocess.run(["codesign", "--force", "--sign", "-", str(path)],
                   check=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    args = parser.parse_args()
    out_dir = args.out_dir.resolve()

    snapshots = sorted(p.name for p in out_dir.glob("v8_context_snapshot*.bin"))
    missing = [name for name in
               [LIBRARY] + ANGLE + RESOURCES + ["sofik_engine_helper"]
               if not (out_dir / name).is_file()]
    if missing or not snapshots:
        print(f"not in {out_dir}: {missing or 'v8_context_snapshot*.bin'}",
              file=sys.stderr)
        return 1

    framework = args.dest.resolve() / f"{FRAMEWORK}.framework"
    if framework.exists():
        shutil.rmtree(framework)
    current = framework / "Versions" / "A"
    for directory in ("Resources", "Libraries", "Helpers", "Headers"):
        (current / directory).mkdir(parents=True)

    # Under the framework's own name, so that a build system links it as any
    # other framework; the install name has to follow, or the loader looks for
    # the name it was built with.
    binary = current / FRAMEWORK
    shutil.copy2(out_dir / LIBRARY, binary)
    subprocess.run(
        ["install_name_tool", "-id",
         f"@rpath/{FRAMEWORK}.framework/Versions/A/{FRAMEWORK}", str(binary)],
        check=True, capture_output=True)
    (current / LIBRARY).symlink_to(FRAMEWORK)
    for name in RESOURCES + snapshots:
        shutil.copy2(out_dir / name, current / "Resources" / name)
    for name in ANGLE:
        shutil.copy2(out_dir / name, current / "Libraries" / name)
    shutil.copy2(HERE / "sofik_engine.h", current / "Headers")
    info_plist(current / "Resources" / "Info.plist", FRAMEWORK, FRAMEWORK,
               BUNDLE_ID, "FMWK", {})
    for suffix, id_suffix in VARIANTS:
        helper_bundle(out_dir, current / "Helpers", suffix, id_suffix)

    # The symbolic links that make it a framework.
    (framework / "Versions" / "Current").symlink_to("A")
    for name in (FRAMEWORK, "Resources", "Libraries", "Helpers", "Headers"):
        (framework / name).symlink_to(f"Versions/Current/{name}")

    # Inside out: a signature seals what is beneath it.
    for library in sorted((current / "Libraries").iterdir()):
        sign(library)
    for bundle in sorted((current / "Helpers").iterdir()):
        sign(bundle)
    sign(framework)

    size = sum(p.stat().st_size for p in current.rglob("*")
               if p.is_file() and not p.is_symlink())
    print(f"{framework}  {version()}  {size / 1e6:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
