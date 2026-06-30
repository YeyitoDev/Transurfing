"""
agente_planes.py - Agentes especializados para objetivos de aprendizaje y proyectos.

Genera planes de acción personalizados para preparaciones (maestría, trabajo,
proyectos) y busca novedades relevantes en internet para tareas de investigación.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any, Dict, List, Optional

import storage
from voz_service import _obtener_cliente, _obtener_cliente_groq, _usar_groq_llm

logger = logging.getLogger(__name__)

# Modelos Groq que ya no están disponibles y sus reemplazos recomendados
MODELOS_GROQ_OBSOLETOS = {
    "llama3-70b-8192": "llama-3.3-70b-versatile",
    "llama3-8b-8192": "llama-3.1-8b-instant",
    "llama2-70b-4096": "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768": "llama-3.3-70b-versatile",
    "gemma-7b-it": "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile": "llama-3.3-70b-versatile",
}


def _modelo_groq_valido(modelo: str) -> str:
    """Devuelve un modelo Groq válido, mapeando modelos decomisionados."""
    if modelo in MODELOS_GROQ_OBSOLETOS:
        return MODELOS_GROQ_OBSOLETOS[modelo]
    return modelo


def _es_modelo_groq(modelo: Optional[str]) -> bool:
    m = (modelo or "").lower()
    return m.startswith(("llama", "mixtral", "gemma", "groq/", "qwen-qwq"))


def _seleccionar_cliente(modelo: Optional[str]):
    """Elige (cliente, modelo) según el proveedor implícito del id seleccionado.

    - Sin selección: respeta el comportamiento por defecto (Groq si está activo).
    - Modelo tipo Groq: usa el cliente Groq si está configurado.
    - Resto: gateway OpenAI-compatible (OpenCode Zen) con el id tal cual.
    """
    if not modelo:
        if _usar_groq_llm():
            return _obtener_cliente_groq(), _modelo_groq_valido(os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"))
        return _obtener_cliente(), os.getenv("LLM_MODEL", "qwen3.5-plus")
    if _es_modelo_groq(modelo):
        cli = _obtener_cliente_groq()
        if cli is not None:
            return cli, _modelo_groq_valido(modelo)
    return _obtener_cliente(), modelo

PLAN_PROMPT = """Eres Jarvis, asistente de planificación de Sergio.

El usuario tiene un objetivo: crear un proyecto, prepararse para una maestría, un nuevo trabajo,
o aprender algo nuevo. Tu trabajo es generar un plan de acción claro y crear tareas concretas.

Responde SOLO con JSON válido, sin markdown:

{
  "mensaje": "Resumen motivador del plan (2 frases)",
  "plan": {
    "semanas": 4,
    "frecuencia": "diaria",
    "primer_paso": "Primer paso concreto para empezar hoy"
  },
  "tareas": [
    {
      "titulo": "Tarea concreta",
      "descripcion": "Detalle de qué hacer",
      "etiqueta": "tarea" | "habito" | "emprendimiento" | "investigacion",
      "prioridad": "alta" | "media" | "baja",
      "objetivo": "nombre del objetivo",
      "repetible": false,
      "dias_semana": ["lun", "mar", "mie"],
      "horas": ["08:00"]
    }
  ]
}

Reglas:
- Genera entre 5 y 10 tareas que cubran validación, aprendizaje y avance práctico.
- Si el objetivo requiere estudio constante, incluye al menos 1 hábito repetible con días de semana y hora.
- Etiqueta correctamente: emprendimiento para proyectos, investigacion para estudios, habito para rutinas.
- El objetivo de cada tarea debe ser el mismo que el objetivo del usuario.
- Sé realista con el tiempo y la progresión de dificultad.
- No uses markdown, solo JSON.
"""

BUSCAR_PROMPT = """Eres Jarvis, un asistente de investigación. El usuario está estudiando un tema.

Responde SOLO con JSON válido, sin markdown:

{
  "mensaje": "Resumen de 2-3 frases con novedades o tendencias relevantes",
  "recursos": [
    {"titulo": "Nombre del recurso", "tipo": "articulo|video|curso|herramienta", "url": "https://ejemplo.com", "relevancia": "Por qué es relevante"}
  ]
}

