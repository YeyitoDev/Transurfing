"""
chat_global_service.py - Agente conversacional global para crear y gestionar tareas.

Mantiene un historial de conversación y permite crear tareas, subtareas y actualizar
parámetros mediante diálogo con el agente.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import storage
from voz_service import _obtener_cliente, _obtener_cliente_groq, _usar_groq_llm

logger = logging.getLogger(__name__)


def _resolve_data_dir() -> Path:
    """Devuelve el directorio de datos disponible y escribible."""
    env_dir = os.getenv("TAREAS_DATA_DIR")
    if env_dir:
        env_path = Path(env_dir)
        try:
            env_path.mkdir(parents=True, exist_ok=True)
            # Prueba de escritura: intentar crear un archivo temporal.
            test_file = env_path / ".write_test"
            with test_file.open("w") as f:
                f.write("1")
            test_file.unlink()
            return env_path
        except OSError:
            logger.warning("TAREAS_DATA_DIR=%s no es escribible; usando data/ local", env_dir)
    return Path(__file__).resolve().parent / "data"


DATA_DIR = _resolve_data_dir()
CHAT_GLOBAL_FILE = DATA_DIR / "chat_global.json"

MAX_HISTORY = 20


def _load_history() -> List[Dict[str, Any]]:
    if not CHAT_GLOBAL_FILE.exists():
        return []
    try:
        with CHAT_GLOBAL_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data[-MAX_HISTORY:]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_history(history: List[Dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CHAT_GLOBAL_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(history[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, CHAT_GLOBAL_FILE)


def _cliente_y_modelo(modelo: Optional[str] = None) -> tuple[Any, str]:
    if modelo:
        # Si el modelo empieza con llama- o groq, usar cliente Groq
        if modelo.startswith("llama-") or "groq" in modelo.lower():
            return _obtener_cliente_groq(), _modelo_groq_valido(modelo)
        return _obtener_cliente(), modelo
    if _usar_groq_llm():
        return _obtener_cliente_groq(), _modelo_groq_valido(os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"))
    return _obtener_cliente(), os.getenv("LLM_MODEL", "qwen3.5-plus")


def _modelo_groq_valido(modelo: str) -> str:
    from voz_service import _modelo_groq_valido as _valid
    return _valid(modelo)


def _tareas_contexto() -> str:
    tareas = storage.listar_tareas()[:20]
    lineas = []
    for t in tareas:
        estado = t.get("estado", "pendiente")
        subtareas = t.get("subtareas", [])
        sub_lineas = []
        for s in subtareas:
            flags = []
            if s.get("resultado"):
                flags.append("resultado")
            if s.get("commit_pendiente"):
                flags.append("commit_pendiente")
            if s.get("commit_sha"):
                flags.append("commiteado")
            flag_str = f" ({', '.join(flags)})" if flags else ""
            sub_lineas.append(
                f"    - [{s.get('id', '')[:6]}] {s.get('titulo', '')}: {s.get('estado', 'pendiente')}{flag_str}"
            )
        lineas.append(
            f"- #{t.get('numero')}: {t['titulo']} [{t.get('etiqueta', 'tarea')}] "
            f"(prioridad {t.get('prioridad', 'media')}, {estado}, progreso {t.get('progreso', 0)}%)"
        )
        if sub_lineas:
            lineas.extend(sub_lineas)
    if not lineas:
        lineas.append("No hay tareas existentes.")
    recordatorios = storage.listar_recordatorios(solo_pendientes=False)[:10]
    if recordatorios:
        lineas.append("\nRecordatorios próximos:")
        for r in recordatorios:
            lineas.append(
                f"- [{r.get('id', '')[:6]}] {r.get('titulo', '')}: {r.get('fecha_hora', '')} ({r.get('estado', 'pendiente')})"
            )
    return "\n".join(lineas)


SYSTEM_PROMPT = """Eres Jarvis, el asistente de productividad de Sergio.
Conversas con el usuario en español para ayudarle a crear y gestionar tareas/cards.

