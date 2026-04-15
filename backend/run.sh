#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f ".env" ]]; then
  echo "Missing backend/.env. Copy backend/.env.example to backend/.env and fill values." >&2
  exit 1
fi

# Prefer project venv so you don't need `source backend/.venv/bin/activate` every time.
if [[ -x ".venv/bin/python3" ]]; then
  PY=".venv/bin/python3"
elif [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

if ! "$PY" -c "import uvicorn" 2>/dev/null; then
  echo "uvicorn is not installed for: $PY" >&2
  echo "Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

if ! "$PY" -c "import dotenv" 2>/dev/null; then
  echo "python-dotenv missing; run: $PY -m pip install -r requirements.txt" >&2
  exit 1
fi

"$PY" <<'PY'
import sys
from pathlib import Path
from dotenv import dotenv_values

cfg = dotenv_values(Path(".env"))
url = (cfg.get("SUPABASE_URL") or "").strip()
key = (cfg.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
if not url or not key:
    print("\nbackend/.env is missing Supabase credentials.\n", file=sys.stderr)
    if not url:
        print("  • SUPABASE_URL is empty — set it to your Project URL (include https://)", file=sys.stderr)
    if not key:
        print("  • SUPABASE_SERVICE_ROLE_KEY is empty — use the Secret / service_role key (server only)", file=sys.stderr)
    print("\nSupabase Dashboard → Project Settings → API:", file=sys.stderr)
    print("  SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co", file=sys.stderr)
    print("  SUPABASE_SERVICE_ROLE_KEY=<copy the Secret key (or legacy service_role)>", file=sys.stderr)
    print("\nDo not use the publishable/anon key for the backend.\n", file=sys.stderr)
    raise SystemExit(1)
PY

PORT="${PORT:-8080}"
if command -v lsof >/dev/null 2>&1; then
  if lsof -iTCP:"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Port $PORT is already in use (another server is probably still running)." >&2
    echo "" >&2
    lsof -iTCP:"$PORT" -sTCP:LISTEN -Pn >&2 || true
    echo "" >&2
    echo "Fix: stop that process (Ctrl+C in its terminal), or free the port:" >&2
    echo "  lsof -ti :$PORT | xargs kill" >&2
    echo "Or use a different port:" >&2
    echo "  PORT=8081 ./backend/run.sh" >&2
    exit 1
  fi
fi

exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

