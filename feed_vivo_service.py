"""
feed_vivo_service.py - Feed "vivo" experimental con búsquedas reales en internet.

Construye consultas a partir de los proyectos activos (hábitos, emprendimientos,
ideas) y trae resultados relevantes de fuentes gratuitas sin API key:

  - arXiv            -> ciencia / papers recientes
  - Hacker News      -> tech, startups, ideas (señales objetivas: puntos/comentarios)
  - Wikipedia        -> contexto de fondo ("ver más allá")

Opcionalmente, si hay una API key configurada, añade búsqueda web general:

  - Tavily   (TAVILY_API_KEY)
  - Brave    (BRAVE_API_KEY)

Cada ítem se puntúa con criterios OBJETIVOS y MEDIBLES (relevancia, recencia,
popularidad y autoridad de la fuente), que se devuelven junto al resultado para
que el ranking sea auditable.

Diseñado para ser barato: cachea el resultado (TTL configurable) y limita el
número de consultas por refresco. Es experimental y se puede desactivar con
FEED_VIVO_ENABLED=0.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

import storage

logger = logging.getLogger(__name__)

# --- Configuración (env) ----------------------------------------------------
ENABLED = os.getenv("FEED_VIVO_ENABLED", "1").strip().lower() not in ("0", "false", "no")
TTL_MIN = int(os.getenv("FEED_VIVO_TTL_MIN", "360"))          # validez del cache (6 h)
MIN_REFRESH_MIN = int(os.getenv("FEED_VIVO_MIN_REFRESH_MIN", "20"))  # anti-spam de "force"
MAX_CONSULTAS = max(1, min(int(os.getenv("FEED_VIVO_MAX_CONSULTAS", "3")), 5))
MAX_ITEMS = int(os.getenv("FEED_VIVO_MAX_ITEMS", "18"))
HTTP_TIMEOUT = float(os.getenv("FEED_VIVO_HTTP_TIMEOUT", "10"))
USER_AGENT = os.getenv("FEED_VIVO_USER_AGENT", "TransurfingFeed/1.0 (+personal-research)")

# Pesos del ranking (suman 1.0). Documentados y devueltos al cliente.
PESOS = {"relevancia": 0.30, "recencia": 0.30, "popularidad": 0.20, "autoridad": 0.20}

# Autoridad fija por fuente (0..1): aproximación a la fiabilidad/curaduría.
AUTORIDAD = {"arxiv": 0.90, "wikipedia": 0.85, "web": 0.75, "hackernews": 0.62}

# Vida media (días) para el decaimiento de recencia por fuente.
HALF_LIFE = {"arxiv": 30.0, "hackernews": 5.0, "web": 7.0, "wikipedia": 540.0}

_CACHE_FILE = storage.DATA_DIR / "feed_vivo_cache.json"

_STOPWORDS = {
    # es
    "para", "como", "este", "esta", "esto", "esos", "esas", "pero", "porque", "donde",
    "cuando", "sobre", "entre", "desde", "hasta", "tiene", "tener", "hacer", "tarea",
    "proyecto", "general", "nuevo", "nueva", "mejor", "mucho", "poco", "todo", "cada",
    # en
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "you", "about",
    "what", "when", "where", "which", "their", "there", "here", "have", "has", "are",
    "was", "will", "would", "could", "should", "more", "than", "then", "they", "them",
}


# --- Utilidades -------------------------------------------------------------
def _tokens(texto: str) -> set:
    palabras = re.findall(r"[a-zA-ZáéíóúñüÁÉÍÓÚÑ0-9]{4,}", (texto or "").lower())
    return {p for p in palabras if p not in _STOPWORDS}


def _relevancia(query: str, texto: str) -> float:
    q = _tokens(query)
    if not q:
        return 0.0
    t = _tokens(texto)
    if not t:
        return 0.0
    inter = len(q & t)
    # Cobertura de los términos de la consulta presentes en el texto (0..1).
    return min(1.0, inter / len(q))


def _parse_dt(valor: Any) -> Optional[datetime]:
    if valor is None or valor == "":
        return None
    try:
        if isinstance(valor, (int, float)):
            return datetime.fromtimestamp(float(valor), tz=timezone.utc)
        s = str(valor).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, OSError, OverflowError):
        return None


def _edad_dias(dt: Optional[datetime]) -> Optional[float]:
    if dt is None:
        return None
    delta = datetime.now(timezone.utc) - dt
    return max(0.0, delta.total_seconds() / 86400.0)


def _recencia(dt: Optional[datetime], fuente: str) -> float:
    edad = _edad_dias(dt)
    if edad is None:
        return 0.35  # sin fecha: valor neutro
    hl = HALF_LIFE.get(fuente, 14.0)
    return math.exp(-edad / hl)


def _norm_url(url: str) -> str:
    u = (url or "").strip().lower()
    u = re.sub(r"#.*$", "", u)
    u = re.sub(r"\?.*$", "", u)
    return u.rstrip("/")


def _puntuar(item: Dict[str, Any], query: str) -> Dict[str, Any]:
    fuente = item["fuente"]
    texto = f"{item.get('titulo', '')} {item.get('resumen', '')}"
    rel = _relevancia(query, texto)
    dt = _parse_dt(item.get("_dt"))
    rec = _recencia(dt, fuente)
    item["fecha"] = dt.date().isoformat() if dt else ""
    pop = float(item.get("_popularidad", 0.3))
    aut = AUTORIDAD.get(fuente, 0.6)
    senales = {
        "relevancia": round(rel, 3),
        "recencia": round(rec, 3),
        "popularidad": round(min(1.0, pop), 3),
        "autoridad": round(aut, 3),
    }
    score = sum(PESOS[k] * senales[k] for k in PESOS)
    item["senales"] = senales
    item["score"] = round(score * 100)
    item.pop("_dt", None)
    item.pop("_popularidad", None)
    return item


def _truncar(texto: str, n: int = 280) -> str:
    t = re.sub(r"\s+", " ", (texto or "")).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


# --- Fuentes ----------------------------------------------------------------
async def _fetch_hackernews(client: httpx.AsyncClient, query: str, tema: str) -> List[Dict[str, Any]]:
    try:
        r = await client.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": query, "tags": "story", "hitsPerPage": 6, "numericFilters": "points>20"},
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except Exception as exc:
        logger.warning("[feed_vivo] HN falló (%s): %s", query, exc)
        return []
    items = []
    for h in hits:
        puntos = int(h.get("points") or 0)
        comentarios = int(h.get("num_comments") or 0)
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        items.append({
            "fuente": "hackernews",
            "fuente_label": "Hacker News",
            "tipo": "discusion",
            "titulo": (h.get("title") or "").strip(),
            "resumen": _truncar(h.get("story_text") or h.get("_highlightResult", {}).get("title", {}).get("value", "")),
            "url": url,
            "tema": tema,
            "_dt": h.get("created_at_i"),
            "_popularidad": min(1.0, (puntos + 2 * comentarios) / 600.0),
            "metricas": {"puntos": puntos, "comentarios": comentarios},
        })
    return items


async def _fetch_arxiv(client: httpx.AsyncClient, query: str, tema: str) -> List[Dict[str, Any]]:
    try:
        r = await client.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": 5,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception as exc:
        logger.warning("[feed_vivo] arXiv falló (%s): %s", query, exc)
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = []
    for entry in root.findall("a:entry", ns):
        titulo = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        resumen = (entry.findtext("a:summary", default="", namespaces=ns) or "").strip()
        publicado = entry.findtext("a:published", default="", namespaces=ns)
        url = (entry.findtext("a:id", default="", namespaces=ns) or "").strip()
        for link in entry.findall("a:link", ns):
            if link.get("rel") == "alternate":
                url = link.get("href", url)
        if not titulo:
            continue
        items.append({
            "fuente": "arxiv",
            "fuente_label": "arXiv",
            "tipo": "ciencia",
            "titulo": titulo,
            "resumen": _truncar(resumen),
            "url": url,
            "tema": tema,
            "_dt": publicado,
            "_popularidad": 0.45,  # sin señal social; relevancia/recencia mandan
        })
    return items


async def _fetch_wikipedia(client: httpx.AsyncClient, query: str, tema: str) -> List[Dict[str, Any]]:
    try:
        r = await client.get(
            "https://es.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search", "srsearch": query,
                "format": "json", "srlimit": 1, "srprop": "snippet",
            },
        )
        r.raise_for_status()
        hits = r.json().get("query", {}).get("search", [])
        if not hits:
            return []
        titulo = hits[0]["title"]
        slug = quote(titulo.replace(" ", "_"), safe="")
        s = await client.get(f"https://es.wikipedia.org/api/rest_v1/page/summary/{slug}")
        extracto = ""
        url = f"https://es.wikipedia.org/wiki/{slug}"
        if s.status_code == 200:
            data = s.json()
            extracto = data.get("extract", "")
            url = data.get("content_urls", {}).get("desktop", {}).get("page", url)
        else:
            extracto = re.sub(r"<[^>]+>", "", hits[0].get("snippet", ""))
    except Exception as exc:
        logger.warning("[feed_vivo] Wikipedia falló (%s): %s", query, exc)
        return []
    return [{
        "fuente": "wikipedia",
        "fuente_label": "Wikipedia",
        "tipo": "referencia",
        "titulo": titulo,
        "resumen": _truncar(extracto),
        "url": url,
        "tema": tema,
        "_dt": None,
        "_popularidad": 0.4,
    }]


async def _fetch_tavily(client: httpx.AsyncClient, query: str, tema: str, api_key: str) -> List[Dict[str, Any]]:
    try:
        r = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key, "query": query, "max_results": 5,
                "search_depth": "basic", "topic": "news", "days": 14, "include_answer": False,
            },
        )
        r.raise_for_status()
        resultados = r.json().get("results", [])
    except Exception as exc:
        logger.warning("[feed_vivo] Tavily falló (%s): %s", query, exc)
        return []
    items = []
    for res in resultados:
        items.append({
            "fuente": "web",
            "fuente_label": "Web",
            "tipo": "noticia",
            "titulo": (res.get("title") or "").strip(),
            "resumen": _truncar(res.get("content") or ""),
            "url": res.get("url") or "",
            "tema": tema,
            "_dt": res.get("published_date"),
            "_popularidad": min(1.0, float(res.get("score") or 0.5)),
        })
    return items


async def _fetch_brave(client: httpx.AsyncClient, query: str, tema: str, api_key: str) -> List[Dict[str, Any]]:
    try:
        r = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 5, "freshness": "pw"},
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        )
        r.raise_for_status()
        resultados = r.json().get("web", {}).get("results", [])
    except Exception as exc:
        logger.warning("[feed_vivo] Brave falló (%s): %s", query, exc)
        return []
    items = []
    for res in resultados:
        items.append({
            "fuente": "web",
            "fuente_label": "Web",
            "tipo": "noticia",
            "titulo": (res.get("title") or "").strip(),
            "resumen": _truncar(res.get("description") or ""),
            "url": res.get("url") or "",
            "tema": tema,
            "_dt": res.get("page_age"),
            "_popularidad": 0.55,
        })
    return items


def _proveedor_web() -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (proveedor, api_key) si hay una búsqueda web configurada."""
    tav = os.getenv("TAVILY_API_KEY", "").strip()
    if tav:
        return "tavily", tav
    brave = os.getenv("BRAVE_API_KEY", "").strip()
    if brave:
        return "brave", brave
    return None, None