Tu objetivo:
1. Entender qué quiere lograr el usuario.
2. Hacer preguntas claras para ajustar el alcance, prioridad, tipo y plan.
3. Cuando tengas suficiente información, proponer crear la tarea/card.
4. Puedes crear subtareas, sugerir próximos pasos o actualizar parámetros de tareas existentes.

Responde SOLO con JSON válido, sin markdown:

{
  "accion": "conversar" | "crear_tarea" | "actualizar_tarea" | "agregar_subtareas" | "eliminar_tarea" | "ejecutar_subtarea" | "commitear_subtarea" | "sincronizar_subtareas" | "eliminar_subtarea" | "crear_recordatorio" | "actualizar_recordatorio" | "eliminar_recordatorio",
  "tarea": {
    "titulo": "...",
    "descripcion": "...",
    "etiqueta": "tarea" | "habito" | "emprendimiento" | "investigacion" | "idea",
    "prioridad": "alta" | "media" | "baja",
    "objetivo": "...",
    "repetible": false,
    "subtareas": ["subtarea 1", "subtarea 2"]
  },
  "tarea_numero": 123,
  "subtarea_id": "abc123",
  "subtareas": ["subtarea 1", "subtarea 2"],
  "cambios": {"descripcion": "...", "prioridad": "alta", "etiqueta": "idea", "repetible": true},
  "recordatorio": {"titulo": "...", "fecha_hora": "YYYY-MM-DDTHH:MM", "tarea_id": "...", "recordatorio_id": "..."},
  "mensaje": "Respuesta conversacional natural en español. Preguntas de seguimiento si aplica.",
  "opciones": ["Sí, créala", "Cambiar prioridad", "Agregar descripción"]
}

