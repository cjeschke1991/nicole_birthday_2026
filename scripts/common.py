"""Shared constants and helpers for the Story of Us pipeline."""
from __future__ import annotations

import os
from pathlib import Path

# Canonical subject order (people + dogs). Used for stable "people" tagging.
SUBJECTS = ["Clay", "Nicole", "Connor", "Hailey", "Cooper", "Zoa"]
DOGS = {"Cooper", "Zoa"}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}

# Project paths (resolved relative to this file's parent's parent = project root).
ROOT = Path(__file__).resolve().parent.parent
PHOTOS_RAW = ROOT / "photos_raw"
COVERS_DIR = PHOTOS_RAW / "covers"
PHOTOS_PROCESSED = ROOT / "photos_processed"
STORY_DIR = ROOT / "story"
STORY_JSON = STORY_DIR / "story.json"
TEMPLATES_DIR = ROOT / "templates"
ASSETS_DIR = ROOT / "assets"
BUILD_DIR = ROOT / "build"
THUMBS_DIR = BUILD_DIR / "thumbs"
CONTACT_DIR = BUILD_DIR / "contact_sheets"
MANIFEST_JSON = BUILD_DIR / "manifest.json"

# Local Playwright browser cache (kept inside the project so it persists).
PLAYWRIGHT_DIR = ROOT / ".playwright"

# Print spec.
DPI = 300
PAGE_W_IN = 11.0   # landscape Letter
PAGE_H_IN = 8.5


def ensure_dirs() -> None:
    for d in (PHOTOS_PROCESSED, BUILD_DIR, THUMBS_DIR, CONTACT_DIR, STORY_DIR):
        d.mkdir(parents=True, exist_ok=True)


def register_heif() -> None:
    """Enable reading HEIC/HEIF files (iPhone originals)."""
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except Exception:
        pass


def sorted_people(people) -> list[str]:
    """Return people in canonical SUBJECTS order."""
    s = set(people)
    return [p for p in SUBJECTS if p in s]
