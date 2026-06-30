"""code_runner_service.py - Ejecuta código generado por el agente para validar que funciona.

ADVERTENCIA DE SEGURIDAD: ejecuta código en el host. Está pensado para uso local del
desarrollador. Se puede desactivar con la variable de entorno CODE_RUNNER_ENABLED=0.
Cada ejecución se hace en un directorio temporal aislado y con timeout.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

_MAX_OUTPUT = 8000
_DEFAULT_TIMEOUT = 15

_EXT = {
    "python": "py",
    "javascript": "js",
}


def runner_habilitado() -> bool:
    """El ejecutor está activo salvo que se desactive explícitamente."""
    return os.getenv("CODE_RUNNER_ENABLED", "1") not in ("0", "false", "False", "")


def _normalizar_lenguaje(lang: str, code: str) -> str:
    lang = (lang or "").lower().strip()
    if lang in ("python", "py", "python3"):
        return "python"
    if lang in ("javascript", "js", "node", "nodejs", "typescript", "ts"):
        return "javascript"
    if lang:
        return lang
    # Heurística cuando no hay lenguaje declarado
    if re.search(r"\b(def |import |print\(|class .+:)", code):
        return "python"
    if re.search(r"(console\.log|=>|\bfunction\b|\bconst\b|\blet\b)", code):
        return "javascript"
    return "python"


def extraer_codigo(texto: str) -> Tuple[str, str]:
    """Extrae el primer bloque de código y su lenguaje desde texto/markdown."""
    if not texto:
        return "", ""
    m = re.search(r"```([a-zA-Z0-9_+\-]*)\n(.*?)```", texto, re.DOTALL)
    if m:
        lang = (m.group(1) or "").strip().lower()
        code = (m.group(2) or "").strip()
        return code, _normalizar_lenguaje(lang, code)
    code = texto.strip()
    return code, _normalizar_lenguaje("", code)


def _comando(lenguaje: str, archivo: str) -> Optional[List[str]]:
    if lenguaje == "python":
        return [sys.executable, archivo]
    if lenguaje == "javascript":
        node = shutil.which("node")
        return [node, archivo] if node else None
    return None


def ejecutar_codigo(codigo: str, lenguaje: str = "", timeout: int = _DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Escribe el código en un temp y lo ejecuta, devolviendo stdout/stderr/exit code."""
    if not runner_habilitado():
        return {"ok": False, "error": "El ejecutor de código está desactivado (CODE_RUNNER_ENABLED=0).", "lenguaje": lenguaje}
    if not (codigo or "").strip():
        return {"ok": False, "error": "No hay código para ejecutar.", "lenguaje": lenguaje}

    lenguaje = _normalizar_lenguaje(lenguaje, codigo)
    ext = _EXT.get(lenguaje)
    if not ext:
        return {"ok": False, "error": f"Lenguaje no soportado para ejecución: {lenguaje}. Soportados: python, javascript.", "lenguaje": lenguaje}

    workdir = tempfile.mkdtemp(prefix="jarvis_run_")
    archivo = os.path.join(workdir, f"main.{ext}")
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write(codigo)
        cmd = _comando(lenguaje, archivo)
        if not cmd:
            return {"ok": False, "error": f"No se encontró el intérprete para {lenguaje} en el sistema.", "lenguaje": lenguaje}
        proc = subprocess.run(
            cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "lenguaje": lenguaje,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[:_MAX_OUTPUT],
            "stderr": (proc.stderr or "")[:_MAX_OUTPUT],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Tiempo de ejecución excedido ({timeout}s).", "lenguaje": lenguaje, "returncode": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "lenguaje": lenguaje}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
