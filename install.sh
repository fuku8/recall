#!/usr/bin/env bash
set -euo pipefail

RECALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"

echo "=== Recall installer ==="
echo "Install dir: $RECALL_DIR"

# --- Prerequisites ---
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required" >&2
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "Error: jq is required (brew install jq / apt install jq)" >&2
  exit 1
fi

if ! python3 -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE VIRTUAL TABLE t USING fts5(x)')" 2>/dev/null; then
  echo "Error: SQLite FTS5 is not available in your Python" >&2
  exit 1
fi

# --- Add hooks to settings.json ---
echo ""
echo "Configuring Claude Code hooks..."

if [ ! -f "$SETTINGS" ]; then
  echo "Error: $SETTINGS not found. Is Claude Code installed?" >&2
  exit 1
fi

cp "$SETTINGS" "$SETTINGS.bak"
echo "  Backup: $SETTINGS.bak"

if jq -e '.hooks' "$SETTINGS" &>/dev/null; then
  if jq -e '.hooks.UserPromptSubmit' "$SETTINGS" &>/dev/null; then
    echo "  UserPromptSubmit hook already exists, skipping"
  else
    jq --arg cmd "python3 $RECALL_DIR/inject_memory.py" \
      '.hooks.UserPromptSubmit = [{"matcher": "", "hooks": [{"type": "command", "command": $cmd, "timeout": 3000}]}]' \
      "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
    echo "  Added UserPromptSubmit hook"
  fi

  if jq -e '.hooks.Stop' "$SETTINGS" &>/dev/null; then
    echo "  Stop hook already exists, skipping"
  else
    jq --arg cmd "python3 $RECALL_DIR/save_session.py" \
      '.hooks.Stop = [{"matcher": "", "hooks": [{"type": "command", "command": $cmd}]}]' \
      "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
    echo "  Added Stop hook"
  fi
else
  jq --arg inject "python3 $RECALL_DIR/inject_memory.py" \
     --arg save "python3 $RECALL_DIR/save_session.py" \
    '.hooks = {
      "UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": $inject, "timeout": 3000}]}],
      "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": $save}]}]
    }' "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
  echo "  Added hooks section"
fi

# --- Import existing sessions ---
echo ""
echo "Importing existing session logs..."
cd "$RECALL_DIR"
python3 import_all.py

echo ""
echo "=== Installation complete ==="
echo ""
echo "Recall is now active. Your next Claude Code session will automatically:"
echo "  - Inject relevant past memories on each prompt"
echo "  - Save conversations when the session ends"
echo ""
echo "Manual search: python3 $RECALL_DIR/search_memory.py \"query\""
echo "Uninstall:     $RECALL_DIR/uninstall.sh"
