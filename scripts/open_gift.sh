#!/usr/bin/env bash
# Open the Nicole birthday photo book PDF for a given version.
# Usage: open_gift.sh v1|v2
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="${1:-v1}"
PDF="$ROOT/versions/$VER/build/Story_of_Us_home.pdf"
VER_ROOT="$ROOT/versions/$VER"

needs_rebuild() {
  local f newest="$PDF"
  for f in "$VER_ROOT/story.json" "$VER_ROOT/assets/css/book.css" \
           "$ROOT/scripts/scatter_recipes.json" "$VER_ROOT/caption_positions.json" \
           "$VER_ROOT"/assets/clipart/*; do
    [[ -e "$f" ]] || continue
    if [[ "$f" -nt "$newest" ]]; then
      return 0
    fi
  done
  return 1
}

if [[ ! -f "$PDF" ]] || needs_rebuild; then
  if [[ -f "$PDF" ]]; then
    echo "==> Rebuilding $VER PDF (assets newer than PDF)..."
  else
    echo "==> PDF not found; rendering $VER..."
  fi
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  export PLAYWRIGHT_BROWSERS_PATH="$ROOT/.playwright"
  python "$ROOT/scripts/render.py" --version "$VER"
fi

open "$PDF"