El campo url debe ser una URL real y verosímil cuando sea posible; si no tienes una URL exacta, usa el sitio más probable (github.com, arxiv.org, coursera.org, etc.) con un path representativo.
"""


def _tareas_relacionadas(objetivo: str) -> List[Dict[str, Any]]:
    """Devuelve tareas existentes que parecen relacionadas con el objetivo."""
    todas = storage.listar_tareas()
    objetivo_lower = objetivo.lower()
    rel = []
    for t in todas:
        texto = f"{t['titulo']} {t.get('descripcion', '')} {t.get('objetivo', '')}".lower()
        # Coincidencia por palabra clave o por objetivo exacto
        if t.get("objetivo", "").lower() == objetivo_lower or any(p in texto for p in objetivo_lower.split() if len(p) > 3):
            rel.append(t)
    return rel[:10]


async def generar_plan(objetivo: str, semanas: int = 4) -> Dict[str, Any]:
    """Genera un plan de tareas para un objetivo usando LLM."""
    if _usar_groq_llm():
        cliente = _obtener_cliente_groq()
        modelo = _modelo_groq_valido(os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"))
    else:
        cliente = _obtener_cliente()
        modelo = os.getenv("LLM_MODEL", "qwen3.5-plus")

    tareas_previas = _tareas_relacionadas(objetivo)
    contexto = "Tareas previas relacionadas:\n"
    if tareas_previas:
        for t in tareas_previas:
            estado = "completada" if t["estado"] == "completada" else f"{t['progreso']}%"
            contexto += f"- {t['titulo']} ({estado})\n"
    else:
        contexto += "No hay tareas previas.\n"

    user_content = (
        f'Objetivo: "{objetivo}"\n'
        f'Duración objetivo: {semanas} semanas\n'
        f'Fecha actual: {date.today().isoformat()}\n\n'
        f'{contexto}'
    )

    try:
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": PLAN_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.4,
            max_tokens=1200,
        )
        contenido = response.choices[0].message.content or ""
        contenido_limpio = contenido.strip()
        if contenido_limpio.startswith("```"):
            lineas = [l for l in contenido_limpio.split("\n") if not l.startswith("```")]
            contenido_limpio = "\n".join(lineas).strip()

        datos = json.loads(contenido_limpio)
        # Asegurar que cada tarea tenga el objetivo
        for t in datos.get("tareas", []):
            t.setdefault("objetivo", objetivo)
        return {
            "accion": "plan_generado",
            "mensaje": datos.get("mensaje", "Plan generado."),
            "plan": datos.get("plan", {}),
            "tareas": datos.get("tareas", []),
        }
    except json.JSONDecodeError:
        logger.error("JSON inválido del LLM para plan: %s", contenido[:300])
        return {"accion": "error", "mensaje": "No pude generar el plan. Intenta de nuevo.", "plan": {}, "tareas": []}
    except Exception as exc:
        logger.exception("Error generando plan: %s", exc)
        return {"accion": "error", "mensaje": "Ocurrió un error generando el plan.", "plan": {}, "tareas": []}


IDEA_PROMPT = """Eres un equipo de agentes investigadores especializados que trabajan para Sergio.
Tu trabajo es VALIDAR la viabilidad de una idea/objetivo que él te describe (estudiar una maestría,
emprender, cambiar de carrera, etc.) y producir un INFORME DETALLADO y profesional.

Responde EXACTAMENTE en este formato (primero un bloque JSON de metadatos, luego el delimitador, luego el informe en Markdown):

<<<META>>>
{
  "titulo": "Título corto de la idea (máx 8 palabras)",
  "descripcion": "Resumen ejecutivo de 1-2 frases",
  "objetivo": "Área/objetivo general",
  "prioridad": "alta" | "media" | "baja",
  "subtareas": ["Paso accionable 1", "Paso accionable 2", "..."]
}
<<<DOCUMENTO>>>
# Título del informe
...resto del informe en Markdown...

El METADATO debe ser JSON válido (sin saltos de línea dentro de los strings). Las subtareas: entre 5 y 12 pasos accionables.

