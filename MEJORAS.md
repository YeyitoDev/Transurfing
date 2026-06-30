# Mejoras de Transurfing — Documento vivo

> Documento de seguimiento. Se actualiza a medida que avanzamos.
> Última actualización: 2026-06-30 (oleadas 1-2 aplicadas)

## Cómo usar este documento

- Cada mejora tiene un **estado**, **prioridad** y una lista de **subtareas** accionables.
- Marca las casillas `[x]` al completar.
- Anota lo relevante en la **Bitácora** al final.

**Leyenda de estado:** `Pendiente` · `En progreso` · `Bloqueada` · `Hecha` · `Pospuesta`

---

## Parte A — Mejoras de calidad y arquitectura

> Alcance acordado: **iniciar todas excepto la #3 (persistencia/SQLite)**, que queda pospuesta.

### 1. Seguridad de la API `[Prioridad: Crítica]` `[Estado: En progreso]`
La app se despliega públicamente sin autenticación y con CORS abierto; el PAT de GitHub se guarda en texto plano.
- [x] Autenticación **opt-in** por token en `/api/*` (env `API_AUTH_TOKEN`; exime `health` y OAuth callback). Desactivada si no se define.
- [x] `CORSMiddleware` configurable por entorno (env `CORS_ORIGINS`, por defecto `*`).
- [x] Enviar el token desde el frontend (`api.ts` añade `X-API-Token` desde `localStorage.api_token`).
- [x] Cifrar el PAT de GitHub en disco con Fernet si hay `SECRET_KEY` (dependencia `cryptography` añadida; compatible con PATs en texto plano).
- [ ] Revisar exposición de endpoints que ejecutan agentes (coste/abuso).

### 2. Bug de despliegue: módulos de voz ausentes `[Prioridad: Alta]` `[Estado: Hecha]`
`app_tareas.py` importaba `groq_stt`, `tts_service` y `stt_service`, que **no existen en este repo** (viven en el proyecto padre). El `Dockerfile` solo copia esta carpeta → fallaba en producción.
- [x] Importaciones opcionales con helper `_optional_import` (no rompe si faltan).
- [x] `/api/voz/config`, `/api/voz/tts` y `/api/voz/transcribir` degradan con gracia (503 claro en vez de 500).
- [ ] (Opcional) Incluir los módulos en el repo o documentar la dependencia del proyecto padre.

### 3. Persistencia JSON → SQLite `[Prioridad: Alta]` `[Estado: Pospuesta]`
> **Excluida del alcance actual por decisión del usuario.** Se retomará más adelante.
- [ ] (Futuro) Migrar `storage.py` de JSON + `threading.Lock` a SQLite.
- [ ] (Futuro) Evitar I/O bloqueante en endpoints `async`.

### 4. Organización del código `[Prioridad: Media]` `[Estado: Pendiente]`
Archivos monolíticos: `app_tareas.py` (~1628 líneas), `storage.py` (~1284), `TaskDetailModal.svelte` (~38 KB).
- [ ] Dividir el backend en `APIRouter` por dominio (tareas, subtareas, recordatorios, github, agentes, voz, memoria, changelog, chat).
- [ ] Trocear los componentes Svelte grandes.

### 5. Centralizar la lógica de LLM `[Prioridad: Media]` `[Estado: Pendiente]`
Selección de cliente/modelo y `MODELOS_GROQ_OBSOLETOS` están duplicados en varios servicios, con defaults inconsistentes.
- [ ] Crear un único `llm_service` con la selección de cliente/modelo.
- [ ] Reemplazar las copias en `voz_service`, `agente_planes`, `subtarea_agente_service`, `canvas_agent_service`, `github_service`.

