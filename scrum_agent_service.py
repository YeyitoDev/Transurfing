"""Agente Scrum Master + Project Manager.

Analiza una tarea (proyecto) y sus subtareas para recomendar los mejores
"quick wins" (alto impacto, bajo esfuerzo) en función del objetivo, además de
un diagnóstico del sprint/backlog y recomendaciones de priorización.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_IMPACTO_VALIDO = {"alto", "medio", "bajo"}
_ESFUERZO_VALIDO = {"alto", "medio", "bajo"}


def _cliente_llm():
    from voz_service import _obtener_cliente, _obtener_cliente_groq

    modelo = os.getenv("LLM_MODEL", "qwen3.5-plus")
    es_groq = modelo.startswith("llama") or modelo.startswith("mixtral") or modelo.startswith("gemma")
    if es_groq:
        return _obtener_cliente_groq(), modelo
    return _obtener_cliente(), modelo


def _serializar_subtareas(subtareas: List[Dict[str, Any]]) -> str:
    if not subtareas:
        return "Sin subtareas todavía."
    lineas = []
    for s in subtareas:
        completada = bool(s.get("completada")) or s.get("estado") == "completada"
        estado = "completada" if completada else (s.get("estado") or "pendiente")
        partes = [f"id={s.get('id')}", f"estado={estado}"]
        if s.get("score") is not None:
            partes.append(f"score={round(float(s['score']))}")
        if s.get("prompt"):
            partes.append("tiene_prompt")
        if s.get("resultado"):
            partes.append("tiene_resultado")
        meta = ", ".join(partes)
        titulo = (s.get("titulo") or "").strip()
        desc = (s.get("descripcion") or "").strip()
        linea = f"- [{meta}] {titulo}"
        if desc:
            linea += f" — {desc[:120]}"
        lineas.append(linea)
    return "\n".join(lineas)


def _norm_nivel(valor: Any, validos: set, defecto: str) -> str:
    v = str(valor or "").strip().lower()
    return v if v in validos else defecto


def _ids_validos(subtareas: List[Dict[str, Any]]) -> set:
    return {str(s.get("id")) for s in subtareas if s.get("id")}


async def analizar_quick_wins(tarea: Dict[str, Any], modelo: Optional[str] = None) -> Dict[str, Any]:
    """Diagnostica el proyecto y recomienda quick wins hacia el objetivo."""
    subtareas = tarea.get("subtareas", []) or []
    subtareas_text = _serializar_subtareas(subtareas)
    objetivo = (tarea.get("objetivo") or "").strip() or "No definido explícitamente."

    total = len(subtareas)
    resueltas = sum(1 for s in subtareas if bool(s.get("completada")) or s.get("estado") == "completada")

    prompt = (
        "Eres un Scrum Master y Project Manager senior. Analiza el proyecto y su backlog de "
        "subtareas y recomienda los mejores QUICK WINS: acciones de ALTO impacto hacia el objetivo "
        "y BAJO esfuerzo, que generen momentum cuanto antes.\n\n"
        f"Proyecto: {tarea.get('titulo', '')}\n"
        f"Objetivo: {objetivo}\n"
        f"Descripción: {tarea.get('descripcion', '') or 'Ninguna'}\n"
        f"Progreso: {resueltas}/{total} subtareas resueltas.\n\n"
        f"Backlog de subtareas (con id y estado):\n{subtareas_text}\n\n"
        "Instrucciones:\n"
        "1. Diagnostica en 2-3 líneas el estado del sprint/backlog respecto al objetivo (qué falta para avanzar).\n"
        "2. Identifica entre 3 y 5 quick wins priorizados (lo más alto impacto / bajo esfuerzo primero). "
        "Si un quick win corresponde a una subtarea EXISTENTE, usa su id en 'subtarea_id'; si es una acción "
        "NUEVA que conviene crear, deja 'subtarea_id' vacío.\n"
        "3. Da 2-4 recomendaciones de Project Manager (secuencia, dependencias, foco, qué dejar para después).\n"
        "4. Señala 1-2 riesgos o bloqueos que podrían frenar el avance.\n"
        "5. Devuelve ÚNICAMENTE un JSON válido con esta forma exacta:\n"
        "{\n"
        '  "analisis": "string",\n'
        '  "quick_wins": [{"titulo": "string", "justificacion": "string", "impacto": "alto|medio|bajo", "esfuerzo": "alto|medio|bajo", "subtarea_id": "id existente o cadena vacía"}],\n'
        '  "recomendaciones": ["string"],\n'
        '  "riesgos": ["string"]\n'
        "}"
    )

    system = (
        "Eres un Scrum Master y Project Manager experto en priorización por valor (impacto/esfuerzo), "
        "sprints y gestión de backlog. Respondes únicamente en JSON válido, en español."
    )

    try:
        cliente, modelo_default = _cliente_llm()
        modelo = modelo or modelo_default
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=1600,
        )
        raw = response.choices[0].message.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        parsed = json.loads(raw)

        ids = _ids_validos(subtareas)
        quick_wins = []
        for qw in (parsed.get("quick_wins") or [])[:6]:
            if not isinstance(qw, dict):
                continue
            titulo = (qw.get("titulo") or "").strip()
            if not titulo:
                continue
            sid = str(qw.get("subtarea_id") or "").strip()
            if sid not in ids:
                sid = ""
            quick_wins.append({
                "titulo": titulo,
                "justificacion": (qw.get("justificacion") or "").strip(),
                "impacto": _norm_nivel(qw.get("impacto"), _IMPACTO_VALIDO, "medio"),
                "esfuerzo": _norm_nivel(qw.get("esfuerzo"), _ESFUERZO_VALIDO, "medio"),
                "subtarea_id": sid,
            })

        return {
            "ok": True,
            "analisis": (parsed.get("analisis") or "").strip(),
            "quick_wins": quick_wins,
            "recomendaciones": [str(r).strip() for r in (parsed.get("recomendaciones") or []) if str(r).strip()][:6],
            "riesgos": [str(r).strip() for r in (parsed.get("riesgos") or []) if str(r).strip()][:4],
        }
    except Exception as exc:
        logger.exception("Error analizando quick wins: %s", exc)
        return {
            "ok": False,
            "error": str(exc),
            "analisis": "No pude generar el análisis Scrum en este momento. Inténtalo de nuevo.",
            "quick_wins": [],
            "recomendaciones": [],
            "riesgos": [],
        }