El DOCUMENTO (después de <<<DOCUMENTO>>>) debe ser Markdown rico y extenso e incluir OBLIGATORIAMENTE:
1. Un título `#` y un resumen ejecutivo.
2. `## Beneficios` — qué gana con esta idea (lista).
3. `## Salidas profesionales` — con una **tabla** de roles, sector y rango salarial estimado en USD/PEN.
4. `## Plan de estudio / postulación` — con una **tabla** de fases, fechas relativas (ej: Semana 1-2) y entregables.
5. `## Cronograma` — un bloque de código ```mermaid con un diagrama (flowchart TD) de las fases en el tiempo.
6. `## Mapa conceptual` — un segundo bloque ```mermaid (flowchart TD) con las áreas de conocimiento clave.
7. `## Análisis monetario` — una **tabla** con costos (matrícula, materiales, tiempo), retorno esperado y totales.
8. `## Comparación de alternativas` — una **tabla** comparando opciones (ej: Matemática vs Física) con pros/contras.
9. `## Fuentes` — lista de fuentes citadas con enlaces verosímiles (universidades, portales oficiales).
10. `## Conclusión y recomendación` — veredicto sobre la viabilidad.

Reglas para mermaid (IMPORTANTE para que se renderice):
- Usa `flowchart TD` con nodos así: `A[Texto simple] --> B[Texto simple]`.
- NO uses paréntesis, comillas, dos puntos ni caracteres especiales dentro de los corchetes.
- Máximo 12 nodos por diagrama.

