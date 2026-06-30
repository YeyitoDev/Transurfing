import json
import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _cliente_llm():
    from voz_service import _obtener_cliente, _obtener_cliente_groq

    modelo = os.getenv("LLM_MODEL", "qwen3.5-plus")
    es_groq = modelo.startswith("llama") or modelo.startswith("mixtral") or modelo.startswith("gemma")
    if es_groq:
        return _obtener_cliente_groq(), modelo
    return _obtener_cliente(), modelo


def _serializar_canvas(canvas: Optional[Dict[str, Any]]) -> str:
    if not canvas:
        return "Canvas vacío."
    bloques = canvas.get("bloques", [])
    links = canvas.get("links", [])
    lineas = []
    lineas.append(f"Bloques ({len(bloques)}):")
    for b in bloques:
        tipo = b.get("tipo", "texto")
        texto = b.get("texto", "")
        if not texto and b.get("contenido"):
            texto = json.dumps(b["contenido"], ensure_ascii=False)
        lineas.append(f"- [{tipo}] {texto[:120].replace(chr(10), ' ')}")
    if links:
        lineas.append(f"Enlaces ({len(links)}):")
        for l in links:
            lineas.append(f"- {l.get('a')} -> {l.get('b')}")
    return "\n".join(lineas)


async def interpretar_canvas(tarea: Dict[str, Any], modelo: Optional[str] = None) -> Dict[str, Any]:
    """Interpreta el canvas de una tarea y genera ideas/estructura."""
    canvas = tarea.get("canvas") or {}
    canvas_text = _serializar_canvas(canvas)

    subtareas = tarea.get("subtareas", [])
    subtareas_text = "\n".join(f"- {s['titulo']}" for s in subtareas) if subtareas else "Sin subtareas."

    prompt = (
        f"Eres un agente de prototipado y arquitectura de ideas. Tu trabajo es interpretar lo que el usuario ha dibujado "
        f"en su lienzo visual y ayudarle a ordenarlo, validarlo y generar nuevas ideas.\n\n"
        f"Tarea: {tarea['titulo']}\n"
        f"Descripción: {tarea.get('descripcion', '') or 'Ninguna'}\n"
        f"Subtareas existentes:\n{subtareas_text}\n\n"
        f"Lienzo visual del usuario:\n{canvas_text}\n\n"
        "Instrucciones:\n"
        "1. Resume en 2-3 líneas qué representa el lienzo (flujo, arquitectura, mapa de ideas, etc.).\n"
        "2. Identifica 3 oportunidades claras o próximos pasos lógicos basados en el dibujo.\n"
        "3. Sugiere 2-3 ideas nuevas que complementen o extiendan lo dibujado.\n"
        "4. Señala 1-2 riesgos o puntos ciegos que debería validar el usuario.\n"
        "5. Devuelve un JSON con las claves: interpretacion (string), oportunidades (array de strings), ideas (array de strings), riesgos (array de strings)."
    )

    system = "Eres un experto en prototipado visual, arquitectura de productos y facilitación de ideas. Respondes únicamente en JSON válido."

    try:
        cliente, modelo_default = _cliente_llm()
        modelo = modelo or modelo_default
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1600,
        )
        raw = response.choices[0].message.content.strip()
        # Extraer JSON si viene envuelto en markdown
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        parsed = json.loads(raw)
        return {
            "ok": True,
            "interpretacion": parsed.get("interpretacion", ""),
            "oportunidades": parsed.get("oportunidades", []),
            "ideas": parsed.get("ideas", []),
            "riesgos": parsed.get("riesgos", []),
        }
    except Exception as exc:
        logger.exception("Error interpretando canvas: %s", exc)
        return {
            "ok": False,
            "error": str(exc),
            "interpretacion": "No pude interpretar el canvas. Intenta agregar más bloques de texto.",
            "oportunidades": [],
            "ideas": [],
            "riesgos": [],
        }