Reglas:
- "conversar": cuando necesites más información. Incluye preguntas específicas en "mensaje".
- "crear_tarea": cuando tengas título y tipo suficientes. Devuelve la tarea completa.
- "actualizar_tarea": para modificar una tarea existente (requiere tarea_numero + cambios).
- "agregar_subtareas": para añadir subtareas a una tarea existente (requiere tarea_numero + subtareas). Usa objetivos concretos como prompts.
- "eliminar_tarea": para borrar una tarea existente (requiere tarea_numero). Pide confirmación antes.
- "ejecutar_subtarea": para que un agente ejecute una subtarea específica (requiere tarea_numero + subtarea_id o menciona 'la primera'/'la de X'). El agente resolverá la subtarea y guardará el resultado.
- "commitear_subtarea": para subir el resultado de una subtarea a GitHub (requiere tarea_numero + subtarea_id). Requiere que la subtarea tenga resultado y archivo destino.
- "sincronizar_subtareas": para reintentar commits pendientes de una tarea (requiere tarea_numero).
- "eliminar_subtarea": para eliminar una subtarea específica de una tarea (requiere tarea_numero + subtarea_id).
- "crear_recordatorio": para crear una alarma/recordatorio en el calendario (requiere recordatorio.titulo, recordatorio.fecha_hora en formato YYYY-MM-DDTHH:MM, y recordatorio.tarea_id). También puedes usar tarea_numero para buscar la tarea.
- "actualizar_recordatorio": para cambiar fecha/hora/título de un recordatorio existente (requiere recordatorio_id en recordatorio).
- "eliminar_recordatorio": para borrar un recordatorio (requiere recordatorio_id en recordatorio).
- "mensaje" debe ser cercano, breve (máx 3 frases) y en español.
- "opciones": array de textos cortos que se mostrarán como botones de respuesta rápida. Usa cuando quieras confirmar acciones, elegir entre alternativas o sugerir parámetros. Máximo 4 opciones.
- Extrae la prioridad del lenguaje: urgente/crítico → alta, importante → media, cuando puedas → baja.
- Si el usuario menciona "hábito", "rutina", "cada día", etiqueta "habito", activa "repetible" y pregunta hora/días.
- Si menciona "proyecto", "emprender", "startup", etiqueta "emprendimiento".
- Si menciona "investigar", "estudiar", "analizar", etiqueta "investigacion".
- Si es una idea sin madurar, etiqueta "idea" y ayuda a validarla.
- Para tareas repetibles diarias (sin ser hábito), usa "repetible": true.
- Cuando el usuario confirme o diga "sí", "crea", "adelante", "borra", "elimina", "ejecuta", "commitea", "sincroniza", "programa", "recordatorio", ejecuta la acción propuesta.
- El contexto incluye tareas, subtareas con IDs cortos y recordatorios próximos. Usa esos IDs para identificar subtareas y recordatorios cuando el usuario se refiera a una en concreto.
- Semana actual: usa el año y semana actual para programar recordatorios "esta semana" o "próxima semana".
"""


def _build_messages(history: List[Dict[str, Any]], user_message: str) -> List[Dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history:
        rol = "user" if h.get("role") == "user" else "assistant"
        content = h.get("content", "")
        if h.get("accion") and h.get("accion") != "conversar":
            content += f"\n[accion: {h['accion']}]"
        messages.append({"role": rol, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _parse_json(content: str) -> Dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        lines = [l for l in content.split("\n") if not l.startswith("```")]
        content = "\n".join(lines).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"accion": "conversar", "mensaje": content}


def _aplicar_crear_tarea(datos: Dict[str, Any]) -> Dict[str, Any]:
    tarea_data = datos.get("tarea", {})
    if not tarea_data.get("titulo"):
        return {"ok": False, "error": "Falta título de tarea"}
    try:
        t = storage.crear_tarea(
            titulo=tarea_data.get("titulo", "Sin título"),
            descripcion=tarea_data.get("descripcion", ""),
            etiqueta=tarea_data.get("etiqueta", "tarea"),
            prioridad=tarea_data.get("prioridad", "media"),
            objetivo=tarea_data.get("objetivo", ""),
            subtareas=tarea_data.get("subtareas", []),
        )
        return {"ok": True, "tarea": t}
    except Exception as e:
        logger.exception("Error creando tarea desde chat global")
        return {"ok": False, "error": str(e)}


def _aplicar_actualizar_tarea(datos: Dict[str, Any]) -> Dict[str, Any]:
    numero = datos.get("tarea_numero")
    cambios = datos.get("cambios", {})
    if not numero:
        return {"ok": False, "error": "Falta número de tarea"}
    tarea = storage.obtener_tarea_por_numero(numero)
    if not tarea:
        return {"ok": False, "error": f"Tarea #{numero} no encontrada"}
    try:
        t = storage.actualizar_tarea(tarea["id"], **cambios)
        return {"ok": True, "tarea": t}
    except Exception as e:
        logger.exception("Error actualizando tarea desde chat global")
        return {"ok": False, "error": str(e)}


def _aplicar_agregar_subtareas(datos: Dict[str, Any]) -> Dict[str, Any]:
    numero = datos.get("tarea_numero")
    subtareas = datos.get("subtareas", [])
    if not numero:
        return {"ok": False, "error": "Falta número de tarea"}
    tarea = storage.obtener_tarea_por_numero(numero)
    if not tarea:
        return {"ok": False, "error": f"Tarea #{numero} no encontrada"}
    try:
        for titulo in subtareas:
            if titulo.strip():
                storage.agregar_subtarea(tarea["id"], titulo.strip())
        t = storage.obtener_tarea(tarea["id"])
        return {"ok": True, "tarea": t}
    except Exception as e:
        logger.exception("Error agregando subtareas desde chat global")
        return {"ok": False, "error": str(e)}


def _aplicar_eliminar_tarea(datos: Dict[str, Any]) -> Dict[str, Any]:
    numero = datos.get("tarea_numero")
    if not numero:
        return {"ok": False, "error": "Falta número de tarea"}
    tarea = storage.obtener_tarea_por_numero(numero)
    if not tarea:
        return {"ok": False, "error": f"Tarea #{numero} no encontrada"}
    try:
        storage.eliminar_tarea(tarea["id"])
        return {"ok": True, "tarea": tarea}
    except Exception as e:
        logger.exception("Error eliminando tarea desde chat global")
        return {"ok": False, "error": str(e)}


def _buscar_subtarea(tarea: Dict[str, Any], subtarea_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Busca una subtarea por ID completo o por prefijo."""
    if not subtarea_id:
        return None
    sid = subtarea_id.strip()
    for s in tarea.get("subtareas", []):
        if s.get("id", "") == sid or s.get("id", "").startswith(sid):
            return s
    return None


