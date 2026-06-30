"""
voz_service.py - Servicio de procesamiento de comandos de voz para tareas.

Usa el cliente OpenAI existente (llm_service.py) para interpretar lenguaje
natural y devolver JSON estructurado con la acción a realizar.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

import storage

load_dotenv()
logger = logging.getLogger(__name__)

DIAS_MAP = {
    "lunes": "lun", "martes": "mar", "miércoles": "mie", "miercoles": "mie",
    "jueves": "jue", "viernes": "vie", "sábado": "sab", "sabado": "sab",
    "domingo": "dom",
    "entre semana": "lun,mar,mie,jue,vie",
    "entre semanas": "lun,mar,mie,jue,vie",
    "toda la semana": "lun,mar,mie,jue,vie,sab,dom",
    "todos los días": "lun,mar,mie,jue,vie,sab,dom",
    "todos los dias": "lun,mar,mie,jue,vie,sab,dom",
    "diario": "lun,mar,mie,jue,vie,sab,dom",
    "diariamente": "lun,mar,mie,jue,vie,sab,dom",
    "fin de semana": "sab,dom",
    "fines de semana": "sab,dom",
}

# Hábitos, palabras clave y tipos
HABITO_KEYWORDS = ["hábito", "habito", "rutina", "cada día", "cada dia", "todos los días", "todos los dias", "repetir", "diario", "diariamente"]
INVESTIGACION_KEYWORDS = ["investiga", "estudiar", "analizar", "buscar info", "buscar información", "aprender sobre", "research"]
EMPRENDIMIENTO_KEYWORDS = ["proyecto", "emprender", "negocio", "startup", "emprendimiento"]
ALTA_KEYWORDS = ["urgente", "importante", "prioridad alta", "crítico", "critico", "apremiante"]
BAJA_KEYWORDS = ["prioridad baja", "poco importante", "cuando puedas", "tranqui"]

HORA_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.|AM|PM|A\.M\.|P\.M\.)?", re.IGNORECASE)
HORA_RE_24 = re.compile(r"\b(\d{1,2}):(\d{2})\b")
PERIODO_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(?:de la (mañana|tarde|noche|madrugada))", re.IGNORECASE)


def _extraer_hora(texto: str) -> list[str]:
    """Extrae horas en formato HH:MM de texto."""
    horas: list[str] = []
    # 24h formato HH:MM
    for m in HORA_RE_24.finditer(texto):
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            horas.append(f"{h:02d}:{mn:02d}")

    # "de la noche / tarde / mañana"
    for m in PERIODO_RE.finditer(texto):
        h = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        periodo = (m.group(3) or "").lower()
        if periodo in ("tarde", "noche") and h != 12:
            h += 12
        elif periodo == "mañana" and h == 12:
            h = 0
        elif periodo == "madrugada" and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= mn <= 59:
            horas.append(f"{h:02d}:{mn:02d}")

    # am/pm
    for m in HORA_RE.finditer(texto):
        if HORA_RE_24.search(m.group(0)) or PERIODO_RE.search(m.group(0)):
            continue
        h = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        ampm = (m.group(3) or "").lower().replace(".", "")
        if "pm" in ampm and h != 12:
            h += 12
        elif "am" in ampm and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= mn <= 59:
            horas.append(f"{h:02d}:{mn:02d}")
    return horas[:3]


def _extraer_dias(texto: str) -> list[str]:
    """Extrae días de la semana del texto."""
    texto_lower = texto.lower()
    dias: list[str] = []
    for clave, valor in DIAS_MAP.items():
        if clave in texto_lower:
            for d in valor.split(","):
                if d not in dias:
                    dias.append(d)
    # Si no hay días pero es hábito, asumir todos los días
    if not dias and any(k in texto_lower for k in HABITO_KEYWORDS):
        dias = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
    return dias


def _extraer_titulo_subtarea(texto: str) -> str:
    """Extrae el título de la subtarea de un comando como 'agregar subtarea X a tarea #N'."""
    t = texto.lower().strip()
    # Quitar conector + referencia a tarea al final
    t = re.sub(r"\s+(a|en|para|de)\s+(la\s+)?tarea\s*(?:número?|numero?|#)?\s*\d+\s*$", "", t, flags=re.IGNORECASE).strip()
    # Quitar referencia a tarea y número sueltos
    t = re.sub(r"tarea\s*(?:número?|numero?|#)?\s*\d+", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"(?:número?|numero?|#)\s*\d+", "", t, flags=re.IGNORECASE).strip()

    # Quitar verbos de acción (palabras completas seguidas de espacio)
    acciones = [
        "agregar", "agrega", "añadir", "añade", "adicionar", "adiciona",
        "crear", "crea", "hacer", "haz", "generar", "genera", "subtarea", "subtareas", "subtask",
    ]
    for _ in range(3):
        anterior = t
        for palabra in acciones:
            t = re.sub(rf"^{palabra}\s+", "", t, flags=re.IGNORECASE).strip()
        if t == anterior:
            break

    # Quitar artículos y preposiciones sueltos al inicio (palabra completa + espacio)
    for _ in range(3):
        anterior = t
        t = re.sub(r"^(a|de|en|con|para|por|la|el|los|las|una|un|que)\s+", "", t, flags=re.IGNORECASE).strip()
        if t == anterior:
            break

    t = t.strip().rstrip(".,;:")
    if t:
        t = t[0].upper() + t[1:]
    return t


def _extraer_titulo(texto: str) -> str:
    """Extrae el título de la acción, eliminando palabras de control, horas y días."""
    # Limpieza iterativa de palabras de control al inicio
    limpio = texto
    patrones = [
        r"^(quiero|quieres|me gustaría|me gustaria|podrías|podrias|puedes|podemos|vamos a|necesito|debería|deberia)\s+(que|generar|crear|hacer|agregar|añadir|me|se|una|un|el|la)\s*",
        r"^(generar|genera|hacer|haz|crear|crea|nueva|nuevo|una|un)\s+(nueva|nuevo|una|un|tarea|hábito|habito|recordatorio|reminder|para|de|que|el|la)\s*",
        r"^(crear|crea|nuevo|nueva|agregar|agrega|hacer|haz|genera|generar|añade|añadir|recordar|recuerda|recuerdame|recuérdame)\s+(un|una|nueva|nuevo|el|la|los|las|me|que|para)\s*",
        r"^(una|un|nueva|nuevo)\s+(tarea|hábito|habito|recordatorio|reminder)\s*(de|para|que|a|el|la)?\s*",
        r"^(tarea|hábito|habito|recordatorio|reminder)\s*(de|para|que|a|el|la)?\s*",
    ]
    for _ in range(3):  # varias pasadas para quitar secuencias anidadas
        anterior = limpio
        for patron in patrones:
            limpio = re.sub(patron, "", limpio, flags=re.IGNORECASE)
        if limpio == anterior:
            break
    # Quitar horas y periodos del día
    limpio = re.sub(r"\s+a\s+las\s+\d{1,2}(?::\d{2})?\s*(?:de\s+la\s+(mañana|tarde|noche|madrugada)|am|pm|a\.m\.|p\.m\.)?", "", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"\s+\d{1,2}:\d{2}\s*(?:am|pm|a\.m\.|p\.m\.)?", "", limpio, flags=re.IGNORECASE)
    # Quitar patrones de repetición
    limpio = re.sub(r"\s+(todos los días|todos los dias|cada día|cada dia|diariamente|diario|repetir|hábito|habito|rutina|a las \d+)(\s+.*)?", "", limpio, flags=re.IGNORECASE)
    limpio = limpio.strip().rstrip(".,;:")
    # Capitalizar primera letra
    if limpio:
        limpio = limpio[0].upper() + limpio[1:]
    return limpio if limpio else texto.strip()


def _detectar_etiqueta(texto: str) -> str:
    t = texto.lower()
    if any(k in t for k in HABITO_KEYWORDS):
        return "habito"
    if any(k in t for k in EMPRENDIMIENTO_KEYWORDS):
        return "emprendimiento"
    if any(k in t for k in INVESTIGACION_KEYWORDS):
        return "investigacion"
    return "tarea"


def _detectar_prioridad(texto: str) -> str:
    t = texto.lower()
    if any(k in t for k in ALTA_KEYWORDS):
        return "alta"
    if any(k in t for k in BAJA_KEYWORDS):
        return "baja"
    return "media"


def _es_consulta(texto: str) -> bool:
    t = texto.lower()
    return any(k in t for k in ["cómo voy", "resumen", "status", "priorizar", "qué hago", "estancadas", "atrasadas", "qué tal", "dame un resumen"])


def _es_resumen(texto: str) -> bool:
    return any(k in texto.lower() for k in ["cómo voy", "resumen", "qué tal", "dame un resumen", "status"])


def _parsear_local(texto: str) -> Optional[Dict[str, Any]]:
    """Parsea comandos simples localmente sin llamar al LLM."""
    t = texto.lower().strip()
    if not t:
        return None

    # Consultas: enviar al LLM para respuesta personalizada
    if _es_resumen(t):
        return None  # resumen necesita contexto real

    # Agregar subtarea a tarea existente por número
    if any(k in t for k in ["subtarea", "subtareas", "subtarea", "subtask"]):
        match = re.search(r"(?:tarea\s*(?:número?|numero?|#)?\s*(\d+)|(?:número?|numero?|#)\s*(\d+))", texto, flags=re.IGNORECASE)
        if match:
            numero = int(match.group(1) or match.group(2))
            titulo_sub = _extraer_titulo_subtarea(texto)
            if titulo_sub:
                tarea = storage.obtener_tarea_por_numero(numero)
                if tarea:
                    return {
                        "accion": "agregar_subtarea",
                        "tarea_id": tarea["id"],
                        "tarea_numero": numero,
                        "subtarea_titulo": titulo_sub,
                        "mensaje": f"Voy a añadir la subtarea **{titulo_sub}** a la tarea #{numero} ({tarea['titulo']}). ¿Confirmas?"
                    }
                return {
                    "accion": "no_entendido",
                    "mensaje": f"No encontré la tarea número {numero}. Revisa el número y repite."
                }

    # Crear tarea / hábito: devolver DRAFT para confirmación, no crear directamente
    if any(k in t for k in ["crear", "crea", "nuevo", "nueva", "agregar", "agrega", "hacer", "haz", "genera", "generar", "añade", "añadir", "recordar", "recuerda", "recuerdame", "recuérdame", "tarea", "hábito", "habito", "rutina"]):
        etiqueta = _detectar_etiqueta(texto)
        titulo = _extraer_titulo(texto)
        if not titulo:
            return None
        dias = _extraer_dias(texto)
        horas = _extraer_hora(texto)
        repetible = etiqueta == "habito" or any(k in t for k in HABITO_KEYWORDS)
        prioridad = _detectar_prioridad(texto)
        tipo_label = "hábito" if etiqueta == "habito" else "recordatorio" if repetible else "tarea"
        articulo = "un" if tipo_label in ("hábito", "recordatorio") else "una"
        return {
            "accion": "confirmar_tarea",
            "draft": {
                "titulo": titulo,
                "descripcion": "",
                "etiqueta": etiqueta,
                "prioridad": prioridad,
                "horas": horas,
                "dias_semana": dias,
                "repetible": repetible,
                "objetivo": "",
            },
            "mensaje": f"Voy a crear {articulo} {tipo_label}: **{titulo}**.\n\n¿Es correcto? Puedes confirmar, cambiar el tipo, añadir detalles o editar el texto."
        }
    return None

_cliente: Optional[AsyncOpenAI] = None
_cliente_groq: Optional[AsyncOpenAI] = None


def _obtener_cliente() -> AsyncOpenAI:
    global _cliente
    if _cliente is not None:
        return _cliente
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY no definida")
    base_url = os.getenv("OPENAI_BASE_URL", "https://opencode.ai/zen/go/v1")
    _cliente = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return _cliente


def _obtener_cliente_groq() -> Optional[AsyncOpenAI]:
    global _cliente_groq
    if _cliente_groq is not None:
        return _cliente_groq
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    _cliente_groq = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    return _cliente_groq


def _usar_groq_llm() -> bool:
    """Usar Groq para LLM si hay key y modelo configurado."""
    return bool(os.getenv("GROQ_LLM_MODEL") and os.getenv("GROQ_API_KEY"))


# Modelos Groq decomisionados y sus reemplazos recomendados
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
    return MODELOS_GROQ_OBSOLETOS.get(modelo, modelo)


SYSTEM_PROMPT = """Eres Jarvis, asistente personal de tareas de Sergio.
Analiza el mensaje del usuario y responde SOLO con JSON válido, sin markdown:

