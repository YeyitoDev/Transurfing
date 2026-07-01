"""
subtarea_sintesis_service.py - Agente que sintetiza y estructura las ideas de una subtarea.

Toma una subtarea (título, descripción, prompt, resultado) junto con el contexto de su
tarea padre y devuelve:
  - una descripción reescrita, clara y accionable,
  - un resumen de una sola línea,
  - una lista estructurada de "subdetalles" (pasos concretos y ordenados).

Por defecto aplica el resultado al almacenamiento (mejora la descripción/resumen de la
subtarea y reemplaza sus subdetalles). Es best-effort: si el LLM no está disponible o
falla, devuelve {"ok": False, "error": ...} sin romper la app.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import storage

logger = logging.getLogger(__name__)

SYSTEM = (
    "Eres un agente experto en estructurar y sintetizar ideas de trabajo. "
    "Conviertes notas dispersas en pasos claros, accionables y bien ordenados. "
    "Respondes ÚNICAMENTE con JSON válido, sin texto adicional."
)


def _cliente_llm(modelo: Optional[str] = None):
    """Devuelve (cliente, modelo) usando la misma lógica que el resto de agentes."""
    from voz_service import _obtener_cliente, _obtener_cliente_groq, _usar_groq_llm

    try:
        if _usar_groq_llm():
            return _obtener_cliente_groq(), modelo or os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
        return _obtener_cliente(), modelo or os.getenv("LLM_MODEL", "qwen3.5-plus")
    except Exception:
        return None, None


def _extraer_json(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    return json.loads(raw)


def _localizar(subtarea_id: str):
    """Devuelve (tarea_decorada, subtarea) o (None, None)."""
    for t in storage.listar_tareas():
        for s in t.get("subtareas", []):
            if s.get("id") == subtarea_id:
                return t, s
    return None, None


def _normalizar_subdetalles(datos: Dict[str, Any]) -> List[Dict[str, str]]:
    salida: List[Dict[str, str]] = []
    for it in datos.get("subdetalles", []) or []:
        if isinstance(it, dict):
            titulo = str(it.get("titulo", "")).strip()
            nota = str(it.get("nota", "")).strip()
        elif isinstance(it, str):
            titulo, nota = it.strip(), ""
        else:
            continue
        if titulo:
            salida.append({"titulo": titulo, "nota": nota})
    return salida


async def sintetizar_subtarea(
    subtarea_id: str,
    modelo: Optional[str] = None,
    instrucciones: str = "",
    aplicar: bool = True,
) -> Dict[str, Any]:
    """Sintetiza una subtarea: mejora su descripción/resumen y genera subdetalles ordenados."""
    tarea, sub = _localizar(subtarea_id)
    if sub is None:
        return {"ok": False, "error": "Subtarea no encontrada"}

    contexto_sub = "\n".join(filter(None, [
        f"Título: {sub.get('titulo', '')}",
        f"Descripción actual: {sub.get('descripcion', '') or 'Ninguna'}",
        f"Prompt/objetivo: {sub.get('prompt', '') or 'Ninguno'}",
        (f"Resultado previo: {(sub.get('resultado', '') or '')[:800]}" if sub.get("resultado") else ""),
    ]))
    sd_actuales = sub.get("subdetalles", []) or []
    sd_text = "\n".join(f"- {sd.get('titulo', '')}" for sd in sd_actuales) or "Ninguno."

    prompt = (
        f"Contexto del proyecto: «{tarea.get('titulo', '')}» "
        f"(categoría: {tarea.get('etiqueta', 'tarea')}).\n\n"
        f"SUBTAREA A SINTETIZAR:\n{contexto_sub}\n\n"
        f"Subdetalles existentes:\n{sd_text}\n\n"
        + (f"Instrucciones adicionales del usuario: {instrucciones.strip()}\n\n" if instrucciones.strip() else "")
        + "Tu trabajo:\n"
        "1. 'descripcion': reescribe la subtarea en 1-2 frases claras y accionables (sintetiza la idea).\n"
        "2. 'resumen': una sola línea (máx 12 palabras) con la esencia.\n"
        "3. 'subdetalles': 3-6 pasos concretos y ORDENADOS para completar la subtarea. "
        "Cada uno: {\"titulo\": \"paso corto y accionable\", \"nota\": \"detalle breve opcional\"}. "
        "Integra y mejora los subdetalles existentes si aportan valor.\n\n"
        "Devuelve SOLO JSON: {\"descripcion\": \"...\", \"resumen\": \"...\", "
        "\"subdetalles\": [{\"titulo\": \"...\", \"nota\": \"...\"}]}."
    )

    cliente, modelo_def = _cliente_llm(modelo)
    if cliente is None:
        return {"ok": False, "error": "LLM no disponible (configura OPENAI_API_KEY/OPENAI_BASE_URL)."}

    try:
        resp = await cliente.chat.completions.create(
            model=modelo or modelo_def,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=1200,
        )
        datos = _extraer_json(resp.choices[0].message.content or "")
    except Exception as exc:
        logger.exception("Error sintetizando subtarea %s: %s", subtarea_id, exc)
        return {"ok": False, "error": str(exc)}

    descripcion = str(datos.get("descripcion", "")).strip()
    resumen = str(datos.get("resumen", "")).strip()
    subdetalles = _normalizar_subdetalles(datos)

    tarea_actualizada = None
    if aplicar:
        if descripcion or resumen:
            storage.actualizar_subtarea(
                subtarea_id,
                descripcion=descripcion or None,
                resumen=resumen or None,
            )
        if subdetalles:
            tarea_actualizada = storage.reemplazar_subdetalles(subtarea_id, subdetalles)
        if tarea_actualizada is None:
            tarea_actualizada = storage.obtener_tarea(tarea.get("id"))

    return {
        "ok": True,
        "descripcion": descripcion,
        "resumen": resumen,
        "subdetalles": subdetalles,
        "aplicado": bool(aplicar),
        "tarea": tarea_actualizada,
    }
