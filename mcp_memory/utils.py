from datetime import datetime
from typing import Any, Dict, Optional


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def get_user_scope(header_user_id: Optional[str], params: Optional[Dict[str, Any]]) -> str:
    if header_user_id and header_user_id.strip():
        return header_user_id.strip()
    if params and isinstance(params.get("user"), str) and params["user"].strip():
        return params["user"].strip()
    return "default"


