# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import io
import struct
import zipfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from zipfile import ZipFile

  from crossbench import path as pth

# Android Binary XML (AXML) Constants
# See https://android.googlesource.com/platform/frameworks/base/+/master/libs/androidfw/include/androidfw/ResourceTypes.h
RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_STRING_POOL_UTF8_FLAG = 1 << 8
RES_CHUNK_HEADER_SIZE = 8
RES_STRING_POOL_HEADER_SIZE = 28


def manifest_package_name(path: pth.LocalPath) -> str:
  if path.suffix == ".apks":
    return _package_name_from_apks(path)
  return _package_name_from_apk(path)


def _package_name_from_apks(path: pth.LocalPath) -> str:
  # .apks is a bundle, we need to extract the base apk
  with zipfile.ZipFile(path, "r") as bundle_zip:
    for name in bundle_zip.namelist():
      if not name.endswith(("base-master.apk", "base.apk")):
        continue
      with bundle_zip.open(name) as base_apk_file:
        with zipfile.ZipFile(io.BytesIO(base_apk_file.read())) as apk_zip:
          return _manifest_package_name_from_zip(apk_zip)
  raise ValueError(f"Could not extract package name from {path}")


def _package_name_from_apk(path: pth.LocalPath) -> str:
  with zipfile.ZipFile(path, "r") as apk_zip:
    return _manifest_package_name_from_zip(apk_zip)
  raise ValueError(f"Could not extract package name from {path}")


def _manifest_package_name_from_zip(apk_zip: ZipFile) -> str:
  with apk_zip.open("AndroidManifest.xml") as manifest_file:
    return parse_binary_manifest_package_name(manifest_file.read())


def parse_binary_manifest_package_name(data: bytes) -> str:
  # Minimal Android Binary XML (AXML) parser.
  # 1. Verify AXML Header
  if len(data) < RES_CHUNK_HEADER_SIZE or struct.unpack_from(
      "<H", data, 0)[0] != RES_XML_TYPE:
    raise ValueError("Invalid Android Binary XML header")

  # 2. Parse String Pool Chunk (0x00010001)
  pos = RES_CHUNK_HEADER_SIZE
  chunk_type, _, chunk_size = struct.unpack_from("<HHL", data, pos)
  if chunk_type != RES_STRING_POOL_TYPE:
    raise ValueError("Expected String Pool chunk")

  string_count, _, flags, string_offset, _ = struct.unpack_from(
      "<LLLLL", data, pos + RES_CHUNK_HEADER_SIZE)
  is_utf8 = (flags & RES_STRING_POOL_UTF8_FLAG) != 0
  strings_start = pos + string_offset

  # Extract all strings
  strings: list[str] = []
  for i in range(string_count):
    offset = struct.unpack_from("<L", data,
                                pos + RES_STRING_POOL_HEADER_SIZE + i * 4)[0]
    str_pos = strings_start + offset
    if is_utf8:
      # UTF-8 encoded: skip lengths (1-2 bytes each) and read until null
      val = data[str_pos]
      str_pos += 1 + (1 if (val & 0x80) else 0)
      val = data[str_pos]
      str_pos += 1 + (1 if (val & 0x80) else 0)
      end = data.find(b"\x00", str_pos)
      strings.append(data[str_pos:end].decode("utf-8", errors="ignore"))
    else:
      # UTF-16LE encoded
      length = struct.unpack_from("<H", data, str_pos)[0]
      str_pos += 4 if (length & 0x8000) else 2
      end = str_pos + (length * 2)
      strings.append(data[str_pos:end].decode("utf-16le", errors="ignore"))

  try:
    manifest_idx = strings.index("manifest")
    package_idx = strings.index("package")
  except ValueError as e:
    raise ValueError(
        "Missing 'manifest' or 'package' tags in string pool") from e

  # 3. Scan Element Chunks for the <manifest> Start Element (0x0102)
  pos += chunk_size
  while pos + RES_CHUNK_HEADER_SIZE <= len(data):
    chunk_type, chunk_header_size, chunk_size = struct.unpack_from(
        "<HHL", data, pos)
    if chunk_type == RES_XML_START_ELEMENT_TYPE:
      # Ext: ns_idx, name_idx, attr_start, attr_size, attr_count, ...
      _, name_idx, attr_start, attr_size, attr_count = struct.unpack_from(
          "<LLHHH", data, pos + chunk_header_size)

      # Found the <manifest> tag
      if name_idx == manifest_idx:
        attr_pos = pos + chunk_header_size + attr_start
        # Iterate over its attributes looking for "package"
        for _ in range(attr_count):
          # Attr: ns_idx, name_idx, val_str_idx, type, data
          _, a_name_idx, a_val_str_idx, _, _ = struct.unpack_from(
              "<LLLLL", data, attr_pos)
          if a_name_idx == package_idx:
            return strings[a_val_str_idx]
          attr_pos += attr_size
    pos += chunk_size

  raise ValueError("Could not find package attribute in manifest")
