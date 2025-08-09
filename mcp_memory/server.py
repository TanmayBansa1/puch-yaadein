import os
import json
import re
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

AUTH_TOKEN = os.getenv("AUTH_TOKEN")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8086"))
DB_PATH = os.getenv("DB_PATH", "./memory.db")

if not AUTH_TOKEN:
    raise RuntimeError("AUTH_TOKEN must be set in environment (.env)")

app = FastAPI(title="Memory-Plus MCP Server", version="0.1.0")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ------------------------------
# Database helpers
# ------------------------------

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
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
    conn.commit()
    conn.close()


init_db()

# ------------------------------
# Auth
# ------------------------------

def ensure_bearer_auth(authorization: Optional[str]) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


# ------------------------------
# JSON-RPC models
# ------------------------------

class JsonRpcRequest(BaseModel):
    jsonrpc: str
    method: str
    id: Optional[Any] = None
    params: Optional[Dict[str, Any]] = None


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


# ------------------------------
# Tool registry and helpers
# ------------------------------

ToolSpec = Dict[str, Any]

def get_user_scope(header_user_id: Optional[str], params: Optional[Dict[str, Any]]) -> str:
    if header_user_id and header_user_id.strip():
        return header_user_id.strip()
    if params and isinstance(params.get("user"), str) and params["user"].strip():
        return params["user"].strip()
    return "default"


def now_iso() -> str:
    return datetime.utcnow().isoformat()


# ------------------------------
# Input validation
# ------------------------------

MAX_CONTENT_LEN = 10_000
MAX_CONTEXT_LEN = 512
MAX_TAGS = 20
MAX_TAG_LEN = 64


def validate_memory_fields(content: Optional[str], tags: Optional[List[str]], context: Optional[str]) -> None:
    if content is not None:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be a non-empty string")
        if len(content) > MAX_CONTENT_LEN:
            raise ValueError(f"content exceeds {MAX_CONTENT_LEN} characters")
    if context is not None:
        if len(context) > MAX_CONTEXT_LEN:
            raise ValueError(f"context exceeds {MAX_CONTEXT_LEN} characters")
    if tags is not None:
        if not isinstance(tags, list):
            raise ValueError("tags must be a list of strings")
        if len(tags) > MAX_TAGS:
            raise ValueError(f"too many tags (max {MAX_TAGS})")
        for t in tags:
            if not isinstance(t, str):
                raise ValueError("each tag must be a string")
            if len(t) > MAX_TAG_LEN:
                raise ValueError(f"tag '{t[:10]}...' exceeds {MAX_TAG_LEN} characters")


# Tool implementations

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
    conn.close()
    return {"updated": updated}


def _parse_time_hints(query: str) -> Optional[Tuple[datetime, datetime]]:
    q = query.lower()
    now = datetime.utcnow()
    if "last week" in q:
        # last ISO week (approx: last 7 days)
        return (now - timedelta(days=7), now)
    if "yesterday" in q:
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return (start, end)
    if "today" in q:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return (start, end)
    return None


def tool_memory_query(user_scope: str, query: str, limit: int) -> Dict[str, Any]:
    time_range = _parse_time_hints(query)
    conn = get_db_connection()
    cur = conn.cursor()
    like = f"%{query}%"
    if time_range:
        start_iso = time_range[0].isoformat()
        end_iso = time_range[1].isoformat()
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
    """Return candidate memory items parsed from free-form text. The assistant should confirm with the user before storing using memory_store."""
    items = _extract_candidates(text)
    return {"candidates": items}


