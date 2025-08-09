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
- Use a cloud provider or reverse proxy (see AWS section below)

5) Connect from Puch
```
/mcp connect https://your-domain.ngrok.app/mcp your_secret_token_here
```

### Docker (local)

```bash
# Build
docker build -t memory-plus .

# Run (app only)
docker run -p 8086:8086 --env-file .env -v $(pwd)/data:/app/data -v $(pwd)/logs:/app/logs memory-plus

# Or via docker-compose with NGINX reverse proxy on :80
docker compose up -d
```

## Deploy to AWS (EC2 + NGINX + your subdomain)

High level:
- Provision EC2 (t2.micro) with a security group allowing 22/tcp and 80/tcp
- SSH into EC2, install Docker & Compose
- Clone repo, create `.env` (AUTH_TOKEN, etc.)
- `docker compose up -d` (starts app + NGINX)
- Point your subdomain (e.g., `mcp.tanmay.space`) A record to the EC2 public IP
- Optionally attach an Elastic IP to keep the IP stable

Commands on EC2 (Amazon Linux 2023):
```bash
sudo yum update -y
# Docker
sudo amazon-linux-extras enable docker
sudo yum install -y docker git
sudo service docker start
sudo usermod -aG docker $USER
newgrp docker
# Docker Compose v2
DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
mkdir -p $DOCKER_CONFIG/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose
chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose

# Clone & run
git clone <your-repo-url> && cd <repo>
cat > .env <<EOF
AUTH_TOKEN=yourtoken
HOST=0.0.0.0
PORT=8086
DB_PATH=/app/data/memory.db
EOF
mkdir -p data logs
docker compose up -d
```

DNS setup (Hostinger):
- Create an A record for `mcp.tanmay.space` pointing to your EC2 Elastic IP
- Wait for DNS to propagate

HTTPS (recommended):
- Simplest: attach an AWS Application Load Balancer with ACM cert for `mcp.tanmay.space`, forward to instance:80
- Or terminate TLS inside NGINX (use certbot and mount certs into the nginx container)

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
