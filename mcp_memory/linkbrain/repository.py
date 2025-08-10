import sqlite3
from typing import Optional

from ..config import DB_PATH


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_link_db() -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_scope TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            byline TEXT,
            site_name TEXT,
            tags TEXT,
            content TEXT,
            word_count INTEGER,
            reading_minutes INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_scope, url)
        );
        """
    )
    # Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_links_user_created ON links(user_scope, created_at DESC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_links_user_url ON links(user_scope, url);")

    # FTS virtual table
    try:
        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS links_fts USING fts5(
                title, byline, site_name, tags, content, user_scope, content_rowid=id
            );
            """
        )
        # Backfill FTS
        cur.execute(
            "INSERT INTO links_fts(rowid, title, byline, site_name, tags, content, user_scope)\n"
            "SELECT id, ifnull(title,''), ifnull(byline,''), ifnull(site_name,''), ifnull(tags,''), ifnull(content,''), user_scope FROM links\n"
            "WHERE id NOT IN (SELECT rowid FROM links_fts);"
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()
    # Add optional columns if missing
    try:
        cur.execute("PRAGMA table_info(links)")
        cols = {row[1] for row in cur.fetchall()}
        if "summary" not in cols:
            cur.execute("ALTER TABLE links ADD COLUMN summary TEXT")
        if "summary_updated_at" not in cols:
            cur.execute("ALTER TABLE links ADD COLUMN summary_updated_at TEXT")
        conn.commit()
    except Exception:
        pass
    conn.close()


def fts_link_upsert(rowid: int, title: str, byline: str, site_name: str, tags: str, content: str, user_scope: str) -> None:
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO links_fts(rowid, title, byline, site_name, tags, content, user_scope) VALUES(?,?,?,?,?,?,?)\n"
            "ON CONFLICT(rowid) DO UPDATE SET title=excluded.title, byline=excluded.byline, site_name=excluded.site_name, tags=excluded.tags, content=excluded.content, user_scope=excluded.user_scope",
            (rowid, title or "", byline or "", site_name or "", tags or "", content or "", user_scope),
        )
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass


def fts_link_delete(rowid: int) -> None:
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM links_fts WHERE rowid = ?", (rowid,))
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass


