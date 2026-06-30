"""
subtarea_agente_service.py - Ejecuta subtareas con agentes LLM y guarda resultados en GitHub.

- Cada subtarea debe tener un campo 'prompt' con instrucciones detalladas para un agente.
- Las subtareas se ejecutan en paralelo usando asyncio.gather.
- Los resultados se intentan commitear en el repo indicado; si falla, se marcan como pendientes.
- Las subtareas pendientes se sincronizan cuando se solicita o cuando hay conectividad.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import storage
from agente_planes import ejecutar_agente
from github_service import commit_file, create_branch

logger = logging.getLogger(__name__)

# Progreso en memoria para animaciones del frontend. Se limpia al reiniciar.
PROGRESO_EJECUCION: Dict[str, Dict[str, Any]] = {}


def _log_progreso(subtarea_id: str, paso: str, detalle: str = "", estado: str = "en_progreso") -> None:
    """Registra un paso del proceso de ejecución para feedback en tiempo real."""
    PROGRESO_EJECUCION[subtarea_id] = {
        "paso": paso,
        "detalle": detalle,
        "estado": estado,
        "timestamp": datetime.now().isoformat(timespec="minutes"),
    }


def obtener_progreso(subtarea_id: str) -> Optional[Dict[str, Any]]:
    """Devuelve el último paso registrado de una subtarea."""
    return PROGRESO_EJECUCION.get(subtarea_id)


def _modelo_por_defecto(modelo: Optional[str] = None) -> str:
    return modelo or os.getenv("LLM_MODEL", "qwen3.5-plus")


def _agente_planner(modelo: Optional[str] = None) -> Dict[str, Any]:
    return {
        "nombre": "jarvis-planner",
        "modelo": _modelo_por_defecto(modelo),
        "system_prompt": (
            "Eres un agente PLANIFICADOR. Tu trabajo es analizar una subtarea y "
            "diseñar un plan de ejecución claro y accionable. "
            "Desglosa el enfoque en pasos concretos, identifica requisitos, riesgos y "
            "el formato esperado del entregable. No ejecutes la tarea todavía, solo planifica. "
            "Responde en markdown breve con una lista de pasos numerados."
        ),
        "skills": [],
        "knowledge": [],
    }


def _agente_executor(modelo: Optional[str] = None) -> Dict[str, Any]:
    return {
        "nombre": "jarvis-executor",
        "modelo": _modelo_por_defecto(modelo),
        "system_prompt": (
            "Eres un agente EJECUTOR. Recibes un plan y debes producir el entregable final "
            "siguiendo el plan al pie de la letra. "
            "Devuelve SOLO el resultado en texto plano o markdown, sin conversación ni explicaciones meta. "
            "Si la tarea requiere código, devuelve el código completo y listo para usar. "
            "Si requiere documentación, devuelve el texto completo. Máxima calidad y detalle."
        ),
        "skills": [],
        "knowledge": [],
    }


def _agente_reviewer(modelo: Optional[str] = None) -> Dict[str, Any]:
    return {
        "nombre": "jarvis-reviewer",
        "modelo": _modelo_por_defecto(modelo),
        "system_prompt": (
            "Eres un agente REVISOR de calidad. Recibes la subtarea, su plan y el resultado producido. "
            "Evalúa críticamente si el resultado cumple el objetivo, su calidad y completitud. "
            "Responde SOLO con JSON válido sin markdown:\n"
            "{\n"
            '  "score": 0-100,\n'
            '  "aprobado": true|false,\n'
            '  "resumen": "resumen ejecutivo de 1-3 frases de lo que se construyó",\n'
            '  "feedback": "puntos concretos de mejora; vacío si está perfecto"\n'
            "}"
        ),
        "skills": [],
        "knowledge": [],
    }


def _parse_revision(raw: str) -> Dict[str, Any]:
    """Extrae el JSON de la revisión de forma robusta."""
    import json
    import re

    texto = raw.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```[a-zA-Z]*\n?", "", texto)
        texto = re.sub(r"\n?```$", "", texto).strip()
    try:
        datos = json.loads(texto)
    except Exception:
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            try:
                datos = json.loads(match.group(0))
            except Exception:
                datos = {}
        else:
            datos = {}
    score = datos.get("score", 0)
    try:
        score = float(score)
    except Exception:
        score = 0.0
    return {
        "score": max(0.0, min(100.0, score)),
        "aprobado": bool(datos.get("aprobado", score >= 70)),
        "resumen": str(datos.get("resumen", "")).strip() or "Sin resumen del revisor.",
        "feedback": str(datos.get("feedback", "")).strip(),
    }


def _contexto_tarea(tarea: Dict[str, Any], prompt: str) -> str:
    return (
        f"CONTEXTO DE LA TAREA PADRE:\n"
        f"Título: {tarea.get('titulo', '')}\n"
        f"Descripción: {tarea.get('descripcion', '') or 'Ninguna'}\n"
        f"Objetivo: {tarea.get('objetivo', '') or 'No especificado'}\n"
        f"Repositorio: {tarea.get('github_repo', '') or 'Ninguno'}\n\n"
        f"INSTRUCCIONES DE LA SUBTAREA:\n{prompt}"
    )


async def ejecutar_subtarea(
    tarea_id: str,
    subtarea_id: str,
    modelo: Optional[str] = None,
    base_resultado: Optional[str] = None,
    feedback_previo: Optional[str] = None,
) -> Dict[str, Any]:
    """Ejecuta una subtarea con el pipeline Planner -> Executor -> Reviewer.

    Si se pasa `base_resultado`, el ejecutor mejora sobre ese resultado previo
    teniendo en cuenta `feedback_previo` (modo iteración).
    """
    _log_progreso(subtarea_id, "validando", "Verificando subtarea y tarea padre", "en_progreso")
    subtarea = storage.obtener_subtarea(subtarea_id)
    if not subtarea:
        _log_progreso(subtarea_id, "error", "Subtarea no encontrada", "error")
        return {"ok": False, "error": "Subtarea no encontrada"}

    tarea = storage.obtener_tarea(tarea_id)
    if not tarea:
        _log_progreso(subtarea_id, "error", "Tarea padre no encontrada", "error")
        return {"ok": False, "error": "Tarea no encontrada"}

    prompt = subtarea.get("prompt", "")
    if not prompt:
        _log_progreso(subtarea_id, "error", "La subtarea no tiene prompt de agente", "error")
        return {"ok": False, "error": "La subtarea no tiene un prompt de agente"}

    contexto = _contexto_tarea(tarea, prompt)
    es_iteracion = bool(base_resultado)

    try:
        # 1. PLANNER
        _log_progreso(subtarea_id, "planificando", "El planificador diseña el enfoque", "en_progreso")
        plan_input = contexto
        if es_iteracion:
            plan_input += (
                f"\n\nRESULTADO PREVIO A MEJORAR:\n{base_resultado}\n\n"
                f"FEEDBACK DEL REVISOR ANTERIOR:\n{feedback_previo or 'Sin feedback previo'}\n\n"
                "Replantea el enfoque para corregir las deficiencias indicadas."
            )
        plan = await ejecutar_agente(_agente_planner(modelo), plan_input, tarea_id=tarea_id, max_tokens=1200)

        # 2. EXECUTOR
        _log_progreso(subtarea_id, "ejecutando", "El ejecutor produce el entregable", "en_progreso")
        exec_input = f"{contexto}\n\nPLAN A SEGUIR:\n{plan}"
        if es_iteracion:
            exec_input += (
                f"\n\nRESULTADO PREVIO (mejóralo, no empieces de cero):\n{base_resultado}\n\n"
                f"FEEDBACK A RESOLVER:\n{feedback_previo or ''}"
            )
        resultado = await ejecutar_agente(_agente_executor(modelo), exec_input, tarea_id=tarea_id, max_tokens=4000)

        # 3. REVIEWER
        _log_progreso(subtarea_id, "revisando", "El revisor evalúa la calidad", "en_progreso")
        review_input = (
            f"{contexto}\n\nPLAN:\n{plan}\n\nRESULTADO PRODUCIDO:\n{resultado}\n\n"
            "Evalúa el resultado y responde en el JSON indicado."
        )
        review_raw = await ejecutar_agente(_agente_reviewer(modelo), review_input, tarea_id=tarea_id, max_tokens=800)
        revision = _parse_revision(review_raw)

        # 4. GUARDAR
        _log_progreso(subtarea_id, "guardando", "Guardando resultado y revisión", "en_progreso")
        iteracion = {
            "timestamp": datetime.now().isoformat(timespec="minutes"),
            "resultado": resultado,
            "plan": plan,
            "score": revision["score"],
            "resumen": revision["resumen"],
            "feedback": revision["feedback"],
        }
        storage.actualizar_subtarea(
            subtarea_id,
            estado="completada",
            resultado=resultado,
            plan=plan,
            revision=revision["feedback"],
            resumen=revision["resumen"],
            score=revision["score"],
            iteracion=iteracion,
        )
        _log_progreso(
            subtarea_id,
            "completado",
            f"Revisado · score {int(revision['score'])}/100",
            "completado",
        )
        return {
            "ok": True,
            "subtarea_id": subtarea_id,
            "resultado": resultado,
            "plan": plan,
            "revision": revision,
        }
    except Exception as e:
        logger.exception("Error ejecutando subtarea %s", subtarea_id)
        _log_progreso(subtarea_id, "error", str(e), "error")
        return {"ok": False, "error": str(e), "subtarea_id": subtarea_id}


async def iterar_subtarea(
    tarea_id: str,
    subtarea_id: str,
    modelo: Optional[str] = None,
    instrucciones_extra: Optional[str] = None,
) -> Dict[str, Any]:
    """Re-ejecuta el pipeline mejorando sobre el resultado previo de la subtarea."""
    subtarea = storage.obtener_subtarea(subtarea_id)
    if not subtarea:
        return {"ok": False, "error": "Subtarea no encontrada"}
    base = subtarea.get("resultado", "")
    if not base:
        return {"ok": False, "error": "La subtarea aún no tiene un resultado base para iterar"}
    feedback = subtarea.get("revision", "")
    if instrucciones_extra:
        feedback = f"{feedback}\n\nINSTRUCCIONES ADICIONALES DEL USUARIO:\n{instrucciones_extra}".strip()
    return await ejecutar_subtarea(
        tarea_id,
        subtarea_id,
        modelo=modelo,
        base_resultado=base,
        feedback_previo=feedback,
    )


async def ejecutar_subtareas_pendientes(
    tarea_id: str,
    modelo: Optional[str] = None,
    max_paralelo: int = 4,
) -> Dict[str, Any]:
    """Ejecuta todas las subtareas pendientes de una tarea en paralelo."""
    tarea = storage.obtener_tarea(tarea_id)
    if not tarea:
        return {"ok": False, "error": "Tarea no encontrada"}

    subtareas = [
        s for s in tarea.get("subtareas", [])
        if s.get("estado") != "completada" and s.get("prompt")
    ]

    if not subtareas:
        return {"ok": True, "mensaje": "No hay subtareas pendientes con prompt", "ejecutadas": []}

    semaforo = asyncio.Semaphore(max_paralelo)

    async def _ejecutar(s):
        async with semaforo:
            return await ejecutar_subtarea(tarea_id, s["id"], modelo)

    resultados = await asyncio.gather(*[_ejecutar(s) for s in subtareas])
    exitosas = [r for r in resultados if r.get("ok")]
    fallidas = [r for r in resultados if not r.get("ok")]

    return {
        "ok": len(fallidas) == 0,
        "tarea_id": tarea_id,
        "ejecutadas": exitosas,
        "fallidas": fallidas,
        "mensaje": f"{len(exitosas)} ejecutadas, {len(fallidas)} fallidas.",
    }


async def _crear_branch_si_no_existe(repo: str, branch: str) -> None:
    """Crea la rama jarvis/subtareas si no existe."""
    try:
        await create_branch(repo, branch)
    except Exception as exc:
        logger.warning("Branch %s ya existe o no se pudo crear: %s", branch, exc)


async def commitear_resultado(
    tarea_id: str,
    subtarea_id: str,
    mensaje_commit: Optional[str] = None,
) -> Dict[str, Any]:
    """Sube el resultado de una subtarea al repo. Si falla, lo deja pendiente."""
    tarea = storage.obtener_tarea(tarea_id)
    if not tarea:
        return {"ok": False, "error": "Tarea no encontrada"}

    subtarea = storage.obtener_subtarea(subtarea_id)
    if not subtarea:
        return {"ok": False, "error": "Subtarea no encontrada"}

    repo = subtarea.get("repo") or tarea.get("github_repo", "")
    if not repo:
        return {"ok": False, "error": "No hay repositorio asociado"}

    archivo = subtarea.get("archivo", "")
    if not archivo:
        return {"ok": False, "error": "La subtarea no indica archivo de destino"}

    resultado = subtarea.get("resultado", "")
    if not resultado:
        return {"ok": False, "error": "La subtarea no tiene resultado para commitear"}

    branch = subtarea.get("branch") or f"jarvis/subtareas-{tarea.get('id', '')}"
    default_mensaje = f"Subtarea: {subtarea.get('titulo', '')}"
    mensaje = (mensaje_commit or default_mensaje)[:100]

    try:
        await _crear_branch_si_no_existe(repo, branch)
        sha = await commit_file(repo, archivo, resultado, branch, mensaje)
        storage.actualizar_subtarea(
            subtarea_id,
            repo=repo,
            branch=branch,
            commit_pendiente=False,
            commit_sha=sha,
        )
        return {"ok": True, "subtarea_id": subtarea_id, "sha": sha, "branch": branch}
    except Exception as exc:
        logger.exception("Error commiteando subtarea %s", subtarea_id)
        storage.actualizar_subtarea(subtarea_id, repo=repo, branch=branch, commit_pendiente=True)
        return {"ok": False, "error": str(exc), "subtarea_id": subtarea_id, "pendiente": True}


async def commitear_resultados_tarea(tarea_id: str) -> Dict[str, Any]:
    """Commitea los resultados de todas las subtareas completadas de una tarea."""
    tarea = storage.obtener_tarea(tarea_id)
    if not tarea:
        return {"ok": False, "error": "Tarea no encontrada"}

    subtareas = [
        s for s in tarea.get("subtareas", [])
        if s.get("estado") == "completada" and s.get("resultado")
    ]

    if not subtareas:
        return {"ok": True, "mensaje": "No hay resultados para commitear", "commits": []}

    resultados = await asyncio.gather(*[
        commitear_resultado(tarea_id, s["id"])
        for s in subtareas
    ])
    exitosas = [r for r in resultados if r.get("ok")]
    fallidas = [r for r in resultados if not r.get("ok")]

    return {
        "ok": len(fallidas) == 0,
        "tarea_id": tarea_id,
        "commits": exitosas,
        "pendientes": fallidas,
        "mensaje": f"{len(exitosas)} commiteados, {len(fallidas)} pendientes.",
    }


async def sincronizar_commits_pendientes(tarea_id: Optional[str] = None) -> Dict[str, Any]:
    """Reintenta commitear subtareas marcadas como pendientes."""
    if tarea_id:
        tareas = [storage.obtener_tarea(tarea_id)]
    else:
        tareas = storage.listar_tareas()

    subtareas_pendientes = []
    for t in tareas:
        if not t:
            continue
        for s in t.get("subtareas", []):
            if s.get("commit_pendiente") and s.get("resultado"):
                subtareas_pendientes.append((t["id"], s["id"]))

    if not subtareas_pendientes:
        return {"ok": True, "mensaje": "No hay commits pendientes", "commits": []}

    resultados = await asyncio.gather(*[
        commitear_resultado(t_id, s_id)
        for t_id, s_id in subtareas_pendientes
    ])
    exitosas = [r for r in resultados if r.get("ok")]
    fallidas = [r for r in resultados if not r.get("ok")]

    return {
        "ok": len(fallidas) == 0,
        "commits": exitosas,
        "pendientes": fallidas,
        "mensaje": f"{len(exitosas)} sincronizados, {len(fallidas)} aún pendientes.",
    }
