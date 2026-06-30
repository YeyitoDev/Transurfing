#!/usr/bin/env bash
# Despliegue a Fly.io. El frontend se compila DENTRO del Dockerfile (multi-stage),
# así que no necesitas construirlo en el host.
#
# Requisitos: flyctl instalado y autenticado (`fly auth login`).
#
# Uso:
#   ./deploy.sh            -> deploy normal
#   ./deploy.sh --setup    -> sólo cargar secretos desde .env (fly secrets import)
#   ./deploy.sh --full     -> secretos + crear volumen si falta + deploy
#
# Variables opcionales: FLY_APP, FLY_REGION, FLY_VOLUME, FLY_VOLUME_SIZE
set -euo pipefail

APP="${FLY_APP:-transurfing}"
REGION="${FLY_REGION:-mia}"
VOLUME="${FLY_VOLUME:-datos}"
VOLUME_SIZE="${FLY_VOLUME_SIZE:-1}"

cargar_secretos() {
  if [[ -f .env ]]; then
    echo "==> Cargando secretos desde .env"
    fly secrets import --app "$APP" < .env
  else
    echo "==> No hay .env; omito secretos (configúralos con: fly secrets set CLAVE=valor)"
  fi
}

crear_volumen() {
  if ! fly volumes list --app "$APP" 2>/dev/null | grep -q "$VOLUME"; then
    echo "==> Creando volumen '$VOLUME' (${VOLUME_SIZE}GB) en $REGION"
    fly volumes create "$VOLUME" --app "$APP" --region "$REGION" --size "$VOLUME_SIZE" --yes
  fi
}

case "${1:-}" in
  --setup)
    cargar_secretos
    exit 0
    ;;
  --full)
    cargar_secretos
    crear_volumen
    ;;
esac

echo "==> Desplegando '$APP' a Fly.io"
fly deploy --app "$APP" --remote-only
echo "==> Listo: https://$APP.fly.dev  (health: https://$APP.fly.dev/api/health)"
