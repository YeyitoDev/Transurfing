"""
storage.py - Capa de persistencia en JSON para el servicio de tareas.

Guarda en un único archivo `data/tareas.json` con escritura atómica
(escribe a un temporal y luego os.replace) para evitar corromper el
archivo si el proceso se interrumpe a mitad de escritura.

Modelo en disco:
{
  "tareas": [
    {
      "id": "t_xxxx",
      "titulo": str,
      "prioridad": "alta" | "media" | "baja",
      "fecha_limite": "YYYY-MM-DD" | null,
      "completada_manual": bool,
      "creada_en": "YYYY-MM-DD",
      "subtareas": [
        {"id": "s_xxxx", "titulo": str, "completada": bool}
      ]
    }
  ]
}
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

def _resolve_data_dir() -> Path:
    """Devuelve el directorio de datos disponible y escribible."""
    env_dir = os.getenv("TAREAS_DATA_DIR")
    if env_dir:
        env_path = Path(env_dir)
        try:
            env_path.mkdir(parents=True, exist_ok=True)
            test_file = env_path / ".write_test"
            with test_file.open("w") as f:
                f.write("1")
            test_file.unlink()
            return env_path
        except OSError:
            logging.getLogger(__name__).warning("TAREAS_DATA_DIR=%s no es escribible; usando data/ local", env_dir)
    return Path(__file__).resolve().parent / "data"


# Ruta del archivo de datos. Configurable por env para el volumen de fly.io.
DATA_DIR = _resolve_data_dir()
DATA_FILE = DATA_DIR / "tareas.json"
PROJECT_DIR = Path(__file__).resolve().parent.parent
CHANGELOG_FILE = PROJECT_DIR / "CHANGELOG.md"
# CHANGELOG.json se guarda en el volumen persistente para sobrevivir redeploys.
CHANGELOG_JSON_FILE = DATA_DIR / "CHANGELOG.json"

# Backend de persistencia: "json" (por defecto) o "sqlite" (opt-in).
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "json").strip().lower()
DB_FILE = Path(os.getenv("DB_PATH") or (DATA_DIR / "tareas.db"))

_lock = threading.Lock()

PRIORIDADES = ("alta", "media", "baja")
ETIQUETAS = ("emprendimiento", "tarea", "habito", "investigacion", "idea")
DIAS_SEMANA = ("lun", "mar", "mie", "jue", "vie", "sab", "dom")


# ---------------------------------------------------------------------------
# Lectura / escritura de bajo nivel
# ---------------------------------------------------------------------------

def _leer_documento_json() -> Optional[Dict[str, Any]]:
    """Lee el documento crudo del archivo JSON, o None si no existe/inválido."""
    if not DATA_FILE.exists():
        return None
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _leer_documento_raw() -> Optional[Dict[str, Any]]:
    """Lee el documento crudo del backend activo (json o sqlite)."""
    if STORAGE_BACKEND == "sqlite":
        import db_backend
        db_backend.configurar(DB_FILE)
        data = db_backend.cargar()
        if data is None:
            # Migración única: si hay un JSON previo, impórtalo a SQLite.
            data = _leer_documento_json()
            if isinstance(data, dict):
                db_backend.guardar(data)
        return data
    return _leer_documento_json()


def _escribir_documento_raw(data: Dict[str, Any]) -> None:
    """Escribe el documento crudo en el backend activo."""
    if STORAGE_BACKEND == "sqlite":
        import db_backend
        db_backend.configurar(DB_FILE)
        db_backend.guardar(data)
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, DATA_FILE)


def _cargar_raw() -> Dict[str, Any]:
    """Carga el documento normalizado desde el backend activo."""
    data = _leer_documento_raw()
    if not isinstance(data, dict) or "tareas" not in data:
        return {"tareas": [], "recordatorios": []}
    data.setdefault("recordatorios", [])
    data.setdefault("agentes", [])
    data.setdefault("skills", [])
    data.setdefault("knowledge", [])
    data.setdefault("github_config", {})
    tareas, cambiado = _migrar_numeros(data.get("tareas", []))
    data["tareas"] = tareas
    if cambiado:
        _guardar_raw(data)
    return data


def _migrar_numeros(tareas: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], bool]:
    """Asigna números secuenciales a tareas que no lo tengan."""
    max_num = 0
    cambiado = False
    for t in tareas:
        num = t.get("numero")
        if isinstance(num, int) and num > max_num:
            max_num = num
    for t in tareas:
        if t.get("numero") is None:
            max_num += 1
            t["numero"] = max_num
            cambiado = True
        for s in t.get("subtareas", []):
            if "estado" not in s:
                s["estado"] = "completada" if s.get("completada") else "pendiente"
                cambiado = True
            if "descripcion" not in s:
                s["descripcion"] = ""
                cambiado = True
            if "prompt" not in s:
                s["prompt"] = ""
                cambiado = True
            if "resultado" not in s:
                s["resultado"] = ""
                cambiado = True
            if "repo" not in s:
                s["repo"] = ""
                cambiado = True
            if "branch" not in s:
                s["branch"] = ""
                cambiado = True
            if "archivo" not in s:
                s["archivo"] = ""
                cambiado = True
            if "commit_pendiente" not in s:
                s["commit_pendiente"] = False
                cambiado = True
            if "commit_sha" not in s:
                s["commit_sha"] = None
                cambiado = True
            if "commit_en" not in s:
                s["commit_en"] = None
                cambiado = True
    return tareas, cambiado


def _guardar_raw(data: Dict[str, Any]) -> None:
    """Escribe el documento en el backend activo (JSON atómico o SQLite)."""
    _escribir_documento_raw(data)


def _nuevo_id(prefijo: str) -> str:
    return f"{prefijo}_{secrets.token_hex(4)}"


def _formato_fecha_hora(dt: datetime) -> str:
    """Devuelve ISO string sin segundos y con T."""
    return dt.strftime("%Y-%m-%dT%H:%M")


# ---------------------------------------------------------------------------
# Lógica derivada (progreso / estado)
# ---------------------------------------------------------------------------

def _esta_completada(tarea: Dict[str, Any]) -> bool:
    subs = tarea.get("subtareas", [])
    total = len(subs)
    completadas = sum(1 for s in subs if s.get("completada"))
    manual = bool(tarea.get("completada_manual"))
    if total > 0:
        return completadas == total or manual
    return manual


def _sync_completada_en(tarea: Dict[str, Any]) -> None:
    """Mantiene `completada_en` en sync con el estado real (para el reseteo diario)."""
    if _esta_completada(tarea):
        if not tarea.get("completada_en"):
            tarea["completada_en"] = date.today().isoformat()
        if tarea.get("etiqueta") == "habito" or tarea.get("repetible"):
            log = tarea.setdefault("habito_log", [])
            hoy = date.today().isoformat()
            if hoy not in log:
                log.append(hoy)
                log.sort()
    else:
        tarea["completada_en"] = None


def _rollover(data: Dict[str, Any]) -> bool:
    """Resetea tareas repetibles (diarias) completadas en un día anterior."""
    hoy = date.today().isoformat()
    cambiado = False
    for t in data["tareas"]:
        if t.get("repetible") and t.get("completada_en") and t["completada_en"] < hoy:
            for s in t.get("subtareas", []):
                s["completada"] = False
            t["completada_manual"] = False
            t["completada_en"] = None
            cambiado = True
    return cambiado


def _decorar(tarea: Dict[str, Any]) -> Dict[str, Any]:
    """Añade `progreso` y `estado` calculados a una tarea."""
    subs = tarea.get("subtareas", [])
    total = len(subs)
    completadas = sum(1 for s in subs if s.get("completada"))

    if total > 0:
        progreso = round(completadas / total * 100, 1)
    else:
        progreso = 100.0 if tarea.get("completada_manual") else 0.0

    return {
        "etiqueta": tarea.get("etiqueta", "tarea"),
        "repetible": bool(tarea.get("repetible", False)),
        "descripcion": tarea.get("descripcion", ""),
        "horas": tarea.get("horas", []),
        "dias_semana": tarea.get("dias_semana", []),
        "objetivo": tarea.get("objetivo", ""),
        "documento": tarea.get("documento", ""),
        "proxima_alta_valor": tarea.get("proxima_alta_valor", ""),
        "chat_sesiones": tarea.get("chat_sesiones", []),
        "github_repo": tarea.get("github_repo", ""),
        "github_branch": tarea.get("github_branch", ""),
        "github_pr_url": tarea.get("github_pr_url", ""),
        "github_pr_number": tarea.get("github_pr_number", None),
        "github_status": tarea.get("github_status", ""),
        "github_agent_log": tarea.get("github_agent_log", {}),
        "numero": tarea.get("numero"),
        "habito_log": tarea.get("habito_log", []),
        **tarea,
        "icono": tarea.get("icono") or _emoji_por_defecto(tarea.get("titulo", ""), tarea.get("etiqueta", "tarea")),
        "color": tarea.get("color", ""),
        "en_progreso_manual": bool(tarea.get("en_progreso_manual", False)),
        "subtareas_total": total,
        "subtareas_completadas": completadas,
        "progreso": progreso,
        "estado": "completada" if _esta_completada(tarea) else "pendiente",
    }


# ---------------------------------------------------------------------------
# API pública: Tareas
# ---------------------------------------------------------------------------

def obtener_tarea(tarea_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t["id"] == tarea_id:
                return _decorar(t)
    return None


def listar_tareas(solo_pendientes: bool = False) -> List[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        if _rollover(data):
            _guardar_raw(data)
    tareas = [_decorar(t) for t in data["tareas"]]
    if solo_pendientes:
        tareas = [t for t in tareas if t["estado"] != "completada"]
    return tareas


TEMPLATES_SUBTAREAS: Dict[str, List[str]] = {
    "emprendimiento": [
        "Empatizar: entender al cliente y su problema",
        "Definir: perfil de usuario y problem statement",
        "Idear: propuesta de valor y posibles soluciones",
        "Prototipar: MVP o prueba rápida de concepto",
        "Testear: validar con usuarios reales",
        "Modelo de negocio: costos, ingresos y canales",
        "Plan de acción: próximos pasos concretos",
    ],
    "investigacion": [
        "Definir la pregunta de investigación",
        "Buscar fuentes y referencias clave",
        "Sintetizar información relevante",
        "Extraer conclusiones y aprendizajes",
        "Documentar resultados",
    ],
    "tarea": [
        "Definir el alcance y criterios de éxito",
        "Planificar pasos y recursos necesarios",
        "Ejecutar el trabajo principal",
        "Revisar y ajustar",
    ],
    "idea": [
        "Describir la idea en una frase",
        "Listar supuestos clave",
        "Evaluar viabilidad y riesgos",
        "Definir siguiente paso para validar",
    ],
    "habito": [],
}


def _siguiente_numero(data: Dict[str, Any]) -> int:
    max_num = 0
    for t in data.get("tareas", []):
        num = t.get("numero")
        if isinstance(num, int) and num > max_num:
            max_num = num
    return max_num + 1


_EMOJI_ETIQUETA = {
    "emprendimiento": "\U0001F680",
    "tarea": "\u2705",
    "habito": "\U0001F501",
    "investigacion": "\U0001F52C",
    "idea": "\U0001F4A1",
}

_EMOJI_KEYWORDS = [
    (("gym", "ejercicio", "correr", "deporte", "entrenar", "fitness"), "\U0001F3CB\uFE0F"),
    (("leer", "libro", "lectura"), "\U0001F4DA"),
    (("código", "codigo", "code", "program", "dev", "app", "web", "api", "bug", "frontend", "backend"), "\U0001F4BB"),
    (("reunión", "reunion", "meeting", "llamada", "call"), "\U0001F4DE"),
    (("comprar", "compras", "mercado"), "\U0001F6D2"),
    (("viaje", "viajar", "vuelo", "avión", "avion"), "\u2708\uFE0F"),
    (("dinero", "finanzas", "presupuesto", "pago", "factura"), "\U0001F4B0"),
    (("salud", "médico", "medico", "doctor", "cita"), "\U0001FA7A"),
    (("diseño", "diseno", "design", "ui", "ux"), "\U0001F3A8"),
    (("escribir", "artículo", "articulo", "blog", "redacción", "redaccion"), "\u270D\uFE0F"),
    (("música", "musica", "canción", "cancion"), "\U0001F3B5"),
    (("comida", "cocinar", "receta", "almuerzo", "cena"), "\U0001F373"),
    (("estudiar", "examen", "curso", "clase", "universidad", "maestría", "maestria"), "\U0001F393"),
    (("email", "correo", "mail"), "\U0001F4E7"),
    (("casa", "hogar", "limpiar", "limpieza"), "\U0001F3E0"),
]


def _emoji_por_defecto(titulo: str, etiqueta: str) -> str:
    """Elige un emoji representativo por palabras clave del título, con fallback por etiqueta."""
    texto = (titulo or "").lower()
    for claves, emoji in _EMOJI_KEYWORDS:
        if any(c in texto for c in claves):
            return emoji
    return _EMOJI_ETIQUETA.get(etiqueta, "\u2705")


def crear_tarea(
    titulo: str,
    prioridad: str = "media",
    fecha_limite: Optional[str] = None,
    etiqueta: str = "tarea",
    repetible: bool = False,
    descripcion: str = "",
    horas: Optional[List[str]] = None,
    dias_semana: Optional[List[str]] = None,
    objetivo: str = "",
    documento: str = "",
    subtareas: Optional[List[str]] = None,
    icono: str = "",
    color: str = "",
) -> Dict[str, Any]:
    if prioridad not in PRIORIDADES:
        prioridad = "media"
    if etiqueta not in ETIQUETAS:
        etiqueta = "tarea"
    # Aplicar template por tipo si no se envían subtareas explícitas
    if subtareas is None and etiqueta in TEMPLATES_SUBTAREAS:
        subtareas = list(TEMPLATES_SUBTAREAS[etiqueta])
    with _lock:
        data = _cargar_raw()
        nueva = {
            "id": _nuevo_id("t"),
            "numero": _siguiente_numero(data),
            "titulo": titulo.strip(),
            "descripcion": descripcion.strip(),
            "prioridad": prioridad,
            "etiqueta": etiqueta,
            "repetible": bool(repetible),
            "horas": horas if horas else [],
            "dias_semana": dias_semana if dias_semana else [],
            "fecha_limite": fecha_limite or None,
            "objetivo": objetivo.strip(),
            "documento": documento or "",
            "icono": (icono or "").strip() or _emoji_por_defecto(titulo, etiqueta),
            "color": (color or "").strip(),
            "proxima_alta_valor": "",
            "chat_sesiones": [],
            "github_repo": "",
            "github_branch": "",
            "github_pr_url": "",
            "github_pr_number": None,
            "github_status": "",
            "github_agent_log": {},
            "completada_manual": False,
            "en_progreso_manual": False,
            "completada_en": None,
            "creada_en": date.today().isoformat(),
            "habito_log": [],
            "canvas": None,
            "subtareas": [
                {
                    "id": _nuevo_id("s"),
                    "titulo": s.strip(),
                    "completada": False,
                    "estado": "pendiente",
                    "descripcion": "",
                    "prompt": "",
                    "resultado": "",
                    "repo": "",
                    "branch": "",
                    "archivo": "",
                    "commit_pendiente": False,
                    "commit_sha": None,
                    "commit_en": None,
                }
                for s in (subtareas or []) if s.strip()
            ],
        }
        data["tareas"].insert(0, nueva)
        _guardar_raw(data)
    return _decorar(nueva)


def obtener_tarea_por_numero(numero: int) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t.get("numero") == numero:
                return _decorar(t)
    return None


def agregar_subtarea_por_numero(
    numero: int,
    titulo: str,
    descripcion: str = "",
    estado: str = "pendiente",
    prompt: str = "",
    repo: str = "",
    archivo: str = "",
) -> Optional[Dict[str, Any]]:
    if estado not in ("pendiente", "en_progreso", "bloqueada", "completada"):
        estado = "pendiente"
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t.get("numero") == numero:
                t.setdefault("subtareas", []).append({
                    "id": _nuevo_id("s"),
                    "titulo": titulo.strip(),
                    "completada": estado == "completada",
                    "estado": estado,
                    "descripcion": descripcion.strip(),
                    "prompt": prompt.strip(),
                    "resultado": "",
                    "repo": repo.strip(),
                    "branch": "",
                    "archivo": archivo.strip(),
                    "commit_pendiente": False,
                    "commit_sha": None,
                    "commit_en": None,
                })
                _sync_completada_en(t)
                _guardar_raw(data)
                return _decorar(t)
    return None


def actualizar_tarea(
    tarea_id: str,
    titulo: Optional[str] = None,
    prioridad: Optional[str] = None,
    fecha_limite: Optional[str] = None,
    completada_manual: Optional[bool] = None,
    etiqueta: Optional[str] = None,
    repetible: Optional[bool] = None,
    descripcion: Optional[str] = None,
    horas: Optional[List[str]] = None,
    dias_semana: Optional[List[str]] = None,
    objetivo: Optional[str] = None,
    documento: Optional[str] = None,
    icono: Optional[str] = None,
    color: Optional[str] = None,
    en_progreso_manual: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t["id"] == tarea_id:
                if titulo is not None:
                    t["titulo"] = titulo.strip()
                if descripcion is not None:
                    t["descripcion"] = descripcion.strip()
                if objetivo is not None:
                    t["objetivo"] = objetivo.strip()
                if documento is not None:
                    t["documento"] = documento
                if icono is not None:
                    t["icono"] = icono.strip()
                if color is not None:
                    t["color"] = color.strip()
                if prioridad is not None and prioridad in PRIORIDADES:
                    t["prioridad"] = prioridad
                if fecha_limite is not None:
                    t["fecha_limite"] = fecha_limite or None
                if completada_manual is not None:
                    t["completada_manual"] = bool(completada_manual)
                if en_progreso_manual is not None:
                    t["en_progreso_manual"] = bool(en_progreso_manual)
                if etiqueta is not None and etiqueta in ETIQUETAS:
                    t["etiqueta"] = etiqueta
                if repetible is not None:
                    t["repetible"] = bool(repetible)
                if horas is not None:
                    t["horas"] = horas
                if dias_semana is not None:
                    t["dias_semana"] = dias_semana
                _sync_completada_en(t)
                _guardar_raw(data)
                return _decorar(t)
    return None


def actualizar_canvas_tarea(tarea_id: str, canvas: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t["id"] == tarea_id:
                t["canvas"] = canvas
                _guardar_raw(data)
                return _decorar(t)
    return None


def eliminar_tarea(tarea_id: str) -> bool:
    with _lock:
        data = _cargar_raw()
        antes = len(data["tareas"])
        data["tareas"] = [t for t in data["tareas"] if t["id"] != tarea_id]
        if len(data["tareas"]) != antes:
            _guardar_raw(data)
            return True
    return False


# ---------------------------------------------------------------------------
# API pública: Subtareas
# ---------------------------------------------------------------------------

def agregar_subtarea(
    tarea_id: str,
    titulo: str,
    descripcion: str = "",
    estado: str = "pendiente",
    prompt: str = "",
    repo: str = "",
    archivo: str = "",
) -> Optional[Dict[str, Any]]:
    if estado not in ("pendiente", "en_progreso", "bloqueada", "completada"):
        estado = "pendiente"
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t["id"] == tarea_id:
                t.setdefault("subtareas", []).append({
                    "id": _nuevo_id("s"),
                    "titulo": titulo.strip(),
                    "completada": estado == "completada",
                    "estado": estado,
                    "descripcion": descripcion.strip(),
                    "prompt": prompt.strip(),
                    "resultado": "",
                    "repo": repo.strip(),
                    "branch": "",
                    "archivo": archivo.strip(),
                    "commit_pendiente": False,
                    "commit_sha": None,
                    "commit_en": None,
                })
                _sync_completada_en(t)
                _guardar_raw(data)
                return _decorar(t)
    return None


def actualizar_subtarea(
    subtarea_id: str,
    titulo: Optional[str] = None,
    completada: Optional[bool] = None,
    descripcion: Optional[str] = None,
    estado: Optional[str] = None,
    prompt: Optional[str] = None,
    resultado: Optional[str] = None,
    repo: Optional[str] = None,
    archivo: Optional[str] = None,
    commit_pendiente: Optional[bool] = None,
    commit_sha: Optional[str] = None,
    plan: Optional[str] = None,
    revision: Optional[str] = None,
    resumen: Optional[str] = None,
    score: Optional[float] = None,
    iteracion: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if estado is not None and estado not in ("pendiente", "en_progreso", "bloqueada", "completada"):
        estado = "pendiente"
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            for s in t.get("subtareas", []):
                if s["id"] == subtarea_id:
                    if titulo is not None:
                        s["titulo"] = titulo.strip()
                    if descripcion is not None:
                        s["descripcion"] = descripcion.strip()
                    if prompt is not None:
                        s["prompt"] = prompt.strip()
                    if resultado is not None:
                        s["resultado"] = resultado.strip()
                    if repo is not None:
                        s["repo"] = repo.strip()
                    if archivo is not None:
                        s["archivo"] = archivo.strip()
                    if commit_pendiente is not None:
                        s["commit_pendiente"] = bool(commit_pendiente)
                    if commit_sha is not None:
                        s["commit_sha"] = commit_sha or None
                        s["commit_en"] = date.today().isoformat() if commit_sha else None
                    if plan is not None:
                        s["plan"] = plan.strip()
                    if revision is not None:
                        s["revision"] = revision.strip()
                    if resumen is not None:
                        s["resumen"] = resumen.strip()
                    if score is not None:
                        s["score"] = score
                    if iteracion is not None:
                        s.setdefault("iteraciones", []).append(iteracion)
                    if estado is not None:
                        s["estado"] = estado
                        if estado == "completada":
                            s["completada"] = True
                        elif estado == "pendiente":
                            s["completada"] = False
                    if completada is not None:
                        s["completada"] = bool(completada)
                        if "estado" not in s or (estado is None and s["completada"]):
                            s["estado"] = "completada" if s["completada"] else "pendiente"
                    _sync_completada_en(t)
                    _guardar_raw(data)
                    return _decorar(t)
    return None


def obtener_subtarea(subtarea_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            for s in t.get("subtareas", []):
                if s["id"] == subtarea_id:
                    return dict(s)
    return None



def eliminar_subtarea(subtarea_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            subs = t.get("subtareas", [])
            nuevas = [s for s in subs if s["id"] != subtarea_id]
            if len(nuevas) != len(subs):
                t["subtareas"] = nuevas
                _sync_completada_en(t)
                _guardar_raw(data)
                return _decorar(t)
    return None


# ---------------------------------------------------------------------------
# API pública: Chat / Sesiones
# ---------------------------------------------------------------------------

def crear_chat_sesion(tarea_id: str, nombre: str) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t["id"] == tarea_id:
                sesiones = t.setdefault("chat_sesiones", [])
                sesion = {
                    "id": _nuevo_id("chat"),
                    "nombre": nombre.strip() or f"Sesión {len(sesiones) + 1}",
                    "creado_en": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "mensajes": [],
                }
                sesiones.append(sesion)
                _guardar_raw(data)
                return _decorar(t)
    return None


def renombrar_chat_sesion(tarea_id: str, sesion_id: str, nombre: str) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t["id"] == tarea_id:
                for sesion in t.get("chat_sesiones", []):
                    if sesion["id"] == sesion_id:
                        sesion["nombre"] = nombre.strip()
                        _guardar_raw(data)
                        return _decorar(t)
                return _decorar(t)
    return None


def agregar_chat_mensaje(tarea_id: str, sesion_id: str, rol: str, texto: str) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t["id"] == tarea_id:
                for sesion in t.get("chat_sesiones", []):
                    if sesion["id"] == sesion_id:
                        sesion["mensajes"].append({
                            "id": _nuevo_id("msg"),
                            "rol": rol,
                            "texto": texto.strip(),
                            "creado_en": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        })
                        _guardar_raw(data)
                        return _decorar(t)
                return _decorar(t)
    return None


def actualizar_proxima_alta_valor(tarea_id: str, texto: str) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t["id"] == tarea_id:
                t["proxima_alta_valor"] = texto.strip()
                _guardar_raw(data)
                return _decorar(t)
    return None


# ---------------------------------------------------------------------------
# API pública: Recordatorios / Alarmas
# ---------------------------------------------------------------------------

def listar_recordatorios(solo_pendientes: bool = False) -> List[Dict[str, Any]]:
    """Devuelve recordatorios con info de tarea/subtarea asociada."""
    with _lock:
        data = _cargar_raw()
    hoy = datetime.now().isoformat(timespec="minutes")
    result = []
    for r in data.get("recordatorios", []):
        if solo_pendientes and r.get("estado") == "completado":
            continue
        tarea = None
        subtarea = None
        for t in data["tareas"]:
            if t["id"] == r.get("tarea_id"):
                tarea = t
                if r.get("subtarea_id"):
                    for s in t.get("subtareas", []):
                        if s["id"] == r["subtarea_id"]:
                            subtarea = s
                            break
                break
        item = dict(r)
        item["tarea_titulo"] = tarea["titulo"] if tarea else None
        item["subtarea_titulo"] = subtarea["titulo"] if subtarea else None
        item["proximo"] = r.get("fecha_hora", "") <= hoy
        result.append(item)
    result.sort(key=lambda x: x.get("fecha_hora", ""))
    return result


def crear_recordatorio(
    titulo: str,
    fecha_hora: str,
    tarea_id: str,
    subtarea_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        # Validar que la tarea existe
        tarea = next((t for t in data["tareas"] if t["id"] == tarea_id), None)
        if not tarea:
            return None
        subtarea = None
        if subtarea_id:
            for s in tarea.get("subtareas", []):
                if s["id"] == subtarea_id:
                    subtarea = s
                    break
            if not subtarea:
                return None
        nuevo = {
            "id": _nuevo_id("a"),
            "titulo": titulo.strip(),
            "fecha_hora": fecha_hora,
            "tarea_id": tarea_id,
            "subtarea_id": subtarea_id,
            "estado": "pendiente",
            "creado_en": _formato_fecha_hora(datetime.now()),
        }
        data.setdefault("recordatorios", []).append(nuevo)
        _guardar_raw(data)
        return dict(nuevo, tarea_titulo=tarea["titulo"],
                    subtarea_titulo=subtarea["titulo"] if subtarea else None,
                    proximo=False)


def actualizar_recordatorio(
    recordatorio_id: str,
    titulo: Optional[str] = None,
    fecha_hora: Optional[str] = None,
    estado: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for r in data.get("recordatorios", []):
            if r["id"] == recordatorio_id:
                if titulo is not None:
                    r["titulo"] = titulo.strip()
                if fecha_hora is not None:
                    r["fecha_hora"] = fecha_hora
                if estado is not None and estado in ("pendiente", "completado"):
                    r["estado"] = estado
                _guardar_raw(data)
                return dict(r)
    return None


def eliminar_recordatorio(recordatorio_id: str) -> bool:
    with _lock:
        data = _cargar_raw()
        antes = len(data.get("recordatorios", []))
        data["recordatorios"] = [r for r in data.get("recordatorios", []) if r["id"] != recordatorio_id]
        if len(data["recordatorios"]) != antes:
            _guardar_raw(data)
            return True
    return False


# ---------------------------------------------------------------------------
# API pública: Agentes especializados, Skills y Knowledge
# ---------------------------------------------------------------------------

def listar_agentes() -> List[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
    return list(data.get("agentes", []))


def listar_skills() -> List[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
    return list(data.get("skills", []))


def listar_knowledge() -> List[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
    return list(data.get("knowledge", []))


def obtener_agente(agente_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for a in data.get("agentes", []):
            if a["id"] == agente_id:
                return dict(a)
    return None


def crear_agente(nombre: str, descripcion: str, modelo: str, system_prompt: str, skills: List[str], knowledge: List[str]) -> Dict[str, Any]:
    with _lock:
        data = _cargar_raw()
        nuevo = {
            "id": _nuevo_id("ag"),
            "nombre": nombre.strip(),
            "descripcion": descripcion.strip(),
            "modelo": modelo.strip(),
            "system_prompt": system_prompt.strip(),
            "skills": list(skills),
            "knowledge": list(knowledge),
            "creado_en": _formato_fecha_hora(datetime.now()),
        }
        data.setdefault("agentes", []).append(nuevo)
        _guardar_raw(data)
        return nuevo


def actualizar_agente(
    agente_id: str,
    nombre: Optional[str] = None,
    descripcion: Optional[str] = None,
    modelo: Optional[str] = None,
    system_prompt: Optional[str] = None,
    skills: Optional[List[str]] = None,
    knowledge: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for a in data.get("agentes", []):
            if a["id"] == agente_id:
                if nombre is not None:
                    a["nombre"] = nombre.strip()
                if descripcion is not None:
                    a["descripcion"] = descripcion.strip()
                if modelo is not None:
                    a["modelo"] = modelo.strip()
                if system_prompt is not None:
                    a["system_prompt"] = system_prompt.strip()
                if skills is not None:
                    a["skills"] = list(skills)
                if knowledge is not None:
                    a["knowledge"] = list(knowledge)
                _guardar_raw(data)
                return dict(a)
    return None


def eliminar_agente(agente_id: str) -> bool:
    with _lock:
        data = _cargar_raw()
        antes = len(data.get("agentes", []))
        data["agentes"] = [a for a in data.get("agentes", []) if a["id"] != agente_id]
        if len(data["agentes"]) != antes:
            _guardar_raw(data)
            return True
    return False


def crear_skill(nombre: str, descripcion: str, instrucciones: str) -> Dict[str, Any]:
    with _lock:
        data = _cargar_raw()
        nuevo = {
            "id": _nuevo_id("sk"),
            "nombre": nombre.strip(),
            "descripcion": descripcion.strip(),
            "instrucciones": instrucciones.strip(),
            "creado_en": _formato_fecha_hora(datetime.now()),
        }
        data.setdefault("skills", []).append(nuevo)
        _guardar_raw(data)
        return nuevo


def actualizar_skill(skill_id: str, nombre: Optional[str] = None, descripcion: Optional[str] = None, instrucciones: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for s in data.get("skills", []):
            if s["id"] == skill_id:
                if nombre is not None:
                    s["nombre"] = nombre.strip()
                if descripcion is not None:
                    s["descripcion"] = descripcion.strip()
                if instrucciones is not None:
                    s["instrucciones"] = instrucciones.strip()
                _guardar_raw(data)
                return dict(s)
    return None


def eliminar_skill(skill_id: str) -> bool:
    with _lock:
        data = _cargar_raw()
        antes = len(data.get("skills", []))
        data["skills"] = [s for s in data.get("skills", []) if s["id"] != skill_id]
        if len(data["skills"]) != antes:
            _guardar_raw(data)
            return True
    return False


def crear_knowledge(nombre: str, tipo: str, contenido: str) -> Dict[str, Any]:
    with _lock:
        data = _cargar_raw()
        nuevo = {
            "id": _nuevo_id("kn"),
            "nombre": nombre.strip(),
            "tipo": tipo,
            "contenido": contenido.strip(),
            "creado_en": _formato_fecha_hora(datetime.now()),
        }
        data.setdefault("knowledge", []).append(nuevo)
        _guardar_raw(data)
        return nuevo


def actualizar_knowledge(knowledge_id: str, nombre: Optional[str] = None, tipo: Optional[str] = None, contenido: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for k in data.get("knowledge", []):
            if k["id"] == knowledge_id:
                if nombre is not None:
                    k["nombre"] = nombre.strip()
                if tipo is not None:
                    k["tipo"] = tipo
                if contenido is not None:
                    k["contenido"] = contenido.strip()
                _guardar_raw(data)
                return dict(k)
    return None


def eliminar_knowledge(knowledge_id: str) -> bool:
    with _lock:
        data = _cargar_raw()
        antes = len(data.get("knowledge", []))
        data["knowledge"] = [k for k in data.get("knowledge", []) if k["id"] != knowledge_id]
        if len(data["knowledge"]) != antes:
            _guardar_raw(data)
            return True
    return False


# ---------------------------------------------------------------------------
# API pública: GitHub config
# ---------------------------------------------------------------------------

def _fernet():
    """Devuelve un objeto Fernet si hay SECRET_KEY y cryptography; si no, None."""
    secret = os.getenv("SECRET_KEY")
    if not secret:
        return None
    try:
        import base64
        import hashlib
        from cryptography.fernet import Fernet
    except Exception:
        return None
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _encrypt_pat(pat: str) -> str:
    """Cifra el PAT si hay clave disponible; si no, lo devuelve tal cual."""
    if not pat:
        return pat
    f = _fernet()
    if not f:
        return pat
    try:
        return "enc:" + f.encrypt(pat.encode("utf-8")).decode("ascii")
    except Exception:
        return pat


def _decrypt_pat(stored: str) -> str:
    """Descifra un PAT con prefijo 'enc:'; los planos (sin prefijo) se devuelven igual."""
    if not stored or not stored.startswith("enc:"):
        return stored or ""
    f = _fernet()
    if not f:
        logging.getLogger(__name__).warning("PAT cifrado pero falta SECRET_KEY/cryptography para descifrar")
        return ""
    try:
        return f.decrypt(stored[4:].encode("ascii")).decode("utf-8")
    except Exception:
        logging.getLogger(__name__).warning("No se pudo descifrar el PAT de GitHub")
        return ""


def get_github_config() -> Dict[str, Any]:
    with _lock:
        data = _cargar_raw()
    cfg = dict(data.get("github_config", {}))
    if cfg.get("pat"):
        cfg["pat"] = _decrypt_pat(cfg["pat"])
    return cfg


def set_github_config(pat: str, username: str = "") -> Dict[str, Any]:
    with _lock:
        data = _cargar_raw()
        data["github_config"] = {
            "pat": _encrypt_pat(pat.strip()),
            "username": username.strip(),
        }
        _guardar_raw(data)
        return dict(data["github_config"])


# ---------------------------------------------------------------------------
# API pública: GitHub en tareas
# ---------------------------------------------------------------------------

def actualizar_github_tarea(
    tarea_id: str,
    repo: Optional[str] = None,
    branch: Optional[str] = None,
    pr_url: Optional[str] = None,
    pr_number: Optional[int] = None,
    status: Optional[str] = None,
    agente_log: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t["id"] == tarea_id:
                if repo is not None:
                    t["github_repo"] = repo.strip()
                    if repo.strip():
                        t["github_status"] = "linked"
                if branch is not None:
                    t["github_branch"] = branch.strip()
                if pr_url is not None:
                    t["github_pr_url"] = pr_url.strip()
                if pr_number is not None:
                    t["github_pr_number"] = pr_number
                if status is not None:
                    t["github_status"] = status.strip()
                if agente_log is not None:
                    t["github_agent_log"] = dict(agente_log)
                _guardar_raw(data)
                return _decorar(t)
    return None


def desvincular_github_tarea(tarea_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _cargar_raw()
        for t in data["tareas"]:
            if t["id"] == tarea_id:
                t["github_repo"] = ""
                t["github_branch"] = ""
                t["github_pr_url"] = ""
                t["github_pr_number"] = None
                t["github_status"] = ""
                t["github_agent_log"] = {}
                _guardar_raw(data)
                return _decorar(t)
    return None


# ---------------------------------------------------------------------------
# API pública: Changelog (JSON estructurado → markdown)
# ---------------------------------------------------------------------------

IMPACTOS_ORDEN = {"critico": 0, "alto": 1, "medio": 2, "bajo": 3}
IMPACTOS_VALIDOS = set(IMPACTOS_ORDEN.keys())


def _normalizar_fecha(fecha: Optional[str]) -> str:
    if not fecha:
        return date.today().isoformat()
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
        return fecha
    except ValueError:
        return date.today().isoformat()


def _leer_changelog_json() -> List[Dict[str, Any]]:
    """Lee las entradas estructuradas del changelog, migrando desde MD si es necesario."""
    if CHANGELOG_JSON_FILE.exists():
        try:
            with CHANGELOG_JSON_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("entries", []) if isinstance(data, dict) else []
        except (json.JSONDecodeError, OSError):
            pass
    if CHANGELOG_FILE.exists():
        return _migrar_changelog_md_a_json()
    return []


def _guardar_changelog_json(entries: List[Dict[str, Any]]) -> None:
    """Guarda el JSON y regenera CHANGELOG.md."""
    CHANGELOG_JSON_FILE.write_text(
        json.dumps({"entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    CHANGELOG_FILE.write_text(_generar_markdown(entries), encoding="utf-8")


def _migrar_changelog_md_a_json() -> List[Dict[str, Any]]:
    """Convierte el markdown actual a entradas estructuradas con fecha de hoy."""
    contenido = CHANGELOG_FILE.read_text(encoding="utf-8")
    entries: List[Dict[str, Any]] = []
    qa_map: Dict[str, List[str]] = {}
    current_top: Optional[str] = None
    current_section: Optional[str] = None
    current_changes: List[str] = []
    current_qa: List[str] = []

    def flush() -> None:
        nonlocal current_section, current_changes, current_qa
        if current_section and (current_changes or current_qa):
            if current_top == "qa":
                qa_map[current_section.lower().strip()] = current_qa
            else:
                entries.append({
                    "id": secrets.token_urlsafe(8),
                    "fecha": date.today().isoformat(),
                    "version": "Unreleased",
                    "seccion": current_section,
                    "impacto": "alto",
                    "cambios": current_changes,
                    "casos_qa": current_qa,
                })
        current_section = None
        current_changes = []
        current_qa = []

    for raw_line in contenido.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## ["):
            flush()
            current_top = "version"
            continue
        if line.startswith("## ") and ("qa" in line.lower() or "prueba" in line.lower() or "test" in line.lower()):
            flush()
            current_top = "qa"
            continue
        if line.startswith("### "):
            flush()
            current_section = line[4:].strip()
            continue
        if line.startswith("- ") or line.startswith("* "):
            text = line[2:].strip()
            if current_top == "qa":
                current_qa.append(text)
            else:
                current_changes.append(text)
            continue
        if line[0].isdigit() and "." in line:
            text = line.split(".", 1)[1].strip()
            if current_top == "qa":
                current_qa.append(text)
            else:
                current_qa.append(text)
            continue

    flush()

    # Asociar casos QA a entradas por similitud de sección
    for entry in entries:
        key = entry["seccion"].lower().strip()
        for qa_key, qa_cases in qa_map.items():
            if key == qa_key or key in qa_key or qa_key in key or _seccion_similar(key, qa_key):
                entry["casos_qa"] = entry["casos_qa"] + qa_cases
                break

    _guardar_changelog_json(entries)
    return entries


def _seccion_similar(a: str, b: str) -> bool:
    a_words = set(a.split())
    b_words = set(b.split())
    if not a_words or not b_words:
        return False
    inter = a_words & b_words
    return len(inter) / max(len(a_words), len(b_words)) >= 0.5


def _generar_markdown(entries: List[Dict[str, Any]]) -> str:
    """Genera markdown ordenado cronológicamente con impacto y detalles."""
    entries_sorted = sorted(
        entries,
        key=lambda e: (
            e.get("fecha", "") or "",
            -IMPACTOS_ORDEN.get(e.get("impacto", "bajo"), 3),
            -entries.index(e),
        ),
        reverse=True,
    )
    impacto_emoji = {"critico": "🔴", "alto": "🟠", "medio": "🟡", "bajo": "🟢"}
    lines = [
        "# Changelog",
        "",
        "> Cronograma de cambios, casos de prueba QA e impacto. Ordenado por fecha (más reciente primero) y destacando el nivel de impacto.",
        "",
    ]
    for e in entries_sorted:
        version = e.get("version", "Unreleased")
        fecha = e.get("fecha", date.today().isoformat())
        seccion = e.get("seccion", "General")
        impacto = e.get("impacto", "bajo")
        emoji = impacto_emoji.get(impacto, "⚪")
        lines.append(f"## [{version}] - {fecha} {emoji} **Impacto {impacto}**")
        lines.append("")
        lines.append(f"### {seccion}")
        for c in e.get("cambios", []):
            if c.strip():
                lines.append(f"- {c.strip()}")
        qa = e.get("casos_qa", [])
        if qa:
            lines.append("")
            lines.append("### QA — Casos de prueba")
            for i, q in enumerate(qa, 1):
                if q.strip():
                    lines.append(f"{i}. {q.strip()}")
        lines.append("")
    return "\n".join(lines)


def leer_changelog() -> str:
    """Devuelve el markdown generado a partir del changelog estructurado."""
    return _generar_markdown(_leer_changelog_json())


def leer_changelog_entries() -> List[Dict[str, Any]]:
    """Devuelve las entradas estructuradas del changelog (para UI de cronograma)."""
    return _leer_changelog_json()


def agregar_entrada_changelog(
    version: str,
    seccion: str,
    cambios: List[str],
    casos_qa: List[str],
    fecha: Optional[str] = None,
    impacto: Optional[str] = None,
) -> str:
    """Añade una nueva entrada, ordena cronológicamente y regenera markdown."""
    impacto = (impacto or "medio").lower().strip()
    if impacto not in IMPACTOS_VALIDOS:
        impacto = "medio"
    fecha = _normalizar_fecha(fecha)
    cambios = [c.strip() for c in cambios if c.strip()]
    casos_qa = [c.strip() for c in casos_qa if c.strip()]
    if not cambios:
        raise ValueError("Se requiere al menos un cambio")

    entry = {
        "id": secrets.token_urlsafe(8),
        "fecha": fecha,
        "version": version.strip(),
        "seccion": seccion.strip(),
        "impacto": impacto,
        "cambios": cambios,
        "casos_qa": casos_qa,
    }
    with _lock:
        entries = _leer_changelog_json()
        entries.append(entry)
        _guardar_changelog_json(entries)
    return _generar_markdown(entries)


def asegurar_skill_changelog() -> Optional[Dict[str, Any]]:
    """Crea la skill 'Changelog Generator' si no existe."""
    skills = listar_skills()
    for s in skills:
        if s["nombre"].lower() == "changelog generator":
            return s
    instrucciones = """Eres un asistente de QA/release notes. Tu trabajo es generar una entrada de changelog a partir de un conjunto de cambios de código.

Para cada entrada debes producir:
1. Versión corta (ej: "1.2.0", "Unreleased").
2. Sección (ej: GitHub, Tareas, Agentes, UI).
3. Impacto: uno de "bajo", "medio", "alto", "critico". Indica cuánto afecta al usuario final o al sistema.
4. Lista de cambios en bullets concisos, enfocados en lo que el usuario final experimenta.
5. Lista de casos de prueba QA numerados, prácticos y verificables.

Formato de salida obligatorio (markdown plano):

## [VERSION] - YYYY-MM-DD — Impacto IMPACTO

### SECCION
- cambio 1
- cambio 2

### QA
1. Paso de prueba 1
2. Paso de prueba 2

Si el usuario no te da cambios, pregunta: "¿Qué cambios o archivos debo incluir en el changelog?".
No inventes funcionalidades que no estén en los cambios proporcionados."""
    return crear_skill(
        nombre="Changelog Generator",
        descripcion="Genera entradas de changelog, impacto y casos de prueba QA a partir de cambios recientes.",
        instrucciones=instrucciones,
    )
