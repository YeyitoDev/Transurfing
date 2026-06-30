"""
vector_store.py - Memoria semántica con LanceDB para el agente personal.

Almacena anotaciones, tareas, ideas y cualquier conocimiento como vectores
de embeddings. Permite búsqueda por similitud semántica y preguntas con
contexto recuperado (RAG).

El vector store se guarda en el mismo directorio de datos que tareas.json
(por defecto tareas_app/data/vector.lance), para que en fly.io se persista
con el mismo volumen.

Requiere:
    pip install lancedb openai tiktoken
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import lancedb
import logging
import numpy as np
import tiktoken
from dotenv import load_dotenv
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

# Cargar .env del directorio padre (proyecto principal)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

VECTOR_DIM = 1536
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def _resolve_data_dir() -> Path:
    """Devuelve el directorio de datos disponible y escribible."""
    env_dir = os.getenv("TAREAS_DATA_DIR")
    if env_dir:
        env_path = Path(env_dir)
        try:
            env_path.mkdir(parents=True, exist_ok=True)
            test_file = env_path / ".write_test"
            with test_file.open("w") as f:
                f.write("1")
            test_file.unlink()
            return env_path
        except OSError:
            logging.getLogger(__name__).warning("TAREAS_DATA_DIR=%s no es escribible; usando data/ local", env_dir)
    return Path(__file__).resolve().parent / "data"


DATA_DIR = _resolve_data_dir()
VECTOR_DB_PATH = DATA_DIR / "vector.lance"

# ---------------------------------------------------------------------------
# Modelo de datos
# ---------------------------------------------------------------------------

class Memory(LanceModel):
    id: str
    text: str
    source: str  # "manual", "tarea", "idea", "telegram", etc.
    source_id: Optional[str]
    created_at: str
    metadata: Optional[str]  # JSON serializado
    vector: Vector(VECTOR_DIM)


# ---------------------------------------------------------------------------
# Cliente de embeddings
# ---------------------------------------------------------------------------

def _get_openai_client() -> Any:
    """Retorna cliente OpenAI compatible para embeddings."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY no está definida en .env")

    base_url = os.getenv("OPENAI_BASE_URL")
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)


def embed_text(text: str) -> List[float]:
    """Genera el embedding de un texto usando OpenAI."""
    client = _get_openai_client()
    response = client.embeddings.create(
        input=[text],
        model=EMBEDDING_MODEL,
    )
    return response.data[0].embedding


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Genera embeddings de varios textos en una sola llamada."""
    client = _get_openai_client()
    response = client.embeddings.create(
        input=texts,
        model=EMBEDDING_MODEL,
    )
    return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# Utilidades de chunking
# ---------------------------------------------------------------------------

def _split_text(text: str, max_tokens: int = 500, overlap: int = 50) -> List[str]:
    """
    Divide un texto en chunks por tokens con solapamiento.
    Usa cl100k_base (modelo de embeddings de OpenAI).
    """
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)

    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    start = 0
    while start < len(tokens):
        end = start + max_tokens
        chunk_tokens = tokens[start:end]
        chunks.append(encoding.decode(chunk_tokens))
        start = end - overlap

    return chunks


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def _get_db() -> lancedb.DBConnection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(VECTOR_DB_PATH))


def _get_table() -> lancedb.table.Table:
    db = _get_db()
    if "memories" in db.table_names():
        return db.open_table("memories")
    return db.create_table("memories", schema=Memory.to_arrow_schema())


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def add_memory(
    text: str,
    source: str = "manual",
    source_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    chunk: bool = True,
) -> List[str]:
    """
    Guarda un texto en la memoria vectorial.
    Si chunk=True, divide el texto en fragmentos y guarda cada uno.
    Retorna los ids creados.
    """
    import json

    table = _get_table()
    now = datetime.utcnow().isoformat()
    meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

    chunks = _split_text(text) if chunk else [text]
    embeddings = embed_texts(chunks)

    rows = []
    ids = []
    for piece, vector in zip(chunks, embeddings):
        mid = str(uuid.uuid4())
        ids.append(mid)
        rows.append({
            "id": mid,
            "text": piece,
            "source": source,
            "source_id": source_id,
            "created_at": now,
            "metadata": meta_json,
            "vector": np.array(vector, dtype=np.float32),
        })

    table.add(rows)
    return ids


def search(query: str, k: int = 5, source: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Busca los k fragmentos más similares a la consulta.
    Opcionalmente filtra por source.
    """
    table = _get_table()
    vector = embed_text(query)

    results = table.search(vector).limit(k)
    if source:
        results = results.where(f"source = '{source}'")

    return [
        {
            "id": r["id"],
            "text": r["text"],
            "source": r["source"],
            "source_id": r["source_id"],
            "created_at": r["created_at"],
            "distance": float(r["_distance"]),
        }
        for r in results.to_list()
    ]


async def ask(question: str, k: int = 5, system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Responde una pregunta usando RAG:
    1. Recupera los fragmentos más relevantes.
    2. Envía el contexto al LLM.
    3. Retorna la respuesta + fuentes.
    """
    from llm_service import _obtener_cliente

    results = search(question, k=k)
    context = "\n\n".join(
        f"[{i+1}] ({r['source']}) {r['text']}" for i, r in enumerate(results)
    )

    if not context:
        return {
            "respuesta": "No encontré información relevante en tu base de datos.",
            "fuentes": [],
        }

    prompt = f"""Responde la pregunta del usuario usando ÚNICAMENTE la información del contexto.
Si no tienes suficiente información, dilo claramente.

Contexto:
{context}

Pregunta: {question}
"""

    default_system = "Eres un asistente personal que responde con precisión usando el contexto proporcionado."
    client = _obtener_cliente()

    response = await client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "qwen3.5-plus"),
        messages=[
            {"role": "system", "content": system_prompt or default_system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    return {
        "respuesta": response.choices[0].message.content,
        "fuentes": results,
        "modelo": response.model,
    }


def sync_tareas() -> int:
    """
    Indexa todas las tareas existentes en la memoria vectorial.
    Retorna la cantidad de chunks creados.
    """
    import storage

    tareas = storage.listar_tareas()
    total = 0
    for t in tareas:
        text = f"Tarea: {t['titulo']}. {t.get('descripcion', '')} Objetivo: {t.get('objetivo', '')}"
        if not text.strip():
            continue
        add_memory(
            text=text,
            source="tarea",
            source_id=t["id"],
            metadata={
                "titulo": t["titulo"],
                "etiqueta": t.get("etiqueta"),
                "prioridad": t.get("prioridad"),
                "estado": t.get("estado"),
            },
        )
        total += 1
    return total


def delete_memory(memory_id: str) -> bool:
    """Elimina un fragmento de memoria por id."""
    table = _get_table()
    table.delete(f"id = '{memory_id}'")
    return True


def stats() -> Dict[str, Any]:
    """Retorna estadísticas básicas de la memoria."""
    table = _get_table()
    return {
        "total_registros": table.count_rows(),
        "ruta": str(VECTOR_DB_PATH),
    }
