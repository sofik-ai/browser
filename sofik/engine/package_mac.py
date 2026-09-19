#!/usr/bin/env python3
# Copyright 2026 Sofik. All rights reserved.
"""Assembles the engine as a host application embeds it on macOS.

    package_mac.py --out-dir out/Engine_arm64 --dest DIR

DIR/sofik_engine/ is what goes into <Host>.app/Contents/Frameworks:

    libsofik_engine.dylib       the engine; sofik_engine.h is its API
    Libraries/libEGL.dylib, libGLESv2.dylib   ANGLE; a bundled GPU process
                                looks in the framework bundle's Libraries/
    icudtl.dat *.pak *.bin      resources, found beside the library
    Helpers/<Helper>.app        renderer, GPU and utility processes
    Helpers/<Helper> (Renderer).app
    Helpers/<Helper> (GPU).app
    include/sofik_engine.h

Inside the main bundle, because the sandbox lets a child process read the main
bundle and nothing else. Three helper bundles, because the content layer picks
one per process type as soon as the host is a bundle -- a renderer that finds
no "(Renderer)" variant fails to launch -- and because that is where the
renderer's JIT entitlement goes when the application is signed for
distribution. They are copies of one executable; signing tells them apart.
"""

import argparse
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

HELPER = "Sofik Engine Helper"
BUNDLE_ID = "ai.sofik.engine.helper"
# (name suffix, bundle id suffix), as content/public/app/mac_helpers.gni.
VARIANTS = [("", ""), (" (Renderer)", ".renderer"), (" (GPU)", "")]

LIBRARIES = ["libsofik_engine.dylib"]
ANGLE = ["libEGL.dylib", "libGLESv2.dylib"]
RESOURCES = ["icudtl.dat", "headless_lib_data.pak", "headless_lib_strings.pak",
             "snapshot_blob.bin"]
HERE = Path(__file__).resolve().parent


def version() -> str:
    fields = dict(line.split("=") for line in
                  (HERE.parents[1] / "chrome" / "VERSION").read_text().split())
    return "{MAJOR}.{MINOR}.{BUILD}.{PATCH}".format(**fields)


def helper_bundle(out_dir: Path, helpers: Path, suffix: str, id_suffix: str):
    name = HELPER + suffix
    contents = helpers / f"{name}.app" / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    shutil.copy2(out_dir / "sofik_engine_helper", contents / "MacOS" / name)
    with open(contents / "Info.plist", "wb") as plist:
        plistlib.dump({
            "CFBundleExecutable": name,
            "CFBundleIdentifier": BUNDLE_ID + id_suffix,
            "CFBundleName": name,
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": version(),
            "CFBundleVersion": version(),
            "LSMinimumSystemVersion": "12.0",
            # No Dock icon, no menu bar: these are not applications.
            "LSUIElement": True,
            "NSSupportsAutomaticGraphicsSwitching": True,
        }, plist)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    args = parser.parse_args()
    out_dir = args.out_dir.resolve()

    engine = args.dest.resolve() / "sofik_engine"
    if engine.exists():
        shutil.rmtree(engine)
    engine.mkdir(parents=True)

    snapshots = sorted(p.name for p in out_dir.glob("v8_context_snapshot*.bin"))
    missing = [name for name in
               LIBRARIES + ANGLE + RESOURCES + ["sofik_engine_helper"]
               if not (out_dir / name).is_file()]
    if missing or not snapshots:
        print(f"not in {out_dir}: {missing or 'v8_context_snapshot*.bin'}",
              file=sys.stderr)
        return 1
    for name in LIBRARIES + RESOURCES + snapshots:
        shutil.copy2(out_dir / name, engine / name)
    (engine / "Libraries").mkdir()
    for name in ANGLE:
        shutil.copy2(out_dir / name, engine / "Libraries" / name)
    for suffix, id_suffix in VARIANTS:
        helper_bundle(out_dir, engine / "Helpers", suffix, id_suffix)
    (engine / "include").mkdir()
    shutil.copy2(HERE / "sofik_engine.h", engine / "include")

    # Ad-hoc, so the bundles are valid on Apple silicon as they are. A host
    # that ships re-signs everything with its own identity and entitlements.
    for bundle in sorted((engine / "Helpers").iterdir()):
        subprocess.run(["codesign", "--force", "--sign", "-", str(bundle)],
                       check=True, capture_output=True)

    size = sum(p.stat().st_size for p in engine.rglob("*") if p.is_file())
    print(f"{engine}  {version()}  {size / 1e6:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
