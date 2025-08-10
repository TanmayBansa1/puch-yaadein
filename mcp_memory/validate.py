from typing import Any, Dict

from .config import USER_PHONE


def tool_validate(user_scope: str, _params: Dict[str, Any] | None = None) -> Dict[str, str]:
    # Returns E.164-like digits without '+' as required by Puch: {country_code}{number}
    # Example: 919876543210
    return {"phone": USER_PHONE}