TOOLS: Dict[str, Dict[str, Any]] = {
    "memory_store": {
        "description": (
            "Store a memory with optional tags and context. "
            "Triggers: remember, save this, note this, keep this, don't forget, favorite, prefer, address, email, phone, birthday. "
            "Use when the user explicitly asks to remember/save something."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The memory text to store"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "context": {"type": "string"},
                "user": {"type": "string", "description": "Optional user scope override"}
            },
            "required": ["content"]
        },
        "handler": lambda user, params: tool_memory_store(user, params.get("content"), params.get("tags"), params.get("context"))
    },
    "memory_query": {
        "description": (
            "Query memories by text and time hints (today, yesterday, last week). "
            "Triggers: what did I say/ask, recall, what is my favorite, did I mention, find my."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
                "user": {"type": "string"}
            },
            "required": ["query"]
        },
        "handler": lambda user, params: tool_memory_query(user, params.get("query"), int(params.get("limit", 20)))
    },
    "memory_list": {
        "description": "List recent memories. Triggers: show my saved items, show my memories, review what you saved.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "offset": {"type": "integer", "default": 0},
                "user": {"type": "string"}
            }
        },
        "handler": lambda user, params: tool_memory_list(user, int(params.get("limit", 20)), int(params.get("offset", 0)))
    },
    "memory_update": {
        "description": (
            "Update a memory by id. Dangerous: confirm with the user before changing saved info. "
            "Triggers: update, edit, change this saved item."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "context": {"type": "string"},
                "user": {"type": "string"}
            },
            "required": ["id"]
        },
        "handler": lambda user, params: tool_memory_update(user, int(params.get("id")), params.get("content"), params.get("tags"), params.get("context"))
    },
    "memory_delete": {
        "description": (
            "Delete a memory by id. Dangerous: confirm with the user before deleting. "
            "Triggers: delete, remove, forget that."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "user": {"type": "string"}
            },
            "required": ["id"]
        },
        "handler": lambda user, params: tool_memory_delete(user, int(params.get("id")))
    },
    "memory_suggest": {
        "description": (
            "Extract candidate facts/preferences from a message that might be worth remembering. "
            "Use when the user shares personal facts or preferences without explicitly asking to remember. "
            "Confirm with the user before storing via memory_store."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The raw user message to analyze"},
                "user": {"type": "string"}
            },
            "required": ["text"]
        },
        "handler": lambda user, params: tool_memory_suggest(user, params.get("text"))
    }
}


# ------------------------------
# Routes
# ------------------------------

@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/mcp")
async def mcp_endpoint(request: Request, authorization: Optional[str] = Header(default=None), x_user_id: Optional[str] = Header(default=None)):
    ensure_bearer_auth(authorization)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        rpc = JsonRpcRequest(**body)
    except Exception as e:
        return JSONResponse(status_code=400, content=JsonRpcResponse(id=body.get("id"), error={"code": -32600, "message": f"Invalid request: {e}"}).model_dump())

    if rpc.jsonrpc != "2.0":
        return JSONResponse(status_code=400, content=JsonRpcResponse(id=rpc.id, error={"code": -32600, "message": "Only JSON-RPC 2.0 is supported"}).model_dump())

    # tools/list
    if rpc.method == "tools/list":
        tools_public: List[Dict[str, Any]] = []
        for name, spec in TOOLS.items():
            schema = spec.get("parameters", {"type": "object"})
            tools_public.append({
                "name": name,
                "description": spec.get("description", ""),
                "parameters": schema,
                "input_schema": schema,
            })
        return JSONResponse(content=JsonRpcResponse(id=rpc.id, result={"tools": tools_public}).model_dump())

    # tools/call
    if rpc.method == "tools/call":
        if not rpc.params or "name" not in rpc.params or "arguments" not in rpc.params:
            return JSONResponse(status_code=400, content=JsonRpcResponse(id=rpc.id, error={"code": -32602, "message": "Missing name/arguments"}).model_dump())
        name = rpc.params["name"]
        arguments = rpc.params.get("arguments") or {}
        tool = TOOLS.get(name)
        if not tool:
            return JSONResponse(status_code=404, content=JsonRpcResponse(id=rpc.id, error={"code": -32601, "message": f"Tool not found: {name}"}).model_dump())
        user_scope = get_user_scope(x_user_id, arguments)
        started = time.time()
        try:
            result = tool["handler"](user_scope, arguments)
            duration_ms = int((time.time() - started) * 1000)
            logging.info("tool_call name=%s user=%s duration_ms=%d success=1", name, user_scope, duration_ms)
            return JSONResponse(content=JsonRpcResponse(id=rpc.id, result=result).model_dump())
        except Exception as e:
            duration_ms = int((time.time() - started) * 1000)
            logging.info("tool_call name=%s user=%s duration_ms=%d success=0 error=%s", name, user_scope, duration_ms, str(e))
            return JSONResponse(status_code=500, content=JsonRpcResponse(id=rpc.id, error={"code": -32000, "message": f"Tool execution error: {str(e)}"}).model_dump())

    # Optional ping
    if rpc.method == "ping":
        return JSONResponse(content=JsonRpcResponse(id=rpc.id, result={"pong": True}).model_dump())

    return JSONResponse(status_code=404, content=JsonRpcResponse(id=rpc.id, error={"code": -32601, "message": f"Method not found: {rpc.method}"}).model_dump())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mcp_memory.server:app", host=HOST, port=PORT, reload=False)
