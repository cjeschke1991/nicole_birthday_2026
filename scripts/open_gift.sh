#!/usr/bin/env bash
# Open the Nicole birthday photo book PDF for a given version.
# Usage: open_gift.sh v1|v2
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="${1:-v1}"
PDF="$ROOT/versions/$VER/build/Story_of_Us_home.pdf"

if [[ ! -f "$PDF" ]]; then
  echo "PDF not found: $PDF" >&2
  echo "Build it first: bash $ROOT/scripts/build_book.sh $VER" >&2
  exit 1
fi

open "$PDF"
