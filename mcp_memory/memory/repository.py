import sqlite3
from typing import Optional

from ..config import DB_PATH


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_scope TEXT NOT NULL,
            content TEXT NOT NULL,
            context TEXT,
            tags TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    # Helpful indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_created ON memories(user_scope, created_at DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_scope, id DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_tags ON memories(user_scope, tags);")

    # Try to set up FTS5 for better search (if available)
    try:
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content, context, tags, user_scope, content_rowid=id
            );
            """
        )
        # Backfill FTS from base table
        cursor.execute("INSERT INTO memories_fts(rowid, content, context, tags, user_scope) SELECT id, content, ifnull(context,''), ifnull(tags,''), user_scope FROM memories WHERE id NOT IN (SELECT rowid FROM memories_fts);")
    except sqlite3.OperationalError:
        # FTS5 not available in this SQLite build; continue without it
        pass
    connection.commit()
    connection.close()


def fts_upsert(rowid: int, content: str, context: str | None, tags: str | None, user_scope: str) -> None:
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO memories_fts(rowid, content, context, tags, user_scope) VALUES(?,?,?,?,?) ON CONFLICT(rowid) DO UPDATE SET content=excluded.content, context=excluded.context, tags=excluded.tags, user_scope=excluded.user_scope",
            (rowid, content, context or "", tags or "", user_scope),
        )
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        # FTS not enabled; ignore
        pass


def fts_delete(rowid: int) -> None:
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM memories_fts WHERE rowid = ?", (rowid,))
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass


