#!/usr/bin/env python3
"""Bulk import all existing Claude Code session logs."""
import sqlite3
from pathlib import Path
from save_session import init_db, parse_session, save_messages, DB_PATH

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)
    total = 0
    jsonl_files = sorted(PROJECTS_DIR.rglob("*.jsonl"), key=lambda f: f.stat().st_mtime)
    for filepath in jsonl_files:
        session_id = filepath.stem
        project = ""
        parts = filepath.parts
        idx = parts.index("projects") if "projects" in parts else -1
        if idx >= 0 and idx + 1 < len(parts):
            project = parts[idx + 1]
        messages = parse_session(filepath)
        if messages:
            count = save_messages(conn, session_id, project, messages)
            if count > 0:
                total += count
                print(f"  {session_id}: {count} messages")
    print(f"\nTotal: {total} messages imported")
    conn.close()


if __name__ == "__main__":
    main()