{
  "accion": "confirmar_tarea" | "agregar_subtarea" | "resumen" | "priorizar" | "consultar" | "no_entendido",
  "draft": {
    "titulo": "...",
    "descripcion": "...",
    "etiqueta": "tarea" | "habito" | "emprendimiento" | "investigacion",
    "prioridad": "alta" | "media" | "baja",
    "horas": ["08:00"],
    "dias_semana": ["lun", "mar"],
    "objetivo": "nombre del proyecto o área de conocimiento"
  },
  "tarea_numero": 123,
  "subtarea_titulo": "título de la subtarea",
  "mensaje": "Respuesta conversacional breve en español"
}

Reglas de clasificación:
- "crear tarea", "agendar", "recordar que", "tengo que", "quiero que generes" → confirmar_tarea
- "hábito", "rutina", "cada día a las", "repetir" → etiqueta="habito", extraer horas (formato HH:MM 24h) y días (lun,mar,mie,jue,vie,sab,dom)
- "investigar", "estudiar", "analizar", "buscar info" → etiqueta="investigacion"
- "proyecto", "emprender", "negocio", "startup", "TREAS" → etiqueta="emprendimiento"
- "urgente", "importante" → prioridad="alta"
- "cómo voy", "resumen", "status", "qué tal" → resumen
- "priorizar", "qué hago primero", "qué hago hoy" → priorizar
- "estancadas", "atrasadas" → consultar (sobre tareas estancadas)
- "agregar subtarea X a la tarea #N", "subtarea X en tarea N" → accion="agregar_subtarea", tarea_numero=N, subtarea_titulo=X

