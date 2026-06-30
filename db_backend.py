"""db_backend.py - Backend SQLite opt-in para `storage.py`.

Guarda el documento completo (las mismas claves que el JSON: tareas,
recordatorios, agentes, skills, knowledge, github_config, ...) en una
tabla de una sola fila. Aporta escritura transaccional y durable (ACID)
y un archivo de base de datos real, manteniendo intacta toda la lógica
de `storage.py`. Es la base para una futura normalización por entidad.

Activación: variable de entorno `STORAGE_BACKEND=sqlite` (opcional
`DB_PATH` para la ruta del archivo .db). Si no se activa, `storage.py`
sigue usando el JSON de siempre.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None
_db_path: Optional[Path] = None


def configurar(db_path: Path) -> None:
    """Define la ruta del archivo SQLite. Debe llamarse antes de usar."""
    global _db_path
    _db_path = Path(db_path)


def _conexion() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        if _db_path is None:
            raise RuntimeError("db_backend no configurado: llama a configurar(db_path)")
        _db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(_db_path), check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL;")
        _conn.execute("PRAGMA synchronous=NORMAL;")
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS documento ("
            " id INTEGER PRIMARY KEY CHECK (id = 1),"
            " data TEXT NOT NULL,"
            " updated_at TEXT NOT NULL"
            ")"
        )
        _conn.commit()
    return _conn


def cargar() -> Optional[Dict[str, Any]]:
    """Devuelve el documento guardado, o None si la tabla está vacía."""
    with _lock:
        conn = _conexion()
        row = conn.execute("SELECT data FROM documento WHERE id = 1").fetchone()
    if not row:
        return None
    try:
        data = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def guardar(data: Dict[str, Any]) -> None:
    """Persiste el documento completo de forma transaccional."""
    payload = json.dumps(data, ensure_ascii=False)
    now = datetime.now().isoformat(timespec="seconds")
    with _lock:
        conn = _conexion()
        conn.execute(
            "INSERT OR REPLACE INTO documento (id, data, updated_at) VALUES (1, ?, ?)",
            (payload, now),
        )
        conn.commit()


def disponible() -> bool:
    try:
        _conexion()
        return True
    except Exception:
        return False
