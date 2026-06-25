#!/usr/bin/env bash
# Build the book: ingest photos -> materialize -> render PDFs for one version.
# Re-runnable and safe: it will NOT overwrite your edited story.json.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"

VERSION="${1:-v1}"
STORY="versions/${VERSION}/story.json"

echo "==> Building version: ${VERSION}"

echo "==> [1/3] Ingesting photos (index + thumbnails)"
python scripts/ingest.py

if [ ! -f "${STORY}" ]; then
  echo "ERROR: ${STORY} not found."
  exit 1
fi

echo "==> [2/3] Materializing full-resolution prints for chosen photos"
python scripts/materialize.py --version "${VERSION}"

echo "==> [3/3] Rendering PDFs"
python scripts/render.py --version "${VERSION}"

echo "==> Done. Open versions/${VERSION}/build/Story_of_Us_home.pdf"
