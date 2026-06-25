"""Shared constants and helpers for the Story of Us pipeline."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Canonical subject order (people + dogs). Used for stable "people" tagging.
SUBJECTS = ["Clay", "Nicole", "Connor", "Hailey", "Cooper", "Zoa"]
DOGS = {"Cooper", "Zoa"}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}

DEFAULT_VERSION = "v1"

# Project paths (resolved relative to this file's parent's parent = project root).
ROOT = Path(__file__).resolve().parent.parent
PHOTOS_RAW = ROOT / "photos_raw"
COVERS_DIR = PHOTOS_RAW / "covers"
PHOTOS_PROCESSED = ROOT / "photos_processed"
STORY_DIR = ROOT / "story"
TEMPLATES_DIR = ROOT / "templates"
ASSETS_DIR = ROOT / "assets"
VERSIONS_DIR = ROOT / "versions"

# Shared ingest output (manifest, thumbnails — not version-specific).
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

# Active book version (set via set_version() before rendering).
_active: "VersionPaths | None" = None


@dataclass(frozen=True)
class VersionPaths:
    """Per-edition paths under versions/{name}/."""

    name: str
    root: Path
    story_json: Path
    css: Path
    photos: Path
    build: Path
    templates: Path

    @classmethod
    def for_name(cls, name: str) -> "VersionPaths":
        root = VERSIONS_DIR / name
        return cls(
            name=name,
            root=root,
            story_json=root / "story.json",
            css=root / "assets" / "css" / "book.css",
            photos=root / "photos",
            build=root / "build",
            templates=root / "templates",
        )


def set_version(name: str) -> VersionPaths:
    """Select the active book version (v1, v2, …)."""
    global _active
    vp = VersionPaths.for_name(name)
    if not vp.story_json.exists():
        raise FileNotFoundError(
            f"Version {name!r} not found at {vp.root.relative_to(ROOT)}"
        )
    _active = vp
    return vp


def get_version() -> VersionPaths:
    if _active is None:
        return set_version(DEFAULT_VERSION)
    return _active


def list_versions() -> list[str]:
    if not VERSIONS_DIR.exists():
        return []
    return sorted(
        p.name for p in VERSIONS_DIR.iterdir()
        if p.is_dir() and (p / "story.json").exists()
    )


# Legacy aliases — prefer get_version() in version-aware scripts.
STORY_JSON = STORY_DIR / "story.json"


def ensure_dirs(version: str | None = None) -> None:
    for d in (PHOTOS_PROCESSED, BUILD_DIR, THUMBS_DIR, CONTACT_DIR, STORY_DIR):
        d.mkdir(parents=True, exist_ok=True)
    vp = VersionPaths.for_name(version or get_version().name)
    vp.build.mkdir(parents=True, exist_ok=True)
    vp.photos.mkdir(parents=True, exist_ok=True)


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


def resolve_photo(rel: str, version: VersionPaths | None = None) -> Path:
    """Version swap photos → shared library → ingest thumbnails."""
    vp = version or get_version()
    for base in (vp.photos, PHOTOS_PROCESSED, THUMBS_DIR):
        path = base / rel
        if path.exists():
            return path
    return PHOTOS_PROCESSED / rel


def resolve_cover(rel: str, version: VersionPaths | None = None) -> Path:
    """Cast portraits: version photos → photos_raw/covers."""
    vp = version or get_version()
    for base in (vp.photos, PHOTOS_RAW):
        path = base / rel
        if path.exists():
            return path
    return PHOTOS_RAW / rel
