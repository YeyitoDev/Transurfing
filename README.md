# ✅ Servicio de Tareas (con subtareas, alarmas y kanban)

Servicio ligero e independiente del bot.

- Vista principal centrada: tareas pendientes.
- Click en una tarea → despliega subtareas + barra de progreso + estado de cada subtarea.
- La tarea se marca **completada** automáticamente cuando todas sus subtareas están listas (o manualmente con el checkbox).
- Etiquetas: `Emprendimiento`, `Tarea`, `Hábito` con filtro por etiqueta.
- Tareas repetibles diarias (se resetean al día siguiente).
- Vista **Kanban** horizontal con columnas Pendientes / En progreso / Completadas.
- **Recordatorios / alarmas** para tareas o subtareas, con pestaña propia.
- **Notificaciones del navegador** para recordatorios próximos.
- Persiste en `data/tareas.json`.

## Correr local

```bash
cd tareas_app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app_tareas:app --reload --port 8077
```

Abre http://localhost:8077

> Nota: el contenedor de Docker/fly.io usa el puerto 8080; el puerto 8077 es solo para desarrollo local.

Los datos se guardan en `tareas_app/data/tareas.json`.

## Correr local en Windows (PowerShell)

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
./start_dev.ps1   # levanta backend (8077) + Vite (5173) en dos ventanas
```

## Seguridad (opcional)

Variables de entorno para endurecer la API sin cambiar el comportamiento por defecto:

- `API_AUTH_TOKEN`: si se define, la API exige el header `X-API-Token` en `/api/*` (el frontend lo toma de `localStorage.api_token`). Se eximen `/api/health`, `/api/auth/status` y el callback OAuth. Cuando está activo, el frontend muestra una **pantalla de login** que pide la clave y la valida contra `/api/auth/check` (con logout en el header). Si no se define, la app funciona sin login.
- `CORS_ORIGINS`: orígenes permitidos separados por comas (por defecto `*`).
- `SECRET_KEY`: si se define (con `cryptography` instalado), el PAT de GitHub se guarda cifrado en disco.

## Desplegar en fly.io

Un solo app sirve la API y el frontend. El volumen persistente mantiene el JSON, la memoria vectorial y el changelog.

### 1. Variables de entorno

Copia el archivo de ejemplo a la raíz del proyecto y rellena los valores reales:

```bash
cp /Users/sergio/Desktop/PERSONAL-AGENT/tareas_app/.env.example /Users/sergio/Desktop/PERSONAL-AGENT/.env
```

Edita `/Users/sergio/Desktop/PERSONAL-AGENT/.env` con al menos:

- `OPENAI_API_KEY` y `OPENAI_BASE_URL` (para agentes, chat, voz y resúmenes).
- `LLM_MODEL` (modelo por defecto). Opcional `LLM_MODELS` (lista separada por comas) para **curar** los modelos del selector. Si no defines `LLM_MODELS`, el selector **autodescubre** los modelos del gateway en `{OPENAI_BASE_URL}/models` (p.ej. OpenCode Zen). `GROQ_API_KEY` + `GROQ_LLM_MODEL` añaden Groq como proveedor alterno; el chat de cada tarea enruta al proveedor según el modelo elegido.
- `STORAGE_BACKEND`: `json` (por defecto) o `sqlite`. Con `sqlite` el documento se guarda en `data/tareas.db` (ruta configurable con `DB_PATH`) de forma transaccional (ACID/WAL); al activarlo por primera vez **importa automáticamente** el `tareas.json` existente. La API y la lógica no cambian.
- `GITHUB_CLIENT_ID` y `GITHUB_CLIENT_SECRET` (opcional, para GitHub).
- `TELEGRAM_BOT_TOKEN`, `WEBHOOK_URL`, etc. (opcional, para el bot).
- Reemplaza `<tu-app>` por el nombre que vas a usar en `fly.toml`.

### 2. Configurar el nombre de la app

Edita `fly.toml` y cambia:

```toml
app = "mis-tareas"
```

por un nombre único global (por ejemplo, `app = "jarvis-tareas"`).

### 3. Desplegar

```bash
cd /Users/sergio/Desktop/PERSONAL-AGENT/tareas_app
./deploy.sh --full
```

Esto hará:
1. Configurar los secretos en Fly.io desde el `.env`.
2. Crear el volumen persistente `datos` si no existe.
3. Construir el frontend (`npm run build`).
4. Ejecutar `fly deploy`.

Tras desplegar: `https://<tu-app>.fly.dev` y `https://<tu-app>.fly.dev/api/health`.

### Comandos útiles

```bash
# Solo build frontend + deploy (si los secretos ya están configurados)
./deploy.sh

# Solo configurar secretos
./deploy.sh --setup

# Ver logs en tiempo real
fly logs --app <tu-app>

# Conectar con la máquina (debug)
fly ssh console --app <tu-app>
```

### 4. Despliegue automático desde GitHub (opcional)

Para que cada `push` a `main` despliegue automáticamente a Fly.io:

1. Genera un token de acceso en Fly.io:

   ```bash
   fly tokens create deploy -x 999999h --app transurfing
   ```

   O con la acción web oficial:

   ```bash
   flyctl auth token
   ```

2. En tu repositorio de GitHub, ve a **Settings → Secrets and variables → Actions** y crea un nuevo **Repository secret**:

   - **Name:** `FLY_API_TOKEN`
   - **Value:** el token que copiaste en el paso anterior.

3. Asegúrate de que los secretos de la aplicación ya estén configurados en Fly.io (solo una vez):

   ```bash
   cd /Users/sergio/Desktop/PERSONAL-AGENT/tareas_app
   ./deploy.sh --setup
   ```

4. El workflow ya está en `.github/workflows/fly.yml`. Desde ahora, cada commit en `main` que toque `tareas_app/**` ejecutará:

   - Build del frontend (`npm install` + `npm run build`).
   - Deploy a Fly.io con `flyctl deploy --remote-only`.

5. También puedes ejecutar el deploy manualmente desde la pestaña **Actions** del repositorio (`workflow_dispatch`).

### 5. Configurar GitHub OAuth (para login con GitHub)

Si quieres usar el botón "Conectar con GitHub" en lugar de pegar un token manual:

1. Ve a **GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**.
2. Rellena:
   - **Application name:** Jarvis Tareas (o el nombre que prefieras).
   - **Homepage URL:** `https://transurfing.fly.dev`
   - **Authorization callback URL:** `https://transurfing.fly.dev/api/github/oauth/callback`
3. Copia el **Client ID** y genera un **Client Secret**.
4. Configura los secretos en Fly.io (o en tu `.env` local):

   ```bash
   flyctl secrets set GITHUB_CLIENT_ID="tu_client_id" GITHUB_CLIENT_SECRET="tu_client_secret" TAREAS_URL="https://transurfing.fly.dev" --app transurfing
   ```

5. Reinicia la app y prueba desde `/github` en la app. La misma pantalla muestra la callback URL que debe estar registrada.

### 6. Nuevas funcionalidades de IA

- **Chat global (botón flotante "Chat con Jarvis")**: permite crear tareas/cards conversando con el agente. El agente hará preguntas para ajustar el alcance, tipo, prioridad y plan, y puede crear subtareas o actualizar tareas existentes.
- **Chat dentro de cada tarea**: ahora permite:
  - Seleccionar el modelo/agente antes de enviar un mensaje.
  - Adjuntar múltiples archivos de texto para que el agente los analice y los tenga en cuenta.
- **Subtareas mejoradas**: cada subtarea tiene ahora **estado** (`pendiente`, `en_progreso`, `bloqueada`, `completada`) y **descripción/prompt** que define el resultado esperado. Puedes editarlos inline desde el detalle de la tarea.

## API

| Método | Ruta | Acción |
|---|---|---|
| GET | `/api/tareas?solo_pendientes=true` | Listar tareas |
| POST | `/api/tareas` | Crear `{titulo, prioridad, fecha_limite}` |
| PATCH | `/api/tareas/{id}` | Editar / `completada_manual` |
| DELETE | `/api/tareas/{id}` | Eliminar tarea |
| POST | `/api/tareas/{id}/subtareas` | Añadir `{titulo}` |
| PATCH | `/api/subtareas/{sid}` | `{completada}` o renombrar |
| DELETE | `/api/subtareas/{sid}` | Eliminar subtarea |
| GET | `/api/recordatorios` | Listar alarmas/recordatorios |
| POST | `/api/recordatorios` | Crear recordatorio `{titulo, fecha_hora, tarea_id, subtarea_id}` |
| PATCH | `/api/recordatorios/{id}` | Editar/marcar `{titulo, fecha_hora, estado}` |
| DELETE | `/api/recordatorios/{id}` | Eliminar recordatorio |
