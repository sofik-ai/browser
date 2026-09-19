# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import argparse
import dataclasses
from typing import TYPE_CHECKING, ClassVar, Optional

from typing_extensions import Self, override

if TYPE_CHECKING:
  from crossbench import path as pth

from crossbench.config import ConfigObject, ConfigParser
from crossbench.parse import PathParser


@dataclasses.dataclass(frozen=True)
class ApkConfig(ConfigObject):
  VALID_EXTENSIONS: ClassVar[tuple[str, ...]] = (".apk", ".apks")

  path: pth.LocalPath
  allow_downgrade: bool = True
  reinstall: bool = True
  modules: Optional[str] = None

  @classmethod
  def apk_path(cls, value: pth.AnyPathLike) -> pth.LocalPath:
    apk_path = PathParser.non_empty_file_path(value, "path")
    if apk_path.suffix not in cls.VALID_EXTENSIONS:
      raise argparse.ArgumentTypeError("APK path must end with .apk or .apks")
    return apk_path

  @classmethod
  @override
  def parse_str(cls, value: str) -> Self:
    return cls.parse_dict({"path": value})

  @classmethod
  @override
  def parse_path(cls, path: pth.LocalPath, **kwargs) -> Self:
    del kwargs
    return cls.parse_dict({"path": path})

  @classmethod
  @override
  def config_parser(cls) -> ConfigParser[Self]:
    parser = ConfigParser(cls)
    parser.add_argument(
        "path",
        type=cls.apk_path,
        help="Path to an Android APK or .apks bundle.")
    parser.add_argument(
        "allow_downgrade",
        type=bool,
        default=True,
        help="Allow APK downgrade during install.")
    parser.add_argument(
        "reinstall",
        aliases=("force",),
        type=bool,
        default=True,
        help="Uninstall and reinstall before each run.")
    parser.add_argument(
        "modules",
        type=str,
        help="Optional bundletool modules list for .apks installs.")
    return parser
