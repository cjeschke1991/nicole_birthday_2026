#!/usr/bin/env bash
# Build the book: ingest photos -> draft story (only if missing) -> render PDFs.
# Re-runnable and safe: it will NOT overwrite your edited story/story.json.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"

echo "==> [1/4] Ingesting photos (index + thumbnails)"
python scripts/ingest.py

if [ ! -f story/story.json ]; then
  echo "==> [2/4] Drafting story/story.json (first run)"
  python scripts/draft_story.py
else
  echo "==> [2/4] story/story.json already exists — keeping your edits."
  echo "        (To regenerate from scratch: python scripts/draft_story.py --force)"
fi

echo "==> [3/4] Materializing full-resolution prints for chosen photos"
python scripts/materialize.py

echo "==> [4/4] Rendering PDFs"
python scripts/render.py

echo "==> Done. See build/Story_of_Us_home.pdf and build/Story_of_Us_shop.pdf"
