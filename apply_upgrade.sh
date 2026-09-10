#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-$PWD}"

if [[ ! -f "$TARGET/pyproject.toml" || ! -d "$TARGET/src/bart_spine_ui" ]]; then
  echo "Target is not a spinerobot_ui repository root: $TARGET" >&2
  echo "Usage: ./apply_upgrade.sh /path/to/bart_spine_ui" >&2
  exit 1
fi

if [[ "$SCRIPT_DIR" == "$(cd "$TARGET" && pwd)" ]]; then
  echo "Upgrade files are already extracted in the repository root."
  exit 0
fi

cp -a "$SCRIPT_DIR/src/." "$TARGET/src/"
cp -a "$SCRIPT_DIR/tests/." "$TARGET/tests/"
echo "Planning upgrade copied to $TARGET"
echo "Next: source .venv/bin/activate && pip install -e . && bart-spine-ui"
