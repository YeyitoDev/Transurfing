#!/usr/bin/env bash
set -euo pipefail

PORT=8077
APP_DIR="/Users/sergio/Desktop/PERSONAL-AGENT/tareas_app"
FRONTEND_DIR="$APP_DIR/frontend"
VENV="/Users/sergio/Desktop/PERSONAL-AGENT/.venv/bin/python"

echo "🚀 Modo desarrollo: FastAPI + Vite (hot reload)"

# Matar procesos previos
pkill -f "uvicorn app_tareas:app --host 127.0.0.1 --port $PORT" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

# Arrancar backend
cd "$APP_DIR"
"$VENV" -m uvicorn app_tareas:app --host 127.0.0.1 --port "$PORT" --reload > /tmp/tareas_backend.log 2>&1 &
BACKEND_PID=$!
echo "   ✅ Backend PID: $BACKEND_PID → http://127.0.0.1:$PORT"

# Arrancar Vite dev server
cd "$FRONTEND_DIR"
npx vite --port 5173 > /tmp/tareas_vite.log 2>&1 &
VITE_PID=$!
echo "   ✅ Vite PID: $VITE_PID → http://127.0.0.1:5173"

sleep 2

echo ""
echo "══════════════════════════════════════════════════════"
echo "  ✅ MODO DESARROLLO ACTIVO"
echo ""
echo "  💻 Vite (HMR):  http://127.0.0.1:5173"
echo "  🔌 API:         http://127.0.0.1:$PORT/api"
echo "  📡 WebSocket:   ws://127.0.0.1:$PORT/ws"
echo ""
echo "  Para detener: kill $BACKEND_PID $VITE_PID"
echo "══════════════════════════════════════════════════════"

wait $BACKEND_PID $VITE_PID
