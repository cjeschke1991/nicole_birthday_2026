#!/usr/bin/env python3
"""Scatter page manifest — one entry per scatter page in story.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import common

ROOT = common.ROOT


@dataclass
class ScatterPage:
    id: str
    year: int
    recipe: str
    photos: list[str]
    captions: list[str]


def iter_scatter_pages(story: dict) -> list[ScatterPage]:
    pages: list[ScatterPage] = []
    for yr in story.get("years", []):
        photos = yr.get("photos", [])
        i, n, seq = 0, len(photos), 0
        year = int(yr["year"])
        while i < n:
            layout = photos[i].get("layout", "hero")
            if not layout.startswith("scatter"):
                i += 1
                continue
            recipe = layout
            group: list[dict] = []
            while i < n and photos[i].get("layout") == recipe and len(group) < 3:
                group.append(photos[i])
                i += 1
            seq += 1
            pages.append(ScatterPage(
                id=f"{year}-{seq:02d}",
                year=year,
                recipe=recipe,
                photos=[g["file"] for g in group],
                captions=[g.get("caption", "") for g in group],
            ))
    return pages


def manifest_path(version: str) -> Path:
    return common.VERSIONS_DIR / version / "scatter_page_manifest.json"


def caption_positions_path(version: str) -> Path:
    return common.VERSIONS_DIR / version / "caption_positions.json"


def load_manifest(version: str) -> list[ScatterPage]:
    path = manifest_path(version)
    if not path.is_file():
        return []
    raw = json.loads(path.read_text())
    return [ScatterPage(**entry) for entry in raw.get("pages", [])]


def write_manifest(story: dict, version: str) -> Path:
    pages = iter_scatter_pages(story)
    path = manifest_path(version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": 1,
        "pages": [asdict(p) for p in pages],
    }, indent=2) + "\n")
    return path


def load_caption_positions(version: str) -> dict[str, dict[str, float]]:
    path = caption_positions_path(version)
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text())
    return raw.get("by_photo", {})


def write_caption_positions(by_photo: dict[str, dict[str, float]], version: str) -> Path:
    path = caption_positions_path(version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "by_photo": by_photo}, indent=2) + "\n")
    return path
