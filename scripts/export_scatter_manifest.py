#!/usr/bin/env python3
"""Write scatter_page_manifest.json (one entry per scatter page in story.json)."""
from __future__ import annotations

import argparse
import json

import common
from common import set_version
from scatter_pages import iter_scatter_pages, write_manifest

ROOT = common.ROOT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v2")
    args = parser.parse_args()

    vp = set_version(args.version)
    story = json.loads(vp.story_json.read_text())
    path = write_manifest(story, args.version)
    pages = iter_scatter_pages(story)
    print(f"Wrote {path.relative_to(ROOT)} ({len(pages)} scatter pages)")


if __name__ == "__main__":
    main()
