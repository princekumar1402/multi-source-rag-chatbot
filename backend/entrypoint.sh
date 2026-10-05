#!/bin/sh
set -e

echo "[entrypoint] Starting Multi-Source RAG Platform Backend..."

# Wait for PostgreSQL if DATABASE_URL is postgresql
if echo "$DATABASE_URL" | grep -q "postgres"; then
    echo "[entrypoint] Waiting for PostgreSQL database connection..."
    python - <<'EOF'
import os
import sys
import time
from urllib.parse import urlparse
import socket

db_url = os.getenv("DATABASE_URL", "")
if not db_url:
    sys.exit(0)

# Replace postgresql+psycopg2 with standard postgresql for urlparse
clean_url = db_url.replace("postgresql+psycopg2://", "postgresql://")
parsed = urlparse(clean_url)
host = parsed.hostname or "postgres"
port = parsed.port or 5432

print(f"[entrypoint] Checking connectivity to {host}:{port}...")
start_time = time.time()
while time.time() - start_time < 60:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[entrypoint] PostgreSQL is accepting TCP connections at {host}:{port}.")
            sys.exit(0)
    except OSError:
        time.sleep(1)

print(f"[entrypoint] Timed out waiting for PostgreSQL at {host}:{port}.", file=sys.stderr)
sys.exit(1)
EOF
fi

# Run database migrations
echo "[entrypoint] Running database migrations (alembic upgrade head)..."
alembic -c /app/backend/alembic.ini upgrade head || {
    echo "[entrypoint] Migration warning: alembic upgrade failed or tables already current."
}

# Ensure persistent data directories exist
mkdir -p "${VECTOR_STORE_PATH:-/app/data/vector_store}"
mkdir -p "/app/data/uploads"

echo "[entrypoint] Launching production ASGI server (Uvicorn)..."
exec uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips "*" \
    --no-access-log