# --- Generación de consultas y preguntas (LLM, best-effort) -----------------
def _cliente_llm():
    from voz_service import _obtener_cliente, _obtener_cliente_groq, _usar_groq_llm
    try:
        if _usar_groq_llm():
            return _obtener_cliente_groq(), os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
        return _obtener_cliente(), os.getenv("LLM_MODEL", "qwen3.5-plus")
    except Exception:
        return None, None


def _consultas_heuristicas(tareas: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    consultas = []
    vistos = set()
    for t in tareas:
        base = (t.get("objetivo") or t.get("titulo") or "").strip()
        if not base:
            continue
        clave = base.lower()[:40]
        if clave in vistos:
            continue
        vistos.add(clave)
        consultas.append({"q": base, "tema": t.get("titulo", base), "lente": t.get("etiqueta", "general")})
        if len(consultas) >= MAX_CONSULTAS:
            break
    return consultas or [{"q": "scientific breakthroughs", "tema": "Ciencia", "lente": "ciencia"}]


async def _generar_consultas(tareas: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    cliente, modelo = _cliente_llm()
    if cliente is None:
        return _consultas_heuristicas(tareas)
    contexto = "\n".join(
        f"- {t.get('titulo', '')} (área: {t.get('objetivo') or t.get('etiqueta', 'general')})"
        for t in tareas[:8]
    ) or "Sin proyectos."
    prompt = (
        "A partir de mis proyectos (hábitos, emprendimientos, ideas), genera consultas de búsqueda "
        "para descubrir lo más relevante y reciente del mundo: ciencia, tecnología y tendencias.\n\n"
        f"PROYECTOS:\n{contexto}\n\n"
        f"Devuelve SOLO JSON: {{\"consultas\": [{{\"q\": \"términos de búsqueda EN INGLÉS, específicos\", "
        "\"tema\": \"etiqueta corta en español\", \"lente\": \"ciencia|tech|negocio\"}}]}}. "
        f"Máximo {MAX_CONSULTAS} consultas, diversas y de alto valor."
    )
    try:
        resp = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Eres un investigador. Devuelves SOLO JSON válido."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=400,
        )
        contenido = (resp.choices[0].message.content or "").strip()
        if contenido.startswith("```"):
            contenido = "\n".join(l for l in contenido.split("\n") if not l.startswith("```")).strip()
        datos = json.loads(contenido)
        consultas = datos.get("consultas", []) if isinstance(datos, dict) else []
        limpias = []
        for c in consultas[:MAX_CONSULTAS]:
            if isinstance(c, dict) and c.get("q"):
                limpias.append({
                    "q": str(c["q"]).strip(),
                    "tema": str(c.get("tema", "")).strip() or str(c["q"]).strip(),
                    "lente": str(c.get("lente", "general")).strip(),
                })
        return limpias or _consultas_heuristicas(tareas)
    except Exception as exc:
        logger.warning("[feed_vivo] no pude generar consultas con LLM: %s", exc)
        return _consultas_heuristicas(tareas)


async def _generar_preguntas(items: List[Dict[str, Any]]) -> Tuple[List[str], str]:
    cliente, modelo = _cliente_llm()
    if cliente is None or not items:
        return [], ""
    titulares = "\n".join(f"- [{it['fuente_label']}] {it['titulo']}" for it in items[:12])
    prompt = (
        "Estos son hallazgos reales que encontré para mis proyectos:\n\n"
        f"{titulares}\n\n"
        "1) Escribe un PANORAMA de 2-3 frases: qué patrón o señal importante revelan estos hallazgos "
        "y qué me invitan a mirar más allá.\n"
        "2) Plantéame 5 PREGUNTAS provocadoras y específicas para investigar, que conecten con mis proyectos.\n"
        "Devuelve SOLO JSON: {\"panorama\": \"...\", \"preguntas\": [\"...\"]}."
    )
    try:
        resp = await cliente.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Eres un mentor analítico. Devuelves SOLO JSON válido."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=600,
        )
        contenido = (resp.choices[0].message.content or "").strip()
        if contenido.startswith("```"):
            contenido = "\n".join(l for l in contenido.split("\n") if not l.startswith("```")).strip()
        datos = json.loads(contenido)
        preguntas = [str(p).strip() for p in datos.get("preguntas", []) if str(p).strip()][:6]
        panorama = str(datos.get("panorama", "")).strip()
        return preguntas, panorama
    except Exception as exc:
        logger.warning("[feed_vivo] no pude generar preguntas con LLM: %s", exc)
        return [], ""