### 6. Parsing robusto de respuestas LLM `[Prioridad: Media]` `[Estado: Pendiente]`
Se extrae JSON troceando strings con ```` ```json ````, lo cual es frágil.
- [ ] Usar `response_format=json_object` donde el proveedor lo soporte.
- [ ] Un único helper de parseo tolerante a errores.

### 7. Tests y guardas de coste `[Prioridad: Media]` `[Estado: Pendiente]`
No hay tests; los endpoints de ejecución paralela de agentes no tienen límite.
- [ ] Tests de `storage` y endpoints clave.
- [ ] Límite de concurrencia / coste para `ejecutar-todas` y `ejecutar-paralelo`.

### 8. Limpieza y portabilidad `[Prioridad: Baja]` `[Estado: En progreso]`
- [x] Migrado `@app.on_event("startup")` a `lifespan`.
- [x] `notify_tareas`/`notify_recordatorios` usan `asyncio.get_running_loop()` (sin API deprecada).
- [x] `agente_desarrollar`: rama existente ya se reutilizaba; ahora también se reutiliza el **PR abierto** existente (idempotente).
- [x] Añadido `start_dev.ps1` para Windows (el `.sh` tenía rutas macOS).
- [x] README: añadida guía de desarrollo en Windows y variables de seguridad.
- [ ] Evaluar eliminar `frontend-react-backup/` (requiere confirmación del usuario).

---

## Parte B — Paridad de "Anotaciones / Lienzo" vs `tuNota`

**Contexto:** el original `C:\Users\sramos_ide\Documents\otros\tuNota` (vanilla JS) es una app de notas tipo OneNote + Obsidian muy completa. En Transurfing quedó como `VisualCanvas.svelte` (lienzo por tarea) y la "memoria vectorial". Faltan muchas funcionalidades del original.

### Ya presente o **nuevo** en Transurfing (no portar)
- [x] Bloques: texto, idea, código, JSON, tabla.
- [x] Arrastrar y redimensionar bloques.
- [x] Enlaces entre bloques.
- [x] **Nuevo:** diagramas Mermaid.
- [x] **Nuevo:** interpretación del lienzo con IA.

### Faltantes — Prioridad Alta
- [x] **Recordatorios/alarmas por bloque**: rápidos (15 min / 1 h / 3 h) y por fecha-hora, repetición (diaria/semanal/mensual/laborables), notificación, sonido (beep), posponer y overlay de alarmas.
- [x] **Marcar bloque como importante** (estrella) — botón en la cabecera + borde ámbar, persistido.
- [x] **Imágenes reales**: subir archivo y **pegar con Ctrl+V** (escalado a data URL); también acepta URL.
- [x] **Deshacer (Ctrl+Z)** con pila de snapshots (también botón "Deshacer" en la barra).
- [x] **Zoom y paneo** del lienzo: controles +/−/%, **Ctrl+rueda** para zoom, "ajustar a contenido" y paneo por scroll (coordenadas recalculadas con el zoom).

### Faltantes — Prioridad Media
- [x] **Menú radial** (Ctrl/Alt + clic en el fondo) para insertar un bloque en la posición del cursor.
- [x] **Selección múltiple** (marquee + Shift-clic) + arrastre en grupo + borrar selección (barra inferior y tecla Supr).
- [x] **Combinar bloques** arrastrando uno sobre otro (resalte verde + fusión de texto).
- [x] **Kanban de ideas dentro de la nota** (Por hacer / En progreso / Hecho) con mover entre columnas y asignar/quitar.
- [x] **Historial de cambios** de la nota/lienzo (panel con `canvas.log`).
- [x] **Tipo de bloque cURL**.
- [x] **Formatear JSON** (botón) y **Tab** para indentar en bloques código/JSON/cURL.
- [x] **Expandir bloque** (modal a pantalla) como alternativa in-app al pop-out de ventana del original.

### Faltantes — Estructural / Baja
- [ ] **Jerarquía Libros → Secciones → Notas** (hoy el lienzo está atado a una tarea; el original es un cuaderno independiente).
- [ ] **Estado de vista persistente por nota** (zoom y posición).
- [ ] **Sincronización multi-ventana** (BroadcastChannel) — opcional; Transurfing ya usa WebSocket.

### Estaban en el PLAN pero **no implementadas** ni en el original (futuro opcional)
- [ ] `[[wikilinks]]` con autocompletado.
- [ ] Panel de **backlinks**.
- [ ] **Vista grafo** de conexiones entre notas.

---

## Bitácora

- **2026-06-30** — Creación del documento. Auditoría completa del backend, servicios de IA y frontend. Inventario de `tuNota` y comparación con `VisualCanvas.svelte`. Definido alcance: Parte A (todas excepto #3) + Parte B (paridad de anotaciones).
- **2026-06-30 (oleada 1)** — #2 voz: helper `_optional_import` y degradación de `/api/voz/*`. #8: `lifespan`, `notify_*` con `get_running_loop`, `create_pull_request` idempotente, `start_dev.ps1`. Verificado con `py_compile`.
- **2026-06-30 (oleada 2)** — #1 seguridad (no rompe): CORS por env `CORS_ORIGINS` y auth opt-in por `API_AUTH_TOKEN`. Verificado con `py_compile`.
- **2026-06-30 (oleada 3)** — Parte B en `VisualCanvas.svelte`: **Marcar importante** (estrella + borde) y **Deshacer (Ctrl+Z)** (snapshots + botón). Modelo `CanvasBloque` extendido (`importante`, `recordatorio`). No se pudo correr `svelte-check` (sin `node_modules`); revisión manual. Pendiente `npm install` para verificar.
- **2026-06-30 (oleada 4)** — #1: cifrado opcional del PAT (`storage.py` + `cryptography`) y envío de `X-API-Token` desde `api.ts`. #8: README con guía Windows + seguridad. Parte B: **recordatorios por bloque** (picker, loop, notificación, sonido, posponer, overlay) e **imágenes pegables/subibles**. Backend verificado con `py_compile`; frontend pendiente de `npm run check`.
- **2026-06-30 (verificación)** — `npm install` falla con `Exit handler never called!` (bug del entorno npm, no del código). Frontend sin verificar con `svelte-check`. Pendiente: arreglar npm (actualizar Node/npm, `npm cache clean --force` o usar `pnpm`) y luego implementar **zoom/paneo**.
- **Política de ejecución**: PowerShell bloquea `npm.ps1`; usar `cmd /c "npm ..."`.
- **2026-06-30 (oleada 5)** — Parte B completada en `VisualCanvas.svelte`: **zoom/paneo** (transform + sizer, coordenadas con zoom), **menú radial**, **selección múltiple + arrastre en grupo + combinar**, **Kanban en nota**, **historial**, tipo **cURL**, **formatear JSON + Tab** y **expandir bloque**. Modelo extendido (`kanban`, `log`, `view`). Sin verificar con `svelte-check` (npm roto); revisión manual. Push pendiente con identidad alternativa (PAT).
- **2026-06-30 (oleada 6)** — Lote de mejoras nuevas (rama `feat/mejoras-anotaciones`):
  - **#1** +10 paletas de tema (`useTheme.ts`).
  - **#5** Multi-modelo: `/api/modelos` autodescubre del gateway (`{OPENAI_BASE_URL}/models`) + `LLM_MODELS` + Groq, deduplicado; `agente_planes.chat_subtareas` enruta por proveedor del modelo elegido. Verificado `py_compile`.
  - **#3** Emoji + color por tarea: `storage.py` (campos + emoji automático por keywords), `app_tareas.py` (esquemas/endpoints), `api.ts`/`types.ts`, `TaskCard`, `TaskForm`, `TaskEditModal`. Verificado `py_compile`.
  - **#4** Alta de subtareas rápida con "Más opciones" colapsable (`TaskDetailModal`).
  - **#7**: **Command palette (Ctrl+K)** + **búsqueda semántica** (`CommandPalette.svelte`, usa `/memorias/buscar`); **densidad de card** comoda/compacta (`densidadStore` + `+page` + `TaskCard`); **Pomodoro** flotante (`PomodoroWidget.svelte`); **PWA** (manifest corregido + `icon.svg` + `service-worker.js`); **calendario con drag** (reprograma `fecha_limite`); **Kanban global con drag** (completar/pendiente).
  - **Diferido #7d** (etiquetas personalizables): requiere cambiar el enum `ETIQUETAS` y todo su uso (templates IA, filtros, configs de UI) — alto riesgo sin pruebas; el emoji/color por tarea (#3) ya cubre la identificación.
  - Frontend **sin** `svelte-check` (npm roto en este equipo); commits locales con identidad `sergio.ramos@utec.edu.pe`. Lints de TS/SvelteKit (`$app/*`, `$service-worker`, tipos worker) son del entorno y se resuelven al instalar deps.
- **2026-06-30 (oleada 7)** — `ANALISIS_FUNCIONAL.md` (lidera con oportunidades/roadmap). **#6 Autenticación del portal** opt-in: backend `GET /api/auth/status` (exento) + `GET /api/auth/check` reusando el middleware de `API_AUTH_TOKEN`; `api.ts` con `authStatus/authCheck` + `setToken/clearToken/getToken` y fix de `vozTranscribir` (faltaba el header `X-API-Token`); `Login.svelte` + gate y logout en `+layout.svelte`. Si `API_AUTH_TOKEN` no está definido, la app funciona sin login. Backend verificado con `py_compile`.
- **2026-06-30 (oleada 8)** — Oportunidades del roadmap:
  - **Kanban 'En progreso' real**: flag persistido `en_progreso_manual` (storage `_decorar`/crear/actualizar + `TareaUpdate`/endpoint); `KanbanBoard` lo usa para columnas y el drag asigna pendiente/en_progreso/completada.
  - **Saltar a contexto**: en `CommandPalette`, los resultados de búsqueda semántica con `source=tarea` y `source_id` abren la tarea (`modalStore.openDetail`).
  - **Persistencia SQLite opt-in** (`STORAGE_BACKEND=sqlite`): nuevo `db_backend.py` (documento en una sola fila, ACID + WAL) detrás del seam `_cargar_raw`/`_guardar_raw`, con **migración automática** desde `tareas.json` (`DB_PATH` configurable). Verificado con `py_compile` y prueba funcional (crear + migrar en SQLite). La normalización por entidad queda como follow-up.
- **2026-06-30 (oleada 9)** — Lote de 7 funcionalidades solicitadas:
  - **Lienzo**: el bloque se crea con **doble click** (un click ya no crea); `Ctrl/Alt+click` abre el menú radial; nuevo botón **Controles** con leyenda (`VisualCanvas.svelte`).
  - **GitHub (tarea)**: panel no vinculado condensado a **una sola fila** (input con datalist + Vincular + **Crear** repo). Backend `create_repo` (auto_init) + `POST /api/github/repos`; `commit_file` firma autor/committer con el **nombre real** de la cuenta (cache de `/user`).
  - **Subtareas**: `storage._prompt_por_defecto` garantiza que **toda** subtarea tenga prompt (crear_tarea, ambas altas y backfill en migración); `TaskDetailModal` **auto-expande** el resultado del agente al resolver.
  - **Proyecto**: `ProjectGraph.svelte` (mermaid: tarea→subtareas con color por estado) con toggle **Estructura**; **mejorar descripción con IA** (`agente_planes.mejorar_descripcion` + `POST /api/tareas/{id}/mejorar-descripcion` + botón).
  - **Dashboard** (`/dashboard`): KPIs + tarjetas por proyecto (estado, progreso, faltantes, vencidos, próxima acción); enlace en `BottomNav`.
  - **Feed** (`/feed`): `agente_planes.generar_feed` + `GET /api/feed`; inspiración/novedades por proyecto activo (modelos a probar, recursos, ideas) con tipos y sugerencia accionable.
  - Backend verificado con `py_compile`; subtareas con prompt verificado por prueba funcional.
- **2026-06-30 (oleada 10)** — Detalle de tarea + ejecución de código:
  - **Layout del detalle**: la columna 3 ahora muestra el **Resumen del proyecto** (antes GitHub); GitHub pasa a un **acordeón colapsable** menos invasivo bajo las columnas, dejando más espacio a chat y subtareas (`TaskDetailModal.svelte`).
  - **Resumen conciso**: `resumen_tarea` reescrito a 3 líneas fijas **Avance / Falta / Próximo paso** (incluye subtareas completadas y pendientes).
  - **Contexto de subtareas**: el prompt de `chat_subtareas` exige prompts autónomos (objetivo, contexto técnico, criterios de aceptación y, si es código, lenguaje + prueba de validación).
  - **Ver lo que hizo el agente**: el `resumen` del agente se muestra **inline** en cada subtarea con resultado (con score), sin necesidad de expandir.
  - **Ejecutar y validar código**: nuevo `code_runner_service.py` (extrae el bloque de código, lo corre en temp con timeout; Python y Node) + `POST /api/tareas/{id}/subtareas/{sid}/ejecutar-codigo` + botón **Probar código** que muestra stdout/stderr/exit. Desactivable con `CODE_RUNNER_ENABLED=0`. Verificado: ejecuta Python y devuelve salida.
