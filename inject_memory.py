#!/usr/bin/env python3
"""UserPromptSubmit hook: extract keywords from prompt, search FTS5, inject context."""
import json
import re
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "memory.db"

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "that",
    "this", "it", "not", "but", "and", "or", "if", "then", "so",
    "what", "how", "when", "where", "who", "which", "there", "here",
}

MAX_RESULTS = 5
MAX_SNIPPET_LEN = 300


def extract_keywords(prompt: str) -> list[str]:
    tokens = re.findall(r'[a-zA-Z][a-zA-Z0-9_.-]{1,}', prompt)
    tokens += re.findall(r'[\u4e00-\u9fff]{2,}|[\u30a1-\u30f4\u30fc]{2,}', prompt)
    keywords = []
    seen = set()
    for t in tokens:
        low = t.lower()
        if low not in STOP_WORDS and low not in seen:
            seen.add(low)
            keywords.append(t)
    return keywords[:10]


def search_memories(keywords: list[str], limit: int = MAX_RESULTS) -> list[dict]:
    if not DB_PATH.exists() or not keywords:
        return []

    conn = sqlite3.connect(str(DB_PATH))
    all_results = {}

    for kw in keywords:
        escaped = '"' + kw.replace('"', '""') + '"'
        try:
            rows = conn.execute("""
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
            """, (escaped, limit * 2)).fetchall()
        except sqlite3.OperationalError:
            continue

        for row in rows:
            mid = row[0]
            if mid not in all_results:
                all_results[mid] = {
                    "id": mid,
                    "session_id": row[1],
                    "role": row[2],
                    "content": row[3],
                    "timestamp": row[4],
                    "project": row[5],
                    "score": row[6],
                    "hit_count": 0,
                }
            all_results[mid]["hit_count"] += 1
            all_results[mid]["score"] += row[6]

    conn.close()

    ranked = sorted(
        all_results.values(),
        key=lambda r: r["hit_count"] * abs(r["score"]),
        reverse=True,
    )
    return ranked[:limit]


def format_context(results: list[dict]) -> str:
    if not results:
        return ""

    lines = ["[Recalled memories]"]
    for r in results:
        snippet = r["content"][:MAX_SNIPPET_LEN]
        if len(r["content"]) > MAX_SNIPPET_LEN:
            snippet += "..."
        date_str = r["timestamp"][:10] if r["timestamp"] else "unknown"
        lines.append(f"- [{date_str}] ({r['role']}) {snippet}")
    return "\n".join(lines)


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    prompt = hook_input.get("prompt", "")
    if not prompt:
        sys.exit(0)

    keywords = extract_keywords(prompt)
    if not keywords:
        sys.exit(0)

    results = search_memories(keywords)
    context = format_context(results)
    if not context:
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
