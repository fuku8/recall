#!/usr/bin/env python3
"""Search memories with FTS5 full-text search."""
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "memory.db"


def build_fts_query(query):
    """Build an FTS5 query that ANDs each whitespace-separated term.

    Quoting each term individually keeps FTS5 from treating it as an operator
    while still producing an AND search. Wrapping the whole query in a single
    pair of quotes makes it a phrase search, which silently returns nothing
    for multi-word input.
    """
    return " AND ".join(
        '"' + term.replace('"', '""') + '"' for term in query.split()
    )


def search(query, limit=10):
    if not DB_PATH.exists():
        print("No memory database found", file=sys.stderr)
        return []
    escaped = build_fts_query(query)
    if not escaped:
        return []
    conn = sqlite3.connect(str(DB_PATH))
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


def selftest():
    """Minimal check for build_fts_query."""
    assert build_fts_query("report") == '"report"'
    assert build_fts_query("report output") == '"report" AND "output"'
    assert build_fts_query("  a   b  ") == '"a" AND "b"'
    assert build_fts_query('say "hi"') == '"say" AND """hi"""'
    assert build_fts_query("") == ""
    print("selftest OK")


def main():
    if len(sys.argv) < 2:
        print("Usage: search_memory.py <query> [limit]", file=sys.stderr)
        sys.exit(1)
    if sys.argv[1] == "--selftest":
        selftest()
        return
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    results = search(query, limit)
    if not results:
        # Don't fail silently - show the query that was actually issued.
        fts = build_fts_query(query) or "(empty)"
        print(f"No memories found. (query: {fts})")
        print("Try fewer terms.", file=sys.stderr)
        return
    print(format_results(results))


if __name__ == "__main__":
    main()
