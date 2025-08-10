from typing import Any, Dict, List, Optional

from ..utils import now_iso
from .repository import (
    get_db_connection,
    fts_link_upsert,
    fts_link_delete,
)
from .parsing import fetch_html, extract_readable_fields, tags_to_str, count_words, estimate_reading_minutes



def tool_link_save(user_scope: str, url: str, tags: Optional[List[str]], title_hint: Optional[str]) -> Dict[str, Any]:
    if not url or not isinstance(url, str):
        raise ValueError("url is required")
    html = fetch_html(url)
    extracted = extract_readable_fields(html, url)
    title = title_hint or extracted["title"]
    content = extracted["content"] or ""
    word_count = count_words(content)
    reading_minutes = estimate_reading_minutes(word_count)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO links (user_scope, url, title, byline, site_name, tags, content, word_count, reading_minutes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_scope, url) DO UPDATE SET
            title=excluded.title,
            byline=excluded.byline,
            site_name=excluded.site_name,
            tags=excluded.tags,
            content=excluded.content,
            word_count=excluded.word_count,
            reading_minutes=excluded.reading_minutes,
            updated_at=excluded.updated_at
        """,
        (
            user_scope,
            url,
            title,
            extracted["byline"],
            extracted["site_name"],
            tags_to_str(tags),
            content,
            word_count,
            reading_minutes,
            now_iso(),
            now_iso(),
        ),
    )
    conn.commit()
    cur.execute("SELECT id FROM links WHERE user_scope = ? AND url = ?", (user_scope, url))
    row = cur.fetchone()
    if row:
        fts_link_upsert(
            row["id"],
            title or "",
            extracted["byline"] or "",
            extracted["site_name"] or "",
            tags_to_str(tags) or "",
            content or "",
            user_scope,
        )
    conn.close()
    return {
        "id": row["id"] if row else None,
        "url": url,
        "title": title,
        "byline": extracted["byline"],
        "site_name": extracted["site_name"],
        "word_count": word_count,
        "reading_minutes": reading_minutes,
    }


def tool_link_fetch(user_scope: str, url: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, url, title, byline, site_name, tags, content, word_count, reading_minutes, created_at, updated_at, summary, summary_updated_at FROM links WHERE user_scope = ? AND url = ?",
        (user_scope, url),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"found": False}
    return {
        "found": True,
        "id": row["id"],
        "url": row["url"],
        "title": row["title"],
        "byline": row["byline"],
        "site_name": row["site_name"],
        "tags": row["tags"].split(",") if row["tags"] else [],
        "content": row["content"],
        "word_count": row["word_count"],
        "reading_minutes": row["reading_minutes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "summary": row["summary"],
        "summary_updated_at": row["summary_updated_at"],
    }


def tool_link_list(user_scope: str, limit: int, offset: int, tag: Optional[str]) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    if tag:
        cur.execute(
            "SELECT id, url, title, byline, site_name, tags, word_count, reading_minutes, created_at, updated_at FROM links WHERE user_scope = ? AND ifnull(tags,'') LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_scope, f"%{tag}%", limit, offset),
        )
    else:
        cur.execute(
            "SELECT id, url, title, byline, site_name, tags, word_count, reading_minutes, created_at, updated_at FROM links WHERE user_scope = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_scope, limit, offset),
        )
    rows = cur.fetchall()
    conn.close()
    items = [
        {
            "id": r["id"],
            "url": r["url"],
            "title": r["title"],
            "byline": r["byline"],
            "site_name": r["site_name"],
            "tags": r["tags"].split(",") if r["tags"] else [],
            "word_count": r["word_count"],
            "reading_minutes": r["reading_minutes"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]
    return {"items": items}


def tool_link_query(user_scope: str, query: str, limit: int) -> Dict[str, Any]:
    import sqlite3 as _sqlite3

    conn = get_db_connection()
    cur = conn.cursor()
    used_fts = False
    try:
        cur.execute(
            """
            SELECT l.id, l.url, l.title, l.byline, l.site_name, l.tags, l.word_count, l.reading_minutes, l.created_at, l.updated_at
            FROM links l JOIN links_fts f ON f.rowid = l.id
            WHERE l.user_scope = ? AND f.links_fts MATCH ?
            ORDER BY l.id DESC LIMIT ?
            """,
            (user_scope, query, limit),
        )
        used_fts = True
    except _sqlite3.OperationalError:
        used_fts = False
    if not used_fts:
        cur.execute(
            """
            SELECT id, url, title, byline, site_name, tags, word_count, reading_minutes, created_at, updated_at
            FROM links
            WHERE user_scope = ? AND (
                ifnull(title,'') LIKE ? OR ifnull(byline,'') LIKE ? OR ifnull(site_name,'') LIKE ? OR ifnull(tags,'') LIKE ? OR ifnull(content,'') LIKE ?
            )
            ORDER BY id DESC LIMIT ?
            """,
            (user_scope, *(f"%{query}%",) * 5, limit),
        )
    rows = cur.fetchall()
    conn.close()
    items = [
        {
            "id": r["id"],
            "url": r["url"],
            "title": r["title"],
            "byline": r["byline"],
            "site_name": r["site_name"],
            "tags": r["tags"].split(",") if r["tags"] else [],
            "word_count": r["word_count"],
            "reading_minutes": r["reading_minutes"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]
    return {"items": items}


def tool_link_delete(user_scope: str, link_id: int) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM links WHERE id = ? AND user_scope = ?", (link_id, user_scope))
    deleted = cur.rowcount
    conn.commit()
    if deleted:
        fts_link_delete(link_id)
    conn.close()
    return {"deleted": deleted}


def tool_link_summarize(user_scope: str, url: str, style: Optional[str]) -> Dict[str, Any]:
    """Prepare cleaned article content for LLM summarization.

    Returns metadata and full cleaned text. The client/LLM should create a
    summary and then persist it via link_store_summary.
    """
    record = tool_link_fetch(user_scope, url)
    if not record.get("found"):
        _ = tool_link_save(user_scope, url, tags=None, title_hint=None)
        record = tool_link_fetch(user_scope, url)
        if not record.get("found"):
            return {"ok": False, "reason": "unable_to_fetch"}

    return {
        "ok": True,
        "url": record.get("url"),
        "title": record.get("title"),
        "byline": record.get("byline"),
        "site_name": record.get("site_name"),
        "content": record.get("content") or "",
        "reading_minutes": record.get("reading_minutes"),
        "word_count": record.get("word_count"),
        "style": style,
    }


def tool_link_store_summary(user_scope: str, url: str, summary_text: str) -> Dict[str, Any]:
    if not summary_text or not summary_text.strip():
        return {"saved": 0}
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE links SET summary = ?, summary_updated_at = ? WHERE user_scope = ? AND url = ?",
        (summary_text.strip(), now_iso(), user_scope, url),
    )
    saved = cur.rowcount
    conn.commit()
    conn.close()
    return {"saved": saved}


def tool_link_get_summary(user_scope: str, url: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, url, title, byline, site_name, summary, summary_updated_at FROM links WHERE user_scope = ? AND url = ?",
        (user_scope, url),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"found": False}
    return {
        "found": True,
        "id": row["id"],
        "url": row["url"],
        "title": row["title"],
        "byline": row["byline"],
        "site_name": row["site_name"],
        "summary": row["summary"],
        "summary_updated_at": row["summary_updated_at"],
    }


def tool_link_digest(user_scope: str, limit: int = 5, tag: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    if tag:
        cur.execute(
            """
            SELECT id, url, title, byline, site_name, summary, summary_updated_at, updated_at
            FROM links
            WHERE user_scope = ? AND ifnull(tags,'') LIKE ? AND ifnull(summary,'') != ''
            ORDER BY datetime(summary_updated_at) DESC, datetime(updated_at) DESC
            LIMIT ?
            """,
            (user_scope, f"%{tag}%", limit),
        )
    else:
        cur.execute(
            """
            SELECT id, url, title, byline, site_name, summary, summary_updated_at, updated_at
            FROM links
            WHERE user_scope = ? AND ifnull(summary,'') != ''
            ORDER BY datetime(summary_updated_at) DESC, datetime(updated_at) DESC
            LIMIT ?
            """,
            (user_scope, limit),
        )
    rows = cur.fetchall()
    conn.close()
    items = [
        {
            "id": r["id"],
            "url": r["url"],
            "title": r["title"],
            "byline": r["byline"],
            "site_name": r["site_name"],
            "summary": r["summary"],
            "summary_updated_at": r["summary_updated_at"],
        }
        for r in rows
    ]
    return {"items": items}


