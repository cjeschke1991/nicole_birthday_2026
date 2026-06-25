# Book Versions

Each folder here is a **fully independent edition** of the photo book.

| Version | Description |
|---------|-------------|
| **v1** | Warm editorial — finished gift version (frozen baseline) |
| **v2** | Experimental redesign — starts as an exact copy of v1 |

## Folder layout (per version)

```
versions/v1/
├── story.json              # captions, photo picks, year intros
├── assets/css/book.css     # visual design
├── photos/                 # version-specific swap images
│   └── covers/             # cast portraits + hand-picked replacements
└── build/                  # generated PDFs, HTML, previews
    ├── Story_of_Us_home.pdf
    └── preview/
```

## Commands

```bash
# Build / view v1 (default)
python scripts/render.py --version v1
open versions/v1/build/Story_of_Us_home.pdf

# Work on v2
python scripts/render.py --version v2
open versions/v2/build/Story_of_Us_home.pdf

# Full pipeline for one version
bash scripts/build_book.sh v2

# Open from anywhere in Terminal (aliases in ~/.zshrc)
nicole_gift_v1
nicole_gift_v2
```

## What's shared vs. independent

| Shared (one copy) | Per-version |
|---|---|
| `photos_raw/` iCloud exports | `story.json` |
| `photos_processed/` library | `assets/css/book.css` |
| `build/manifest.json` from ingest | `photos/` swap images |
| `scripts/`, `templates/` | `build/` PDFs & previews |

Photo lookup order: **version `photos/`** → shared `photos_processed/` → `build/thumbs/`.
