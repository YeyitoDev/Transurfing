# start_dev.ps1 - Modo desarrollo en Windows (FastAPI + Vite con hot reload)
# Uso:  ./start_dev.ps1   (desde la raiz del proyecto)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$frontend = Join-Path $root 'frontend'

Write-Host "Modo desarrollo: FastAPI (8077) + Vite (5173)" -ForegroundColor Cyan

# Backend (FastAPI con reload) en una ventana nueva
Start-Process -FilePath 'powershell' -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location -LiteralPath '$root'; python -m uvicorn app_tareas:app --host 127.0.0.1 --port 8077 --reload"
)

# Frontend (Vite dev server con HMR) en otra ventana nueva
Start-Process -FilePath 'powershell' -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location -LiteralPath '$frontend'; npx vite --port 5173"
)

Write-Host ""
Write-Host "  Vite (HMR):  http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "  API:         http://127.0.0.1:8077/api" -ForegroundColor Green
Write-Host "  WebSocket:   ws://127.0.0.1:8077/ws" -ForegroundColor Green
Write-Host ""
Write-Host "Se abrieron dos ventanas (backend y frontend). Cierralas para detener." -ForegroundColor Yellow
