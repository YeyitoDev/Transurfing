# syntax=docker/dockerfile:1

# --- Etapa 1: compilar el frontend (SvelteKit + adapter-static -> /app/web) ---
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# svelte.config.js usa adapter-static con pages/assets en ../web => /app/web
RUN npm run build

# --- Etapa 2: runtime Python (FastAPI sirve API + estático) ---
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la app (web/ está en .dockerignore: se trae compilado de la etapa 1)
COPY . .
COPY --from=frontend /app/web ./web

# El volumen persistente de Fly.io se monta en /data
ENV TAREAS_DATA_DIR=/data

EXPOSE 8080

CMD ["uvicorn", "app_tareas:app", "--host", "0.0.0.0", "--port", "8080"]
