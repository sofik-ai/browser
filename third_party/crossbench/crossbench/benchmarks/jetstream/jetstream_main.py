# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Type

from typing_extensions import override

from crossbench.benchmarks.jetstream.jetstream_3 import JetStream3Benchmark, \
    JetStream3Probe, JetStream3ProbeContext, JetStream3Story, ProbeClsTupleT

if TYPE_CHECKING:
  from crossbench.benchmarks.base import VersionParts


class JetStreamMainProbe(JetStream3Probe):
  __doc__ = JetStream3Probe.__doc__
  NAME: ClassVar[str] = "jetstream_main"

  @override
  def get_context_cls(self) -> Type[JetStreamMainProbeContext]:
    return JetStreamMainProbeContext


class JetStreamMainProbeContext(JetStream3ProbeContext):
  pass


"""
 JSON.stringify(
   BENCHMARKS.sort(
      (a, b) => a.name.toLowerCase() < b.name.toLowerCase() ? 1 : -1
    ).reduce((data, b) => {
     data[b.name] = Array.from(b.tags).sort();
     return data}, {}),
  undefined, "  ").replaceAll("[", "(").replaceAll("]", ")");
"""
JETSTREAM_MAIN_STORY_DATA = {
    "zlib-wasm": ("all", "default", "wasm"),
    "WSL": ("all", "default", "js", "wsl"),
    "web-ssr": ("all", "default", "js", "ssr", "web"),
    "validatorjs": ("all", "default", "js", "regexp"),
    "UniPoker": ("all", "default", "js", "rexbench"),
    "typescript-octane": ("all", "disabled", "js", "octane", "typescript"),
    "typescript-lib": ("all", "default", "js", "typescript"),
    "tsf-wasm": ("all", "default", "wasm"),
    "transformersjs-whisper-wasm":
        ("all", "disabled", "transformersjs", "wasm"),
    "transformersjs-bert-wasm": ("all", "default", "transformersjs", "wasm"),
    "threejs": ("all", "default", "js"),
    "tfjs-wasm-simd": ("all", "disabled", "wasm"),
    "tfjs-wasm": ("all", "disabled", "wasm"),
    "sync-fs": ("all", "default", "generators", "js"),
    "Sunspider": ("all", "default", "js", "sunspider"),
    "stanford-crypto-sha256": ("all", "default", "js", "seamonster"),
    "stanford-crypto-pbkdf2": ("all", "default", "js", "seamonster"),
    "stanford-crypto-aes": ("all", "default", "js", "seamonster"),
    "sqlite3-wasm": ("all", "default", "wasm"),
    "splay": ("all", "default", "js", "octane"),
    "source-map-wtb": ("all", "default", "js", "wtb"),
    "segmentation": ("all", "default", "js", "workertests"),
    "richards-wasm": ("all", "default", "wasm"),
    "richards": ("all", "default", "js", "octane"),
    "regexp-octane": ("all", "default", "js", "octane", "regexp"),
    "raytrace-public-class-fields": ("all", "classfields", "default", "js"),
    "raytrace-private-class-fields": ("all", "classfields", "default", "js"),
    "raytrace": ("all", "default", "js", "octane"),
    "quicksort-wasm": ("all", "disabled", "wasm"),
    "proxy-vue": ("all", "default", "js", "proxy"),
    "proxy-mobx": ("all", "default", "js", "proxy"),
    "prismjs-startup-es6": ("all", "default", "es6", "js", "parser", "prismjs",
                            "regexp", "startup"),
    "prismjs-startup-es5": ("all", "disabled", "es5", "js", "parser", "prismjs",
                            "regexp", "startup"),
    "prettier-wtb": ("all", "default", "js", "wtb"),
    "postcss-wtb": ("all", "default", "js", "wtb"),
    "pdfjs": ("all", "default", "js", "octane"),
    "OfflineAssembler": ("all", "default", "js", "rexbench"),
    "octane-code-load": ("all", "codeload", "default", "js", "octane"),
    "navier-stokes": ("all", "default", "js", "octane"),
    "multi-inspector-code-load":
        ("all", "codeload", "default", "inspector", "js"),
    "mobx-startup": ("all", "default", "es6", "js", "mobx", "startup"),
    "ML": ("all", "ares", "default", "js"),
    "mandreel": ("all", "default", "js", "octane"),
    "lebab-wtb": ("all", "disabled", "js", "wtb"),
    "lazy-collections": ("all", "default", "generators", "js"),
    "Kotlin-compose-wasm": ("all", "default", "wasm"),
    "json-stringify-inspector":
        ("all", "default", "inspector", "js", "json", "seamonster"),
    "json-parse-inspector":
        ("all", "default", "inspector", "js", "json", "seamonster"),
    "jsdom-d3-startup": ("all", "d3", "default", "js", "jsdom", "startup"),
    "js-tokens": ("all", "default", "generators", "js"),
    "j2cl-box2d-wasm": ("all", "default", "wasm"),
    "intl": ("all", "disabled", "internationalization", "js"),
    "HashSet-wasm": ("all", "disabled", "wasm"),
    "hash-map": ("all", "default", "js", "simple"),
    "gcc-loops-wasm": ("all", "disabled", "wasm"),
    "gbemu": ("all", "default", "js", "octane"),
    "gaussian-blur": ("all", "default", "js", "seamonster"),
    "FlightPlanner": ("all", "default", "js", "rexbench"),
    "first-inspector-code-load":
        ("all", "codeload", "default", "inspector", "js"),
    "esprima-next-wtb": ("all", "default", "js", "wtb"),
    "espree-wtb": ("all", "default", "js", "wtb"),
    "earley-boyer": ("all", "default", "js", "octane"),
    "doxbee-promise": ("all", "default", "js", "promise", "simple"),
    "doxbee-async": ("all", "default", "js", "simple"),
    "dotnet-interp-wasm": ("all", "default", "dotnet", "wasm"),
    "dotnet-aot-wasm": ("all", "default", "dotnet", "wasm"),
    "delta-blue": ("all", "default", "js", "octane"),
    "Dart-flute-todomvc-wasm": ("all", "default", "wasm"),
    "Dart-flute-complex-wasm": ("all", "disabled", "wasm"),
    "crypto": ("all", "default", "js", "octane"),
    "chai-wtb": ("all", "default", "js", "wtb"),
    "cdjs": ("all", "default", "js"),
    "Box2D": ("all", "default", "js", "octane"),
    "bomb-workers": ("all", "default", "js", "workertests"),
    "bigint-paillier": ("all", "bigint", "bigintmisc", "disabled", "js"),
    "bigint-noble-secp256k1":
        ("all", "bigint", "bigintnoble", "disabled", "js"),
    "bigint-noble-ed25519": ("all", "bigint", "bigintnoble", "default", "js"),
    "bigint-noble-bls12-381":
        ("all", "bigint", "bigintnoble", "disabled", "js"),
    "bigint-bigdenary": ("all", "bigint", "bigintmisc", "disabled", "js"),
    "Basic": ("all", "ares", "default", "js"),
    "babylonjs-startup-es6":
        ("all", "babylonjs", "class", "default", "es6", "js", "startup"),
    "babylonjs-startup-es5":
        ("all", "babylonjs", "class", "disabled", "es5", "js", "startup"),
    "babylonjs-scene-es6":
        ("all", "babylonjs", "default", "es6", "js", "scene"),
    "babylonjs-scene-es5":
        ("all", "babylonjs", "disabled", "es5", "js", "scene"),
    "babylon-wtb": ("all", "default", "js", "wtb"),
    "Babylon": ("all", "ares", "default", "js"),
    "babel-wtb": ("all", "default", "js", "wtb"),
    "babel-minify-wtb": ("all", "default", "js", "wtb"),
    "async-fs": ("all", "default", "generators", "js"),
    "argon2-wasm": ("all", "default", "wasm"),
    "Air": ("all", "ares", "default", "js"),
    "ai-astar": ("all", "default", "js", "seamonster"),
    "acorn-wtb": ("all", "default", "js", "wtb"),
    "8bitbench-wasm": ("all", "default", "wasm")
}

class JetStreamMainStory(JetStream3Story):
  __doc__ = JetStream3Story.__doc__
  NAME: ClassVar[str] = "jetstream_main"
  URL: ClassVar[str] = "https://chromium-workloads.web.app/jetstream/main/"
  URL_OFFICIAL: ClassVar[
      str] = "https://chromium-workloads.web.app/jetstream/main/"
  URL_CHROME_FORK: ClassVar[
      str] = "https://chromium-workloads.web.app/jetstream/main-custom/"
  STORY_DATA = JETSTREAM_MAIN_STORY_DATA
  SUBSTORIES: ClassVar[tuple[str, ...]] = tuple(STORY_DATA.keys())


class JetStreamMainBenchmark(JetStream3Benchmark):
  """
  Benchmark runner for the JetStream main development version.
  """

  NAME: ClassVar[str] = "jetstream_main"
  DEFAULT_STORY_CLS: ClassVar = JetStreamMainStory
  PROBES: ClassVar[ProbeClsTupleT] = (JetStreamMainProbe,)

  @classmethod
  @override
  def version(cls) -> VersionParts:
    return ("main",)
