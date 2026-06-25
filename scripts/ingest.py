#!/usr/bin/env python3
"""
Ingest exported People-album photos into a deduped, year-bucketed *index*.

Designed for large libraries (thousands of photos). To stay fast and avoid
writing gigabytes of full-resolution copies, ingest only:
  1. De-duplicates the same file across albums by content hash (md5),
     unioning the "people" tags (who is in each photo).
  2. Reads EXIF capture date (falls back to file mtime).
  3. Analyzes every unique photo IN PARALLEL: dimensions, sharpness, perceptual
     hash, screenshot heuristic.
  4. Merges perceptual near-duplicates (e.g. burst shots), keeping the sharpest.
  5. Writes a JPEG THUMBNAIL per surviving photo (browser-renderable, also for
     HEIC) into build/thumbs/<year>/.
  6. Builds per-year contact sheets (capped for readability) and build/manifest.json.

Full-resolution print JPEGs are produced later, only for chosen photos, by
scripts/materialize.py.

Usage:
    python scripts/ingest.py [--workers N] [--thumb 1100]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
import imagehash

import common
from common import (
    BUILD_DIR, CONTACT_DIR, IMAGE_EXTS, MANIFEST_JSON, PHOTOS_RAW,
    SUBJECTS, THUMBS_DIR, DPI,
)

THUMB_MAX = 1100           # px, long edge of thumbnails (proof quality)
CONTACT_COLS = 6
CONTACT_CELL = 320
CONTACT_CAP = 48           # max thumbnails shown per year on a contact sheet
PHASH_DISTANCE = 3         # <= this hamming distance => near-duplicate (strict)
LOW_RES_MP = 2.0
BLUR_THRESHOLD = 80.0

DOGS = {"Cooper", "Zoa"}


def md5_of_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def exif_date(img: Image.Image, fallback: Path) -> tuple[datetime, bool]:
    """Return (capture_datetime, found_in_exif). Falls back to file mtime."""
    try:
        exif = img.getexif()
        for tag in (36867, 306):
            val = exif.get(tag)
            if val:
                try:
                    return datetime.strptime(str(val)[:19], "%Y:%m:%d %H:%M:%S"), True
                except ValueError:
                    pass
        try:
            ifd = exif.get_ifd(0x8769)
        except Exception:
            ifd = {}
        for tag in (36867, 36868):
            val = ifd.get(tag)
            if val:
                try:
                    return datetime.strptime(str(val)[:19], "%Y:%m:%d %H:%M:%S"), True
                except ValueError:
                    pass
    except Exception:
        pass
    return datetime.fromtimestamp(fallback.stat().st_mtime), False


def laplacian_variance(img: Image.Image) -> float:
    import numpy as np
    g = img.convert("L").resize((256, 256))
    a = np.asarray(g, dtype="float32")
    lap = (-4 * a[1:-1, 1:-1] + a[:-2, 1:-1] + a[2:, 1:-1]
           + a[1:-1, :-2] + a[1:-1, 2:])
    return float(lap.var())


def looks_like_screenshot(path: Path, w: int, h: int) -> bool:
    name = path.name.lower()
    if "screenshot" in name or "screen shot" in name:
        return True
    if path.suffix.lower() == ".png":
        ar = max(w, h) / max(1, min(w, h))
        for target in (19.5 / 9, 16 / 9, 2436 / 1125):
            if abs(ar - target) < 0.04:
                return True
    return False


def _init_worker():
    common.register_heif()


def analyze(args) -> dict:
    """Worker: analyze one unique photo and write its thumbnail."""
    src_str, subjects = args
    src = Path(src_str)
    try:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            dt, has_exif_date = exif_date(im, src)
            ph = str(imagehash.phash(im))
            sharp = laplacian_variance(im)
            thumb = im.convert("RGB")
            thumb.thumbnail((THUMB_MAX, THUMB_MAX))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "src": src_str}

    year = str(dt.year)
    short = src.stem[:18].replace(" ", "_")
    uid = hashlib.md5(src_str.encode()).hexdigest()[:6]
    fname = f"{dt.strftime('%Y-%m-%d')}_{short}_{uid}.jpg"
    rel = f"{year}/{fname}"

    thumb_dir = THUMBS_DIR / year
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb.save(thumb_dir / fname, "JPEG", quality=85)

    flags = []
    mp = (w * h) / 1e6
    if mp < LOW_RES_MP:
        flags.append("low_res")
    if looks_like_screenshot(src, w, h):
        flags.append("screenshot")
    if sharp < BLUR_THRESHOLD:
        flags.append("blurry")
    if not has_exif_date:
        flags.append("no_date")  # year is a guess (fell back to file date)

    return {
        "file": rel,
        "src": str(src),
        "date": dt.strftime("%Y-%m-%d"),
        "people": common.sorted_people(subjects),
        "w": w, "h": h, "megapixels": round(mp, 1),
        "sharpness": round(sharp, 1),
        "phash": ph,
        "flags": flags,
        "max_print_short_edge_in": round(min(w, h) / DPI, 1),
    }


def detect_pool_only(subj_md5: dict) -> set:
    """Flag a mis-exported album that is really the whole library: i.e. it
    contains >=90% of the union of all OTHER albums (so it can't be a real,
    person-specific 'People' album). Such an album is used only as a photo
    pool, never as a people tag."""
    pool_only = set()
    sets = {s: set(d.keys()) for s, d in subj_md5.items()}
    for s in SUBJECTS:
        others = set().union(*[sets[o] for o in SUBJECTS if o != s]) or set()
        if others and len(sets[s] & others) / len(others) >= 0.9 and len(sets[s]) > len(others):
            pool_only.add(s)
    return pool_only


def collect_unique(by_hash: dict) -> tuple[list, set]:
    """photos_raw walk -> {md5: subjects-set, src}. Returns (tasks, pool_only).

    A 'pool_only' album contributes its photos to the pool but is NOT used as a
    people tag (handles the case where the whole library was exported into one
    person's folder by mistake)."""
    subj_md5 = {s: {} for s in SUBJECTS}
    for subject in SUBJECTS:
        folder = PHOTOS_RAW / subject
        if not folder.is_dir():
            continue
        for p in sorted(folder.iterdir()):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                subj_md5[subject][md5_of_file(p)] = p

    pool_only = detect_pool_only(subj_md5)

    # Only ingest photos that belong to at least one REAL (non-pool) album.
    # Photos that exist solely in a pool-only album (the whole-library mis-export)
    # are dropped, since they carry no reliable people signal.
    for subject in SUBJECTS:
        if subject in pool_only:
            continue
        for digest, p in subj_md5[subject].items():
            rec = by_hash.setdefault(digest, {"src": p, "subjects": set()})
            rec["subjects"].add(subject)
    tasks = [(str(r["src"]), sorted(r["subjects"])) for r in by_hash.values()]
    return tasks, pool_only


def merge_near_duplicates(entries: list) -> list:
    """Merge perceptual near-dupes; keep sharpest; union people; delete extra thumbs."""
    buckets: list[dict] = []
    index: dict[str, list] = defaultdict(list)  # coarse bucket by phash prefix
    removed = 0
    for e in entries:
        ph = imagehash.hex_to_hash(e["phash"])
        key = e["phash"][:4]
        match = None
        for cand_key in (key,):
            for b in index[cand_key]:
                if (ph - imagehash.hex_to_hash(b["phash"])) <= PHASH_DISTANCE:
                    match = b
                    break
            if match:
                break
        if match:
            match["people"] = common.sorted_people(set(match["people"]) | set(e["people"]))
            # keep the sharper / higher-res of the two
            keep_new = (e["sharpness"], e["megapixels"]) > (match["sharpness"], match["megapixels"])
            loser = match if keep_new else e
            # remove loser's thumbnail
            tp = THUMBS_DIR / loser["file"]
            try:
                tp.unlink()
            except FileNotFoundError:
                pass
            removed += 1
            if keep_new:
                people = match["people"]
                match.clear()
                match.update(e)
                match["people"] = people
                index[match["phash"][:4]].append(match)
        else:
            buckets.append(e)
            index[key].append(e)
    if removed:
        print(f"  merged {removed} near-duplicate photo(s).")
    return buckets


def build_contact_sheets(by_year: dict) -> None:
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 15)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
    except Exception:
        font = font_sm = ImageFont.load_default()

    for year, items in sorted(by_year.items()):
        # show the most "story-worthy" first: more people, then sharper
        ranked = sorted(items, key=lambda e: (len(e["people"]), e["sharpness"]), reverse=True)
        shown = ranked[:CONTACT_CAP]
        n = len(shown)
        cols = CONTACT_COLS
        rows = max(1, (n + cols - 1) // cols)
        cell, pad, label_h = CONTACT_CELL, 12, 44
        W = cols * cell + pad * (cols + 1)
        H = rows * (cell + label_h) + pad * (rows + 1) + 54
        sheet = Image.new("RGB", (W, H), (244, 240, 232))
        draw = ImageDraw.Draw(sheet)
        title = f"{year}  —  {len(items)} photos"
        if len(items) > CONTACT_CAP:
            title += f"  (showing top {CONTACT_CAP} by people/sharpness)"
        draw.text((pad, 16), title, fill=(60, 50, 45), font=font)

        for i, e in enumerate(shown):
            r, c = divmod(i, cols)
            x = pad + c * (cell + pad)
            y = 54 + pad + r * (cell + label_h + pad)
            tp = THUMBS_DIR / e["file"]
            try:
                with Image.open(tp) as t:
                    t = t.copy()
                    t.thumbnail((cell, cell))
                    sheet.paste(t, (x + (cell - t.width) // 2, y + (cell - t.height) // 2))
            except Exception:
                pass
            initials = "".join(p[0] for p in e["people"]) or "?"
            flag = ("  [" + ",".join(e["flags"]) + "]") if e["flags"] else ""
            draw.text((x, y + cell + 3), f"#{i+1} {e['date']}", fill=(70, 60, 55), font=font_sm)
            draw.text((x, y + cell + 20), f"{initials}{flag}", fill=(120, 80, 60), font=font_sm)

        sheet.save(CONTACT_DIR / f"{year}.jpg", "JPEG", quality=86)
    print(f"  contact sheets: build/contact_sheets/")


def summarize(by_year: dict) -> dict:
    total = sum(len(v) for v in by_year.values())
    flagged, per_person = defaultdict(int), defaultdict(int)
    for items in by_year.values():
        for e in items:
            for f in e["flags"]:
                flagged[f] += 1
            for p in e["people"]:
                per_person[p] += 1
    return {
        "total_photos": total,
        "years": {y: len(v) for y, v in sorted(by_year.items())},
        "flagged": dict(flagged),
        "per_person": dict(per_person),
    }


def main() -> None:
    global THUMB_MAX
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=0, help="0 = auto (cpu count)")
    ap.add_argument("--thumb", type=int, default=THUMB_MAX)
    args = ap.parse_args()
    THUMB_MAX = args.thumb

    common.ensure_dirs()
    common.register_heif()

    # Fresh thumbnails + contact sheets each run.
    for d in (THUMBS_DIR, CONTACT_DIR):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    print("Scanning albums and de-duplicating by content hash...")
    by_hash: dict = {}
    tasks, pool_only = collect_unique(by_hash)
    if not tasks:
        print("No photos found in photos_raw/<Subject>/. See README.md.")
        MANIFEST_JSON.write_text(json.dumps({"years": {}, "summary": {}}, indent=2))
        return
    if pool_only:
        print(f"  NOTE: album(s) {sorted(pool_only)} look like a full-library "
              f"mis-export (they contain ~all other albums). Using them as a photo "
              f"pool only, NOT as a people tag.")
    print(f"{len(tasks)} unique files after exact de-dup. Analyzing in parallel...")

    workers = args.workers or None
    entries, errors = [], []
    done = 0
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as ex:
        futs = [ex.submit(analyze, t) for t in tasks]
        for fut in as_completed(futs):
            res = fut.result()
            done += 1
            if done % 500 == 0:
                print(f"  analyzed {done}/{len(tasks)}")
            if "error" in res:
                errors.append(res)
            else:
                entries.append(res)

    if errors:
        print(f"  {len(errors)} file(s) could not be read (skipped).")

    by_year_pre = defaultdict(list)
    for e in entries:
        by_year_pre[e["file"].split("/")[0]].append(e)

    print("Merging near-duplicates...")
    merged = []
    for year, items in by_year_pre.items():
        merged.extend(merge_near_duplicates(items))

    by_year = defaultdict(list)
    for e in sorted(merged, key=lambda e: e["date"]):
        e.pop("phash", None)
        by_year[e["file"].split("/")[0]].append(e)

    build_contact_sheets(by_year)
    summary = summarize(by_year)
    MANIFEST_JSON.write_text(json.dumps(
        {"years": dict(sorted(by_year.items())), "summary": summary}, indent=2))

    print("\n=== Ingest complete ===")
    print(f"Unique photos indexed: {summary['total_photos']}")
    for y, n in summary["years"].items():
        print(f"   {y}: {n}")
    if summary["flagged"]:
        print("Flagged:", dict(summary["flagged"]))
    print("Appearances by subject:", dict(summary["per_person"]))
    print("Manifest: build/manifest.json  |  Thumbnails: build/thumbs/")


if __name__ == "__main__":
    main()
