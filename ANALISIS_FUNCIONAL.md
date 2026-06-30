# Análisis funcional — Transurfing

Plataforma personal de **gestión de tareas potenciada con IA**: combina un gestor de tareas/subtareas, recordatorios, un lienzo visual, agentes de IA, integración con GitHub y comandos por voz. Es **monousuario** (single-tenant) y se sirve como una sola app que entrega API + frontend.

---

## 1. Oportunidades y roadmap (prioridad)

Ordenadas por valor/alineación con el objetivo. El estado refleja el desarrollo en curso.

### Prioridad alta

- **#6 Autenticación del portal (acceso controlado)** — *EN DESARROLLO*.
  - Hoy existe un gate **opt-in** por `API_AUTH_TOKEN` (header `X-API-Token`) pero sin pantalla de login.
  - Plan: endpoint `GET /api/auth/status` (exento) + `GET /api/auth/check`, componente `Login.svelte` y gate en `+layout.svelte`. Si no hay `API_AUTH_TOKEN`, la app funciona igual que hoy (sin login).
  - Beneficio: cerrar el portal con una passphrase sin tocar el resto del flujo.

- **Cobertura de token en todas las llamadas** — `vozTranscribir` hacía `fetch` sin el header `X-API-Token`; se corrige para que la voz funcione con auth activa.

### Prioridad media

- **#7d Etiquetas personalizables (color + emoji)** — hoy `etiqueta` es un enum fijo (`emprendimiento/tarea/habito/investigacion/idea`) usado en plantillas de IA, filtros y UI. Convertirlo en taxonomía editable (CRUD de etiquetas con color/emoji) es de alto impacto pero requiere tocar varios módulos; el emoji/color **por tarea** ya mitiga la identificación.
- **Kanban "En progreso" asignable** — la columna se deriva del avance de subtareas; añadir un estado explícito permitiría arrastrar a "En progreso".
- **Búsqueda semántica enriquecida** — el Command Palette ya consulta `/memorias/buscar`; falta enlazar cada resultado a su tarea/origen para "saltar" al contexto.

### Prioridad baja / estratégica

- **Persistencia JSON → SQLite/Postgres** — el JSON es simple pero limita concurrencia/escala; migración con capa de repositorio.
- **Multiusuario real** — si el portal deja de ser personal, hace falta modelo de usuarios/sesiones.
- **Notificaciones push (web-push)** — la PWA ya es instalable; faltaría Service Worker push + VAPID en backend.
- **Tests automatizados de frontend** — hoy sólo se valida el backend con `py_compile`.

---

## 2. Propósito y actores