Escribe en español. Sé concreto, realista y cita cifras plausibles.
"""


def _parsear_idea(contenido: str) -> Optional[Dict[str, Any]]:
    """Extrae metadatos JSON y documento markdown de la respuesta del LLM."""
    texto = contenido.strip()
    # Quitar fences markdown externos si los hubiera
    if "<<<DOCUMENTO>>>" not in texto:
        return None
    meta_part, doc_part = texto.split("<<<DOCUMENTO>>>", 1)
    meta_part = meta_part.replace("<<<META>>>", "").strip()
    # Aislar el objeto JSON dentro de meta_part
    inicio = meta_part.find("{")
    fin = meta_part.rfind("}")
    if inicio == -1 or fin == -1:
        return None
    try:
        meta = json.loads(meta_part[inicio:fin + 1])
    except json.JSONDecodeError:
        return None
    documento = doc_part.strip()
    # Quitar fences de markdown que envuelvan todo el documento
    if documento.startswith("```"):
        lineas = documento.split("\n")
        if lineas[0].startswith("```"):
            lineas = lineas[1:]
        if lineas and lineas[-1].strip() == "```":
            lineas = lineas[:-1]
        documento = "\n".join(lineas).strip()
    return {"meta": meta, "documento": documento}


async def analizar_idea(prompt: str) -> Dict[str, Any]:
    """Genera un informe profundo para validar una idea/objetivo del usuario."""
    if _usar_groq_llm():
        cliente = _obtener_cliente_groq()
        modelo = _modelo_groq_valido(os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"))
    else:
        cliente = _obtener_cliente()
        modelo = os.getenv("LLM_MODEL", "qwen3.5-plus")

    tareas_previas = _tareas_relacionadas(prompt)
    contexto = ""
    if tareas_previas:
        contexto = "\nTareas/contexto previo del usuario:\n" + "\n".join(
            f"- {t['titulo']} ({t.get('objetivo', '')})" for t in tareas_previas
        )

    user_content = (
        f"Idea/objetivo a validar:\n\"{prompt}\"\n\n"
        f"Fecha actual: {date.today().isoformat()}{contexto}\n\n"
        "Genera el informe completo siguiendo el formato indicado (<<<META>>> JSON y <<<DOCUMENTO>>> Markdown)."
    )

    try:
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": IDEA_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.5,
            max_tokens=5000,
        )
        contenido = response.choices[0].message.content or ""
        parsed = _parsear_idea(contenido)
        if not parsed:
            logger.error("Formato inesperado del LLM para idea: %s", contenido[:300])
            return {"accion": "error", "mensaje": "No pude generar el informe. Intenta reformular la idea.", "documento": "", "subtareas": []}

        meta = parsed["meta"]
        return {
            "accion": "idea_analizada",
            "titulo": meta.get("titulo", "Idea por validar"),
            "descripcion": meta.get("descripcion", ""),
            "objetivo": meta.get("objetivo", ""),
            "prioridad": meta.get("prioridad", "media"),
            "documento": parsed["documento"],
            "subtareas": meta.get("subtareas", []),
        }
    except Exception as exc:
        logger.exception("Error analizando idea: %s", exc)
        return {"accion": "error", "mensaje": "Ocurrió un error generando el informe.", "documento": "", "subtareas": []}


def _parsear_subtareas_json(texto: str) -> List[Dict[str, str]]:
    """Extrae array de objetos {titulo, prompt, archivo} de un texto JSON."""
    texto = texto.strip()
    if not texto or texto == "[]":
        return []
    # Eliminar posible delimitador de código markdown
    if texto.startswith("```"):
        lineas = texto.splitlines()
        if lineas[0].strip().startswith("```"):
            lineas = lineas[1:]
        if lineas and lineas[-1].strip().startswith("```"):
            lineas = lineas[:-1]
        texto = "\n".join(lineas).strip()
    try:
        data = json.loads(texto)
    except json.JSONDecodeError:
        logger.warning("No se pudo parsear JSON de subtareas, intentando líneas")
        # fallback: líneas con título opcional
        return [
            {"titulo": line.strip("- ").strip(), "prompt": "", "archivo": ""}
            for line in texto.splitlines()
            if line.strip() and line.strip().upper() not in ("NINGUNA", "[]")
        ]
    if not isinstance(data, list):
        return []
    resultado = []
    for item in data:
        if isinstance(item, str):
            resultado.append({"titulo": item, "prompt": "", "archivo": ""})
        elif isinstance(item, dict):
            titulo = item.get("titulo", "")
            if not titulo:
                continue
            resultado.append({
                "titulo": titulo.strip(),
                "prompt": str(item.get("prompt", "")).strip(),
                "archivo": str(item.get("archivo", "")).strip(),
            })
    return resultado


async def chat_subtareas(
    tarea: Dict[str, Any],
    sesion_id: str,
    mensaje: str,
    modelo: Optional[str] = None,
    archivos: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Chat para generar subtareas y priorizar dentro de una tarea."""
    logger.info("[chat_subtareas] tarea=%s sesion=%s mensaje=%s", tarea.get("id"), sesion_id, mensaje[:80])
    cliente, modelo = _seleccionar_cliente(modelo)

    # Recuperar historial de la sesión actual
    sesion = None
    for s in tarea.get("chat_sesiones", []):
        if s["id"] == sesion_id:
            sesion = s
            break
    historial = []
    if sesion:
        for m in sesion.get("mensajes", [])[-10:]:
            historial.append(f"{m['rol'].upper()}: {m['texto']}")
    historial_text = "\n".join(historial) if historial else "Sin mensajes previos."

    subtareas_actuales = "\n".join(f"- {s['titulo']}" for s in tarea.get("subtareas", [])) or "Sin subtareas."

    archivos_texto = ""
    if archivos:
        partes = []
        for a in archivos:
            nombre = a.get("nombre", "archivo")
            tipo = a.get("tipo", "text/plain")
            contenido = a.get("contenido", "")
            if not contenido:
                continue
            partes.append(f"--- ARCHIVO: {nombre} (tipo: {tipo}) ---\n{contenido}\n--- FIN ARCHIVO ---")
        archivos_texto = "\n\n".join(partes)

    es_primer_mensaje = len(sesion.get("mensajes", [])) == 0 if sesion else True
    prompt = (
        f"Eres Jarvis, un asistente de productividad. Ayuda a descomponer la tarea del usuario en subtareas claras, accionables y con suficiente detalle para que un agente autónomo pueda ejecutarlas en paralelo.\n\n"
        f"TAREA: {tarea['titulo']}\n"
        f"Descripción: {tarea.get('descripcion', '') or 'Ninguna'}\n"
        f"Prioridad: {tarea.get('prioridad', 'media')}. Progreso: {tarea.get('progreso', 0)}%.\n"
        f"Objetivo/área: {tarea.get('objetivo', '') or 'no especificado'}\n"
        f"Repositorio vinculado: {tarea.get('github_repo', '') or 'ninguno'}\n\n"
        f"Subtareas actuales:\n{subtareas_actuales}\n\n"
        f"Historial reciente de la conversación:\n{historial_text}\n\n"
        f"{('Archivos adjuntos:\n' + archivos_texto + '\n\n') if archivos_texto else ''}"
        f"MENSAJE DEL USUARIO: {mensaje}\n\n"
        "Responde en formato estructurado con estas secciones EXACTAS:\n"
        "<<<RESPUESTA>>>\n"
        "[respuesta natural en 2-3 párrafos, concreta, con preguntas de seguimiento si hace falta]\n"
        "<<<SUBTAREAS>>>\n"
        "[JSON válido con array de objetos. Cada objeto: {\"titulo\": \"...\", \"prompt\": \"...\", \"archivo\": \"...\"}. El prompt debe ser detallado, como si fuera a enviarse a un agente. El archivo es el path relativo en el repo donde guardar el resultado. Escribe [] si no corresponde crear subtareas.]\n"
        "<<<PROXIMA_ALTA_VALOR>>>\n"
        "[una sola frase con la próxima acción de mayor valor para la tarea]\n"
        "<<<TITULO_SESION>>>\n"
        "[título corto y descriptivo para esta conversación basado en el mensaje del usuario, máximo 5 palabras]\n"
    )

    try:
        logger.info("[chat_subtareas] llamando LLM modelo=%s", modelo)
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Eres un asistente pragmático. Devuelve SIEMPRE las cuatro secciones con los delimitadores exactos."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=1200,
        )
        contenido = response.choices[0].message.content.strip()
        logger.info("[chat_subtareas] raw contenido:\n%s", contenido[:500])
    except Exception as exc:
        logger.exception("Error en chat_subtareas: %s", exc)
        return {"respuesta": "No pude procesar el mensaje ahora. Intenta de nuevo.", "subtareas": [], "proxima_alta_valor": "", "titulo_sesion": ""}

    respuesta_texto = ""
    subtareas_texto = ""
    proxima_alta_valor = ""
    titulo_sesion = ""

    if "<<<RESPUESTA>>>" in contenido:
        partes = contenido.split("<<<RESPUESTA>>>")
        resto = partes[1] if len(partes) > 1 else contenido
        if "<<<SUBTAREAS>>>" in resto:
            respuesta_texto, resto = resto.split("<<<SUBTAREAS>>>", 1)
        else:
            respuesta_texto = resto
            resto = ""
        if "<<<PROXIMA_ALTA_VALOR>>>" in resto:
            subtareas_texto, resto = resto.split("<<<PROXIMA_ALTA_VALOR>>>", 1)
        else:
            subtareas_texto = resto
            resto = ""
        if "<<<TITULO_SESION>>>" in resto:
            proxima_alta_valor, titulo_sesion = resto.split("<<<TITULO_SESION>>>", 1)
        else:
            proxima_alta_valor = resto
    else:
        respuesta_texto = contenido

    subtareas = _parsear_subtareas_json(subtareas_texto)

    resultado = {
        "respuesta": respuesta_texto.strip() or "No pude generar una respuesta clara.",
        "subtareas": subtareas,
        "proxima_alta_valor": proxima_alta_valor.strip(),
        "titulo_sesion": titulo_sesion.strip() or "",
    }
    logger.info("[chat_subtareas] resultado parseado: %s", resultado)
    return resultado


