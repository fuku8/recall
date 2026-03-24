# Recall

Local, zero-dependency long-term memory for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Recall automatically saves your Claude Code conversations to a local SQLite database and injects relevant past memories into each new prompt — giving Claude persistent context across sessions without any external API.

## How it works

```
You type a prompt
       ↓
  [UserPromptSubmit hook]
  Extract keywords → FTS5 search → inject relevant memories
       ↓
  Claude responds with context from past sessions
       ↓
  [Stop hook]
  Save conversation to SQLite
```

- **Keyword extraction** — Pulls English words and CJK terms from your prompt
- **FTS5 full-text search** — Finds relevant past conversations using SQLite's built-in trigram tokenizer
- **Time-decay scoring** — Recent memories rank higher (30-day half-life)
- **Multi-keyword boost** — Messages matching multiple keywords are prioritized
- **Noise filtering** — Slash commands (`/exit`, `/clear`, etc.) are excluded
- **Secret redaction** — API keys, tokens, passwords, and PEM keys are replaced with `[REDACTED]` before saving

## Requirements

- Python 3.10+ (with SQLite FTS5 support — included by default on macOS and most Linux)
- [jq](https://jqlang.github.io/jq/) (for `install.sh` to modify settings.json)
- Claude Code

## Install

```bash
git clone https://github.com/fuku8/recall.git
cd recall
chmod +x install.sh uninstall.sh
./install.sh
```

This will:
1. Add `UserPromptSubmit` and `Stop` hooks to `~/.claude/settings.json`
2. Import all existing Claude Code session logs into the database
3. Set `memory.db` permissions to 600 (owner-only read/write)

## Uninstall

```bash
./uninstall.sh
```

Removes hooks from settings.json. Your `memory.db` is preserved.

To fully remove: `rm -rf /path/to/recall`

## Manual search

```bash
python3 search_memory.py "search query"
python3 search_memory.py "search query" 20  # limit results
```

## Files

| File | Purpose |
|------|---------|
| `inject_memory.py` | UserPromptSubmit hook — searches and injects memories |
| `save_session.py` | Stop hook — saves session to database |
| `search_memory.py` | CLI tool for manual memory search |
| `import_all.py` | Bulk import existing session logs |
| `install.sh` | One-command setup |
| `uninstall.sh` | Clean removal of hooks |
| `memory.db` | SQLite database (auto-created, gitignored) |

## Comparison with claude-subconscious

| | Recall | claude-subconscious |
|---|--------|---------------------|
| Storage | Local SQLite | Letta cloud |
| Dependencies | Python stdlib only | Letta API key |
| Cost | Free | Letta API pricing |
| Privacy | Fully local | Data sent to external server |
| Intelligence | Keyword-based FTS5 | AI-powered memory management |
| Setup | `git clone` + `./install.sh` | Plugin marketplace |

Recall trades AI-powered memory curation for complete privacy and zero cost.

## Security

- **Secret redaction** — Patterns like `sk-*`, `ghp_*`, `xoxb-*`, `AIza*`, `api_key=...`, `token:...`, `password=...`, and PEM private keys are automatically replaced with `[REDACTED]` before being stored in the database
- **File permissions** — `memory.db` is set to 600 (owner-only) during installation
- **Fully local** — No data leaves your machine. No external API calls.

## License

MIT
