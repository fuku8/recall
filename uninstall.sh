#!/usr/bin/env bash
set -euo pipefail

RECALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"

echo "=== Recall uninstaller ==="

if [ ! -f "$SETTINGS" ]; then
  echo "No settings.json found, nothing to do."
  exit 0
fi

if ! command -v jq &>/dev/null; then
  echo "Error: jq is required to modify settings" >&2
  exit 1
fi

cp "$SETTINGS" "$SETTINGS.bak"

jq --arg dir "$RECALL_DIR" '
  if .hooks then
    .hooks |= with_entries(
      .value |= map(
        .hooks |= map(select(.command | test($dir) | not))
      ) |
      map(select(.hooks | length > 0))
    ) |
    if .hooks | to_entries | length == 0 then del(.hooks) else . end
  else . end
' "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"

echo "Hooks removed from settings.json"
echo ""
echo "Note: memory.db is preserved at $RECALL_DIR/memory.db"
echo "To fully remove: rm -rf $RECALL_DIR"