async def ejecutar_agente(agente: Dict[str, Any], prompt: str, tarea_id: Optional[str] = None, max_tokens: int = 1200) -> str:
    """Ejecuta un agente especializado con su modelo y contexto propios."""
    from voz_service import _obtener_cliente, _obtener_cliente_groq

    modelo = agente.get("modelo", "llama-3.3-70b-versatile")
    es_groq = modelo.startswith("llama") or modelo.startswith("mixtral") or modelo.startswith("gemma")

    if es_groq:
        cliente = _obtener_cliente_groq()
        modelo = _modelo_groq_valido(modelo)
    else:
        cliente = _obtener_cliente()

    system = agente.get("system_prompt", "Eres un asistente útil.").strip()

    # Inyectar skills y knowledge como contexto
    contexto = []
    skills = agente.get("skills", [])
    knowledge_ids = agente.get("knowledge", [])
    if skills or knowledge_ids:
        for sk in storage.listar_skills():
            if sk["id"] in skills:
                contexto.append(f"## Skill: {sk['nombre']}\n{sk['instrucciones']}")
        for kn in storage.listar_knowledge():
            if kn["id"] in knowledge_ids:
                contexto.append(f"## Knowledge: {kn['nombre']}\n{kn['contenido']}")

    if tarea_id:
        tarea = storage.obtener_tarea(tarea_id)
        if tarea:
            contexto.append(f"## Contexto de tarea: {tarea['titulo']}\n{tarea.get('descripcion', '')}")

    contexto_text = "\n\n".join(contexto)
    if contexto_text:
        prompt = f"{contexto_text}\n\n---\n\nPregunta o tarea del usuario:\n{prompt}"

    try:
        logger.info("[ejecutar_agente] agente=%s modelo=%s max_tokens=%s", agente.get("nombre"), modelo, max_tokens)
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.exception("Error ejecutando agente: %s", exc)
        raise