IMPORTANTE:
- NUNCA crees la tarea directamente. Siempre devuelve accion="confirmar_tarea" con un draft.
- Para agregar_subtarea, devuelve accion="agregar_subtarea" y confirma; no agregues la subtarea directamente.
- Si el mensaje es ambiguo, pide clarificación en "mensaje" y devuelve draft con tu mejor suposición.
- Si no detectas el tipo, usa etiqueta="tarea" y pregunta en el mensaje si es un hábito, emprendimiento o investigación.
- "draft" solo se incluye si accion=="confirmar_tarea". Si no, omítelo o usa null.
- "mensaje" siempre debe estar presente, breve (máx 2 frases), natural y en español.
- Para resumen/priorizar/consultar, el contexto real del usuario se inyecta en el prompt.
"""


def _construir_contexto() -> str:
    """Genera un resumen del estado actual del usuario para inyectar en el prompt."""
    tareas = storage.listar_tareas()
    pendientes = [t for t in tareas if t["estado"] != "completada"]
    completadas = [t for t in tareas if t["estado"] == "completada"]
    hoy = date.today().isoformat()
    vencidas = [t for t in pendientes if t.get("fecha_limite") and t["fecha_limite"] < hoy]
    en_progreso = [t for t in pendientes if 0 < t["progreso"] < 100]
    alta = [t for t in pendientes if t["prioridad"] == "alta"]

    # Estancadas (>3 días)
    hace_3 = (date.today() - __import__("datetime").timedelta(days=3)).isoformat()
    estancadas = [t for t in pendientes if t.get("creada_en", hoy) < hace_3 and t["progreso"] < 100]

    # Investigación activa
    investigacion = [t for t in pendientes if t["etiqueta"] == "investigacion"]
    emprendimiento = [t for t in pendientes if t["etiqueta"] == "emprendimiento"]

    lineas = [
        f"- Tareas pendientes: {len(pendientes)}",
        f"- Tareas completadas: {len(completadas)}",
        f"- Vencidas: {len(vencidas)}",
        f"- En progreso: {len(en_progreso)}",
        f"- Alta prioridad: {len(alta)}",
        f"- Estancadas (>3 días): {len(estancadas)}",
        f"- Proyectos de emprendimiento: {len(emprendimiento)}",
        f"- Investigaciones activas: {len(investigacion)}",
    ]
    if vencidas:
        lineas.append("- Vencidas: " + ", ".join(t["titulo"] for t in vencidas[:3]))
    if estancadas:
        lineas.append("- Estancadas: " + ", ".join(t["titulo"] for t in estancadas[:3]))
    if alta:
        lineas.append("- Alta prioridad: " + ", ".join(t["titulo"] for t in alta[:3]))

    return "\n".join(lineas)


def _ejecutar_resultado(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta el resultado parseado (local o LLM) y guarda en storage."""
    accion = datos.get("accion", "no_entendido")
    mensaje = datos.get("mensaje", "No entendí lo que dijiste.")

    resultado: Dict[str, Any] = {
        "accion": accion,
        "mensaje": mensaje,
        "tarea_creada": None,
        "draft": None,
        "tarea_numero": None,
        "subtarea_titulo": None,
    }

    if accion == "crear_tarea" and datos.get("tarea"):
        # Convertir accion legacy a confirmar_tarea para evitar creación directa
        datos["accion"] = "confirmar_tarea"
        datos["draft"] = datos.pop("tarea")
        return _ejecutar_resultado(datos)

    if accion == "confirmar_tarea" and datos.get("draft"):
        resultado["draft"] = datos["draft"]
        resultado["mensaje"] = mensaje or "Revisa el borrador y confirma si está correcto."

    if accion == "agregar_subtarea":
        numero = datos.get("tarea_numero")
        if not numero and datos.get("tarea_id"):
            tarea = storage.obtener_tarea(datos.get("tarea_id"))
            if tarea:
                numero = tarea["numero"]
        resultado["tarea_numero"] = numero
        resultado["subtarea_titulo"] = datos.get("subtarea_titulo")
        if not mensaje and numero and datos.get("subtarea_titulo"):
            tarea = storage.obtener_tarea_por_numero(numero)
            titulo_tarea = tarea["titulo"] if tarea else "la tarea"
            resultado["mensaje"] = f"Voy a añadir **{datos['subtarea_titulo']}** a la tarea #{numero} ({titulo_tarea}). ¿Confirmas?"

    return resultado


