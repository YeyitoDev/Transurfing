"""
app_tareas.py - Servicio de Tareas con Subtareas (FastAPI + JSON).

Sirve:
  - API REST en /api/*
  - Frontend estático en /

Ejecutar local:
    uvicorn app_tareas:app --reload --port 8077
Luego abre http://localhost:8077
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import secrets
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List, Dict

import fastapi
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Añadir directorio padre al path para importar stt_service, llm_service, etc.
_PARENT_DIR = Path(__file__).resolve().parent.parent
_PARENT_DIR_STR = str(_PARENT_DIR)
if _PARENT_DIR_STR not in sys.path:
    sys.path.insert(0, _PARENT_DIR_STR)

# Cargar variables de entorno del .env del directorio padre
load_dotenv(_PARENT_DIR / ".env")

import github_service
import storage
import vector_store

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y limpieza del servicio."""
    try:
        storage.asegurar_skill_changelog()
    except Exception as exc:
        logger.warning("No se pudo crear skill de changelog: %s", exc)
    yield


app = FastAPI(title="Servicio de Tareas", version="2.0", lifespan=lifespan)

# Orígenes CORS configurables por entorno (por defecto "*" para no romper el uso actual).
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Autenticación opcional por token. Si API_AUTH_TOKEN está definido, se exige en /api/*
# (excepto health y el callback OAuth de GitHub). Si no, el comportamiento es el actual.
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "").strip()
_AUTH_EXEMPT_PREFIXES = ("/api/health", "/api/github/oauth", "/api/auth/status")


@app.middleware("http")
async def _auth_middleware(request: fastapi.Request, call_next):
    if API_AUTH_TOKEN:
        path = request.url.path
        if path.startswith("/api/") and not path.startswith(_AUTH_EXEMPT_PREFIXES):
            provided = request.headers.get("X-API-Token", "")
            auth_header = request.headers.get("Authorization", "")
            if not provided and auth_header.lower().startswith("bearer "):
                provided = auth_header[7:].strip()
            if provided != API_AUTH_TOKEN:
                return fastapi.responses.JSONResponse({"detail": "No autorizado"}, status_code=401)
    return await call_next(request)


# ---------------------------------------------------------------------------
# WebSocket: sincronización en tiempo real
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, msg: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


mgr = ConnectionManager()


def notify_tareas():
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(mgr.broadcast({"type": "tareas_changed"}))


def notify_recordatorios():
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(mgr.broadcast({"type": "recordatorios_changed"}))


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TareaCreate(BaseModel):
    titulo: str = Field(min_length=1)
    descripcion: str = ""
    prioridad: str = "media"
    fecha_limite: Optional[str] = None
    etiqueta: str = "tarea"
    repetible: bool = False
    horas: List[str] = Field(default_factory=list)
    dias_semana: List[str] = Field(default_factory=list)
    objetivo: str = ""
    subtareas: Optional[List[str]] = None
    icono: str = ""
    color: str = ""


class TareaUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    prioridad: Optional[str] = None
    fecha_limite: Optional[str] = None
    completada_manual: Optional[bool] = None
    en_progreso_manual: Optional[bool] = None
    etiqueta: Optional[str] = None
    repetible: Optional[bool] = None
    horas: Optional[List[str]] = None
    dias_semana: Optional[List[str]] = None
    objetivo: Optional[str] = None
    icono: Optional[str] = None
    color: Optional[str] = None


class SubtareaCreate(BaseModel):
    titulo: str = Field(min_length=1)
    descripcion: Optional[str] = ""
    estado: Optional[str] = "pendiente"
    prompt: Optional[str] = ""
    repo: Optional[str] = ""
    archivo: Optional[str] = ""


class SubtareaUpdate(BaseModel):
    titulo: Optional[str] = None
    completada: Optional[bool] = None
    descripcion: Optional[str] = None
    estado: Optional[str] = None
    prompt: Optional[str] = None
    resultado: Optional[str] = None
    repo: Optional[str] = None
    archivo: Optional[str] = None
    commit_pendiente: Optional[bool] = None
    commit_sha: Optional[str] = None


class RecordatorioCreate(BaseModel):
    titulo: str = Field(min_length=1)
    fecha_hora: str = Field(min_length=1)  # formato YYYY-MM-DDTHH:MM
    tarea_id: str = Field(min_length=1)
    subtarea_id: Optional[str] = None


class RecordatorioUpdate(BaseModel):
    titulo: Optional[str] = None
    fecha_hora: Optional[str] = None
    estado: Optional[str] = None


class CanvasUpdate(BaseModel):
    canvas: Dict[str, Any] = Field(default_factory=dict)


class CanvasInterpretarRequest(BaseModel):
    modelo: Optional[str] = None


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "tareas"}


@app.get("/api/auth/status")
def auth_status():
    """Indica si la API exige token (login). Exento de autenticación."""
    return {"required": bool(API_AUTH_TOKEN)}


@app.get("/api/auth/check")
def auth_check():
    """Valida el token actual: el middleware ya lo exige, así que si responde, es válido."""
    return {"ok": True}


# ---------------------------------------------------------------------------
# API: Tareas
# ---------------------------------------------------------------------------

@app.get("/api/tareas")
def listar_tareas(solo_pendientes: bool = False):
    return storage.listar_tareas(solo_pendientes=solo_pendientes)


@app.get("/api/tareas/{tarea_id}")
def obtener_tarea(tarea_id: str):
    t = storage.obtener_tarea(tarea_id)
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    return t


@app.get("/api/tareas/{tarea_id}/canvas")
def obtener_canvas(tarea_id: str):
    t = storage.obtener_tarea(tarea_id)
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    return {"canvas": t.get("canvas")}


@app.post("/api/tareas/{tarea_id}/canvas")
def guardar_canvas(tarea_id: str, data: CanvasUpdate):
    t = storage.actualizar_canvas_tarea(tarea_id, data.canvas)
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    notify_tareas()
    return t


@app.post("/api/tareas/{tarea_id}/canvas/interpretar")
async def interpretar_canvas(tarea_id: str, data: CanvasInterpretarRequest):
    t = storage.obtener_tarea(tarea_id)
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    import canvas_agent_service
    res = await canvas_agent_service.interpretar_canvas(t, data.modelo)
    return res


class ScrumQuickWinsRequest(BaseModel):
    modelo: Optional[str] = None


@app.post("/api/tareas/{tarea_id}/scrum")
async def scrum_quick_wins(tarea_id: str, data: ScrumQuickWinsRequest):
    """Agente Scrum + Project Manager: recomienda quick wins hacia el objetivo."""
    t = storage.obtener_tarea(tarea_id)
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    import scrum_agent_service
    return await scrum_agent_service.analizar_quick_wins(t, data.modelo)


@app.post("/api/tareas", status_code=201)
def crear_tarea(data: TareaCreate):
    t = storage.crear_tarea(
        data.titulo, data.prioridad, data.fecha_limite, data.etiqueta, data.repetible, data.descripcion, data.horas, data.dias_semana, data.objetivo, subtareas=data.subtareas, icono=data.icono, color=data.color
    )
    notify_tareas()
    return t


@app.patch("/api/tareas/{tarea_id}")
def actualizar_tarea(tarea_id: str, data: TareaUpdate):
    t = storage.actualizar_tarea(
        tarea_id,
        titulo=data.titulo,
        descripcion=data.descripcion,
        prioridad=data.prioridad,
        fecha_limite=data.fecha_limite,
        completada_manual=data.completada_manual,
        etiqueta=data.etiqueta,
        repetible=data.repetible,
        horas=data.horas,
        dias_semana=data.dias_semana,
        objetivo=data.objetivo,
        icono=data.icono,
        color=data.color,
        en_progreso_manual=data.en_progreso_manual,
    )
    if t is None:
        raise HTTPException(404, "Tarea no encontrada")
    notify_tareas()
    return t


@app.delete("/api/tareas/{tarea_id}")
def eliminar_tarea(tarea_id: str):
    if not storage.eliminar_tarea(tarea_id):
        raise HTTPException(404, "Tarea no encontrada")
    notify_tareas()
    return {"mensaje": "Tarea eliminada"}


@app.get("/api/tareas/numero/{numero}")
def obtener_tarea_por_numero(numero: int):
    t = storage.obtener_tarea_por_numero(numero)
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    return t


@app.post("/api/tareas/numero/{numero}/subtareas", status_code=201)
def agregar_subtarea_por_numero(numero: int, data: SubtareaCreate):
    t = storage.agregar_subtarea_por_numero(
        numero,
        data.titulo,
        descripcion=data.descripcion or "",
        estado=data.estado or "pendiente",
        prompt=data.prompt or "",
        repo=data.repo or "",
        archivo=data.archivo or "",
    )
    if t is None:
        raise HTTPException(404, "Tarea no encontrada")
    notify_tareas()
    return t


# ---------------------------------------------------------------------------
# API: Subtareas
# ---------------------------------------------------------------------------

@app.post("/api/tareas/{tarea_id}/subtareas", status_code=201)
def agregar_subtarea(tarea_id: str, data: SubtareaCreate):
    t = storage.agregar_subtarea(
        tarea_id,
        data.titulo,
        descripcion=data.descripcion or "",
        estado=data.estado or "pendiente",
        prompt=data.prompt or "",
        repo=data.repo or "",
        archivo=data.archivo or "",
    )
    if t is None:
        raise HTTPException(404, "Tarea no encontrada")
    notify_tareas()
    return t


@app.patch("/api/subtareas/{subtarea_id}")
def actualizar_subtarea(subtarea_id: str, data: SubtareaUpdate):
    t = storage.actualizar_subtarea(
        subtarea_id,
        titulo=data.titulo,
        completada=data.completada,
        descripcion=data.descripcion,
        estado=data.estado,
        prompt=data.prompt,
        resultado=data.resultado,
        repo=data.repo,
        archivo=data.archivo,
        commit_pendiente=data.commit_pendiente,
        commit_sha=data.commit_sha,
    )
    if t is None:
        raise HTTPException(404, "Subtarea no encontrada")
    notify_tareas()
    return t


@app.delete("/api/subtareas/{subtarea_id}")
def eliminar_subtarea(subtarea_id: str):
    t = storage.eliminar_subtarea(subtarea_id)
    if t is None:
        raise HTTPException(404, "Subtarea no encontrada")
    notify_tareas()
    return t


# ---------------------------------------------------------------------------
# Ejecución de subtareas con agentes y commits
# ---------------------------------------------------------------------------

class SubtareaEjecutarRequest(BaseModel):
    modelo: Optional[str] = None


class SubtareaIterarRequest(BaseModel):
    modelo: Optional[str] = None
    instrucciones: Optional[str] = None


@app.post("/api/tareas/{tarea_id}/subtareas/{subtarea_id}/ejecutar")
async def ejecutar_subtarea_endpoint(tarea_id: str, subtarea_id: str, data: SubtareaEjecutarRequest):
    """Ejecuta una subtarea con el pipeline Planner -> Executor -> Reviewer."""
    import subtarea_agente_service
    res = await subtarea_agente_service.ejecutar_subtarea(tarea_id, subtarea_id, modelo=data.modelo)
    if res.get("ok"):
        notify_tareas()
    return res


class EjecutarCodigoRequest(BaseModel):
    codigo: str = ""
    lenguaje: str = ""


@app.post("/api/tareas/{tarea_id}/subtareas/{subtarea_id}/ejecutar-codigo")
def ejecutar_codigo_subtarea(tarea_id: str, subtarea_id: str, data: EjecutarCodigoRequest):
    """Ejecuta el código de una subtarea (o el provisto) y devuelve la salida para validar que funciona."""
    import code_runner_service
    codigo = data.codigo
    lenguaje = data.lenguaje
    if not codigo.strip():
        sub = storage.obtener_subtarea(subtarea_id)
        if not sub:
            raise HTTPException(status_code=404, detail="Subtarea no encontrada")
        codigo, lang_detect = code_runner_service.extraer_codigo(sub.get("resultado", ""))
        lenguaje = lenguaje or lang_detect
    return code_runner_service.ejecutar_codigo(codigo, lenguaje)


@app.post("/api/tareas/{tarea_id}/subtareas/{subtarea_id}/iterar")
async def iterar_subtarea_endpoint(tarea_id: str, subtarea_id: str, data: SubtareaIterarRequest):
    """Re-ejecuta el pipeline mejorando sobre el resultado previo de la subtarea."""
    import subtarea_agente_service
    res = await subtarea_agente_service.iterar_subtarea(
        tarea_id, subtarea_id, modelo=data.modelo, instrucciones_extra=data.instrucciones
    )
    if res.get("ok"):
        notify_tareas()
    return res


@app.post("/api/tareas/{tarea_id}/subtareas/ejecutar-todas")
async def ejecutar_subtareas_todas_endpoint(tarea_id: str, data: SubtareaEjecutarRequest):
    """Ejecuta todas las subtareas pendientes de una tarea en paralelo."""
    import subtarea_agente_service
    res = await subtarea_agente_service.ejecutar_subtareas_pendientes(tarea_id, modelo=data.modelo)
    if res.get("ok"):
        notify_tareas()
    return res


@app.get("/api/tareas/{tarea_id}/subtareas/{subtarea_id}/progreso")
async def progreso_subtarea_endpoint(tarea_id: str, subtarea_id: str):
    """Devuelve el paso actual de ejecución de una subtarea para animaciones del frontend."""
    import subtarea_agente_service
    return subtarea_agente_service.obtener_progreso(subtarea_id) or {"paso": "esperando", "detalle": "Sin actividad reciente", "estado": "esperando"}


@app.post("/api/tareas/{tarea_id}/subtareas/{subtarea_id}/commit")
async def commitear_subtarea_endpoint(tarea_id: str, subtarea_id: str):
    """Sube el resultado de una subtarea al repositorio vinculado."""
    import subtarea_agente_service
    res = await subtarea_agente_service.commitear_resultado(tarea_id, subtarea_id)
    notify_tareas()
    return res


@app.post("/api/tareas/{tarea_id}/subtareas/sincronizar")
async def sincronizar_subtareas_endpoint(tarea_id: str):
    """Reintenta subir subtareas marcadas como commit pendiente."""
    import subtarea_agente_service
    res = await subtarea_agente_service.sincronizar_commits_pendientes(tarea_id)
    notify_tareas()
    return res


# ---------------------------------------------------------------------------
# API: Recordatorios / Alarmas
# ---------------------------------------------------------------------------

@app.get("/api/recordatorios")
def listar_recordatorios(solo_pendientes: bool = True):
    return storage.listar_recordatorios(solo_pendientes=solo_pendientes)


@app.post("/api/recordatorios", status_code=201)
def crear_recordatorio(data: RecordatorioCreate):
    r = storage.crear_recordatorio(data.titulo, data.fecha_hora, data.tarea_id, data.subtarea_id)
    if r is None:
        raise HTTPException(404, "Tarea o subtarea no encontrada")
    notify_recordatorios()
    return r


@app.patch("/api/recordatorios/{recordatorio_id}")
def actualizar_recordatorio(recordatorio_id: str, data: RecordatorioUpdate):
    r = storage.actualizar_recordatorio(recordatorio_id, data.titulo, data.fecha_hora, data.estado)
    if r is None:
        raise HTTPException(404, "Recordatorio no encontrado")
    notify_recordatorios()
    return r


@app.delete("/api/recordatorios/{recordatorio_id}")
def eliminar_recordatorio(recordatorio_id: str):
    if not storage.eliminar_recordatorio(recordatorio_id):
        raise HTTPException(404, "Recordatorio no encontrado")
    notify_recordatorios()
    return {"mensaje": "Recordatorio eliminado"}


# ---------------------------------------------------------------------------
# Agente: resumen inteligente de tareas
# ---------------------------------------------------------------------------

@app.get("/api/agente/recordatorio")
def agente_recordatorio():
    """Genera un resumen inteligente con status, tareas estancadas, ideas y noticias."""
    from datetime import date, timedelta

    tareas = storage.listar_tareas()
    pendientes = [t for t in tareas if t["estado"] != "completada"]
    completadas = [t for t in tareas if t["estado"] == "completada"]
    hoy = date.today().isoformat()

    # === STATUS ===
    en_progreso = [t for t in pendientes if t["progreso"] > 0 and t["progreso"] < 100]
    sin_empezar = [t for t in pendientes if t["progreso"] == 0]
    vencidas = [t for t in pendientes if t.get("fecha_limite") and t["fecha_limite"] < hoy]

    status_lineas = []
    status_lineas.append(f"📊 Status: {len(pendientes)} pendientes, {len(completadas)} completadas")
    if en_progreso:
        status_lineas.append(f"🔄 En progreso: {len(en_progreso)} tarea(s)")
    if vencidas:
        status_lineas.append(f"⚠️ Vencidas: {len(vencidas)} tarea(s)")

    # === TAREAS ESTANCADAS (sin avanzar >3 días) ===
    hace_3 = (date.today() - timedelta(days=3)).isoformat()
    estancadas = []
    for t in pendientes:
        creada = t.get("creada_en", hoy)
        ultima_mod = t.get("completada_en") or creada
        if creada < hace_3 and t["progreso"] < 100:
            dias = (date.today() - date.fromisoformat(creada)).days
            estancadas.append({
                "id": t["id"],
                "titulo": t["titulo"],
                "descripcion": t.get("descripcion", ""),
                "dias": dias,
                "progreso": t["progreso"],
                "etiqueta": t["etiqueta"],
                "prioridad": t["prioridad"],
            })
    estancadas.sort(key=lambda x: x["dias"], reverse=True)

    estancadas_lineas = []
    if estancadas:
        estancadas_lineas.append(f"🚫 Tareas estancadas ({len(estancadas)}):")
        for t in estancadas[:3]:
            estancadas_lineas.append(f"  • {t['titulo']} — {t['dias']} días sin avanzar ({t['progreso']}%)")
        if len(estancadas) > 3:
            estancadas_lineas.append(f"  ... y {len(estancadas) - 3} más")
    else:
        estancadas_lineas.append("✅ No tienes tareas estancadas")

    # === IDEAS ===
    emprendimiento = [t for t in pendientes if t["etiqueta"] == "emprendimiento"]
    ideas = []
    for t in emprendimiento:
        sugerencias = []
        if t["progreso"] == 0:
            sugerencias.append("Define el primer paso concreto para arrancar")
        elif t["progreso"] < 50:
            sugerencias.append("Divide en subtareas más pequeñas para mantener momentum")
        else:
            sugerencias.append("Estás cerca de completarla — define qué falta para el cierre")
        if not t.get("descripcion"):
            sugerencias.append("Añade una descripción para clarificar el objetivo")
        ideas.append({
            "tarea_id": t["id"],
            "titulo": t["titulo"],
            "progreso": t["progreso"],
            "sugerencia": "; ".join(sugerencias),
        })

    ideas_lineas = []
    if ideas:
        ideas_lineas.append(f"�💡 Ideas para mejorar ({len(ideas)}):")
        for i in ideas[:3]:
            ideas_lineas.append(f"  • {i['titulo']} ({i['progreso']}%): {i['sugerencia']}")
    else:
        ideas_lineas.append("�💡 No tienes proyectos de emprendimiento activos")

    # === NOTICIAS / INVESTIGACIÓN ===
    investigacion = [t for t in pendientes if t["etiqueta"] == "investigacion"]
    noticias = []
    for t in investigacion:
        temas = []
        # Extraer palabras clave del título y descripción
        texto = (t["titulo"] + " " + t.get("descripcion", "")).lower()
        temas_detectados = []
        if "ia" in texto or "inteligencia artificial" in texto or "llm" in texto:
            temas_detectados.append("Nuevos modelos LLM y avances en IA están publicándose semanalmente — revisa arxiv.org")
        if "react" in texto or "frontend" in texto or "web" in texto:
            temas_detectados.append("React 19 y Server Components son tendencia — considera migrar")
        if "python" in texto or "fastapi" in texto or "backend" in texto:
            temas_detectados.append("FastAPI 0.100+ soporta lifespan async — actualiza si usas versiones viejas")
        if "pwa" in texto or "mobile" in texto:
            temas_detectados.append("PWA con Workbox y Vite es el estándar actual para apps instalables")
        if not temas_detectados:
            temas_detectados.append(f"Busca artículos recientes sobre: {t['titulo']}")
        noticias.append({
            "tarea_id": t["id"],
            "titulo": t["titulo"],
            "temas": temas_detectados,
        })

    noticias_lineas = []
    if noticias:
        noticias_lineas.append(f"🔬 Investigación activa ({len(noticias)}):")
        for n in noticias[:2]:
            noticias_lineas.append(f"  • {n['titulo']}:")
            for tema in n["temas"][:2]:
                noticias_lineas.append(f"    → {tema}")
    else:
        noticias_lineas.append("🔬 No tienes tareas de investigación activas")

    # === PREGUNTAS PROACTIVAS ===
    preguntas = []
    if vencidas:
        preguntas.append(f"¿Quieres que reagende las {len(vencidas)} tarea(s) vencida(s)?")
    if en_progreso:
        t = en_progreso[0]
        preguntas.append(f"¿Avanzaste en '{t['titulo']}'? Lleva {t['progreso']}%.")
    if sin_empezar:
        t = sin_empezar[0]
        preguntas.append(f"¿Quieres que divida '{t['titulo']}' en pasos más pequeños?")
    if emprendimiento:
        t = emprendimiento[0]
        preguntas.append(f"¿Necesitas ideas para avanzar en '{t['titulo']}'?")
    if noticias:
        t = noticias[0]
        preguntas.append(f"¿Te interesa un resumen de novedades sobre '{t['titulo']}'?")
    if not preguntas:
        preguntas.append("¿Quieres que hagamos un repaso de tus objetivos de hoy?")

    # === MENSAJE COMPLETO ===
    mensaje = "\n\n".join([
        "\n".join(status_lineas),
        "\n".join(estancadas_lineas),
        "\n".join(ideas_lineas),
        "\n".join(noticias_lineas),
    ])

    # === DESTACADAS ===
    destacadas = sorted(pendientes, key=lambda t: (
        0 if t["prioridad"] == "alta" else 1 if t["prioridad"] == "media" else 2,
        0 if t.get("fecha_limite") and t["fecha_limite"] < hoy else 1
    ))[:5]

    return {
        "titulo": f"Tienes {len(pendientes)} tarea(s) pendiente(s)" + (f", {len(vencidas)} vencida(s)" if vencidas else ""),
        "mensaje": mensaje,
        "tareas": [{"id": t["id"], "titulo": t["titulo"], "prioridad": t["prioridad"], "descripcion": t.get("descripcion", ""), "fecha_limite": t.get("fecha_limite"), "vencida": t.get("fecha_limite") and t["fecha_limite"] < hoy} for t in destacadas],
        "total": len(pendientes),
        "vencidas": len(vencidas),
        "alta": len([t for t in pendientes if t["prioridad"] == "alta"]),
        "media": len([t for t in pendientes if t["prioridad"] == "media"]),
        "baja": len([t for t in pendientes if t["prioridad"] == "baja"]),
        "en_progreso": len(en_progreso),
        "sin_empezar": len(sin_empezar),
        "estancadas": estancadas,
        "ideas": ideas,
        "noticias": noticias,
        "preguntas": preguntas,
    }


@app.get("/api/agente/checkin")
def agente_checkin():
    """Genera un mensaje proactivo de check-in para el usuario."""
    from datetime import date, timedelta

    tareas = storage.listar_tareas()
    pendientes = [t for t in tareas if t["estado"] != "completada"]
    hoy = date.today().isoformat()
    vencidas = [t for t in pendientes if t.get("fecha_limite") and t["fecha_limite"] < hoy]
    en_progreso = [t for t in pendientes if 0 < t["progreso"] < 100]
    sin_empezar = [t for t in pendientes if t["progreso"] == 0]

    contexto = []
    if vencidas:
        contexto.append(f"Tienes {len(vencidas)} tarea(s) vencida(s).")
    if en_progreso:
        contexto.append(f"{len(en_progreso)} tarea(s) en progreso.")
    if sin_empezar:
        contexto.append(f"{len(sin_empezar)} tarea(s) sin empezar.")
    if not pendientes:
        contexto.append("No tienes tareas pendientes. ¡Buen momento para planificar!")

    preguntas = []
    if vencidas:
        preguntas.append("¿Reagendamos lo vencido?")
    if en_progreso:
        preguntas.append(f"¿Avanzaste en '{en_progreso[0]['titulo']}'?")
    if sin_empezar:
        preguntas.append(f"¿Empezamos con '{sin_empezar[0]['titulo']}'?")
    if not preguntas:
        preguntas.append("¿Qué objetivo quieres plantear hoy?")

    mensaje = " ".join(contexto)
    if not mensaje:
        mensaje = "Hola Sergio, ¿cómo va tu día?"

    return {
        "titulo": "Check-in de Jarvis",
        "mensaje": mensaje,
        "preguntas": preguntas,
        "total": len(pendientes),
        "vencidas": len(vencidas),
    }


# ---------------------------------------------------------------------------
# Voz: procesamiento de comandos con LLM
# ---------------------------------------------------------------------------

class VozComando(BaseModel):
    texto: str = Field(min_length=1)


@app.post("/api/voz/procesar")
async def voz_procesar(data: VozComando):
    import voz_service
    return await voz_service.procesar_comando_voz(data.texto)


class VozConfirmar(BaseModel):
    draft: dict


@app.post("/api/voz/confirmar")
def voz_confirmar(data: VozConfirmar):
    import voz_service
    resultado = voz_service.confirmar_tarea(data.draft)
    if resultado.get("tarea_creada"):
        notify_tareas()
    return resultado


class VozActualizar(BaseModel):
    tarea_id: str
    cambios: dict


@app.post("/api/voz/actualizar")
def voz_actualizar(data: VozActualizar):
    import voz_service
    resultado = voz_service.actualizar_tarea(data.tarea_id, data.cambios)
    if resultado.get("tarea_actualizada"):
        notify_tareas()
    return resultado


@app.get("/api/voz/resumen")
async def voz_resumen():
    import voz_service
    mensaje = await voz_service.generar_resumen_narrativo()
    return {"mensaje": mensaje}


# ---------------------------------------------------------------------------
# Agente especializado: planes de estudio/proyectos y búsqueda de novedades
# ---------------------------------------------------------------------------

class AgentePlanRequest(BaseModel):
    objetivo: str = Field(min_length=3)
    semanas: int = 4


@app.post("/api/agente/plan")
async def agente_plan(data: AgentePlanRequest):
    import agente_planes
    return await agente_planes.generar_plan(data.objetivo, data.semanas)


class AgenteBuscarRequest(BaseModel):
    tema: str = Field(min_length=3)


@app.post("/api/agente/buscar")
async def agente_buscar(data: AgenteBuscarRequest):
    import agente_planes
    return await agente_planes.buscar_novedades(data.tema)


@app.get("/api/feed")
async def feed_endpoint():
    """Genera un feed de inspiración/novedades para los proyectos activos."""
    import agente_planes
    tareas = storage.listar_tareas(solo_pendientes=True)
    return await agente_planes.generar_feed(tareas)


@app.get("/api/feed-vivo")
async def feed_vivo_endpoint(force: bool = False):
    """Feed vivo (experimental): búsquedas reales en internet con scoring objetivo y medible."""
    import feed_vivo_service
    tareas = storage.listar_tareas(solo_pendientes=True)
    try:
        return await feed_vivo_service.generar_feed_vivo(tareas, force=force)
    except Exception as exc:
        logger.exception("Error generando feed vivo: %s", exc)
        return {"experimental": True, "enabled": True, "items": [], "preguntas": [],
                "error": str(exc), "generado_en": ""}


class AgenteIdeaRequest(BaseModel):
    prompt: str = Field(min_length=5)


@app.post("/api/agente/idea")
async def agente_idea(data: AgenteIdeaRequest):
    """Analiza una idea, genera un informe profundo y crea una tarea tipo 'idea'."""
    import agente_planes
    resultado = await agente_planes.analizar_idea(data.prompt)
    if resultado.get("accion") != "idea_analizada":
        return resultado

    tarea = storage.crear_tarea(
        titulo=resultado["titulo"],
        prioridad=resultado.get("prioridad", "media"),
        etiqueta="idea",
        descripcion=resultado.get("descripcion", ""),
        objetivo=resultado.get("objetivo", ""),
        documento=resultado.get("documento", ""),
        subtareas=resultado.get("subtareas", []),
    )
    notify_tareas()
    return {"accion": "idea_creada", "mensaje": f"💡 Idea analizada y creada: {tarea['titulo']}", "tarea": tarea}


class ResumenTareaRequest(BaseModel):
    tarea_id: str = Field(min_length=1)


class ChatSesionCreate(BaseModel):
    tarea_id: str = Field(min_length=1)
    nombre: str = "Nueva sesión"


class ChatMensajeCreate(BaseModel):
    tarea_id: str = Field(min_length=1)
    sesion_id: str = Field(min_length=1)
    texto: str = Field(min_length=1)
    modelo: Optional[str] = None
    archivos: Optional[List[Dict[str, str]]] = None


@app.post("/api/tareas/{tarea_id}/chat-sesiones")
def crear_chat_sesion_endpoint(tarea_id: str, data: ChatSesionCreate):
    """Crea una nueva sesión de chat dentro de una tarea."""
    tarea = storage.crear_chat_sesion(tarea_id, data.nombre)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    notify_tareas()
    return {"tarea": tarea}


@app.post("/api/tareas/{tarea_id}/chat-mensajes")
async def enviar_chat_mensaje_endpoint(tarea_id: str, data: ChatMensajeCreate):
    """Envía un mensaje al chat, obtiene respuesta del agente y genera subtareas sugeridas."""
    logger.info("[chat] tarea=%s sesion=%s texto=%s", tarea_id, data.sesion_id, data.texto[:80])
    tarea = storage.obtener_tarea(tarea_id)
    if not tarea:
        logger.warning("[chat] tarea no encontrada: %s", tarea_id)
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Guardar mensaje del usuario
    storage.agregar_chat_mensaje(tarea_id, data.sesion_id, "user", data.texto)

    # Generar respuesta del agente
    import agente_planes
    archivos = data.archivos or []
    respuesta = await agente_planes.chat_subtareas(
        tarea, data.sesion_id, data.texto, modelo=data.modelo, archivos=archivos
    )
    logger.info("[chat] respuesta: subtareas=%s proxima=%s titulo=%s", respuesta.get("subtareas"), respuesta.get("proxima_alta_valor", "")[:40], respuesta.get("titulo_sesion", ""))

    # Guardar respuesta del agente
    tarea = storage.agregar_chat_mensaje(tarea_id, data.sesion_id, "assistant", respuesta["respuesta"])

    # Renombrar sesión automáticamente si es el primer mensaje y el agente sugirió título
    if respuesta.get("titulo_sesion"):
        tarea = storage.renombrar_chat_sesion(tarea_id, data.sesion_id, respuesta["titulo_sesion"])

    # Actualizar próxima acción de alto valor
    if respuesta.get("proxima_alta_valor"):
        tarea = storage.actualizar_proxima_alta_valor(tarea_id, respuesta["proxima_alta_valor"])

    # Aplicar subtareas generadas si el usuario las aceptó implícitamente
    if respuesta.get("subtareas"):
        for sub in respuesta["subtareas"]:
            if isinstance(sub, dict):
                storage.agregar_subtarea(
                    tarea_id,
                    sub.get("titulo", ""),
                    prompt=sub.get("prompt", ""),
                    archivo=sub.get("archivo", ""),
                    repo=tarea.get("github_repo", ""),
                )
            elif isinstance(sub, str):
                storage.agregar_subtarea(tarea_id, sub)
        tarea = storage.obtener_tarea(tarea_id)

    notify_tareas()
    return {"tarea": tarea, "respuesta": respuesta["respuesta"]}


@app.post("/api/tareas/{tarea_id}/proxima-alta-valor")
def actualizar_proxima_alta_valor_endpoint(tarea_id: str, data: ChatMensajeCreate):
    """Actualiza manualmente el resumen de la próxima acción de mayor valor."""
    tarea = storage.actualizar_proxima_alta_valor(tarea_id, data.texto)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    notify_tareas()
    return {"tarea": tarea}


@app.post("/api/agente/resumen-tarea")
async def resumen_tarea(data: ResumenTareaRequest):
    """Genera un resumen concreto de qué hacer con la tarea."""
    import agente_planes
    tarea = storage.obtener_tarea(data.tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    try:
        resumen = await agente_planes.resumen_tarea(tarea)
        return {"resumen": resumen}
    except Exception as exc:
        logger.exception("Error generando resumen de tarea: %s", exc)
        return {"resumen": "No pude generar el resumen en este momento."}


@app.get("/api/agente/resumen-dashboard")
async def resumen_dashboard_endpoint(etiqueta: Optional[str] = None):
    """Genera un análisis narrativo del estado de los proyectos (opcionalmente por categoría)."""
    import agente_planes
    tareas = storage.listar_tareas()
    if etiqueta and etiqueta != "todas":
        tareas = [t for t in tareas if t.get("etiqueta") == etiqueta]
    try:
        resumen = await agente_planes.resumen_dashboard(tareas)
        return {"resumen": resumen}
    except Exception as exc:
        logger.exception("Error generando resumen de dashboard: %s", exc)
        return {"resumen": "", "error": "No pude generar el análisis en este momento."}


@app.post("/api/tareas/{tarea_id}/mejorar-descripcion")
async def mejorar_descripcion_endpoint(tarea_id: str):
    """Mejora la descripción del proyecto/tarea con IA y la guarda."""
    import agente_planes
    tarea = storage.obtener_tarea(tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    nueva = await agente_planes.mejorar_descripcion(tarea)
    if not nueva:
        raise HTTPException(status_code=502, detail="No se pudo generar la descripción")
    actualizada = storage.actualizar_tarea(tarea_id, descripcion=nueva)
    notify_tareas()
    return {"tarea": actualizada, "descripcion": nueva}


# ---------------------------------------------------------------------------
# Agentes especializados
# ---------------------------------------------------------------------------

class AgenteCreate(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: str = ""
    modelo: str = "llama-3.3-70b-versatile"
    system_prompt: str = ""
    skills: List[str] = []
    knowledge: List[str] = []


class AgenteUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    modelo: Optional[str] = None
    system_prompt: Optional[str] = None
    skills: Optional[List[str]] = None
    knowledge: Optional[List[str]] = None


class SkillCreate(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: str = ""
    instrucciones: str = ""


class KnowledgeCreate(BaseModel):
    nombre: str = Field(min_length=1)
    tipo: str = "texto"
    contenido: str = ""


class EjecutarAgente(BaseModel):
    prompt: str = Field(min_length=1)
    tarea_id: Optional[str] = None


class EjecutarParalelo(BaseModel):
    agente_ids: List[str] = Field(min_length=1)
    prompt: str = Field(min_length=1)


@app.get("/api/agentes")
def listar_agentes_endpoint():
    return {
        "agentes": storage.listar_agentes(),
        "skills": storage.listar_skills(),
        "knowledge": storage.listar_knowledge(),
    }


@app.post("/api/agentes")
def crear_agente_endpoint(data: AgenteCreate):
    agente = storage.crear_agente(data.nombre, data.descripcion, data.modelo, data.system_prompt, data.skills, data.knowledge)
    return {"agente": agente}


@app.patch("/api/agentes/{agente_id}")
def actualizar_agente_endpoint(agente_id: str, data: AgenteUpdate):
    agente = storage.actualizar_agente(
        agente_id,
        nombre=data.nombre,
        descripcion=data.descripcion,
        modelo=data.modelo,
        system_prompt=data.system_prompt,
        skills=data.skills,
        knowledge=data.knowledge,
    )
    if not agente:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    return {"agente": agente}


@app.delete("/api/agentes/{agente_id}")
def eliminar_agente_endpoint(agente_id: str):
    if not storage.eliminar_agente(agente_id):
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    return {"ok": True}


@app.post("/api/agentes/{agente_id}/ejecutar")
async def ejecutar_agente_endpoint(agente_id: str, data: EjecutarAgente):
    agente = storage.obtener_agente(agente_id)
    if not agente:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    import agente_planes
    try:
        respuesta = await agente_planes.ejecutar_agente(agente, data.prompt, data.tarea_id)
        return {"respuesta": respuesta}
    except Exception as exc:
        logger.exception("Error ejecutando agente %s", agente_id)
        raise HTTPException(status_code=502, detail=f"Error del agente: {exc}")


@app.post("/api/agentes/ejecutar-paralelo")
async def ejecutar_agentes_paralelo_endpoint(data: EjecutarParalelo):
    import agente_planes
    import asyncio

    async def ejecutar(agente_id: str):
        agente = storage.obtener_agente(agente_id)
        if not agente:
            return {"agente_id": agente_id, "error": "Agente no encontrado"}
        try:
            respuesta = await agente_planes.ejecutar_agente(agente, data.prompt)
            return {"agente_id": agente_id, "agente_nombre": agente["nombre"], "respuesta": respuesta}
        except Exception as exc:
            logger.exception("Error ejecutando agente %s", agente_id)
            return {"agente_id": agente_id, "agente_nombre": agente.get("nombre", "?"), "error": str(exc)}

    resultados = await asyncio.gather(*[ejecutar(aid) for aid in data.agente_ids])
    return {"resultados": resultados}


@app.post("/api/skills")
def crear_skill_endpoint(data: SkillCreate):
    skill = storage.crear_skill(data.nombre, data.descripcion, data.instrucciones)
    return {"skill": skill}


@app.patch("/api/skills/{skill_id}")
def actualizar_skill_endpoint(skill_id: str, data: SkillCreate):
    skill = storage.actualizar_skill(skill_id, data.nombre, data.descripcion, data.instrucciones)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill no encontrado")
    return {"skill": skill}


@app.delete("/api/skills/{skill_id}")
def eliminar_skill_endpoint(skill_id: str):
    if not storage.eliminar_skill(skill_id):
        raise HTTPException(status_code=404, detail="Skill no encontrado")
    return {"ok": True}


@app.post("/api/knowledge")
def crear_knowledge_endpoint(data: KnowledgeCreate):
    k = storage.crear_knowledge(data.nombre, data.tipo, data.contenido)
    return {"knowledge": k}


@app.patch("/api/knowledge/{knowledge_id}")
def actualizar_knowledge_endpoint(knowledge_id: str, data: KnowledgeCreate):
    k = storage.actualizar_knowledge(knowledge_id, data.nombre, data.tipo, data.contenido)
    if not k:
        raise HTTPException(status_code=404, detail="Knowledge no encontrado")
    return {"knowledge": k}


@app.delete("/api/knowledge/{knowledge_id}")
def eliminar_knowledge_endpoint(knowledge_id: str):
    if not storage.eliminar_knowledge(knowledge_id):
        raise HTTPException(status_code=404, detail="Knowledge no encontrado")
    return {"ok": True}


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

class GitHubConfigCreate(BaseModel):
    pat: str = Field(min_length=1)
    username: str = ""


class GitHubLinkRepo(BaseModel):
    repo: str = Field(min_length=1)


class GitHubRepoCreate(BaseModel):
    name: str = Field(min_length=1)
    private: bool = True
    description: str = ""


class GitHubDesarrollar(BaseModel):
    prompt: str = ""


class ChangelogEntry(BaseModel):
    version: str = Field(min_length=1)
    seccion: str = Field(min_length=1)
    cambios: List[str] = Field(default_factory=list)
    casos_qa: List[str] = Field(default_factory=list)
    fecha: Optional[str] = None
    impacto: str = "medio"


class ChangelogGenerate(BaseModel):
    cambios: str = Field(min_length=1)
    version: str = "Unreleased"
    seccion: str = "General"
    impacto: str = "medio"


# Almacén temporal de estados OAuth (state -> timestamp). Expira en 10 minutos.
_oauth_states: Dict[str, float] = {}


def _public_url() -> str:
    """URL pública del backend, usada para construir el callback de OAuth."""
    return os.getenv("TAREAS_URL", "http://localhost:8077").rstrip("/")


@app.get("/api/github/config")
def get_github_config_endpoint():
    """Devuelve la configuración de GitHub (sin el PAT)."""
    cfg = storage.get_github_config()
    return {
        "username": cfg.get("username", ""),
        "configured": bool(cfg.get("pat")),
        "oauth_available": github_service.is_oauth_configured(),
    }


@app.post("/api/github/config")
async def set_github_config_endpoint(data: GitHubConfigCreate):
    """Guarda PAT y valida contra la API de GitHub (modo manual)."""
    valid = await github_service.validate_token(data.pat)
    if not valid["ok"]:
        raise HTTPException(status_code=400, detail=valid["error"])
    username = data.username.strip() or valid["username"]
    storage.set_github_config(data.pat, username)
    return {"ok": True, "username": username, "scopes": valid.get("scopes", [])}


@app.get("/api/github/oauth")
def start_github_oauth():
    """Inicia el flujo OAuth: redirige al usuario a GitHub."""
    if not github_service.is_oauth_configured():
        raise HTTPException(status_code=400, detail="GitHub OAuth no está configurado en el servidor (faltan GITHUB_CLIENT_ID y GITHUB_CLIENT_SECRET)")
    public_url = _public_url()
    if "localhost" in public_url or "127.0.0.1" in public_url:
        raise HTTPException(
            status_code=400,
            detail=f"TAREAS_URL apunta a localhost ({public_url}). Configura TAREAS_URL con la URL pública de la app (ej: https://transurfing.fly.dev)"
        )
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = time.time() + 600
    # Limpiar estados expirados
    now = time.time()
    for s in list(_oauth_states.keys()):
        if _oauth_states[s] < now:
            del _oauth_states[s]
    redirect_uri = f"{public_url}/api/github/oauth/callback"
    try:
        url = github_service.get_oauth_url(state, redirect_uri)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url, "redirect_uri": redirect_uri}


@app.get("/api/github/oauth/callback")
async def github_oauth_callback(code: str = "", state: str = ""):
    """Callback de GitHub OAuth: intercambia el código por un token y redirige al frontend."""
    public_url = _public_url()
    frontend_url = f"{public_url}/github"
    redirect_uri = f"{public_url}/api/github/oauth/callback"
    logger.info("[github oauth callback] code=%s state=%s redirect_uri=%s", bool(code), bool(state), redirect_uri)
    if not code:
        return fastapi.responses.RedirectResponse(f"{frontend_url}?error=no_code")
    if state not in _oauth_states:
        logger.warning("[github oauth callback] state inválido: %s", state)
        return fastapi.responses.RedirectResponse(f"{frontend_url}?error=invalid_state")
    del _oauth_states[state]

    result = await github_service.exchange_oauth_code(code, redirect_uri)
    if not result["ok"]:
        logger.warning("[github oauth callback] error intercambiando código: %s", result.get("error"))
        return fastapi.responses.RedirectResponse(f"{frontend_url}?error={result.get('error', 'oauth_error')}")

    storage.set_github_config(result["access_token"], result["username"])
    logger.info("[github oauth callback] usuario conectado: %s", result.get("username"))
    return fastapi.responses.RedirectResponse(f"{frontend_url}?success=1")


@app.get("/api/github/diagnostico")
def github_diagnostico():
    """Devuelve información de diagnóstico para depurar la conexión GitHub."""
    public_url = _public_url()
    cfg = github_service.get_user_config()
    callback_url = f"{public_url}/api/github/oauth/callback"
    problemas = []
    if "localhost" in public_url or "127.0.0.1" in public_url:
        problemas.append("TAREAS_URL apunta a localhost; configura la URL pública de Fly.io.")
    if not github_service.is_oauth_configured():
        problemas.append("GITHUB_CLIENT_ID y/o GITHUB_CLIENT_SECRET no están configurados.")
    return {
        "tareas_url": public_url,
        "oauth_configurado": github_service.is_oauth_configured(),
        "callback_url": callback_url,
        "frontend_url": f"{public_url}/github",
        "github_configurado": bool(cfg.get("pat")),
        "github_username": cfg.get("username", ""),
        "problemas": problemas,
        "mensaje": "Asegúrate de que la Callback URL esté registrada en tu GitHub OAuth App con la URL indicada en 'callback_url'.",
    }


@app.get("/api/github/callback-test")
def github_callback_test():
    """Endpoint de prueba para verificar que la URL de callback es accesible."""
    return {"ok": True, "callback_url": f"{_public_url()}/api/github/oauth/callback", "mensaje": "Si ves esto, el callback es accesible desde internet."}


@app.post("/api/github/repos")
async def create_github_repo_endpoint(data: GitHubRepoCreate):
    """Crea un repositorio nuevo en la cuenta del usuario."""
    try:
        repo = await github_service.create_repo(
            data.name, private=data.private, description=data.description
        )
        return {"ok": True, "repo": repo}
    except Exception as exc:
        logger.exception("Error creando repo GitHub")
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/github/repos")
async def list_github_repos_endpoint():
    """Lista repositorios del usuario."""
    try:
        repos = await github_service.list_repos()
        return {"repos": repos}
    except Exception as exc:
        logger.exception("Error listando repos GitHub")
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/tareas/{tarea_id}/github")
def link_github_repo_endpoint(tarea_id: str, data: GitHubLinkRepo):
    """Vincula un repositorio a una tarea."""
    tarea = storage.actualizar_github_tarea(tarea_id, repo=data.repo)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    notify_tareas()
    return {"tarea": tarea}


@app.delete("/api/tareas/{tarea_id}/github")
def unlink_github_repo_endpoint(tarea_id: str):
    """Desvincula el repositorio de una tarea."""
    tarea = storage.desvincular_github_tarea(tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    notify_tareas()
    return {"tarea": tarea}


@app.post("/api/tareas/{tarea_id}/agente-desarrollar")
async def agente_desarrollar_endpoint(tarea_id: str, data: GitHubDesarrollar):
    """Ejecuta el agente de desarrollo para crear una rama y un PR."""
    tarea = storage.obtener_tarea(tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    try:
        resultado = await github_service.agente_desarrollar(tarea, data.prompt)
        notify_tareas()
        return resultado
    except Exception as exc:
        logger.exception("Error en agente desarrollador")
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/tareas/{tarea_id}/github-status")
async def github_status_endpoint(tarea_id: str):
    """Devuelve estado actual del PR vinculado a la tarea."""
    tarea = storage.obtener_tarea(tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    pr_status = None
    if tarea.get("github_repo") and tarea.get("github_pr_number"):
        try:
            pr_status = await github_service.get_pull_request(tarea["github_repo"], tarea["github_pr_number"])
        except Exception as exc:
            logger.warning("No se pudo obtener estado del PR: %s", exc)
    return {"tarea": tarea, "pr_status": pr_status}


@app.post("/api/tareas/{tarea_id}/github-merge")
async def github_merge_endpoint(tarea_id: str):
    """Mergea el PR vinculado a la tarea."""
    tarea = storage.obtener_tarea(tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if not tarea.get("github_repo") or not tarea.get("github_pr_number"):
        raise HTTPException(status_code=400, detail="La tarea no tiene un PR vinculado")
    try:
        result = await github_service.merge_pull_request(tarea["github_repo"], tarea["github_pr_number"])
        storage.actualizar_github_tarea(tarea_id, status="pr_merged")
        notify_tareas()
        return result
    except Exception as exc:
        logger.exception("Error mergeando PR")
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------

@app.get("/api/changelog")
def get_changelog():
    """Devuelve el contenido actual de CHANGELOG.md."""
    return {"content": storage.leer_changelog()}


@app.get("/api/changelog/entries")
def get_changelog_entries():
    """Devuelve las entradas estructuradas para la UI de cronograma."""
    return {"entries": storage.leer_changelog_entries()}


@app.post("/api/changelog")
def add_changelog_entry(data: ChangelogEntry):
    """Añade una nueva entrada al changelog."""
    content = storage.agregar_entrada_changelog(
        version=data.version,
        seccion=data.seccion,
        cambios=data.cambios,
        casos_qa=data.casos_qa,
        fecha=data.fecha,
        impacto=data.impacto,
    )
    return {"ok": True, "content": content}


@app.post("/api/changelog/generate")
async def generate_changelog(data: ChangelogGenerate):
    """Usa la skill 'Changelog Generator' para producir una entrada y añadirla."""
    skill = storage.asegurar_skill_changelog()
    if not skill:
        raise HTTPException(status_code=500, detail="No se pudo crear la skill de changelog")

    prompt = f"""Genera una entrada de changelog para la sección '{data.seccion}' con versión '{data.version}' e impacto '{data.impacto}'.

Cambios a incluir:
{data.cambios}

Devuelve SOLO el markdown con el formato:
## [VERSION] - YYYY-MM-DD — Impacto IMPACTO

### SECCION
- cambio 1
- cambio 2

### QA
1. paso 1
2. paso 2
"""
    try:
        from agente_planes import ejecutar_agente
        agente_para_ejecutar = {
            "nombre": skill["nombre"],
            "modelo": skill.get("modelo", "llama-3.3-70b-versatile"),
            "system_prompt": skill["instrucciones"],
            "skills": [],
            "knowledge": [],
        }
        resultado = await ejecutar_agente(agente_para_ejecutar, prompt)
    except Exception as exc:
        logger.exception("Error generando changelog con agente")
        raise HTTPException(status_code=500, detail=f"Error del agente: {exc}")

    # Parsear resultado para extraer version, impacto, cambios y casos QA
    lines = resultado.splitlines()
    version = data.version
    seccion = data.seccion
    impacto = data.impacto
    cambios: List[str] = []
    casos_qa: List[str] = []
    bloque_actual: Optional[str] = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## [") and "]" in stripped:
            version = stripped.split("[")[1].split("]")[0]
            # Buscar impacto en la línea de versión: "— Impacto alto" o "Impacto alto"
            m = re.search(r"[iI]mpacto\s+(\w+)", stripped)
            if m and m.group(1).lower() in {"bajo", "medio", "alto", "critico"}:
                impacto = m.group(1).lower()
            continue
        if stripped.startswith("### "):
            nombre = stripped[4:].strip().lower()
            if "qa" in nombre or "prueba" in nombre or "test" in nombre:
                bloque_actual = "qa"
            else:
                seccion = stripped[4:].strip()
                bloque_actual = "cambios"
            continue
        if bloque_actual == "cambios" and (stripped.startswith("- ") or stripped.startswith("* ")):
            cambios.append(stripped[2:].strip())
        elif bloque_actual == "qa" and (stripped[0].isdigit() or stripped.startswith("- ") or stripped.startswith("* ")):
            txt = stripped
            if txt[0].isdigit():
                txt = txt.split(".", 1)[1].strip() if "." in txt else txt
            elif txt.startswith("- ") or txt.startswith("* "):
                txt = txt[2:].strip()
            casos_qa.append(txt)

    if not cambios:
        return {"ok": False, "error": "No se pudieron extraer cambios del resultado del agente", "raw": resultado}

    content = storage.agregar_entrada_changelog(
        version=version,
        seccion=seccion,
        cambios=cambios,
        casos_qa=casos_qa,
        impacto=impacto,
    )
    return {"ok": True, "content": content, "raw": resultado}


@app.post("/api/changelog/skill")
def ensure_changelog_skill():
    """Crea la skill 'Changelog Generator' si no existe."""
    skill = storage.asegurar_skill_changelog()
    return {"skill": skill}


def _optional_import(name: str):
    """Importa un módulo opcional (algunos viven en el proyecto padre).

    Devuelve None si no está disponible, en lugar de romper el endpoint.
    """
    try:
        return importlib.import_module(name)
    except Exception as exc:  # ImportError u otros
        logger.warning("Módulo opcional '%s' no disponible: %s", name, exc)
        return None


@app.get("/api/voz/config")
async def voz_config():
    """Devuelve la configuración del motor de voz disponible."""
    groq_stt = _optional_import("groq_stt")
    tts_service = _optional_import("tts_service")
    stt_service = _optional_import("stt_service")
    return {
        "groq": bool(groq_stt and groq_stt.disponible()),
        "local_whisper": stt_service is not None,
        "speech_api": True,
        "tts_premium": bool(tts_service and tts_service.disponible()),
    }


@app.post("/api/voz/tts")
async def voz_tts(data: dict):
    """Genera audio TTS premium. Si no está disponible, devuelve 503."""
    tts_service = _optional_import("tts_service")
    if not tts_service or not tts_service.disponible():
        raise HTTPException(status_code=503, detail="TTS premium no configurado")
    texto = data.get("texto", "")
    if not texto:
        raise HTTPException(status_code=400, detail="Texto vacío")
    try:
        audio = await tts_service.sintetizar(texto)
        return fastapi.Response(content=audio, media_type="audio/mpeg", headers={"Content-Length": str(len(audio))})
    except Exception as exc:
        logger.error("Error TTS: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error TTS: {exc}")


@app.post("/api/voz/transcribir")
async def voz_transcribir(request: fastapi.Request):
    """Transcribe audio. Usa Groq (rápido) si está configurado, si no Whisper local."""
    content_type = request.headers.get("content-type", "")
    if "webm" in content_type:
        fmt = "webm"
    elif "ogg" in content_type:
        fmt = "ogg"
    elif "wav" in content_type:
        fmt = "wav"
    elif "mp4" in content_type or "m4a" in content_type:
        fmt = "m4a"
    else:
        fmt = "webm"
    audio = await request.body()
    if not audio:
        raise HTTPException(status_code=400, detail="No se recibió audio")
    groq_stt = _optional_import("groq_stt")
    stt_service = _optional_import("stt_service")
    if not groq_stt and not stt_service:
        raise HTTPException(status_code=503, detail="Transcripción no disponible: faltan los módulos de voz (groq_stt/stt_service)")
    try:
        if groq_stt and groq_stt.disponible():
            texto = await groq_stt.transcribir_audio(audio, fmt)
            return {"texto": texto, "motor": "groq"}
        if not stt_service:
            raise HTTPException(status_code=503, detail="Whisper local no disponible")
        texto = await stt_service.transcribir_audio(audio, fmt)
        return {"texto": texto, "motor": "whisper-local"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error transcribiendo audio: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error en transcripción: {exc}")


# ---------------------------------------------------------------------------
# Chat global (agente conversacional para crear y gestionar tareas)
# ---------------------------------------------------------------------------

class ChatGlobalMensaje(BaseModel):
    texto: str = Field(min_length=1)
    modelo: Optional[str] = None
    archivos: Optional[List[Dict[str, str]]] = None


_modelos_cache: dict = {"ts": 0.0, "data": None}


def _label_modelo(mid: str) -> str:
    base = (mid or "").split("/")[-1].replace("-", " ").replace("_", " ").strip()
    return base.title() if base else mid


async def _descubrir_modelos_gateway() -> List[Dict[str, str]]:
    """Lista modelos del gateway OpenAI-compatible (OpenCode Zen) vía GET /models."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []
    base_url = os.getenv("OPENAI_BASE_URL", "https://opencode.ai/zen/go/v1").rstrip("/")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(base_url + "/models", headers={"Authorization": f"Bearer {api_key}"})
            r.raise_for_status()
            payload = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudieron autodescubrir modelos del gateway: %s", exc)
        return []
    items = payload.get("data") or payload.get("models") or [] if isinstance(payload, dict) else []
    out: List[Dict[str, str]] = []
    for it in items:
        if isinstance(it, dict):
            mid = (it.get("id") or it.get("name") or "").strip()
            desc = (it.get("description") or "").strip()
        else:
            mid = str(it).strip()
            desc = ""
        if not mid:
            continue
        out.append({
            "id": mid,
            "nombre": _label_modelo(mid),
            "proveedor": "opencode",
            "descripcion": desc or "Modelo del gateway OpenCode Zen",
        })
    return out


@app.get("/api/modelos")
async def listar_modelos():
    """Modelos LLM disponibles: curados por env (LLM_MODELS), autodescubiertos del gateway y Groq."""
    from voz_service import _usar_groq_llm
    base_model = os.getenv("LLM_MODEL", "qwen3.5-plus")
    groq_model = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
    modelos: List[Dict[str, str]] = []

    manual = [m.strip() for m in os.getenv("LLM_MODELS", "").split(",") if m.strip()]
    for mid in manual:
        modelos.append({"id": mid, "nombre": _label_modelo(mid), "proveedor": "opencode", "descripcion": "Configurado en LLM_MODELS"})

    if not manual and (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL")):
        now = time.time()
        if _modelos_cache["data"] is None or now - _modelos_cache["ts"] > 300:
            _modelos_cache["data"] = await _descubrir_modelos_gateway()
            _modelos_cache["ts"] = now
        modelos.extend(_modelos_cache["data"] or [])

    if _usar_groq_llm():
        modelos.append({"id": groq_model, "nombre": "Groq · " + _label_modelo(groq_model), "proveedor": "groq", "descripcion": "Rápido y versátil (Groq)"})

    if not any(m["id"] == base_model for m in modelos):
        modelos.insert(0, {"id": base_model, "nombre": _label_modelo(base_model), "proveedor": "opencode", "descripcion": "Modelo por defecto"})

    seen = set()
    unicos: List[Dict[str, str]] = []
    for m in modelos:
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        unicos.append(m)

    default = base_model if any(m["id"] == base_model for m in unicos) else (unicos[0]["id"] if unicos else base_model)
    return {"default": default, "modelos": unicos}


@app.post("/api/chat-global")
async def chat_global_endpoint(data: ChatGlobalMensaje):
    """Envía un mensaje al chat global y devuelve la respuesta del agente."""
    import chat_global_service
    try:
        resultado = await chat_global_service.procesar_mensaje(
            data.texto,
            modelo=data.modelo,
            archivos=data.archivos or []
        )
        if resultado.get("tarea") or resultado.get("accion") == "eliminar_tarea":
            notify_tareas()
        return resultado
    except Exception as exc:
        logger.exception("Error en chat global")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/chat-global")
def chat_global_historial():
    """Devuelve el historial del chat global."""
    import chat_global_service
    return {"historial": chat_global_service.obtener_historial()}


@app.delete("/api/chat-global")
def chat_global_limpiar():
    """Limpia el historial del chat global."""
    import chat_global_service
    chat_global_service.limpiar_historial()
    return {"ok": True}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await mgr.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        mgr.disconnect(ws)


# ---------------------------------------------------------------------------
# Memoria vectorial (LanceDB)
# ---------------------------------------------------------------------------

class MemoriaCreate(BaseModel):
    texto: str = Field(min_length=1)
    fuente: str = "manual"
    metadata: Optional[dict] = None


class MemoriaQuery(BaseModel):
    consulta: str = Field(min_length=1)
    k: int = 5
    fuente: Optional[str] = None


class AgentePregunta(BaseModel):
    pregunta: str = Field(min_length=1)
    k: int = 5


@app.post("/api/memorias")
def crear_memoria(data: MemoriaCreate):
    """Guarda una anotación o conocimiento en la memoria vectorial."""
    try:
        ids = vector_store.add_memory(
            text=data.texto,
            source=data.fuente,
            metadata=data.metadata,
        )
        return {"ok": True, "ids": ids, "mensaje": f"Memoria indexada en {len(ids)} fragmentos"}
    except Exception as exc:
        logger.error("Error guardando memoria: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/memorias/buscar")
def buscar_memorias(data: MemoriaQuery):
    """Búsqueda semántica sobre la memoria vectorial."""
    try:
        resultados = vector_store.search(data.consulta, k=data.k, source=data.fuente)
        return {"consulta": data.consulta, "resultados": resultados}
    except Exception as exc:
        logger.error("Error buscando memoria: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/agente/preguntar")
async def agente_preguntar(data: AgentePregunta):
    """El agente responde usando RAG sobre la memoria vectorial."""
    try:
        return await vector_store.ask(data.pregunta, k=data.k)
    except Exception as exc:
        logger.error("Error en agente preguntar: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/memorias/sync-tareas")
def sync_tareas_memoria():
    """Indexa todas las tareas existentes en la memoria vectorial."""
    try:
        total = vector_store.sync_tareas()
        return {"ok": True, "tareas_indexadas": total}
    except Exception as exc:
        logger.error("Error sincronizando tareas: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/memorias/stats")
def stats_memoria():
    """Estadísticas de la memoria vectorial."""
    return vector_store.stats()


# ---------------------------------------------------------------------------
# Frontend estático (SPA fallback)
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/{path:path}")
async def spa_fallback(path: str):
    """Sirve archivos estáticos si existen, o index.html para rutas del SPA."""
    if path.startswith("api/") or path.startswith("ws"):
        raise HTTPException(status_code=404, detail="Not found")
    file_path = WEB_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(WEB_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8077)
