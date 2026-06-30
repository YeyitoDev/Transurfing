"""
github_service.py - Integración con la API de GitHub para agentes de desarrollo.

Usa un Personal Access Token (PAT) para operar sobre repositorios de la cuenta del usuario.
Todas las operaciones de escritura se hacen en ramas y pull requests, nunca directamente
sobre la rama principal.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

import storage

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _pat() -> Optional[str]:
    cfg = storage.get_github_config()
    return cfg.get("pat")


def _headers() -> Dict[str, str]:
    pat = _pat()
    if not pat:
        raise RuntimeError("GitHub PAT no configurado")
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _full_repo(repo: str) -> str:
    repo = repo.strip()
    if "/" in repo:
        return repo
    cfg = storage.get_github_config()
    owner = cfg.get("username")
    if not owner:
        raise RuntimeError("No se pudo determinar el owner del repo")
    return f"{owner}/{repo}"


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

def get_user_config() -> Dict[str, Any]:
    return storage.get_github_config()


def set_user_config(pat: str, username: str = "") -> Dict[str, Any]:
    return storage.set_github_config(pat, username)


async def validate_token(pat: Optional[str] = None) -> Dict[str, Any]:
    """Valida un token (PAT u OAuth) contra la API de GitHub y devuelve info del usuario."""
    token = pat or _pat()
    if not token:
        return {"ok": False, "error": "No hay token configurado"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{GITHUB_API}/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        if res.status_code != 200:
            return {"ok": False, "error": f"GitHub error {res.status_code}: {res.text}"}
        data = res.json()
        scopes = res.headers.get("X-OAuth-Scopes", "")
        return {
            "ok": True,
            "username": data.get("login"),
            "name": data.get("name"),
            "scopes": [s.strip() for s in scopes.split(",") if s.strip()],
        }
    except Exception as exc:
        logger.exception("Error validando token GitHub")
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# OAuth GitHub App
# ---------------------------------------------------------------------------

GITHUB_OAUTH_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_ACCESS_TOKEN = "https://github.com/login/oauth/access_token"


def get_oauth_client_credentials() -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (client_id, client_secret) desde variables de entorno."""
    return os.getenv("GITHUB_CLIENT_ID"), os.getenv("GITHUB_CLIENT_SECRET")


def is_oauth_configured() -> bool:
    client_id, client_secret = get_oauth_client_credentials()
    return bool(client_id and client_secret)


def get_oauth_url(state: str, redirect_uri: str) -> str:
    """Genera la URL para redirigir al usuario a GitHub OAuth."""
    client_id, _ = get_oauth_client_credentials()
    if not client_id:
        raise RuntimeError("GitHub OAuth no está configurado (falta GITHUB_CLIENT_ID)")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "repo workflow read:user",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GITHUB_OAUTH_AUTHORIZE}?{query}"