async def resumen_tarea(tarea: Dict[str, Any]) -> str:
    """Genera un resumen accionable sobre qué hacer con una tarea."""
    if _usar_groq_llm():
        cliente = _obtener_cliente_groq()
        modelo = _modelo_groq_valido(os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"))
    else:
        cliente = _obtener_cliente()
        modelo = os.getenv("LLM_MODEL", "qwen3.5-plus")

    subtareas_pendientes = [s["titulo"] for s in tarea.get("subtareas", []) if not s.get("completada")]
    subtareas_text = "\n".join(f"- {s}" for s in subtareas_pendientes) if subtareas_pendientes else "Sin subtareas pendientes."
    fecha = tarea.get("fecha_limite") or "sin fecha límite"

    prompt = (
        f"Resumen ejecutivo para la tarea del usuario: {tarea['titulo']}.\n"
        f"Prioridad: {tarea.get('prioridad', 'media')}. Estado: {tarea.get('estado', 'pendiente')}. Progreso: {tarea.get('progreso', 0)}%.\n"
        f"Descripción: {tarea.get('descripcion', '') or 'Ninguna'}\n"
        f"Fecha límite: {fecha}\n"
        f"Objetivo/área: {tarea.get('objetivo', '') or 'no especificado'}\n"
        f"Subtareas pendientes:\n{subtareas_text}\n\n"
        "Instrucciones: en 3-4 bullets cortos, di qué debe hacer el usuario ahora, qué riesgos hay si no avanza, y qué priorizar."
    )

    try:
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Eres Jarvis, asistente de productividad. Sé concreto, accionable y directo."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip() or "Sin resumen disponible."
    except Exception as exc:
        logger.exception("Error generando resumen de tarea: %s", exc)
        return "No pude generar el resumen en este momento."


async def mejorar_descripcion(tarea: Dict[str, Any]) -> str:
    """Genera una descripción mejorada y clara del proyecto/tarea usando LLM."""
    if _usar_groq_llm():
        cliente = _obtener_cliente_groq()
        modelo = _modelo_groq_valido(os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"))
    else:
        cliente = _obtener_cliente()
        modelo = os.getenv("LLM_MODEL", "qwen3.5-plus")

    subtareas = [s["titulo"] for s in tarea.get("subtareas", [])]
    subtareas_text = "\n".join(f"- {s}" for s in subtareas) if subtareas else "Sin subtareas."

    prompt = (
        "Mejora y enriquece la descripción de este proyecto/tarea para que sea clara y motivadora.\n"
        f"Título: {tarea['titulo']}\n"
        f"Descripción actual: {tarea.get('descripcion', '') or 'Ninguna'}\n"
        f"Objetivo/área: {tarea.get('objetivo', '') or 'no especificado'}\n"
        f"Etiqueta: {tarea.get('etiqueta', 'tarea')}\n"
        f"Subtareas:\n{subtareas_text}\n\n"
        "Devuelve SOLO la descripción mejorada (2-4 frases), sin títulos ni comentarios meta. "
        "Explica qué es, su propósito y el resultado esperado. Español, tono claro y profesional."
    )

    try:
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Eres un redactor experto en describir proyectos de forma clara y concisa."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.exception("Error mejorando descripción: %s", exc)
        return ""


async def buscar_novedades(tema: str) -> Dict[str, Any]:
    """Busca novedades relevantes para un tema de investigación usando LLM."""
    if _usar_groq_llm():
        cliente = _obtener_cliente_groq()
        modelo = _modelo_groq_valido(os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"))
    else:
        cliente = _obtener_cliente()
        modelo = os.getenv("LLM_MODEL", "qwen3.5-plus")

    try:
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": BUSCAR_PROMPT},
                {"role": "user", "content": f'Tema: "{tema}"\nFecha actual: {date.today().isoformat()}\n\nResume novedades, tendencias y recursos útiles relevantes para este tema.'},
            ],
            temperature=0.5,
            max_tokens=800,
        )
        contenido = response.choices[0].message.content or ""
        contenido_limpio = contenido.strip()
        if contenido_limpio.startswith("```"):
            lineas = [l for l in contenido_limpio.split("\n") if not l.startswith("```")]
            contenido_limpio = "\n".join(lineas).strip()

        datos = json.loads(contenido_limpio)
        return {
            "accion": "novedades",
            "mensaje": datos.get("mensaje", "Aquí tienes novedades relevantes."),
            "recursos": datos.get("recursos", []),
        }
    except json.JSONDecodeError:
        logger.error("JSON inválido del LLM para novedades: %s", contenido[:300])
        return {"accion": "error", "mensaje": "No pude buscar novedades ahora.", "recursos": []}
    except Exception as exc:
        logger.exception("Error buscando novedades: %s", exc)
        return {"accion": "error", "mensaje": "Ocurrió un error buscando novedades.", "recursos": []}


_FEED_SISTEMA = (
    "Eres un curador de novedades e inspiración para proyectos personales. "
    "Devuelves SOLO JSON válido, sin markdown ni texto extra."
)


async def generar_feed(tareas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Genera un feed de inspiración/novedades por proyecto activo usando LLM."""
    if _usar_groq_llm():
        cliente = _obtener_cliente_groq()
        modelo = _modelo_groq_valido(os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"))
    else:
        cliente = _obtener_cliente()
        modelo = os.getenv("LLM_MODEL", "qwen3.5-plus")

    activos = [t for t in tareas if t.get("estado") != "completada"][:6]
    generado_en = date.today().isoformat()
    if not activos:
        return {"items": [], "generado_en": generado_en}

    lista = "\n".join(
        f"- {t['titulo']} (área: {t.get('objetivo', '') or t.get('etiqueta', 'general')})"
        for t in activos
    )
    prompt = (
        f"Fecha actual: {generado_en}.\n"
        f"Estos son mis proyectos activos:\n{lista}\n\n"
        "Para cada proyecto sugiere 1-2 ítems de feed que me mantengan inspirado e informado: "
        "novedades a vigilar, herramientas o modelos que probar, ideas o recursos relevantes para ese dominio "
        "(por ejemplo, si el proyecto es de IA, modelos nuevos que valga la pena probar).\n"
        "Responde SOLO con JSON: {\"items\": [{\"proyecto\": \"<titulo exacto>\", "
        "\"tipo\": \"modelo|noticia|inspiracion|recurso|consejo\", \"titulo\": \"...\", "
        "\"resumen\": \"1-2 frases\", \"sugerencia\": \"acción concreta para mi proyecto\"}]}. "
        "Máximo 10 ítems en total. Español."
    )
    contenido = ""
    try:
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": _FEED_SISTEMA},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1200,
        )
        contenido = (response.choices[0].message.content or "").strip()
        if contenido.startswith("```"):
            contenido = "\n".join(l for l in contenido.split("\n") if not l.startswith("```")).strip()
        datos = json.loads(contenido)
        crudos = datos.get("items", []) if isinstance(datos, dict) else (datos if isinstance(datos, list) else [])
        items = []
        for it in crudos[:12]:
            if not isinstance(it, dict):
                continue
            items.append({
                "proyecto": str(it.get("proyecto", "")).strip(),
                "tipo": str(it.get("tipo", "inspiracion")).strip().lower(),
                "titulo": str(it.get("titulo", "")).strip(),
                "resumen": str(it.get("resumen", "")).strip(),
                "sugerencia": str(it.get("sugerencia", "")).strip(),
            })
        return {"items": items, "generado_en": generado_en}
    except json.JSONDecodeError:
        logger.error("JSON inválido del LLM para feed: %s", contenido[:300])
        return {"items": [], "generado_en": generado_en, "error": "respuesta no válida"}
    except Exception as exc:
        logger.exception("Error generando feed: %s", exc)
        return {"items": [], "generado_en": generado_en, "error": str(exc)}
