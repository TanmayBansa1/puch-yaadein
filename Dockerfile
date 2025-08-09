# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (build + runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY mcp_memory ./mcp_memory

# Default env; override in runtime via --env-file
ENV HOST=0.0.0.0 \
    PORT=8086 \
    DB_PATH=/app/data/memory.db

EXPOSE 8086

CMD ["uvicorn", "mcp_memory.app:app", "--host", "0.0.0.0", "--port", "8086"]


