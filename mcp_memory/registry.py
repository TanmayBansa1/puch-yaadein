from typing import Any, Dict, List

from .tools import (
    tool_memory_store,
    tool_memory_query,
    tool_memory_list,
    tool_memory_update,
    tool_memory_delete,
    tool_memory_suggest,
)
from .tools_extra import tool_memory_export, tool_memory_stats, tool_memory_context, tool_memory_summary


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
    },
    "memory_export": {
        "description": "Export all memories for this user as JSON (string)",
        "parameters": {"type": "object", "properties": {"user": {"type": "string"}}},
        "handler": lambda user, params: tool_memory_export(user)
    },
    "memory_stats": {
        "description": "Basic memory stats: total and per-day counts (last 7 days)",
        "parameters": {"type": "object", "properties": {"user": {"type": "string"}}},
        "handler": lambda user, params: tool_memory_stats(user)
    },
    "memory_context": {
        "description": "Get memories related to a context/tag keyword",
        "parameters": {
            "type": "object",
            "properties": {
                "context": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
                "user": {"type": "string"}
            },
            "required": ["context"]
        },
        "handler": lambda user, params: tool_memory_context(user, params.get("context"), int(params.get("limit", 20)))
    },
    "memory_summary": {
        "description": "Summarize recent memories with top tags and highlights (range: today|yesterday|last_week)",
        "parameters": {
            "type": "object",
            "properties": {
                "range": {"type": "string", "enum": ["today", "yesterday", "last_week"], "default": "last_week"},
                "user": {"type": "string"}
            }
        },
        "handler": lambda user, params: tool_memory_summary(user, params.get("range", "last_week"))
    }
}


