from typing import Any, Dict, Optional
from pydantic import BaseModel


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


