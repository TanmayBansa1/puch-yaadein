import time
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .auth import ensure_bearer_auth
from .config import HOST, PORT
from .db import init_db
from .jsonrpc import JsonRpcRequest, JsonRpcResponse
from .registry import TOOLS
from .utils import get_user_scope
from .ratelimit import RateLimiter


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(title="Memory-Plus MCP Server", version="0.1.0")
    # Logging: console + file
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, "mcp.log")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        fh = logging.FileHandler(log_path)
        fh.setFormatter(formatter)
        root_logger.addHandler(fh)
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        root_logger.addHandler(sh)

    limiter = RateLimiter(rate_per_sec=5.0, burst=15)

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/mcp")
    async def mcp_endpoint(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_user_id: Optional[str] = Header(default=None),
    ):
        ensure_bearer_auth(authorization)

        try:
            body = await request.json()
        except Exception:
            req_id = str(uuid.uuid4())
            return JSONResponse(
                status_code=400,
                headers={"x-request-id": req_id},
                content=JsonRpcResponse(id=None, error={"code": -32700, "message": "Parse error", "data": {"request_id": req_id}}).model_dump(),
            )

        try:
            rpc = JsonRpcRequest(**body)
        except Exception as e:
            req_id = str(uuid.uuid4())
            return JSONResponse(
                status_code=400,
                headers={"x-request-id": req_id},
                content=JsonRpcResponse(id=body.get("id"), error={"code": -32600, "message": f"Invalid request: {e}", "data": {"request_id": req_id}}).model_dump(),
            )

        if rpc.jsonrpc != "2.0":
            req_id = str(uuid.uuid4())
            return JSONResponse(
                status_code=400,
                headers={"x-request-id": req_id},
                content=JsonRpcResponse(id=rpc.id, error={"code": -32600, "message": "Only JSON-RPC 2.0 is supported", "data": {"request_id": req_id}}).model_dump(),
            )

        # Rate limit per user/ip key
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{x_user_id or 'default'}"
        if not limiter.allow(key):
            req_id = str(uuid.uuid4())
            logging.info("rate_limited request_id=%s client=%s user=%s", req_id, client_ip, x_user_id or 'default')
            return JSONResponse(status_code=429, headers={"x-request-id": req_id}, content=JsonRpcResponse(id=rpc.id, error={"code": -32001, "message": "Rate limit exceeded"}).model_dump())

        # tools/list
        if rpc.method == "tools/list":
            req_id = str(uuid.uuid4())
            tools_public: List[Dict[str, Any]] = []
            for name, spec in TOOLS.items():
                schema = spec.get("parameters", {"type": "object"})
                tools_public.append(
                    {
                        "name": name,
                        "description": spec.get("description", ""),
                        "parameters": schema,
                        "input_schema": schema,
                    }
                )
            return JSONResponse(headers={"x-request-id": req_id}, content=JsonRpcResponse(id=rpc.id, result={"request_id": req_id, "tools": tools_public}).model_dump())

        # tools/call
        if rpc.method == "tools/call":
            req_id = str(uuid.uuid4())
            if not rpc.params or "name" not in rpc.params or "arguments" not in rpc.params:
                return JSONResponse(
                    status_code=400,
                    headers={"x-request-id": req_id},
                    content=JsonRpcResponse(id=rpc.id, error={"code": -32602, "message": "Missing name/arguments", "data": {"request_id": req_id}}).model_dump(),
                )
            name = rpc.params["name"]
            arguments = rpc.params.get("arguments") or {}
            tool = TOOLS.get(name)
            if not tool:
                return JSONResponse(
                    status_code=404,
                    headers={"x-request-id": req_id},
                    content=JsonRpcResponse(id=rpc.id, error={"code": -32601, "message": f"Tool not found: {name}", "data": {"request_id": req_id}}).model_dump(),
                )
            user_scope = get_user_scope(x_user_id, arguments)
            started = time.time()
            try:
                result = tool["handler"](user_scope, arguments)
                if isinstance(result, dict):
                    result = {"request_id": req_id, **result}
                duration_ms = int((time.time() - started) * 1000)
                logging.info("tool_call request_id=%s name=%s user=%s duration_ms=%d success=1", req_id, name, user_scope, duration_ms)
                return JSONResponse(headers={"x-request-id": req_id}, content=JsonRpcResponse(id=rpc.id, result=result).model_dump())
            except Exception as e:
                duration_ms = int((time.time() - started) * 1000)
                logging.info("tool_call request_id=%s name=%s user=%s duration_ms=%d success=0 error=%s", req_id, name, user_scope, duration_ms, str(e))
                return JSONResponse(
                    status_code=500,
                    headers={"x-request-id": req_id},
                    content=JsonRpcResponse(id=rpc.id, error={"code": -32000, "message": f"Tool execution error: {str(e)}", "data": {"request_id": req_id}}).model_dump(),
                )

        # Optional ping
        if rpc.method == "ping":
            req_id = str(uuid.uuid4())
            return JSONResponse(headers={"x-request-id": req_id}, content=JsonRpcResponse(id=rpc.id, result={"request_id": req_id, "pong": True}).model_dump())

        req_id = str(uuid.uuid4())
        return JSONResponse(
            status_code=404,
            headers={"x-request-id": req_id},
            content=JsonRpcResponse(id=rpc.id, error={"code": -32601, "message": f"Method not found: {rpc.method}", "data": {"request_id": req_id}}).model_dump(),
        )

    return app


app = create_app()


