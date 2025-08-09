import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List

from .db import get_db_connection


def tool_memory_export(user_scope: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, content, context, tags, created_at, updated_at FROM memories WHERE user_scope = ? ORDER BY id ASC",
        (user_scope,),
    )
    rows = cur.fetchall()
    conn.close()
    export = [
        {
            "id": r["id"],
            "content": r["content"],
            "context": r["context"],
            "tags": r["tags"].split(",") if r["tags"] else [],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]
    return {"json": json.dumps(export, ensure_ascii=False)}


def tool_memory_stats(user_scope: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM memories WHERE user_scope = ?", (user_scope,))
    total = int(cur.fetchone()["c"])
    cur.execute("SELECT substr(created_at,1,10) AS day, COUNT(*) AS c FROM memories WHERE user_scope = ? GROUP BY day ORDER BY day DESC LIMIT 7", (user_scope,))
    per_day = [{"day": r["day"], "count": int(r["c"])} for r in cur.fetchall()]
    conn.close()
    return {"total": total, "per_day": per_day}


def tool_memory_context(user_scope: str, context: str, limit: int = 20) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, content, context, tags, created_at, updated_at
        FROM memories
        WHERE user_scope = ? AND (ifnull(context,'') LIKE ? OR ifnull(tags,'') LIKE ?)
        ORDER BY id DESC LIMIT ?
        """,
        (user_scope, f"%{context}%", f"%{context}%", limit),
    )
    rows = cur.fetchall()
    conn.close()
    items = [
        {
            "id": r["id"],
            "content": r["content"],
            "context": r["context"],
            "tags": r["tags"].split(",") if r["tags"] else [],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]
    return {"items": items}


def tool_memory_summary(user_scope: str, range_hint: str = "last_week") -> Dict[str, Any]:
    now = datetime.utcnow()
    if range_hint == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_hint == "yesterday":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now - timedelta(days=7)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, content, context, tags, created_at FROM memories WHERE user_scope = ? AND created_at >= ? ORDER BY id DESC LIMIT 100",
        (user_scope, start.isoformat()),
    )
    rows = cur.fetchall()
    conn.close()
    # Heuristic summary: top tags and a few highlights
    tags_counter: Dict[str, int] = {}
    highlights: List[str] = []
    for r in rows:
        tags = r["tags"].split(",") if r["tags"] else []
        for t in tags:
            if t:
                tags_counter[t] = tags_counter.get(t, 0) + 1
        if len(highlights) < 5:
            highlights.append(r["content"]) 
    top_tags = sorted(tags_counter.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "count": len(rows),
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
        "highlights": highlights,
    }


