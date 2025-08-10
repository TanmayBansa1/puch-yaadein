import re
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..utils import now_iso
from ..validation import validate_memory_fields
from .repository import get_db_connection, fts_upsert, fts_delete


def tool_memory_store(user_scope: str, content: str, tags: Optional[List[str]], context: Optional[str]) -> Dict[str, Any]:
    validate_memory_fields(content, tags, context)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memories (user_scope, content, context, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            user_scope,
            content,
            context or None,
            ",".join(tags) if tags else None,
            now_iso(),
            now_iso(),
        ),
    )
    conn.commit()
    memory_id = cur.lastrowid
    # FTS sync (best-effort)
    fts_upsert(memory_id, content, context, ",".join(tags) if tags else None, user_scope)
    conn.close()
    return {"id": memory_id}


def tool_memory_list(user_scope: str, limit: int, offset: int) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, content, context, tags, created_at, updated_at FROM memories WHERE user_scope = ? ORDER BY id DESC LIMIT ? OFFSET ?",
        (user_scope, limit, offset),
    )
    rows = cur.fetchall()
    conn.close()

    def row_to_dict(r: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": r["id"],
            "content": r["content"],
            "context": r["context"],
            "tags": r["tags"].split(",") if r["tags"] else [],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }

    return {"items": [row_to_dict(r) for r in rows]}


def tool_memory_delete(user_scope: str, memory_id: int) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM memories WHERE id = ? AND user_scope = ?",
        (memory_id, user_scope),
    )
    deleted = cur.rowcount
    conn.commit()
    if deleted:
        fts_delete(memory_id)
    conn.close()
    return {"deleted": deleted}


def tool_memory_update(user_scope: str, memory_id: int, content: Optional[str], tags: Optional[List[str]], context: Optional[str]) -> Dict[str, Any]:
    validate_memory_fields(content, tags, context)
    fields: List[str] = []
    values: List[Any] = []
    if content is not None:
        fields.append("content = ?")
        values.append(content)
    if context is not None:
        fields.append("context = ?")
        values.append(context)
    if tags is not None:
        fields.append("tags = ?")
        values.append(",".join(tags) if tags else None)
    fields.append("updated_at = ?")
    values.append(now_iso())
    if not fields:
        return {"updated": 0}
    values.extend([memory_id, user_scope])
    sql = f"UPDATE memories SET {', '.join(fields)} WHERE id = ? AND user_scope = ?"
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, tuple(values))
    updated = cur.rowcount
    conn.commit()
    if updated:
        # Fetch latest row to sync FTS
        cur.execute("SELECT content, context, tags FROM memories WHERE id = ? AND user_scope = ?", (memory_id, user_scope))
        row = cur.fetchone()
        if row:
            fts_upsert(memory_id, row["content"], row["context"], row["tags"], user_scope)
    conn.close()
    return {"updated": updated}


def _parse_time_hints(query: str) -> Optional[Tuple[str, str]]:
    from datetime import datetime, timedelta

    q = query.lower()
    now = datetime.utcnow()
    if "last week" in q:
        start = (now - timedelta(days=7)).isoformat()
        end = now.isoformat()
        return start, end
    if "yesterday" in q:
        start_dt = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(days=1)
        return start_dt.isoformat(), end_dt.isoformat()
    if "today" in q:
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(days=1)
        return start_dt.isoformat(), end_dt.isoformat()
    return None


