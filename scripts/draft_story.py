#!/usr/bin/env python3
"""
Draft story/story.json from build/manifest.json:
  - selects the best ~N photos per year (favors more people, penalizes
    blurry/low-res, excludes screenshots),
  - orders them by date,
  - assigns layouts (hero / full / pair / collage),
  - writes placeholder captions + year intros for you (and the AI) to refine.

Safety: if story/story.json already exists, writes story/story.draft.json instead
(so your edits are never clobbered). Use --force to overwrite story.json.

Usage:
    python scripts/draft_story.py [--max 7] [--force]
"""
from __future__ import annotations

import argparse
import json

import common
from common import DEFAULT_VERSION, MANIFEST_JSON, STORY_DIR, SUBJECTS, set_version


def natural_join(names: list[str]) -> str:
    names = list(names)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return ", ".join(names[:-1]) + f" & {names[-1]}"


def caption_for(entry: dict) -> str:
    people = entry.get("people", [])
    dogs = [p for p in people if p in ("Cooper", "Zoa")]
    humans = [p for p in people if p not in ("Cooper", "Zoa")]
    if len(humans) >= 4:
        base = "The whole crew"
    elif set(humans) == {"Clay", "Nicole"}:
        base = "Just the two of us"
    elif humans:
        base = natural_join(humans)
    else:
        base = natural_join(dogs) if dogs else "A moment to remember"
    if dogs and len(humans) >= 1:
        base += f" (and {natural_join(dogs)})"
    return base


def score(entry: dict) -> float:
    s = len(entry.get("people", [])) * 2.0
    flags = entry.get("flags", [])
    if "blurry" in flags:
        s -= 2
    if "low_res" in flags:
        s -= 3
    if "screenshot" in flags:
        s -= 100  # effectively exclude
    s += min(entry.get("megapixels", 0), 12) * 0.1
    return s


def assign_layouts(photos: list[dict]) -> list[dict]:
    if not photos:
        return []
    result = []
    photos[0]["layout"] = "full" if len(photos[0]["people"]) >= 4 else "hero"
    result.append(photos[0])
    rest = photos[1:]
    idx, m = 0, len(rest)
    while idx < m:
        remaining = m - idx
        if remaining >= 3:
            take = min(5, remaining)
            if remaining - take == 1 and take > 3:  # avoid a lonely orphan
                take -= 1
            for g in rest[idx:idx + take]:
                g["layout"] = "collage"
            result += rest[idx:idx + take]
            idx += take
        elif remaining == 2:
            rest[idx]["layout"] = rest[idx + 1]["layout"] = "pair"
            result += rest[idx:idx + 2]
            idx += 2
        else:
            rest[idx]["layout"] = "hero"
            result.append(rest[idx])
            idx += 1
    return result


def pick_cover(manifest: dict) -> str | None:
    best, best_score = None, -1.0
    for items in manifest.get("years", {}).values():
        for e in items:
            landscape = e["w"] >= e["h"]
            sc = len(e["people"]) + (1.5 if landscape else 0) + e.get("megapixels", 0) * 0.05
            if "screenshot" in e.get("flags", []):
                continue
            if sc > best_score:
                best, best_score = e["file"], sc
    return best


def build_story(manifest: dict, max_per_year: int) -> dict:
    years_out = []
    for year, items in sorted(manifest.get("years", {}).items()):
        ranked = sorted(items, key=score, reverse=True)
        ranked = [e for e in ranked
                  if "screenshot" not in e.get("flags", []) and e.get("people")]
        chosen = ranked[:max_per_year]
        chosen.sort(key=lambda e: e["date"])
        photos = []
        for e in chosen:
            photos.append({
                "file": e["file"],
                "caption": caption_for(e),
                "people": e["people"],
                "layout": "hero",
                "date": e["date"],
                "_flags": e.get("flags", []),
            })
        photos = assign_layouts(photos)
        for p in photos:
            p.pop("_flags", None)
        years_out.append({
            "year": int(year),
            "title": "",
            "intro": f"(Add a sentence or two about what made {year} special — "
                     f"trips, milestones, the little everyday things.)",
            "photos": photos,
        })

    cast = [{"name": s, "cover": f"covers/{s.lower()}.jpg"} for s in SUBJECTS]
    return {
        "book": {
            "title": "The Story of Us",
            "subtitle": "Clay & Nicole",
            "kicker": "A Birthday Keepsake",
            "dedication": "For Nicole, on your birthday — every page is a thank-you "
                          "for the life we've built together. I love you. — Clay",
            "accent": "terracotta",
            "cover": pick_cover(manifest),
            "cast_title": "Our Little Family",
            "cast_lede": "The people (and pups) who make up our story.",
            "cast": cast,
        },
        "years": years_out,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=7, help="max photos per year")
    ap.add_argument("--force", action="store_true", help="overwrite story.json")
    ap.add_argument("--version", default=DEFAULT_VERSION, help="target version folder")
    args = ap.parse_args()

    vp = set_version(args.version)

    if not MANIFEST_JSON.exists():
        print("No build/manifest.json. Run scripts/ingest.py first.")
        return
    manifest = json.loads(MANIFEST_JSON.read_text())
    if not manifest.get("years"):
        print("Manifest has no photos yet. Export photos and run ingest first.")
        return

    story = build_story(manifest, args.max)
    STORY_DIR.mkdir(parents=True, exist_ok=True)
    target = vp.story_json if (args.force or not vp.story_json.exists()) else vp.root / "story.draft.json"
    target.write_text(json.dumps(story, indent=2, ensure_ascii=False))

    total = sum(len(y["photos"]) for y in story["years"])
    print(f"Drafted {total} photos across {len(story['years'])} years -> "
          f"{target.relative_to(common.ROOT)}")
    if target != vp.story_json:
        print(f"(versions/{vp.name}/story.json already exists; wrote a draft alongside it. "
              "Use --force to overwrite.)")


if __name__ == "__main__":
    main()