- **Propósito**: capturar ideas y tareas, planificarlas con IA, ejecutarlas (incluso generando código y PRs) y dar seguimiento con recordatorios, calendario y kanban.
- **Actores**:
  - **Usuario** (uno): gestiona y configura. Acceso protegible con token opcional (sin usuarios/login reales todavía → #6).
  - **Agentes de IA**: Jarvis (chat global), agentes especializados y el pipeline de subtareas, que actúan en nombre del usuario.

---

## 3. Arquitectura funcional

- **Backend**: FastAPI monolítico (`app_tareas.py`, ~62 KB) + persistencia JSON (`storage.py`) + memoria vectorial (`vector_store.py`).
- **Servicios de IA**: gateway compatible con OpenAI (OpenCode Zen) + Groq alterno; `agente_planes.py`, `chat_global_service.py`, `subtarea_agente_service.py`, `canvas_agent_service.py`, `voz_service.py`.
- **Frontend**: SvelteKit + Svelte 5 (PWA) en `frontend/`. (`frontend-react-backup/` es la versión React heredada, en desuso.)
- **Tiempo real**: WebSocket `/ws` que emite `tareas_changed` / `recordatorios_changed`.
- **Despliegue**: `Dockerfile` + Fly.io con volumen persistente para JSON, memoria y changelog.

---

## 4. Módulos funcionales

| Módulo | Endpoints clave | Capacidades |
| --- | --- | --- |
| **Tareas** | `/api/tareas` (CRUD), `/numero/{n}` | Prioridad, etiqueta, fecha límite, repetible (hábitos), horas/días, objetivo, **emoji+color**; estado/`progreso` derivados; completar auto o manual. |
| **Subtareas** | `/api/subtareas`, `/api/tareas/{id}/subtareas/*` | Estados, `descripcion`/`prompt`; **ejecución IA** (Planner→Executor→Reviewer), `iterar`, `ejecutar-todas`, `progreso`, `commit` y `sincronizar` a GitHub. |
| **Recordatorios** | `/api/recordatorios` | CRUD para tarea/subtarea, "próximo", notificaciones del navegador. |
| **Chat global (Jarvis)** | `/api/chat-global` | Crea/edita/elimina tareas, agrega subtareas, ejecuta/commitea, gestiona recordatorios. |
| **Chat por tarea** | `/api/tareas/{id}/chat-mensajes` | Multi-modelo (ruteo por proveedor) + adjuntos. |
| **Agentes** | `/api/agentes`, `/api/skills`, `/api/knowledge` | CRUD de agentes (modelo + system prompt + skills + knowledge), ejecución individual y **en paralelo**. |
| **Lienzo visual** | `/api/tareas/{id}/canvas[/interpretar]` | Bloques tipados (texto/idea/código/JSON/cURL/imagen/tabla/diagrama), enlaces, **kanban en nota**, zoom/paneo, recordatorios por bloque, imágenes, **interpretación IA**. |
| **GitHub** | `/api/github/*` | OAuth + PAT (cifrado opcional), repos, PR idempotente, diagnóstico. |
| **Voz** | `/api/voz/*` | STT/TTS degradables, procesar→draft→confirmar, resumen narrativo. |
| **Agente proactivo** | `/api/agente/*` | Resumen inteligente (destacadas, vencidas, **estancadas**, ideas, noticias, preguntas), check-in, **plan** por objetivo, buscar novedades. |
| **Memoria semántica** | `/api/memorias[/buscar]` | Guardar anotaciones y **buscar por significado**; base del Command Palette y de preguntas con fuentes. |
| **Changelog/QA** | `/api/changelog/*` | Entradas estructuradas (versión/impacto/cambios/QA) y **generación asistida**. |
| **Modelos LLM** | `/api/modelos` | Autodescubrimiento del gateway + curado (`LLM_MODELS`) + Groq, deduplicado. |

**Vistas (frontend)**: Inicio, Completadas, **Calendario** (drag para reprogramar), **Kanban** (drag), Alarmas, Agentes, GitHub, Changelog, Voz.

**Productividad/UX**: **Command palette (Ctrl+K)** con búsqueda semántica, **Pomodoro**, **densidad de card**, temas/paletas, **PWA instalable**.

---

## 5. Flujos clave (end-to-end)

- **Idea → ejecución → PR**: crear tarea (form/voz/chat) → generar subtareas → ejecutar con IA → commitear → PR en GitHub.
- **Planificación proactiva**: agente genera resumen/plan → el usuario crea tareas desde drafts.
- **Captura visual**: lienzo de la tarea → interpretar con IA → ideas/riesgos.
- **Recuperación de contexto**: guardar en memoria → búsqueda semántica desde Ctrl+K.

---

## 6. Modelo de datos (entidades)

`Tarea` · `Subtarea` (+`SubtareaIteracion`) · `Recordatorio` · `Agente`/`Skill`/`Knowledge` · `ChatSession`/`ChatMessage` · `TareaCanvas` (`CanvasBloque`/`CanvasLink`/`CanvasLogEntry`) · `ChangelogEntry` · `Memoria` (vector store). Definiciones en `frontend/src/lib/types.ts`. Persistencia: JSON (`data/*.json`) + índice vectorial.

---

## 7. Integraciones externas

Gateway OpenAI-compatible (OpenCode Zen), Groq, GitHub API, APIs del navegador (Notifications, Web Speech) y TTS/STT premium opcional.

---

## 8. No funcionales

- **Seguridad**: auth opcional por token, **cifrado del PAT** (Fernet/`SECRET_KEY`), CORS por env.
- **Resiliencia**: imports opcionales que **degradan** funciones (voz, vectores) en lugar de romper.
- **Tiempo real + offline**: WebSocket + PWA con precache.

---

## 9. Fortalezas

- Cobertura funcional muy amplia para un usuario: del "to-do" simple a **ejecución autónoma de trabajo** y entrega a GitHub.
- IA integrada en múltiples puntos (planificar, ejecutar, interpretar, conversar, buscar).
- UX cuidada (tiempo real, lienzo, command palette, temas, PWA).
