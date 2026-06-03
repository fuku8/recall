#!/usr/bin/env python3
"""Save Claude Code session conversations to SQLite FTS5."""
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "memory.db"
PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Redact secrets before saving to database
SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|apikey)\s*[=:]\s*\S+'),
    re.compile(r'(?i)(secret|token|password|passwd|pwd)\s*[=:]\s*\S+'),
    re.compile(r'(?i)(authorization|bearer)\s*[=:]\s*\S+'),
    re.compile(r'sk-[a-zA-Z0-9_-]{20,}'),          # OpenAI/Anthropic style keys
    re.compile(r'ghp_[a-zA-Z0-9]{36,}'),            # GitHub PAT
    re.compile(r'gho_[a-zA-Z0-9]{36,}'),            # GitHub OAuth
    re.compile(r'xoxb-[a-zA-Z0-9-]+'),              # Slack bot token
    re.compile(r'xoxp-[a-zA-Z0-9-]+'),              # Slack user token
    re.compile(r'AIza[a-zA-Z0-9_-]{35}'),           # Google API key
    re.compile(r'-----BEGIN\s+(RSA\s+)?PRIVATE KEY-----[\s\S]*?-----END'),
]


def redact_secrets(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub('[REDACTED]', text)
    return text


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            project TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content,
            role,
            project,
            content=memories,
            content_rowid=id,
            tokenize='trigram'
        )
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, role, project)
            VALUES (new.id, new.content, new.role, new.project);
        END
    """)
    conn.commit()


def get_session_from_stdin():
    """Read session info from Stop hook stdin JSON (transcript_path + session_id)."""
    try:
        data = json.loads(sys.stdin.read())
        session_id = data.get("session_id", "")
        transcript_path = data.get("transcript_path", "")
        if not transcript_path:
            return None, None, None
        filepath = Path(transcript_path).expanduser()
        if not filepath.exists():
            return None, None, None
        if not session_id:
            session_id = filepath.stem
        project = ""
        parts = filepath.parts
        idx = parts.index("projects") if "projects" in parts else -1
        if idx >= 0 and idx + 1 < len(parts):
            project = parts[idx + 1]
        return filepath, session_id, project
    except (json.JSONDecodeError, ValueError, OSError):
        return None, None, None


def find_latest_session():
    """Fallback: find the most recently modified session JSONL (deprecated)."""
    jsonl_files = list(PROJECTS_DIR.rglob("*.jsonl"))
    if not jsonl_files:
        return None, None, None
    latest = max(jsonl_files, key=lambda f: f.stat().st_mtime)
    session_id = latest.stem
    project = ""
    parts = latest.parts
    idx = parts.index("projects") if "projects" in parts else -1
    if idx >= 0 and idx + 1 < len(parts):
        project = parts[idx + 1]
    return latest, session_id, project


def parse_session(filepath):
    messages = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry_type = entry.get("type", "")
            if entry_type not in ("user", "assistant"):
                continue
            role = entry_type
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, list):
                texts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        texts.append(block)
                content = "\n".join(texts)
            if not content or len(content) < 10:
                continue
            if content.strip().startswith("<command-name>/"):
                continue
            content = redact_secrets(content)
            ts = entry.get("timestamp", datetime.now(timezone.utc).isoformat())
            messages.append({"role": role, "content": content, "timestamp": ts})
    return messages


def save_messages(conn, session_id, project, messages):
    cur = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE session_id = ?", (session_id,)
    )
    if cur.fetchone()[0] > 0:
        return 0
    count = 0
    for msg in messages:
        conn.execute(
            "INSERT INTO memories (session_id, role, content, timestamp, project) VALUES (?, ?, ?, ?, ?)",
            (session_id, msg["role"], msg["content"], msg["timestamp"], project),
        )
        count += 1
    conn.commit()
    return count


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)
    # Prefer stdin-provided transcript_path from Stop hook
    filepath, session_id, project = get_session_from_stdin()
    if filepath is None:
        # Fallback for environments where stdin is unavailable
        filepath, session_id, project = find_latest_session()
    if filepath is None:
        print("No session logs found", file=sys.stderr)
        conn.close()
        return
    messages = parse_session(filepath)
    if not messages:
        print(f"No messages in session {session_id}", file=sys.stderr)
        conn.close()
        return
    count = save_messages(conn, session_id, project, messages)
    print(f"Saved {count} messages from session {session_id}")
    conn.close()


if __name__ == "__main__":
    main()
