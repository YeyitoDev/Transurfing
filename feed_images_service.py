"""feed_images_service.py - Enriquece ítems del feed con imágenes.

Estrategia (en orden):
  1. Si el ítem tiene URL, extrae la imagen Open Graph (o Twitter card).
  2. Si no hay OG o no hay URL, consulta Unsplash API (requiere UNSPLASH_ACCESS_KEY).
  3. Fallback: placeholder generado con placehold.co usando el tema/categoría.

No guarda el secreto en disco; todo se configura por variables de entorno.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
ENABLED = os.getenv("FEED_IMAGES_ENABLED", "1").strip().lower() not in ("0", "false", "no")
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
HTTP_TIMEOUT = float(os.getenv("FEED_IMAGES_TIMEOUT", "6"))
USER_AGENT = "TransurfingFeed/1.0 (+image-enrichment)"

# Colores para placeholders según etiqueta del proyecto.
COLORES_CATEGORIA: Dict[str, str] = {
    "habito": "4ade80",
    "emprendimiento": "f472b6",
    "investigacion": "60a5fa",
    "idea": "fbbf24",
    "tarea": "a78bfa",
    "general": "94a3b8",
}

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
class _OGParser(HTMLParser):
    """Parser mínimo para extraer og:image / twitter:image de HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.og_image: Optional[str] = None
        self.twitter_image: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "meta":
            return
        attr: Dict[str, str] = {}
        for k, v in attrs:
            attr[k.lower()] = (v or "").lower()
        content = attr.get("content")
        if not content:
            return
        if attr.get("property") == "og:image":
            self.og_image = content
        elif attr.get("name") in ("twitter:image", "twitter:image:src"):
            self.twitter_image = content


def _color_por_categoria(categoria: str) -> str:
    return COLORES_CATEGORIA.get(categoria.lower().strip(), COLORES_CATEGORIA["general"])


def _placeholder_url(query: str, categoria: str = "general") -> str:
    """Genera un placeholder visual con el tema y color de categoría."""
    color = _color_por_categoria(categoria)
    texto = (query or "Transurfing").strip()[:22]
    return f"https://placehold.co/600x400/{color}/1e293b?text={texto.replace(' ', '+')}"


# ---------------------------------------------------------------------------
# Proveedores de imagen
# ---------------------------------------------------------------------------
async def _extract_og_image(url: str) -> Optional[str]:
    """Intenta obtener la imagen Open Graph de una URL (relativa -> absoluta)."""
    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            follow_redirects=True,
        ) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            # Limitar a los primeros 100 KB para no parsear páginas enormes.
            parser = _OGParser()
            parser.feed(r.text[:100_000])
            img = parser.og_image or parser.twitter_image
            if not img:
                return None
            return urljoin(str(r.url), img)
    except Exception as exc:
        logger.warning("[feed_images] OG falló para %s: %s", url, exc)
        return None


async def _unsplash_image(query: str) -> Optional[str]:
    """Busca una imagen en Unsplash usando la API oficial."""
    if not UNSPLASH_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            r = await client.get(
                "https://api.unsplash.com/search/photos",
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
                params={"query": query, "per_page": 1, "orientation": "landscape"},
            )
            if r.status_code != 200:
                return None
            results = r.json().get("results", [])
            if not results:
                return None
            return results[0].get("urls", {}).get("small")
    except Exception as exc:
        logger.warning("[feed_images] Unsplash falló para %s: %s", query, exc)
        return None


async def _resolve_image(query: str, url: Optional[str] = None, categoria: str = "general") -> str:
    """Resuelve la URL final de imagen para un ítem."""
    if not ENABLED:
        return ""

    # 1. Open Graph (si hay URL).
    if url:
        og = await _extract_og_image(url)
        if og:
            return og

    # 2. Unsplash por palabras clave.
    unsplash = await _unsplash_image(query)
    if unsplash:
        return unsplash

    # 3. Placeholder visual.
    return _placeholder_url(query, categoria)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
async def enrich_curado(items: List[Dict[str, Any]], tareas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Añade imagen_url a cada ítem del feed curado (LLM) usando su categoría."""
    if not items or not ENABLED:
        return items

    tareas_por_titulo = {str(t.get("titulo", "")).strip(): t for t in tareas}

    async def _enrich_one(it: Dict[str, Any]) -> str:
        proyecto = str(it.get("proyecto", "")).strip()
        tarea = tareas_por_titulo.get(proyecto)
        etiqueta = str(tarea.get("etiqueta", "general")).strip() if tarea else "general"
        query = f"{etiqueta} {proyecto}" if proyecto else etiqueta
        return await _resolve_image(query, url=None, categoria=etiqueta)

    imagenes = await asyncio.gather(*[_enrich_one(it) for it in items], return_exceptions=True)
    for it, img in zip(items, imagenes):
        if isinstance(img, Exception):
            it["imagen_url"] = _placeholder_url(str(it.get("proyecto", "")), "general")
        else:
            it["imagen_url"] = img
    return items


async def enrich_vivo(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Añade imagen_url a cada ítem del feed vivo (URLs reales)."""
    if not items or not ENABLED:
        return items

    async def _enrich_one(it: Dict[str, Any]) -> str:
        url = str(it.get("url", "")).strip()
        tema = str(it.get("tema", "")).strip()
        query = tema or str(it.get("titulo", "")).strip()
        return await _resolve_image(query, url=url if url else None, categoria="general")

    imagenes = await asyncio.gather(*[_enrich_one(it) for it in items], return_exceptions=True)
    for it, img in zip(items, imagenes):
        if isinstance(img, Exception):
            it["imagen_url"] = _placeholder_url(str(it.get("tema", "")), "general")
        else:
            it["imagen_url"] = img
    return items