def tool_memory_query(user_scope: str, query: str, limit: int) -> Dict[str, Any]:
    time_range = _parse_time_hints(query)
    conn = get_db_connection()
    cur = conn.cursor()
    like = f"%{query}%"
    used_fts = False
    # Prefer FTS when available
    try:
        if time_range:
            start_iso, end_iso = time_range
            cur.execute(
                """
                SELECT m.id, m.content, m.context, m.tags, m.created_at, m.updated_at
                FROM memories m
                JOIN memories_fts f ON f.rowid = m.id
                WHERE m.user_scope = ?
                  AND m.created_at BETWEEN ? AND ?
                  AND f.memories_fts MATCH ?
                ORDER BY m.id DESC LIMIT ?
                """,
                (user_scope, start_iso, end_iso, query, limit),
            )
        else:
            cur.execute(
                """
                SELECT m.id, m.content, m.context, m.tags, m.created_at, m.updated_at
                FROM memories m
                JOIN memories_fts f ON f.rowid = m.id
                WHERE m.user_scope = ? AND f.memories_fts MATCH ?
                ORDER BY m.id DESC LIMIT ?
                """,
                (user_scope, query, limit),
            )
        used_fts = True
    except sqlite3.OperationalError:
        used_fts = False

    if not used_fts:
        if time_range:
            start_iso, end_iso = time_range
            cur.execute(
                """
                SELECT id, content, context, tags, created_at, updated_at
                FROM memories
                WHERE user_scope = ?
                  AND created_at BETWEEN ? AND ?
                  AND (content LIKE ? OR ifnull(context,'') LIKE ? OR ifnull(tags,'') LIKE ?)
                ORDER BY id DESC LIMIT ?
                """,
                (user_scope, start_iso, end_iso, like, like, like, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, content, context, tags, created_at, updated_at
                FROM memories
                WHERE user_scope = ?
                  AND (content LIKE ? OR ifnull(context,'') LIKE ? OR ifnull(tags,'') LIKE ?)
                ORDER BY id DESC LIMIT ?
                """,
                (user_scope, like, like, like, limit),
            )
    rows = cur.fetchall()
    conn.close()

    def row_to_dict(r: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": r["id"],
            "content": r["content"],
            "context": r["context"],
            "tags": r["tags"].split(",") if r["tags"] else [],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }

    return {"items": [row_to_dict(r) for r in rows]}


def _extract_candidates(text: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    lowered = text.strip()

    # Generic "remember that ..." pattern
    m = re.search(r"remember(?:\s+that)?\s+(.*)$", lowered, flags=re.IGNORECASE)
    if m:
        content = m.group(1).strip().rstrip(".")
        if content:
            candidates.append({
                "content": content,
                "tags": ["remember"],
                "context": "general",
                "confidence": 0.8,
            })

    # Favorite X is Y
    m = re.search(r"my\s+favorite\s+([a-zA-Z ]+?)\s+is\s+(.+)$", lowered, flags=re.IGNORECASE)
    if m:
        kind = m.group(1).strip()
        value = m.group(2).strip().rstrip(".")
        candidates.append({
            "content": f"My favorite {kind} is {value}",
            "tags": ["favorite", kind.replace(" ", "_")],
            "context": "preferences",
            "confidence": 0.9,
        })

    # Email detection
    m = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", lowered)
    if m:
        email = m.group(1)
        candidates.append({
            "content": f"My email is {email}",
            "tags": ["contact", "email"],
            "context": "contact",
            "confidence": 0.75,
        })

    # Phone number (very naive)
    m = re.search(r"(\+?\d[\d\-\s]{7,}\d)", lowered)
    if m and len(m.group(1)) <= 20:
        phone = m.group(1)
        candidates.append({
            "content": f"My phone number is {phone}",
            "tags": ["contact", "phone"],
            "context": "contact",
            "confidence": 0.6,
        })

    # Address cue
    if re.search(r"i\s+live\s+in\s+", lowered, flags=re.IGNORECASE):
        after = re.split(r"i\s+live\s+in\s+", lowered, flags=re.IGNORECASE)[-1].strip().rstrip(".")
        if after:
            candidates.append({
                "content": f"I live in {after}",
                "tags": ["address"],
                "context": "profile",
                "confidence": 0.7,
            })

    # Birthday cue (very naive)
    if re.search(r"birthday|bday|dob", lowered, flags=re.IGNORECASE):
        candidates.append({
            "content": text.strip(),
            "tags": ["birthday"],
            "context": "profile",
            "confidence": 0.5,
        })

    # Fallback: if short, treat whole text as candidate with low confidence
    if not candidates and 5 <= len(text) <= 160:
        candidates.append({
            "content": text.strip(),
            "tags": ["note"],
            "context": "general",
            "confidence": 0.4,
        })

    # Ensure fields validate
    pruned: List[Dict[str, Any]] = []
    for c in candidates:
        try:
            validate_memory_fields(c.get("content"), c.get("tags"), c.get("context"))
            pruned.append(c)
        except Exception:
            continue
    return pruned[:5]


def tool_memory_suggest(user_scope: str, text: str) -> Dict[str, Any]:
    items = _extract_candidates(text)
    return {"candidates": items}


# ----- Admin/analytics utilities (moved from tools_extra.py) -----

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
    cur.execute(
        "SELECT substr(created_at,1,10) AS day, COUNT(*) AS c FROM memories WHERE user_scope = ? GROUP BY day ORDER BY day DESC LIMIT 7",
        (user_scope,),
    )
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


