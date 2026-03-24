#!/usr/bin/env python3
"""Search memories with FTS5 full-text search."""
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "memory.db"


def search(query, limit=10):
    if not DB_PATH.exists():
        print("No memory database found", file=sys.stderr)
        return []
    conn = sqlite3.connect(str(DB_PATH))
    escaped = '"' + query.replace('"', '""') + '"'
    results = conn.execute("""
        SELECT
            m.id,
            m.session_id,
            m.role,
            m.content,
            m.timestamp,
            m.project,
            memories_fts.rank AS fts_rank
        FROM memories_fts
        JOIN memories m ON m.id = memories_fts.rowid
        WHERE memories_fts MATCH ?
        ORDER BY (
            memories_fts.rank
            * (1.0 / (1.0 + (julianday('now') - julianday(m.timestamp)) / 30.0))
        )
        LIMIT ?
    """, (escaped, limit)).fetchall()
    conn.close()
    return results


def format_results(results):
    if not results:
        return "No memories found."
    output = []
    for r in results:
        role, content, ts = r[2], r[3], r[4]
        snippet = content[:500] + "..." if len(content) > 500 else content
        date_str = ts[:10] if ts else "unknown"
        output.append(f"[{date_str}] ({role}) {snippet}")
    return "\n---\n".join(output)


def main():
    if len(sys.argv) < 2:
        print("Usage: search_memory.py <query> [limit]", file=sys.stderr)
        sys.exit(1)
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    results = search(query, limit)
    print(format_results(results))


if __name__ == "__main__":
    main()
