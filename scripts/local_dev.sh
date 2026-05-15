#!/usr/bin/env bash
# Start the full local dev stack
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."

echo "==> Voyager Travel Agent — Local Dev"
echo ""

# Check for .env
if [ ! -f "$ROOT/.env" ]; then
  echo "No .env found — copying .env.example..."
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Edit .env with your API keys before running!"
  exit 1
fi

# Check Python deps
if ! python3 -c "import langgraph" 2>/dev/null; then
  echo "==> Installing Python deps..."
  pip install -e "$ROOT[dev]"
fi

# Check Node deps
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "==> Installing frontend deps..."
  cd "$ROOT/frontend" && npm install
fi

# Launch API (background)
echo "==> Starting API on http://localhost:8000"
cd "$ROOT"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

# Launch frontend (background)
echo "==> Starting frontend on http://localhost:5173"
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Voyager running:"
echo "  API:      http://localhost:8000"
echo "  UI:       http://localhost:5173"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

trap "kill $API_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait
