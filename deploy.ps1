# Despliegue a Fly.io en Windows. El frontend se compila DENTRO del Dockerfile
# (multi-stage), así que no necesitas construirlo en el host.
#
# Requisitos: flyctl instalado y autenticado (`fly auth login`).
#
# Uso:
#   ./deploy.ps1                 -> deploy normal
#   ./deploy.ps1 -Action setup   -> sólo cargar secretos desde .env
#   ./deploy.ps1 -Action full    -> secretos + crear volumen si falta + deploy
#
# Variables opcionales (entorno): FLY_APP, FLY_REGION, FLY_VOLUME, FLY_VOLUME_SIZE
param(
    [ValidateSet('deploy', 'setup', 'full')]
    [string]$Action = 'deploy'
)
$ErrorActionPreference = 'Stop'

$App        = if ($env:FLY_APP) { $env:FLY_APP } else { 'transurfing' }
$Region     = if ($env:FLY_REGION) { $env:FLY_REGION } else { 'mia' }
$Volume     = if ($env:FLY_VOLUME) { $env:FLY_VOLUME } else { 'datos' }
$VolumeSize = if ($env:FLY_VOLUME_SIZE) { $env:FLY_VOLUME_SIZE } else { '1' }

function Cargar-Secretos {
    if (Test-Path .env) {
        Write-Host "==> Cargando secretos desde .env" -ForegroundColor Cyan
        Get-Content .env | fly secrets import --app $App
    }
    else {
        Write-Host "==> No hay .env; omito secretos (usa: fly secrets set CLAVE=valor)" -ForegroundColor Yellow
    }
}

function Crear-Volumen {
    $existe = (fly volumes list --app $App 2>$null | Select-String -SimpleMatch $Volume)
    if (-not $existe) {
        Write-Host "==> Creando volumen '$Volume' (${VolumeSize}GB) en $Region" -ForegroundColor Cyan
        fly volumes create $Volume --app $App --region $Region --size $VolumeSize --yes
    }
}

if ($Action -eq 'setup') { Cargar-Secretos; return }
if ($Action -eq 'full') { Cargar-Secretos; Crear-Volumen }

Write-Host "==> Desplegando '$App' a Fly.io" -ForegroundColor Cyan
fly deploy --app $App --remote-only
Write-Host "==> Listo: https://$App.fly.dev  (health: https://$App.fly.dev/api/health)" -ForegroundColor Green
