# Memory-Plus MCP Server (Phase 1)

AI-powered local memory + contextual recall as an MCP server for Puch AI. MCP-only implementation (no web UI). Built to maximize user adoption for the Puch Hackathon.

## What this is
- MCP server exposing memory tools: store, query, list, update, delete
- Bearer token auth (required by Puch)
- JSON-RPC over HTTP at `/mcp`
- SQLite for persistent local storage

## Hackathon compatibility
- Complies with Puch MCP server requirements and HTTPS expectations
- Uses only MCP-supported features (no videos/resources/prompts) per docs
- Based on the official starter approach for bearer auth and tool registration ([TurboML MCP Starter](https://github.com/TurboML-Inc/mcp-starter))

## Quick start

1) Create and activate venv, then install deps
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2) Configure environment
```bash
cp .env.example .env
# edit .env and set AUTH_TOKEN=your_secret_token_here
```

3) Run the server
```bash
python -m mcp_memory.server
# Server listens on 0.0.0.0:8086 by default
```

4) Expose publicly for Puch (HTTPS)
- Use ngrok or deploy to a cloud provider

5) Connect from Puch
```
/mcp connect https://your-domain.ngrok.app/mcp your_secret_token_here
```

## Tools (Phase 1)
- `memory_store(content: str, tags?: list[str], context?: str)`
- `memory_query(query: str, limit?: int)`
- `memory_list(limit?: int, offset?: int)`
- `memory_update(id: int, content?: str, tags?: list[str], context?: str)`
- `memory_delete(id: int)`

All tools accept optional user scoping via header `X-User-Id`; otherwise default scope is `default`.

## Notes
- JSON-RPC methods exposed at `/mcp`:
  - `tools/list` → returns tool registry
  - `tools/call` → executes a tool by name
- Health endpoint: `/health`
- Env: `AUTH_TOKEN` (required), `HOST`, `PORT`, `DB_PATH` (optional)

## References
- Puch Hackathon: `https://puch.ai/hack`
- Puch MCP docs and requirements: `https://puch.ai/mcp`
- MCP Spec: `https://modelcontextprotocol.io/docs/getting-started/intro`
- Starter repo: [TurboML MCP Starter](https://github.com/TurboML-Inc/mcp-starter)