def confirmar_tarea(draft: Dict[str, Any]) -> Dict[str, Any]:
    """Crea una tarea a partir de un draft confirmado por el usuario."""
    try:
        t = storage.crear_tarea(
            titulo=draft.get("titulo", "Sin título"),
            prioridad=draft.get("prioridad", "media"),
            fecha_limite=draft.get("fecha_limite"),
            etiqueta=draft.get("etiqueta", "tarea"),
            repetible=draft.get("etiqueta") == "habito" or draft.get("repetible", False),
            descripcion=draft.get("descripcion", ""),
            horas=draft.get("horas", []),
            dias_semana=draft.get("dias_semana", []),
            objetivo=draft.get("objetivo", ""),
        )
        return {"accion": "tarea_creada", "mensaje": f"✅ Tarea creada: {t['titulo']}", "tarea_creada": t}
    except Exception as e:
        logger.exception("Error confirmando tarea desde voz: %s", e)
        return {"accion": "error", "mensaje": "No pude crear la tarea. Intenta de nuevo.", "tarea_creada": None}


def actualizar_tarea(tarea_id: str, cambios: Dict[str, Any]) -> Dict[str, Any]:
    """Actualiza una tarea existente con los cambios proporcionados."""
    try:
        t = storage.actualizar_tarea(tarea_id, **cambios)
        if not t:
            return {"accion": "error", "mensaje": "No encontré la tarea para actualizar.", "tarea_creada": None}
        return {"accion": "tarea_actualizada", "mensaje": f"✏️ Tarea actualizada: {t['titulo']}", "tarea_actualizada": t}
    except Exception as e:
        logger.exception("Error actualizando tarea desde voz: %s", e)
        return {"accion": "error", "mensaje": "No pude actualizar la tarea. Intenta de nuevo.", "tarea_creada": None}


