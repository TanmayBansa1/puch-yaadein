from typing import List, Optional

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


