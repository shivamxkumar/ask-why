#!/usr/bin/env bash
# ASK//WHY — start backend (FastAPI) and frontend (Vite) together.
# Usage: ./start.sh            (API on :8011, UI on :5174)
#        ASKWHY_PORT=9000 UI_PORT=5180 ./start.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
API_PORT="${ASKWHY_PORT:-8011}"
UI_PORT="${UI_PORT:-5174}"

# optional secrets/config (never committed): backend/.env
if [ -f "$ROOT/backend/.env" ]; then set -a; . "$ROOT/backend/.env"; set +a; fi

if [ ! -x "$ROOT/backend/.venv/bin/uvicorn" ]; then
  echo "→ creating Python venv and installing backend dependencies"
  python3 -m venv "$ROOT/backend/.venv"
  "$ROOT/backend/.venv/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
fi
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "→ installing frontend dependencies"
  (cd "$ROOT/frontend" && npm install --silent)
fi

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT") &
(cd "$ROOT/frontend" && ASKWHY_API="http://127.0.0.1:$API_PORT" npx vite --port "$UI_PORT" --strictPort) &

echo ""
echo "  ASK//WHY  →  http://localhost:$UI_PORT   (API: http://127.0.0.1:$API_PORT/api/health)"
echo "  AI analysis: $([ -n "${ANTHROPIC_API_KEY:-}" ] && echo "enabled (${ASKWHY_MODEL:-claude-opus-5-5})" || echo "off — set ANTHROPIC_API_KEY in backend/.env")"
echo ""
wait
