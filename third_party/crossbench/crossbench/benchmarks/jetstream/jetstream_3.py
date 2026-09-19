# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import annotations

import abc
import logging
from typing import TYPE_CHECKING, ClassVar, Sequence, Type

from typing_extensions import override

from crossbench.benchmarks.jetstream.jetstream_2 import JetStream2Benchmark, \
    JetStream2BenchmarkStoryFilter, JetStream2Probe, JetStream2ProbeContext, \
    JetStream2Story
from crossbench.helper import url_helper
from crossbench.helper.collection_helper import close_matches_message
from crossbench.parse import ObjectParser

if TYPE_CHECKING:
  import argparse

  from crossbench.runner.actions import Actions


# TODO: introduce JetStreamProbe
class JetStream3Probe(JetStream2Probe, metaclass=abc.ABCMeta):
  """
  JetStream3-specific Probe.
  Extracts all JetStream 3 times and scores.
  """


class JetStream3ProbeContext(JetStream2ProbeContext):
  JS: ClassVar[str] = "return JetStream.resultsJSON('simple');"

  @override
  def to_json(self, actions: Actions) -> dict[str, float]:
    result = super().to_json(actions)
    lowercase_results = {}

    for key, value in result.items():
      lowercase_results[key.lower()] = value

    return lowercase_results


# TODO: introduce JetStreamStory
class JetStream3Story(JetStream2Story, metaclass=abc.ABCMeta):
  STORY_DATA: ClassVar[dict[str, tuple[str, ...]]]

  @classmethod
  @override
  def default_story_names(cls) -> tuple[str, ...]:
    return tuple(
        name for name, tags in cls.STORY_DATA.items() if "default" in tags)

  @classmethod
  def all_tags(cls) -> frozenset[str]:
    return frozenset(tag for tags in cls.STORY_DATA.values() for tag in tags)

  @property
  @override
  def url_params(self) -> dict[str, str]:
    params: dict[str, str] = super().url_params
    if self.substories != self.default_story_names():
      params["test"] = ",".join(self.substories)
    return params

  @property
  @override
  def test_url(self) -> str:
    params: dict[str, str] = self.url_params
    params["developerMode"] = ""
    params["startAutomatically"] = ""
    official_test_url = url_helper.update_url_query(self.URL, params)
    return official_test_url

  @override
  def setup_stories(self, actions: Actions) -> None:
    pass


ProbeClsTupleT = tuple[Type[JetStream3Probe], ...]


class JetStream3BenchmarkStoryFilter(JetStream2BenchmarkStoryFilter):
  __doc__ = JetStream2BenchmarkStoryFilter.__doc__

  @classmethod
  @override
  def add_cli_arguments(
      cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser = super().add_cli_arguments(parser)
    parser.add_argument(
        "--no-prefetch",
        dest="prefetch_resources",
        default=True,
        action="store_false",
        help=("Disable resources prefetching for better source positions. "
              "This might skew results as we do network request on the hot"
              "path"))
    return parser

  @classmethod
  @override
  def _add_story_filtering_arguments(
      cls, group: argparse._MutuallyExclusiveGroup) -> None:
    super()._add_story_filtering_arguments(group)
    group.add_argument(
        "--story-tags",
        "--story-tag",
        "--tag",
        action="append",
        default=[],
        help=("Comma-separated list of tags to filter stories. "
              "Only stories that have all specified tags will be included."))

  @classmethod
  def url_params_from_cli(cls, args: argparse.Namespace) -> dict[str, str]:
    url_params: dict[str, str] = super().url_params_from_cli(args)
    if not args.prefetch_resources:
      url_params["prefetchResources"] = "false"
    return url_params

  @override
  def process_all(self, patterns: Sequence[str]) -> None:
    if story_tags := self.args.story_tags:
      story_tags = ObjectParser.sequence(story_tags)
      patterns = self.process_tags(story_tags)
    super().process_all(patterns)

  def process_tags(self, story_tags: Sequence[str]) -> Sequence[str]:
    all_tags = self.story_cls.all_tags()
    all_names = self.story_cls.all_story_names()
    tags: set[str] = set()
    for tag_list in story_tags:
      for tag in tag_list.split(","):
        tag = tag.strip()
        if not tag:
          raise ValueError("Empty tag")
        if tag not in all_tags:
          error_message, alternative = close_matches_message(
              tag, all_tags, "story tag")
          if not alternative:
            raise ValueError(error_message)
          logging.error(error_message)
          tag = alternative
        tags.add(tag)
    story_data = self.story_cls.STORY_DATA
    filtered_names: list[str] = [
        name for name in all_names if tags.issubset(story_data.get(name))
    ]
    if not filtered_names:
      raise ValueError(f"No stories found with tags: {tags}")
    return filtered_names

# TODO: introduce JetStreamBenchmark
class JetStream3Benchmark(JetStream2Benchmark):
  STORY_FILTER_CLS: ClassVar = JetStream3BenchmarkStoryFilter
  DEFAULT_STORY_CLS: ClassVar[Type[JetStream3Story]]

  @classmethod
  @override
  def describe(cls) -> dict[str, object]:
    data = super().describe()
    data["tags"] = sorted(cls.DEFAULT_STORY_CLS.all_tags())
    return data
