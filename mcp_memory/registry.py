from typing import Any, Dict, List

from .memory.tools import (
    tool_memory_store,
    tool_memory_query,
    tool_memory_list,
    tool_memory_update,
    tool_memory_delete,
    tool_memory_suggest,
    tool_memory_export,
    tool_memory_stats,
    tool_memory_context,
    tool_memory_summary,
)
from .linkbrain.tools import (
    tool_link_save,
    tool_link_fetch,
    tool_link_list,
    tool_link_query,
    tool_link_delete,
    tool_link_summarize,
    tool_link_store_summary,
    tool_link_get_summary,
    tool_link_digest,
)
from .validate import tool_validate


TOOLS: Dict[str, Dict[str, Any]] = {
    "validate": {
        "description": "Return the user's phone number for bearer token validation (required by Puch)",
        "parameters": {"type": "object", "properties": {}},
        "handler": lambda user, params: tool_validate(user, params),
    },
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
    },
    # LinkBrain tools
    "link_save": {
        "description": (
            "Save a URL to your reading library; fetch and clean the page content (Medium, Hashnode, blogs, docs). "
            "Triggers: save this link, add to reading list, remember this article."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "title": {"type": "string", "description": "Optional custom title"},
                "user": {"type": "string"}
            },
            "required": ["url"]
        },
        "handler": lambda user, params: tool_link_save(user, params.get("url"), params.get("tags"), params.get("title"))
    },
    "link_fetch": {
        "description": "Fetch a saved link with cleaned text and metadata",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "user": {"type": "string"}
            },
            "required": ["url"]
        },
        "handler": lambda user, params: tool_link_fetch(user, params.get("url"))
    },
    "link_list": {
        "description": "List saved links (optionally by tag)",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "offset": {"type": "integer", "default": 0},
                "tag": {"type": "string"},
                "user": {"type": "string"}
            }
        },
        "handler": lambda user, params: tool_link_list(user, int(params.get("limit", 20)), int(params.get("offset", 0)), params.get("tag"))
    },
    "link_query": {
        "description": "Search across all saved links with full-text (title/byline/site/tags/content)",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
                "user": {"type": "string"}
            },
            "required": ["query"]
        },
        "handler": lambda user, params: tool_link_query(user, params.get("query"), int(params.get("limit", 20)))
    },
    "link_delete": {
        "description": "Delete a saved link by id (dangerous; confirm)",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "user": {"type": "string"}
            },
            "required": ["id"]
        },
        "handler": lambda user, params: tool_link_delete(user, int(params.get("id")))
    },
    "link_summarize": {
        "description": (
            "Prepare cleaned article text for summarization (saves & cleans if needed). "
            "Usage: call link_summarize to get 'content', then have the assistant summarize that text, "
            "then call link_store_summary with {url, summary} to persist."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "style": {"type": "string", "description": "Optional style/tone hint for the summary"},
                "user": {"type": "string"}
            },
            "required": ["url"]
        },
        "handler": lambda user, params: tool_link_summarize(user, params.get("url"), params.get("style"))
    },
    "link_store_summary": {
        "description": (
            "Store a model-generated summary for a URL so it can be reused later. "
            "Call this right after summarizing the 'content' returned by link_summarize (or link_fetch)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "summary": {"type": "string"},
                "user": {"type": "string"}
            },
            "required": ["url", "summary"]
        },
        "handler": lambda user, params: tool_link_store_summary(user, params.get("url"), params.get("summary"))
    },
    "link_get_summary": {
        "description": "Get the stored summary for a URL (fast path).",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}, "user": {"type": "string"}},
            "required": ["url"]
        },
        "handler": lambda user, params: tool_link_get_summary(user, params.get("url"))
    },
    "link_digest": {
        "description": "Get a digest of recent links with stored summaries (optionally filter by tag).",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 5}, "tag": {"type": "string"}, "user": {"type": "string"}}
        },
        "handler": lambda user, params: tool_link_digest(user, int(params.get("limit", 5)), params.get("tag"))
    }
}