async def procesar_comando_voz(texto: str) -> Dict[str, Any]:
    """
    Procesa un comando de voz y ejecuta la acción correspondiente.

    Returns:
        dict con: accion, tarea_creada (opcional), mensaje
    """
    # 1. Intentar parseo local rápido para comandos simples
    local = _parsear_local(texto)
    if local:
        logger.info("Comando de voz parseado localmente: %s", local)
        return _ejecutar_resultado(local)

    # 2. Fallback a LLM para comandos complejos / consultas
    fecha_actual = date.today().isoformat()
    if _usar_groq_llm():
        cliente = _obtener_cliente_groq()
        modelo = _modelo_groq_valido(os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"))
    else:
        cliente = _obtener_cliente()
        modelo = os.getenv("LLM_MODEL", "qwen3.5-plus")

    user_content = f'Mensaje del usuario: "{texto}"\nFecha actual: {fecha_actual}'
    if _es_consulta(texto):
        user_content += f"\n\nContexto real del usuario:\n{_construir_contexto()}"

    try:
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        contenido = response.choices[0].message.content or ""
        contenido_limpio = contenido.strip()
        if contenido_limpio.startswith("```"):
            lineas = [l for l in contenido_limpio.split("\n") if not l.startswith("```")]
            contenido_limpio = "\n".join(lineas).strip()

        datos = json.loads(contenido_limpio)
        return _ejecutar_resultado(datos)

    except json.JSONDecodeError:
        logger.error("JSON inválido del LLM: %s", contenido_limpio[:200])
        return {"accion": "no_entendido", "mensaje": "No pude procesar tu mensaje. ¿Puedes repetir?", "tarea_creada": None}
    except Exception as exc:
        logger.exception("Error en procesar_comando_voz: %s", exc)
        return {"accion": "error", "mensaje": "Ocurrió un error procesando tu mensaje.", "tarea_creada": None}


async def generar_resumen_narrativo() -> str:
    """Genera un resumen narrativo conversacional del estado del usuario."""
    modelo = os.getenv("LLM_MODEL", "qwen3.5-plus")
    cliente = _obtener_cliente()
    contexto = _construir_contexto()

    prompt = (
        "Eres Jarvis. Basándote en el contexto del usuario, genera un mensaje "
        "conversacional breve (máx 3 frases) en español, en segunda persona, "
        "que le diga cómo va con sus tareas y qué debería priorizar. "
        "Sé directo, cercano y útil. No uses markdown ni listas, solo texto natural."
    )

    try:
        response = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Contexto:\n{contexto}"},
            ],
            temperature=0.5,
            max_tokens=200,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.exception("Error generando resumen narrativo: %s", exc)
        return "No pude generar el resumen en este momento."
