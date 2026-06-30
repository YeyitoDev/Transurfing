"""adjuntos_service.py - Procesa adjuntos del chat para enriquecer el contexto del agente.

Soporta:
- text/*: se incluye el texto tal cual.
- URLs (tipo 'url'): se descarga la página y se extrae el texto legible.
- application/pdf: se extrae el texto (si pypdf/PyPDF2 está disponible).
- image/*: se devuelve como data URL para modelos con visión.

Devuelve (texto_contexto, imagenes) donde `imagenes` son data URLs base64.
"""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_MAX_URL = 6000
_MAX_PDF = 8000
_MAX_TEXT = 12000


async def procesar_adjuntos(archivos: Optional[List[Dict[str, str]]]) -> Tuple[str, List[str]]:
    """Convierte la lista de adjuntos en (texto_contexto, imagenes_data_urls)."""
    textos: List[str] = []
    imagenes: List[str] = []
    for a in archivos or []:
        nombre = (a.get("nombre") or "adjunto").strip()
        tipo = (a.get("tipo") or "").lower().strip()
        contenido = a.get("contenido", "") or ""
        es_url = tipo == "url" or (not tipo and contenido.strip().lower().startswith(("http://", "https://")))
        if not contenido and not es_url:
            continue
        try:
            if es_url:
                texto = await _fetch_url(contenido.strip())
                if texto:
                    textos.append(f"--- CONTENIDO DE URL: {contenido.strip()} ---\n{texto}\n--- FIN URL ---")
                else:
                    textos.append(f"[no se pudo leer la URL: {contenido.strip()}]")
            elif tipo.startswith("image/"):
                imagenes.append(contenido)
                textos.append(f"[imagen adjunta: {nombre}]")
            elif tipo == "application/pdf" or nombre.lower().endswith(".pdf"):
                texto = _extraer_pdf(contenido)
                if texto:
                    textos.append(f"--- DOCUMENTO PDF: {nombre} ---\n{texto}\n--- FIN PDF ---")
                else:
                    textos.append(f"[PDF adjunto sin texto extraíble: {nombre}]")
            else:
                texto = _maybe_decode_text(contenido)
                textos.append(f"--- ARCHIVO: {nombre} (tipo: {tipo or 'text/plain'}) ---\n{texto}\n--- FIN ARCHIVO ---")
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo procesar adjunto %s: %s", nombre, exc)
            textos.append(f"[no se pudo procesar el adjunto: {nombre}]")
    return "\n\n".join(textos), imagenes


async def _fetch_url(url: str, timeout: int = 12) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JarvisBot/1.0)"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
        r = await client.get(url)
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "").lower()
        if "html" in ct:
            return _html_a_texto(r.text)[:_MAX_URL]
        if "json" in ct or "text" in ct or ct == "":
            return (r.text or "")[:_MAX_URL]
        return f"[contenido no textual ({ct or 'desconocido'})]"


def _html_a_texto(html: str) -> str:
    html = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r"<[^>]+>", " ", html)
    texto = texto.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _extraer_pdf(contenido: str) -> str:
    data = _data_url_a_bytes(contenido)
    if not data:
        return ""
    PdfReader = None
    try:
        from pypdf import PdfReader as _R  # type: ignore
        PdfReader = _R
    except Exception:
        try:
            from PyPDF2 import PdfReader as _R  # type: ignore
            PdfReader = _R
        except Exception:
            logger.info("pypdf/PyPDF2 no disponible; no se extrae texto del PDF")
            return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        partes = [(page.extract_text() or "") for page in reader.pages[:20]]
        return "\n".join(partes).strip()[:_MAX_PDF]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error extrayendo PDF: %s", exc)
        return ""


def _data_url_a_bytes(contenido: str) -> bytes:
    if not contenido:
        return b""
    if contenido.startswith("data:"):
        try:
            return base64.b64decode(contenido.split(",", 1)[1])
        except Exception:
            return b""
    try:
        return base64.b64decode(contenido)
    except Exception:
        return b""


def _maybe_decode_text(contenido: str) -> str:
    if contenido.startswith("data:"):
        data = _data_url_a_bytes(contenido)
        try:
            return data.decode("utf-8", errors="replace")[:_MAX_TEXT]
        except Exception:
            return "[contenido binario no legible]"
    return contenido[:_MAX_TEXT]
