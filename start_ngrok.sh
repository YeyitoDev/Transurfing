#!/usr/bin/env bash
set -euo pipefail

# ── Configuración ──────────────────────────────────────────────
PORT=8077
NGROK_LOG="/Users/sergio/Desktop/PERSONAL-AGENT/ngrok.log"
APP_DIR="/Users/sergio/Desktop/PERSONAL-AGENT/tareas_app"
VENV="/Users/sergio/Desktop/PERSONAL-AGENT/.venv/bin/python"
# ────────────────────────────────────────────────────────────────

echo "🚀 Iniciando servicio de tareas en puerto $PORT..."

# Matar procesos previos
pkill -f "uvicorn app_tareas:app" 2>/dev/null || true
pkill -f "ngrok http $PORT" 2>/dev/null || true
sleep 1

# Build del frontend
echo "📦 Compilando frontend..."
cd "$APP_DIR/frontend"
npm run build > /tmp/tareas_build.log 2>&1 || echo "   ⚠️  Build falló, usando web/ existente"
echo "   ✅ Frontend compilado → web/"

# Arrancar backend
cd "$APP_DIR"
"$VENV" -m uvicorn app_tareas:app --host 0.0.0.0 --port "$PORT" > /tmp/tareas_app.log 2>&1 &
BACKEND_PID=$!
echo "   ✅ Backend PID: $BACKEND_PID"

# Esperar a que el backend arranque
for i in $(seq 1 10); do
  if curl -s -o /dev/null -w "" "http://localhost:$PORT/api/tareas" 2>/dev/null; then
    echo "   ✅ Backend respondiendo en http://localhost:$PORT"
    break
  fi
  sleep 0.5
done

# Arrancar ngrok con el dominio estático gratuito
DOMAIN="robin-open-widely.ngrok-free.app"
PUBLIC_URL="https://$DOMAIN"

echo "🌐 Iniciando ngrok..."
echo "   Dominio estático: $PUBLIC_URL"
ngrok http --url="$DOMAIN" "$PORT" \
  --log="$NGROK_LOG" \
  --log-format=logfmt \
  > /dev/null 2>&1 &
NGROK_PID=$!
echo "   ✅ ngrok PID: $NGROK_PID"

echo ""
echo "══════════════════════════════════════════════════════"
echo "  ✅ SERVICIO ACTIVO"
echo ""
echo "  📱 Pública:  $PUBLIC_URL"
echo "  💻 Local:    http://localhost:$PORT"
echo "  📊 Panel:    http://127.0.0.1:4040"
echo ""
echo "  Para detener: kill $BACKEND_PID $NGROK_PID"
echo "══════════════════════════════════════════════════════"

# Mantener el script corriendo
wait $BACKEND_PID