async def _aplicar_ejecutar_subtarea(datos: Dict[str, Any]) -> Dict[str, Any]:
    numero = datos.get("tarea_numero")
    subtarea_id = datos.get("subtarea_id")
    if not numero:
        return {"ok": False, "error": "Falta número de tarea"}
    tarea = storage.obtener_tarea_por_numero(numero)
    if not tarea:
        return {"ok": False, "error": f"Tarea #{numero} no encontrada"}
    subtarea = _buscar_subtarea(tarea, subtarea_id)
    if not subtarea:
        return {"ok": False, "error": f"Subtarea '{subtarea_id}' no encontrada en la tarea #{numero}"}
    try:
        import subtarea_agente_service
        res = await subtarea_agente_service.ejecutar_subtarea(tarea["id"], subtarea["id"])
        t_actualizada = storage.obtener_tarea(tarea["id"])
        if res.get("ok"):
            return {"ok": True, "tarea": t_actualizada, "subtarea_id": subtarea["id"], "resultado": res.get("resultado")}
        return {"ok": False, "error": res.get("error", "Error desconocido"), "tarea": t_actualizada}
    except Exception as e:
        logger.exception("Error ejecutando subtarea desde chat global")
        return {"ok": False, "error": str(e)}


async def _aplicar_commitear_subtarea(datos: Dict[str, Any]) -> Dict[str, Any]:
    numero = datos.get("tarea_numero")
    subtarea_id = datos.get("subtarea_id")
    if not numero:
        return {"ok": False, "error": "Falta número de tarea"}
    tarea = storage.obtener_tarea_por_numero(numero)
    if not tarea:
        return {"ok": False, "error": f"Tarea #{numero} no encontrada"}
    subtarea = _buscar_subtarea(tarea, subtarea_id)
    if not subtarea:
        return {"ok": False, "error": f"Subtarea '{subtarea_id}' no encontrada en la tarea #{numero}"}
    try:
        import subtarea_agente_service
        res = await subtarea_agente_service.commitear_resultado(tarea["id"], subtarea["id"])
        t_actualizada = storage.obtener_tarea(tarea["id"])
        if res.get("ok"):
            return {"ok": True, "tarea": t_actualizada, "subtarea_id": subtarea["id"], "sha": res.get("sha")}
        return {"ok": False, "error": res.get("error", "Error desconocido"), "tarea": t_actualizada, "pendiente": res.get("pendiente")}
    except Exception as e:
        logger.exception("Error commiteando subtarea desde chat global")
        return {"ok": False, "error": str(e)}


async def _aplicar_sincronizar_subtareas(datos: Dict[str, Any]) -> Dict[str, Any]:
    numero = datos.get("tarea_numero")
    if not numero:
        return {"ok": False, "error": "Falta número de tarea"}
    tarea = storage.obtener_tarea_por_numero(numero)
    if not tarea:
        return {"ok": False, "error": f"Tarea #{numero} no encontrada"}
    try:
        import subtarea_agente_service
        res = await subtarea_agente_service.sincronizar_commits_pendientes(tarea["id"])
        t_actualizada = storage.obtener_tarea(tarea["id"])
        return {"ok": res.get("ok"), "tarea": t_actualizada, "mensaje": res.get("mensaje", "")}
    except Exception as e:
        logger.exception("Error sincronizando subtareas desde chat global")
        return {"ok": False, "error": str(e)}