async def exchange_oauth_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    """Intercambia el código OAuth de GitHub por un access token."""
    client_id, client_secret = get_oauth_client_credentials()
    if not client_id or not client_secret:
        return {"ok": False, "error": "GitHub OAuth no está configurado"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                GITHUB_OAUTH_ACCESS_TOKEN,
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
        if res.status_code != 200:
            return {"ok": False, "error": f"GitHub error {res.status_code}: {res.text}"}
        data = res.json()
        if "error" in data:
            return {"ok": False, "error": data.get("error_description", data["error"])}
        access_token = data.get("access_token")
        if not access_token:
            return {"ok": False, "error": "GitHub no devolvió access_token"}
        # Validar el token y obtener el usuario
        valid = await validate_token(access_token)
        if not valid["ok"]:
            return {"ok": False, "error": valid.get("error", "Token inválido")}
        return {
            "ok": True,
            "access_token": access_token,
            "token_type": data.get("token_type", "bearer"),
            "scope": data.get("scope", ""),
            "username": valid["username"],
            "scopes": valid.get("scopes", []),
        }
    except Exception as exc:
        logger.exception("Error intercambiando código OAuth de GitHub")
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Repositorios
# ---------------------------------------------------------------------------

async def list_repos() -> List[Dict[str, Any]]:
    """Lista repositorios del usuario autenticado (públicos, privados y de organizaciones)."""
    url = f"{GITHUB_API}/user/repos"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.get(
            url,
            headers=_headers(),
            params={"sort": "updated", "per_page": 100, "affiliation": "owner,collaborator,organization_member"},
        )
    if res.status_code != 200:
        raise RuntimeError(f"GitHub error {res.status_code}: {res.text}")
    return [
        {
            "full_name": r["full_name"],
            "name": r["name"],
            "owner": r["owner"]["login"],
            "default_branch": r["default_branch"],
            "url": r["html_url"],
        }
        for r in res.json()
    ]


async def get_repo(repo: str) -> Dict[str, Any]:
    full = _full_repo(repo)
    url = f"{GITHUB_API}/repos/{full}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.get(url, headers=_headers())
    if res.status_code != 200:
        raise RuntimeError(f"GitHub error {res.status_code}: {res.text}")
    r = res.json()
    return {
        "full_name": r["full_name"],
        "name": r["name"],
        "owner": r["owner"]["login"],
        "default_branch": r["default_branch"],
        "url": r["html_url"],
    }


async def get_repo_tree(repo: str, path: str = "", branch: Optional[str] = None) -> List[Dict[str, Any]]:
    """Devuelve árbol plano de archivos de un repo hasta un path."""
    full = _full_repo(repo)
    repo_data = await get_repo(repo)
    ref = branch or repo_data["default_branch"]
    url = f"{GITHUB_API}/repos/{full}/git/trees/{ref}"
    if path:
        url = f"{GITHUB_API}/repos/{full}/contents/{path}?ref={ref}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        if path:
            res = await client.get(url, headers=_headers())
            if res.status_code != 200:
                raise RuntimeError(f"GitHub error {res.status_code}: {res.text}")
            items = res.json()
            if not isinstance(items, list):
                items = [items]
            return [
                {"type": i.get("type"), "path": i.get("path"), "name": i.get("name"), "sha": i.get("sha")}
                for i in items
            ]
        res = await client.get(url, headers=_headers(), params={"recursive": "1"})
        if res.status_code != 200:
            raise RuntimeError(f"GitHub error {res.status_code}: {res.text}")
        data = res.json()
        return [
            {"type": t.get("type"), "path": t.get("path"), "sha": t.get("sha")}
            for t in data.get("tree", [])
            if t.get("type") == "blob"
        ]


async def get_file_content(repo: str, path: str, branch: Optional[str] = None) -> str:
    """Lee contenido de un archivo como texto."""
    full = _full_repo(repo)
    repo_data = await get_repo(repo)
    ref = branch or repo_data["default_branch"]
    url = f"{GITHUB_API}/repos/{full}/contents/{path}?ref={ref}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.get(url, headers=_headers())
    if res.status_code != 200:
        raise RuntimeError(f"GitHub error {res.status_code}: {res.text}")
    data = res.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return data.get("content", "")


# ---------------------------------------------------------------------------
# Ramas y commits
# ---------------------------------------------------------------------------

async def create_branch(repo: str, new_branch: str, base_branch: Optional[str] = None) -> str:
    """Crea una nueva rama a partir de base_branch o default_branch."""
    full = _full_repo(repo)
    repo_data = await get_repo(repo)
    base = base_branch or repo_data["default_branch"]
    url = f"{GITHUB_API}/repos/{full}/git/refs/heads/{base}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.get(url, headers=_headers())
        if res.status_code != 200:
            raise RuntimeError(f"GitHub error {res.status_code}: {res.text}")
        base_sha = res.json()["object"]["sha"]

        create_res = await client.post(
            f"{GITHUB_API}/repos/{full}/git/refs",
            headers=_headers(),
            json={"ref": f"refs/heads/{new_branch}", "sha": base_sha},
        )
        if create_res.status_code == 422:
            # La rama ya existe
            return base_sha
        if create_res.status_code != 201:
            raise RuntimeError(f"GitHub error {create_res.status_code}: {create_res.text}")
        return create_res.json()["object"]["sha"]


async def commit_file(
    repo: str,
    path: str,
    content: str,
    branch: str,
    message: str,
) -> str:
    """Crea o actualiza un archivo en una rama y devuelve el SHA del commit."""
    full = _full_repo(repo)
    url = f"{GITHUB_API}/repos/{full}/contents/{path}"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    # Obtener SHA actual si existe
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.get(url, headers=_headers(), params={"ref": branch})
        current_sha = None
        if res.status_code == 200:
            current_sha = res.json().get("sha")

        body: Dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if current_sha:
            body["sha"] = current_sha

        res = await client.put(url, headers=_headers(), json=body)
        if res.status_code not in (200, 201):
            raise RuntimeError(f"GitHub error {res.status_code}: {res.text}")
        return res.json()["commit"]["sha"]


# ---------------------------------------------------------------------------
# Pull requests
# ---------------------------------------------------------------------------

async def create_pull_request(
    repo: str,
    title: str,
    body: str,
    head: str,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Crea un PR y devuelve su número y URL."""
    full = _full_repo(repo)
    repo_data = await get_repo(repo)
    base_branch = base or repo_data["default_branch"]
    url = f"{GITHUB_API}/repos/{full}/pulls"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(
            url,
            headers=_headers(),
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base_branch,
            },
        )
    if res.status_code != 201:
        raise RuntimeError(f"GitHub error {res.status_code}: {res.text}")
    data = res.json()
    return {
        "number": data["number"],
        "url": data["html_url"],
        "state": data["state"],
        "title": data["title"],
        "head": data["head"]["ref"],
        "base": data["base"]["ref"],
    }


async def get_pull_request(repo: str, pr_number: int) -> Dict[str, Any]:
    full = _full_repo(repo)
    url = f"{GITHUB_API}/repos/{full}/pulls/{pr_number}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.get(url, headers=_headers())
    if res.status_code != 200:
        raise RuntimeError(f"GitHub error {res.status_code}: {res.text}")
    data = res.json()
    return {
        "number": data["number"],
        "url": data["html_url"],
        "state": data["state"],
        "merged": data.get("merged", False),
        "title": data["title"],
        "head": data["head"]["ref"],
        "base": data["base"]["ref"],
    }


async def merge_pull_request(repo: str, pr_number: int) -> Dict[str, Any]:
    full = _full_repo(repo)
    url = f"{GITHUB_API}/repos/{full}/pulls/{pr_number}/merge"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.put(url, headers=_headers(), json={"merge_method": "squash"})
    if res.status_code != 200:
        raise RuntimeError(f"GitHub error {res.status_code}: {res.text}")
    return {"merged": True, "sha": res.json().get("sha")}


# ---------------------------------------------------------------------------
# Agente: flujo de desarrollo
# ---------------------------------------------------------------------------

async def agente_desarrollar(
    tarea: Dict[str, Any],
    prompt_extra: str = "",
) -> Dict[str, Any]:
    """
    Orquesta al agente para que lea el repo, proponga cambios y abra un PR.
    Devuelve un resumen con la URL del PR, archivos cambiados y pros/contras.
    """
    from agente_planes import ejecutar_agente

    repo = tarea.get("github_repo")
    if not repo:
        return {"ok": False, "error": "La tarea no tiene un repositorio vinculado"}

    repo_data = await get_repo(repo)
    default_branch = repo_data["default_branch"]
    branch_name = f"jarvis/{tarea['id']}"

    # 1. Leer estructura del repo
    try:
        tree = await get_repo_tree(repo)
        # Limitar archivos relevantes (evitar node_modules, binarios, etc.)
        archivos = [
            f"{t['path']}"
            for t in tree
            if _archivo_relevante(t["path"])
        ][:30]
    except Exception as exc:
        logger.warning("No se pudo leer el árbol del repo: %s", exc)
        archivos = []

    # 2. Leer contenido de archivos clave (máximo 5)
    contenidos: List[Dict[str, str]] = []
    for path in archivos[:5]:
        try:
            contenido = await get_file_content(repo, path)
            contenidos.append({"path": path, "content": contenido})
        except Exception as exc:
            logger.warning("No se pudo leer %s: %s", path, exc)

    # 3. Pedir al agente un plan de cambios
    contexto = _construir_prompt_desarrollo(tarea, repo_data, archivos, contenidos, prompt_extra)
    agente = {
        "nombre": "jarvis-developer",
        "modelo": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        "system_prompt": _SYSTEM_PROMPT_DESARROLLO,
        "skills": [],
        "knowledge": [],
    }
    respuesta_agente = await ejecutar_agente(agente, contexto, max_tokens=4000)

    # 4. Parsear respuesta
    plan = _parsear_plan_desarrollo(respuesta_agente)
    if not plan["archivos"]:
        return {
            "ok": False,
            "error": "El agente no propuso cambios de código.",
            "agente_respuesta": respuesta_agente,
        }

    # 5. Crear rama y aplicar cambios
    try:
        await create_branch(repo, branch_name, default_branch)
    except Exception as exc:
        return {"ok": False, "error": f"No se pudo crear la rama: {exc}", "agente_respuesta": respuesta_agente}

    commits = []
    for cambio in plan["archivos"]:
        try:
            sha = await commit_file(repo, cambio["path"], cambio["content"], branch_name, cambio["mensaje"])
            commits.append({"path": cambio["path"], "sha": sha})
        except Exception as exc:
            logger.exception("Error aplicando cambio en %s", cambio["path"])
            return {"ok": False, "error": f"Error en {cambio['path']}: {exc}", "agente_respuesta": respuesta_agente}

    # 6. Crear PR
    try:
        pr = await create_pull_request(
            repo,
            title=plan["titulo_pr"],
            body=plan["body_pr"],
            head=branch_name,
            base=default_branch,
        )
    except Exception as exc:
        return {"ok": False, "error": f"No se pudo crear el PR: {exc}", "agente_respuesta": respuesta_agente}

    # 7. Guardar estado en la tarea
    storage.actualizar_github_tarea(
        tarea["id"],
        repo=repo,
        branch=branch_name,
        pr_url=pr["url"],
        pr_number=pr["number"],
        status="pr_open",
        agente_log=plan,
    )

    return {
        "ok": True,
        "repo": repo,
        "branch": branch_name,
        "pr": pr,
        "archivos": [c["path"] for c in plan["archivos"]],
        "resumen": plan["resumen"],
        "pros": plan["pros"],
        "contras": plan["contras"],
        "agente_respuesta": respuesta_agente,
    }


_SYSTEM_PROMPT_DESARROLLO = """Eres Jarvis Developer, un agente senior de software.

Tu trabajo es analizar una tarea y el código de un repositorio, y proponer cambios concretos para implementarla. NUNCA modifiques directamente la rama principal; siempre generas cambios que el usuario revisará en un pull request.

Responde ÚNICAMENTE con un objeto JSON válido con esta estructura exacta:

{
  "titulo_pr": "Título breve y descriptivo para el pull request",
  "body_pr": "Descripción detallada del PR en Markdown. Explica qué cambios hiciste, por qué, y cómo probarlos.",
  "resumen": "Resumen ejecutivo de 2-3 frases para el usuario",
  "pros": ["ventaja 1", "ventaja 2", ...],
  "contras": ["riesgo 1", "riesgo 2", ...],
  "archivos": [
    {
      "path": "ruta/relativa/al/archivo",
      "content": "CONTENIDO COMPLETO DEL ARCHIVO",
      "mensaje": "mensaje de commit descriptivo"
    }
  ]
}

Reglas:
- Cada archivo debe incluir su contenido COMPLETO, no solo un diff.
- Si el archivo ya existe, reescríbelo con los cambios aplicados.
- Si el archivo es nuevo, usa el path correcto.
- Máximo 5 archivos para no saturar la revisión.
- Sé conservador: no reescribas archivos que no necesitan cambios.
- Los mensajes de commit deben estar en inglés, imperativo ("Add feature...").
- Devuelve SOLO el JSON, sin markdown ni explicaciones adicionales.
"""


EXTENSIONES_RELEVANTES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".json", ".md",
    ".yml", ".yaml", ".toml", ".ini", ".cfg", ".sh", ".sql", ".rs", ".go", ".java",
    ".c", ".cpp", ".h", ".rb", ".php", ".swift", ".kt", ".dart",
}


RUTAS_EXCLUIDAS = {
    "node_modules", "__pycache__", ".git", "dist", "build", "target", "vendor",
    "bin", "obj", ".next", "out", "coverage", ".venv", "venv", "env", "site-packages",
}


def _archivo_relevante(path: str) -> bool:
    lower = path.lower()
    for excluida in RUTAS_EXCLUIDAS:
        if f"/{excluida}/" in lower or lower.startswith(f"{excluida}/"):
            return False
    for ext in EXTENSIONES_RELEVANTES:
        if lower.endswith(ext):
            return True
    return False


def _construir_prompt_desarrollo(
    tarea: Dict[str, Any],
    repo_data: Dict[str, Any],
    archivos: List[str],
    contenidos: List[Dict[str, str]],
    prompt_extra: str = "",
) -> str:
    partes = [
        f"Repositorio: {repo_data['full_name']} (rama principal: {repo_data['default_branch']})",
        f"Tarea: {tarea['titulo']}",
        f"Descripción: {tarea.get('descripcion', '')}",
        f"Objetivo/área: {tarea.get('objetivo', '')}",
        f"Próxima acción de alto valor: {tarea.get('proxima_alta_valor', '')}",
    ]
    if prompt_extra:
        partes.append(f"Instrucciones adicionales del usuario: {prompt_extra}")
    partes.append("\nArchivos en el repo:")
    for path in archivos:
        partes.append(f"- {path}")
    if contenidos:
        partes.append("\nContenido de archivos relevantes:")
        for item in contenidos:
            partes.append(f"\n--- {item['path']} ---")
            partes.append(item["content"][:4000])
    partes.append("\nGenera el JSON con el plan de cambios.")
    return "\n".join(partes)


def _parsear_plan_desarrollo(respuesta: str) -> Dict[str, Any]:
    """Extrae el JSON del plan de desarrollo de la respuesta del agente."""
    texto = respuesta.strip()
    if texto.startswith("```"):
        lineas = [l for l in texto.split("\n") if not l.startswith("```")]
        texto = "\n".join(lineas).strip()

    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio == -1 or fin == -1:
        return {"titulo_pr": "", "body_pr": "", "resumen": "", "pros": [], "contras": [], "archivos": []}

    try:
        data = json.loads(texto[inicio:fin + 1])
    except json.JSONDecodeError:
        return {"titulo_pr": "", "body_pr": "", "resumen": "", "pros": [], "contras": [], "archivos": []}

    return {
        "titulo_pr": data.get("titulo_pr", "Cambios automáticos de Jarvis"),
        "body_pr": data.get("body_pr", ""),
        "resumen": data.get("resumen", ""),
        "pros": data.get("pros", []),
        "contras": data.get("contras", []),
        "archivos": data.get("archivos", []),
    }