# --- Cache ------------------------------------------------------------------
def _leer_cache() -> Optional[Dict[str, Any]]:
    try:
        with _CACHE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _guardar_cache(payload: Dict[str, Any]) -> None:
    try:
        storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_FILE.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "payload": payload}, f, ensure_ascii=False)
        os.replace(tmp, _CACHE_FILE)
    except OSError as exc:
        logger.warning("[feed_vivo] no pude guardar cache: %s", exc)


# --- Orquestación -----------------------------------------------------------
async def generar_feed_vivo(tareas: List[Dict[str, Any]], force: bool = False) -> Dict[str, Any]:
    """Devuelve el feed vivo (con cache y rate-limit). Experimental."""
    if not ENABLED:
        return {"experimental": True, "enabled": False, "items": [], "preguntas": [],
                "aviso": "Feed vivo desactivado (FEED_VIVO_ENABLED=0).", "generado_en": ""}

    cache = _leer_cache()
    ahora = time.time()
    if cache and "payload" in cache:
        edad_min = (ahora - cache.get("ts", 0)) / 60.0
        if not force and edad_min < TTL_MIN:
            out = dict(cache["payload"])
            out["cache"] = True
            return out
        if force and edad_min < MIN_REFRESH_MIN:
            out = dict(cache["payload"])
            out["cache"] = True
            out["rate_limited"] = True
            out["aviso"] = f"Refresco limitado: espera {int(MIN_REFRESH_MIN - edad_min)} min para volver a consultar."
            return out

    activos = [t for t in tareas if t.get("estado") != "completada"]
    consultas = await _generar_consultas(activos)
    proveedor, api_key = _proveedor_web()

    fuentes_usadas = {"arxiv", "hackernews", "wikipedia"}
    crudos: List[Dict[str, Any]] = []

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers, follow_redirects=True) as client:
        tareas_fetch = []
        for i, c in enumerate(consultas):
            q, tema = c["q"], c["tema"]
            tareas_fetch.append(_fetch_hackernews(client, q, tema))
            tareas_fetch.append(_fetch_arxiv(client, q, tema))
            if proveedor == "tavily" and api_key:
                tareas_fetch.append(_fetch_tavily(client, q, tema, api_key))
                fuentes_usadas.add("web(tavily)")
            elif proveedor == "brave" and api_key:
                tareas_fetch.append(_fetch_brave(client, q, tema, api_key))
                fuentes_usadas.add("web(brave)")
            if i == 0:  # Wikipedia solo para el tema principal (ahorra consultas)
                tareas_fetch.append(_fetch_wikipedia(client, q, tema))

        resultados = await asyncio.gather(*tareas_fetch, return_exceptions=True)

    # Mapear cada bloque de resultados a su consulta para puntuar la relevancia.
    idx = 0
    bloques_por_consulta = (2 + (1 if proveedor else 0))
    for i, c in enumerate(consultas):
        n = bloques_por_consulta + (1 if i == 0 else 0)
        for _ in range(n):
            if idx >= len(resultados):
                break
            bloque = resultados[idx]
            idx += 1
            if isinstance(bloque, Exception) or not bloque:
                continue
            for it in bloque:
                if it.get("titulo") and it.get("url"):
                    _puntuar(it, c["q"])
                    crudos.append(it)

    # Dedup por URL normalizada, conservando el de mayor score.
    mejores: Dict[str, Dict[str, Any]] = {}
    for it in crudos:
        clave = _norm_url(it["url"]) or it["titulo"].lower()
        if clave not in mejores or it["score"] > mejores[clave]["score"]:
            mejores[clave] = it

    items = sorted(mejores.values(), key=lambda x: x["score"], reverse=True)[:MAX_ITEMS]

    preguntas, panorama = await _generar_preguntas(items)

    payload = {
        "experimental": True,
        "enabled": True,
        "items": items,
        "preguntas": preguntas,
        "panorama": panorama,
        "consultas": consultas,
        "fuentes": sorted(fuentes_usadas),
        "criterios": PESOS,
        "ttl_min": TTL_MIN,
        "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cache": False,
        "rate_limited": False,
    }
    if items:
        _guardar_cache(payload)
    return payload