def _aplicar_eliminar_subtarea(datos: Dict[str, Any]) -> Dict[str, Any]:
    numero = datos.get("tarea_numero")
    subtarea_id = datos.get("subtarea_id")
    if not numero:
        return {"ok": False, "error": "Falta número de tarea"}
    tarea = storage.obtener_tarea_por_numero(numero)
    if not tarea:
        return {"ok": False, "error": f"Tarea #{numero} no encontrada"}
    subtarea = _buscar_subtarea(tarea, subtarea_id)
    if not subtarea:
        return {"ok": False, "error": f"Subtarea '{subtarea_id}' no encontrada en la tarea #{numero}"}
    try:
        t_actualizada = storage.eliminar_subtarea(subtarea["id"])
        return {"ok": True, "tarea": t_actualizada}
    except Exception as e:
        logger.exception("Error eliminando subtarea desde chat global")
        return {"ok": False, "error": str(e)}


def _buscar_recordatorio(recordatorio_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not recordatorio_id:
        return None
    for r in storage.listar_recordatorios(solo_pendientes=False):
        if r.get("id") == recordatorio_id or r.get("id", "").startswith(recordatorio_id):
            return r
    return None


def _aplicar_crear_recordatorio(datos: Dict[str, Any]) -> Dict[str, Any]:
    rec = datos.get("recordatorio", {})
    tarea_id = rec.get("tarea_id")
    numero = datos.get("tarea_numero")
    if not tarea_id and not numero:
        return {"ok": False, "error": "Falta tarea asociada al recordatorio"}
    tarea = None
    if tarea_id:
        tarea = storage.obtener_tarea(tarea_id)
    elif numero:
        tarea = storage.obtener_tarea_por_numero(numero)
    if not tarea:
        return {"ok": False, "error": "Tarea asociada al recordatorio no encontrada"}
    titulo = rec.get("titulo", tarea.get("titulo", "Recordatorio")).strip()
    fecha_hora = rec.get("fecha_hora")
    if not fecha_hora:
        return {"ok": False, "error": "Falta fecha y hora del recordatorio (formato YYYY-MM-DDTHH:MM)"}
    try:
        r = storage.crear_recordatorio(titulo, fecha_hora, tarea["id"])
        if r is None:
            return {"ok": False, "error": "No se pudo crear el recordatorio"}
        try:
            import app_tareas
            app_tareas.notify_recordatorios()
        except Exception:
            pass
        return {"ok": True, "tarea": tarea, "recordatorio": r}
    except Exception as e:
        logger.exception("Error creando recordatorio desde chat global")
        return {"ok": False, "error": str(e)}


def _aplicar_actualizar_recordatorio(datos: Dict[str, Any]) -> Dict[str, Any]:
    rec = datos.get("recordatorio", {})
    recordatorio_id = rec.get("recordatorio_id")
    if not recordatorio_id:
        return {"ok": False, "error": "Falta ID del recordatorio"}
    recordatorio = _buscar_recordatorio(recordatorio_id)
    if not recordatorio:
        return {"ok": False, "error": "Recordatorio no encontrado"}
    try:
        r = storage.actualizar_recordatorio(
            recordatorio["id"],
            titulo=rec.get("titulo") if rec.get("titulo") else None,
            fecha_hora=rec.get("fecha_hora") if rec.get("fecha_hora") else None,
            estado=rec.get("estado") if rec.get("estado") else None,
        )
        if r is None:
            return {"ok": False, "error": "No se pudo actualizar el recordatorio"}
        try:
            import app_tareas
            app_tareas.notify_recordatorios()
        except Exception:
            pass
        return {"ok": True, "recordatorio": r}
    except Exception as e:
        logger.exception("Error actualizando recordatorio desde chat global")
        return {"ok": False, "error": str(e)}


def _aplicar_eliminar_recordatorio(datos: Dict[str, Any]) -> Dict[str, Any]:
    rec = datos.get("recordatorio", {})
    recordatorio_id = rec.get("recordatorio_id")
    if not recordatorio_id:
        return {"ok": False, "error": "Falta ID del recordatorio"}
    recordatorio = _buscar_recordatorio(recordatorio_id)
    if not recordatorio:
        return {"ok": False, "error": "Recordatorio no encontrado"}
    try:
        storage.eliminar_recordatorio(recordatorio["id"])
        try:
            import app_tareas
            app_tareas.notify_recordatorios()
        except Exception:
            pass
        return {"ok": True, "recordatorio": recordatorio}
    except Exception as e:
        logger.exception("Error eliminando recordatorio desde chat global")
        return {"ok": False, "error": str(e)}


async def procesar_mensaje(user_message: str, modelo: Optional[str] = None, archivos: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Procesa un mensaje del chat global, conversa con el LLM y aplica acciones."""
    history = _load_history()
    history.append({"role": "user", "content": user_message, "date": date.today().isoformat()})

    cliente, modelo = _cliente_y_modelo(modelo)
    contexto = _tareas_contexto()
    import adjuntos_service
    archivos_texto, _imagenes = await adjuntos_service.procesar_adjuntos(archivos)
    prompt = f"{user_message}\n\nTareas existentes:\n{contexto}"
    if archivos_texto:
        prompt += f"\n\nArchivos adjuntos:\n{archivos_texto}"
    messages = _build_messages(history, prompt)

    try:
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=messages,
            temperature=0.5,
            max_tokens=1200,
        )
        raw = response.choices[0].message.content or ""
        datos = _parse_json(raw)
    except Exception as exc:
        logger.exception("Error en chat global LLM")
        return {"accion": "error", "mensaje": "No pude procesar tu mensaje. Intenta de nuevo.", "tarea": None}

    accion = datos.get("accion", "conversar")
    tarea = None
    aplicado = None

    if accion == "crear_tarea":
        aplicado = _aplicar_crear_tarea(datos)
    elif accion == "actualizar_tarea":
        aplicado = _aplicar_actualizar_tarea(datos)
    elif accion == "agregar_subtareas":
        aplicado = _aplicar_agregar_subtareas(datos)
    elif accion == "eliminar_tarea":
        aplicado = _aplicar_eliminar_tarea(datos)
    elif accion == "ejecutar_subtarea":
        aplicado = await _aplicar_ejecutar_subtarea(datos)
    elif accion == "commitear_subtarea":
        aplicado = await _aplicar_commitear_subtarea(datos)
    elif accion == "sincronizar_subtareas":
        aplicado = await _aplicar_sincronizar_subtareas(datos)
    elif accion == "eliminar_subtarea":
        aplicado = _aplicar_eliminar_subtarea(datos)
    elif accion == "crear_recordatorio":
        aplicado = _aplicar_crear_recordatorio(datos)
    elif accion == "actualizar_recordatorio":
        aplicado = _aplicar_actualizar_recordatorio(datos)
    elif accion == "eliminar_recordatorio":
        aplicado = _aplicar_eliminar_recordatorio(datos)

    if aplicado:
        if aplicado.get("ok"):
            tarea = aplicado.get("tarea")
            if accion == "eliminar_tarea":
                tarea = None
        else:
            datos["accion"] = "error"
            datos["mensaje"] = f"{datos.get('mensaje', '')}\n\nError: {aplicado.get('error', 'desconocido')}"

    assistant_content = datos.get("mensaje", "")
    history.append({
        "role": "assistant",
        "content": assistant_content,
        "accion": accion,
        "opciones": datos.get("opciones", []),
        "date": date.today().isoformat(),
    })
    _save_history(history)

    return {
        "accion": accion,
        "mensaje": datos.get("mensaje", ""),
        "tarea": tarea,
        "tarea_numero": datos.get("tarea_numero"),
        "subtarea_id": datos.get("subtarea_id"),
        "subtareas": datos.get("subtareas", []),
        "cambios": datos.get("cambios", {}),
        "recordatorio": aplicado.get("recordatorio") if aplicado else None,
        "opciones": datos.get("opciones", []),
    }


def obtener_historial() -> List[Dict[str, Any]]:
    return _load_history()


def limpiar_historial() -> None:
    _save_history([])
