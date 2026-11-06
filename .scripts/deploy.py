#!/usr/bin/env python3
"""Automatiza el release y deploy de los servicios configurados en repos.json.

Flujo (según AGENTS.md y la arquitectura del proyecto):
  1. Lee los repositorios desde repos.json y los ordena por dependencia
     (ver ORDEN_DESPLIEGUE_DEFECTO). Las entradas con "deploy": false —por
     ejemplo `infra`— se ignoran, aunque limpiar_ramas.py las siga usando.
  2. Por cada repo: fetch, valida que existan las ramas de release y cuenta los
     commits de `origin/develop` que todavía no están en `origin/main`. Si no
     hay cambios NO se abre PR ni se tagea: se informa "SIN CAMBIOS" y se sigue.
  3. Calcula la versión CalVer (YYYY.MM.DD, con sufijo .1, .2... si ya existe un
     tag ese día), considerando tags locales y remotos.
  4. Crea (o reutiliza) el Pull Request de release `develop -> main`.
  5. Espera checks / pide confirmación interactiva para mergear a `main`.
  6. Al mergear, crea y empuja el tag anotado `vYYYY.MM.DD`.
  7. El push a `main` dispara el CI/CD en GitHub Actions.
  8. Opcionalmente monitorea el workflow de despliegue en vivo (--watch).

Uso:
  python .scripts/deploy.py [OPCIONES]

Opciones principales:
  --dry-run             Simula todo el proceso sin crear PRs, merges ni tags.
  --status              Muestra el estado de cada servicio sin modificar nada.
  --create-pr-only      Solo crea los PRs de release sin mergearlos ni tagear.
  --auto, -y, --yes     Modo no interactivo: mergea y tagea sin confirmación.
  --watch, -w           Monitorea el workflow de GitHub Actions tras el merge.
  --wait-checks         Espera que los checks del PR pasen antes de mergear.
  --calver, --version V Fuerza una versión CalVer específica (ej. 2026.10.30).
  --only A,B,C          Ejecuta solo para los servicios indicados.
  --skip A,B,C          Omite los servicios indicados.
  --no-tag              No crea ni empuja el tag de Git tras el merge.
  --no-fetch            No ejecuta `git fetch` (usa las refs locales actuales).
  --config PATH         Ruta al archivo repos.json (default: .scripts/repos.json).

Config (repos.json):
  {
    "repos": [
      { "folder": "gateway" },
      { "folder": "auth-service", "deploy": { "order": 20, "workflow": "Build Auth Service" } },
      { "folder": "infra", "branch": "main", "deploy": false }
    ]
  }

  Claves de `deploy` (todas opcionales):
    false        deshabilita el release/deploy de esa entrada; limpiar_ramas.py la sigue usando.
    enabled      alternativa en formato objeto a `"deploy": false`.
    order        entero para ordenar el despliegue (menor primero).
    from         rama origen del release (default: develop, o main si el repo no tiene develop).
    to           rama destino del release (default: main).
    workflow     nombre del workflow de GitHub Actions a monitorear con --watch.
    tag          false para no crear ni empujar tag en ese repo.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Orden de despliegue recomendado por dependencias entre servicios:
# datos y modelos base -> lógica de negocio / media -> routing -> clientes.
# Las entradas de repos.json que no figuren acá se agregan al final, salvo que
# definan su propio `deploy.order`.
ORDEN_DESPLIEGUE_DEFECTO: Dict[str, int] = {
    "profile": 10,        # Esquema de usuarios, migraciones Alembic
    "auth-service": 20,   # Cuentas, sesiones, JWT
    "server": 30,         # Servidores, canales, roles, permisos
    "text-channel": 40,   # Mensajería e historial
    "voice-calls": 50,    # Sesiones de voz LiveKit
    "notifications": 60,  # Notificaciones y contadores de no leídos
    "gateway": 70,        # Routing y relays hacia los microservicios
    "web-client": 80,     # Cliente de usuarios Expo (Web + Android)
    "backoffice": 90,     # Cliente de administración staff Expo
}

ORDEN_SIN_DEFINIR = 10_000
RAMA_DESTINO_DEFECTO = "main"
RAMAS_ORIGEN_DEFECTO: Tuple[str, ...] = ("develop",)
PATRON_CALVER = re.compile(r"^\d{4}\.\d{2}\.\d{2}(?:\.\d+)?$")


# ---------------------------------------------------------------------------
# Formato de consola y colores
# ---------------------------------------------------------------------------

class Color:
    """Códigos ANSI seguros para terminal."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


def configurar_salida() -> None:
    """Configura UTF-8 en stdout/stderr, flush inmediato y activa colores ANSI en Windows."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            pass

    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def c(texto: str, estilo: str) -> str:
    """Aplica color ANSI a un texto."""
    return f"{estilo}{texto}{Color.RESET}"


def preguntar(mensaje: str) -> Optional[str]:
    """Pide una respuesta por consola. Devuelve None si el usuario corta la entrada."""
    try:
        return input(mensaje).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


# ---------------------------------------------------------------------------
# Ejecución de comandos
# ---------------------------------------------------------------------------

def ejecutar(
    cmd: List[str],
    cwd: Optional[Path] = None,
    capture: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Ejecuta un comando sin shell."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Ejecuta `git -C <repo> <args>`."""
    return ejecutar(["git", "-C", str(repo), *args], check=check)


def gh(repo: Path, *args: str, capture: bool = True, check: bool = False) -> subprocess.CompletedProcess:
    """Ejecuta `gh <args>` dentro del directorio del repositorio."""
    try:
        return ejecutar(["gh", *args], cwd=repo, capture=capture, check=check)
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=["gh", *args], returncode=127, stdout="", stderr="GitHub CLI (gh) no está instalado"
        )


def detalle_error(res: subprocess.CompletedProcess) -> str:
    """Primera línea útil de error de un comando, para mensajes de consola."""
    texto = (res.stderr or "") + ("\n" + res.stdout if res.stdout else "")
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]
    for linea in lineas:
        if linea.lower().startswith(("error:", "fatal:", "gh:", "x ")):
            return linea
    return lineas[-1] if lineas else ""


# ---------------------------------------------------------------------------
# Verificaciones del entorno
# ---------------------------------------------------------------------------

def verificar_prerrequisitos(solo_status: bool = False, dry_run: bool = False) -> None:
    """Verifica que Git y GitHub CLI (gh) estén disponibles y autenticados."""
    try:
        res = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if res.returncode != 0:
            sys.exit(c("ERROR: Git no está disponible en PATH.", Color.RED))
    except FileNotFoundError:
        sys.exit(c("ERROR: Git no está instalado o no se encuentra en PATH.", Color.RED))

    try:
        res = subprocess.run(["gh", "--version"], capture_output=True, text=True)
        if res.returncode != 0:
            if solo_status or dry_run:
                print(c("Aviso: 'gh' no está disponible en PATH.", Color.YELLOW))
                return
            sys.exit(c("ERROR: GitHub CLI (gh) no está disponible en PATH.", Color.RED))
    except FileNotFoundError:
        if solo_status or dry_run:
            print(c("Aviso: 'gh' no está instalado o no se encuentra en PATH.", Color.YELLOW))
            return
        sys.exit(
            c("ERROR: GitHub CLI (gh) no está instalado. Instálalo desde https://cli.github.com/", Color.RED)
        )

    res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if res.returncode != 0:
        aviso = (
            "GitHub CLI no está autenticado o el token expiró.\n"
            "  -> Para re-autenticar, ejecuta: gh auth refresh -h github.com (o gh auth login)"
        )
        if solo_status or dry_run:
            print(c(f"Aviso: {aviso}", Color.YELLOW))
        else:
            sys.exit(c(f"ERROR: {aviso}", Color.RED))


# ---------------------------------------------------------------------------
# Carga de repositorios
# ---------------------------------------------------------------------------

@dataclass
class RepoInfo:
    """Un repositorio del workspace con la configuración de release/deploy."""

    nombre: str
    path: Path
    branch_origen: Optional[str] = None      # None => autodetectar (develop)
    branch_destino: str = RAMA_DESTINO_DEFECTO
    orden: Optional[int] = None
    workflow: Optional[str] = None
    crear_tag: bool = True

    def clave_orden(self) -> Tuple[int, str]:
        if self.orden is not None:
            return (self.orden, self.nombre.lower())
        return (ORDEN_DESPLIEGUE_DEFECTO.get(self.nombre, ORDEN_SIN_DEFINIR), self.nombre.lower())


def _leer_opciones_deploy(item: Dict[str, Any], folder: str) -> Tuple[bool, Dict[str, Any]]:
    """Normaliza el campo `deploy` de una entrada de repos.json a (habilitado, opciones)."""
    valor = item.get("deploy", True)
    if isinstance(valor, bool):
        return valor, {}
    if isinstance(valor, dict):
        return bool(valor.get("enabled", True)), valor
    print(c(f"Aviso: 'deploy' de '{folder}' debe ser true/false o un objeto; se ignora el valor.", Color.YELLOW))
    return True, {}


def _entero_o_none(valor: Any) -> Optional[int]:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def cargar_repositorios(
    raiz: Path,
    config_path: Path,
    filtro_only: Optional[List[str]] = None,
    filtro_skip: Optional[List[str]] = None,
) -> List[RepoInfo]:
    """Lee repos.json y arma la lista ordenada de repositorios a procesar."""
    entradas: List[Any] = []

    if config_path.is_file():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(c(f"ERROR: no se pudo leer {config_path}: {e}", Color.RED))
            return []
        entradas = data.get("repos") if isinstance(data, dict) else None
        if not isinstance(entradas, list):
            print(c(f"ERROR: {config_path} debe tener la forma {{ \"repos\": [ ... ] }}.", Color.RED))
            return []
    else:
        print(c(f"Aviso: no se encontró {config_path}; se usa la lista de servicios por defecto.", Color.YELLOW))
        entradas = [{"folder": nombre} for nombre in ORDEN_DESPLIEGUE_DEFECTO]

    repos: Dict[str, RepoInfo] = {}
    deshabilitados: List[str] = []

    for indice, item in enumerate(entradas, start=1):
        if not isinstance(item, dict) or not item.get("folder"):
            print(c(f"Aviso: entrada #{indice} de repos.json sin 'folder'; se omite.", Color.YELLOW))
            continue

        folder = str(item["folder"]).strip()
        if not item.get("enabled", True):
            continue

        habilitado, opciones = _leer_opciones_deploy(item, folder)
        if not habilitado:
            deshabilitados.append(folder)
            continue

        repo_path = Path(folder) if Path(folder).is_absolute() else raiz / folder
        if not repo_path.is_dir():
            print(c(f"Aviso: '{folder}' no existe en {raiz}; se omite.", Color.YELLOW))
            continue
        if not (repo_path / ".git").exists():
            print(c(f"Aviso: '{folder}' no es un repositorio git; se omite.", Color.YELLOW))
            continue

        origen = opciones.get("from") or opciones.get("origen")
        destino = opciones.get("to") or opciones.get("destino") or RAMA_DESTINO_DEFECTO
        repos[folder] = RepoInfo(
            nombre=folder,
            path=repo_path,
            branch_origen=str(origen) if origen else None,
            branch_destino=str(destino),
            orden=_entero_o_none(opciones.get("order")),
            workflow=str(opciones["workflow"]) if opciones.get("workflow") else None,
            crear_tag=bool(opciones.get("tag", True)),
        )

    ordenados = sorted(repos.values(), key=lambda repo: repo.clave_orden())

    if filtro_only:
        por_nombre = {repo.nombre.lower(): repo for repo in ordenados}
        deshabilitados_lower = {nombre.lower() for nombre in deshabilitados}
        seleccionados: List[RepoInfo] = []
        for pedido in filtro_only:
            clave = pedido.lower().rstrip("/\\")
            if not clave:
                continue
            elegido = por_nombre.get(clave)
            if elegido is None:
                if clave in deshabilitados_lower:
                    print(c(f"Aviso: '{pedido}' tiene el deploy deshabilitado en repos.json; se omite.", Color.YELLOW))
                else:
                    print(c(f"Aviso: --only '{pedido}' no coincide con ningún repo configurado; se omite.", Color.YELLOW))
                continue
            if elegido not in seleccionados:
                seleccionados.append(elegido)
        ordenados = seleccionados

    if filtro_skip:
        omitidos = {pedido.strip().lower().rstrip("/\\") for pedido in filtro_skip if pedido.strip()}
        ordenados = [repo for repo in ordenados if repo.nombre.lower() not in omitidos]

    return ordenados


def resolver_config_path(valor: Optional[str], raiz: Path) -> Path:
    """Resuelve la ruta de repos.json (absoluta, relativa al cwd o al workspace)."""
    script_dir = Path(__file__).resolve().parent
    if valor:
        ruta = Path(valor)
        if ruta.is_absolute():
            return ruta
        desde_cwd = Path.cwd() / ruta
        if desde_cwd.is_file():
            return desde_cwd
        desde_raiz = raiz / ruta
        if desde_raiz.is_file():
            return desde_raiz
        desde_script = script_dir / ruta
        return desde_script if desde_script.is_file() else desde_raiz

    for candidato in (script_dir / "repos.json", raiz / "repos.json", raiz / ".scripts" / "repos.json"):
        if candidato.is_file():
            return candidato
    return script_dir / "repos.json"


# ---------------------------------------------------------------------------
# CalVer y Git helpers
# ---------------------------------------------------------------------------

def obtener_calver_base(fecha: Optional[datetime.date] = None) -> str:
    """Devuelve la fecha actual en formato CalVer: YYYY.MM.DD."""
    d = fecha or datetime.date.today()
    return f"{d.year}.{d.month:02d}.{d.day:02d}"


def clave_version(tag: str) -> Tuple[int, ...]:
    """Clave de ordenamiento numérica para tags CalVer (v2026.10.30 < v2026.10.30.1)."""
    return tuple(int(numero) for numero in re.findall(r"\d+", tag))


def resolver_siguiente_calver(tags_existentes: List[str], calver_base: str) -> str:
    """Calcula la versión CalVer final considerando posibles sufijos .1, .2...

    Si 'v2026.10.30' no existe -> devuelve '2026.10.30'.
    Si 'v2026.10.30' ya existe -> busca '2026.10.30.1', '2026.10.30.2', etc.
    """
    tags_set = set(tags_existentes)
    if f"v{calver_base}" not in tags_set:
        return calver_base

    micro = 1
    while f"v{calver_base}.{micro}" in tags_set:
        micro += 1
    return f"{calver_base}.{micro}"


def existe_ref(repo: Path, ref: str) -> bool:
    return git(repo, "rev-parse", "--verify", "--quiet", ref).returncode == 0


def sha_ref(repo: Path, ref: str) -> Optional[str]:
    res = git(repo, "rev-parse", "--verify", "--quiet", ref)
    sha = res.stdout.strip() if res.returncode == 0 else ""
    return sha or None


def obtener_tags(repo: Path, consultar_remoto: bool = True) -> List[str]:
    """Tags del repo (locales + remotos), ordenados por versión ascendente."""
    tags = set()

    res = git(repo, "tag", "-l")
    if res.returncode == 0:
        tags.update(linea.strip() for linea in res.stdout.splitlines() if linea.strip())

    if consultar_remoto:
        res = git(repo, "ls-remote", "--tags", "--refs", "origin")
        if res.returncode == 0:
            for linea in res.stdout.splitlines():
                partes = linea.split()
                if len(partes) >= 2 and partes[1].startswith("refs/tags/"):
                    tags.add(partes[1][len("refs/tags/"):].strip())

    return sorted(tags, key=lambda tag: (clave_version(tag), tag))


def fetch_remoto(repo: Path) -> Tuple[bool, str]:
    """Ejecuta `git fetch origin --prune`."""
    res = git(repo, "fetch", "origin", "--prune")
    if res.returncode != 0:
        return False, detalle_error(res)
    return True, ""


def fetch_rama(repo: Path, rama: str) -> Tuple[bool, str]:
    """Actualiza únicamente la ref `origin/<rama>`."""
    res = git(repo, "fetch", "origin", rama)
    if res.returncode != 0:
        return False, detalle_error(res)
    return True, ""


def resolver_ramas(repo: RepoInfo) -> Tuple[Optional[str], str, Optional[str]]:
    """Determina (rama_origen, rama_destino, error) para el release del repo.

    Devuelve origen=None y un mensaje en `error` cuando el repo no tiene un
    flujo de release válido (sin `develop`, origen == destino, etc.).
    """
    destino = repo.branch_destino

    if not existe_ref(repo.path, f"refs/remotes/origin/{destino}"):
        if existe_ref(repo.path, f"refs/heads/{destino}"):
            return None, destino, f"la rama '{destino}' existe solo localmente (falta pushearla a origin)"
        return None, destino, f"no existe la rama destino '{destino}' en origin"

    origen = repo.branch_origen
    if origen:
        if not existe_ref(repo.path, f"refs/remotes/origin/{origen}"):
            return None, destino, f"no existe la rama origen '{origen}' en origin"
    else:
        for candidata in RAMAS_ORIGEN_DEFECTO:
            if existe_ref(repo.path, f"refs/remotes/origin/{candidata}"):
                origen = candidata
                break
        if not origen:
            return None, destino, f"no existe la rama 'develop' en origin (repo sin flujo develop -> {destino})"

    if origen == destino:
        return None, destino, f"la rama origen y la destino son la misma ('{origen}'): no hay release posible"

    return origen, destino, None


def obtener_commits(repo: Path, rango: str, sin_merges: bool = False) -> Optional[List[Tuple[str, str]]]:
    """Lista [(sha_corto, subject)] de un rango git. Devuelve None si git falla."""
    args = ["log", rango, "--oneline"]
    if sin_merges:
        args.append("--no-merges")
    res = git(repo, *args)
    if res.returncode != 0:
        return None

    commits: List[Tuple[str, str]] = []
    for linea in res.stdout.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        sha, _, msg = linea.partition(" ")
        commits.append((sha, msg))
    return commits


def obtener_commits_pendientes(repo: Path, origen: str, destino: str) -> Optional[List[Tuple[str, str]]]:
    """Commits presentes en `origin/<origen>` que todavía no están en `origin/<destino>`."""
    return obtener_commits(repo, f"origin/{destino}..origin/{origen}")


def obtener_commits_divergentes(repo: Path, origen: str, destino: str) -> List[Tuple[str, str]]:
    """Commits reales (sin merge-commits de release) que están en destino y no en origen."""
    return obtener_commits(repo, f"origin/{origen}..origin/{destino}", sin_merges=True) or []


# ---------------------------------------------------------------------------
# GitHub PR helpers
# ---------------------------------------------------------------------------

def buscar_pr_release_existente(
    repo: Path, origen: str, destino: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Busca un PR abierto con head=<origen> y base=<destino>.

    Devuelve (pr, error). Si `gh` falla, `pr` es None y `error` describe el problema.
    """
    res = gh(
        repo,
        "pr",
        "list",
        "--head",
        origen,
        "--base",
        destino,
        "--state",
        "open",
        "--json",
        "number,title,url,mergeable",
    )
    if res.returncode != 0:
        return None, detalle_error(res) or f"`gh pr list` falló con código {res.returncode}"

    try:
        prs = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        return None, "respuesta inválida de `gh pr list`"

    if isinstance(prs, list) and prs:
        return prs[0], None
    return None, None


def armar_cuerpo_pr(
    nombre_repo: str, calver: str, commits: List[Tuple[str, str]], origen: str, destino: str
) -> str:
    """Construye la descripción en Markdown del PR de Release siguiendo el estándar del equipo."""
    prs_incluidos: List[str] = []
    otros_commits: List[str] = []

    for sha, msg in commits:
        match = re.match(r"Merge pull request #(\d+) from (.+)", msg)
        if match:
            pr_num, rama = match.groups()
            prs_incluidos.append(f"- #{pr_num} (`{rama}`)")
        else:
            otros_commits.append(f"- `{sha}` {msg}")

    cuerpo = [
        f"Release `{origen} → {destino}` de `{nombre_repo}` (CalVer {calver}).",
        "",
        "**Commits incluidos:**",
    ]

    if prs_incluidos:
        cuerpo.append("\n*Pull Requests integrados:*")
        cuerpo.extend(prs_incluidos)
        if otros_commits:
            cuerpo.append("\n*Commits directos o detallados:*")
            cuerpo.extend(otros_commits)
    else:
        cuerpo.extend(otros_commits if otros_commits else ["- Sin descripción adicional."])

    cuerpo.append("")
    cuerpo.append(f"**Deploy:** merge a `{destino}` dispara el pipeline CI/CD (tests + build ECR + deploy SSM / Expo).")
    cuerpo.append(f"Tag asociado: `v{calver}`.")

    return "\n".join(cuerpo)


def crear_pr_release(
    repo: Path,
    nombre_repo: str,
    origen: str,
    destino: str,
    calver: str,
    commits: List[Tuple[str, str]],
) -> Tuple[bool, str, str]:
    """Crea el PR en GitHub. Devuelve (éxito, número, url_o_error)."""
    titulo = f"Release/{calver}"
    cuerpo = armar_cuerpo_pr(nombre_repo, calver, commits, origen, destino)

    res = gh(
        repo,
        "pr",
        "create",
        "--base",
        destino,
        "--head",
        origen,
        "--title",
        titulo,
        "--body",
        cuerpo,
    )
    if res.returncode == 0:
        url = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else ""
        match = re.search(r"/pull/(\d+)", url)
        return True, (match.group(1) if match else url), url

    return False, "", detalle_error(res) or "`gh pr create` falló"


def esperar_checks_pr(repo: Path, pr_num: str) -> Tuple[bool, str]:
    """Espera a que los checks del PR finalicen. Los PRs sin checks se consideran OK."""
    res = gh(repo, "pr", "checks", pr_num, "--json", "name,state")
    if res.returncode != 0:
        if "no checks" in (res.stderr or "").lower():
            return True, "el PR no tiene checks configurados"
    else:
        try:
            checks = json.loads(res.stdout or "[]")
        except json.JSONDecodeError:
            checks = []
        if not checks:
            return True, "el PR no tiene checks configurados"

    print(c(f"  Esperando checks CI del PR #{pr_num}...", Color.CYAN))
    res = gh(repo, "pr", "checks", pr_num, "--watch", capture=False)
    if res.returncode == 0:
        return True, ""
    return False, "uno o más checks del PR fallaron"


def mergear_pr(repo: Path, pr_num: str, calver: str, head_sha: Optional[str]) -> Tuple[bool, str]:
    """Mergea el PR con 'gh pr merge --merge' (merge commit estándar, nunca borra ramas)."""
    argumentos = ["pr", "merge", pr_num, "--merge", "--subject", f"Release/{calver}"]
    if head_sha:
        argumentos += ["--match-head-commit", head_sha]

    res = gh(repo, *argumentos)
    if res.returncode == 0:
        return True, ""
    return False, detalle_error(res) or "`gh pr merge` falló"


def obtener_merge_commit(repo: Path, pr_num: str) -> Optional[str]:
    """SHA del commit de merge que creó GitHub para el PR (None si no se puede leer)."""
    res = gh(repo, "pr", "view", pr_num, "--json", "mergeCommit,state")
    if res.returncode != 0:
        return None
    try:
        data = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        return None
    merge_commit = data.get("mergeCommit")
    if isinstance(merge_commit, dict):
        sha = merge_commit.get("oid")
        return str(sha) if sha else None
    return None


def sha_tag_remoto(repo: Path, tag_name: str) -> Optional[str]:
    """SHA del commit al que apunta un tag en origin (None si no existe)."""
    res = git(repo, "ls-remote", "--tags", "origin", f"refs/tags/{tag_name}")
    if res.returncode != 0:
        return None

    directo = None
    pelado = None
    for linea in res.stdout.splitlines():
        partes = linea.split()
        if len(partes) < 2:
            continue
        sha, ref = partes[0], partes[1]
        if ref == f"refs/tags/{tag_name}":
            directo = sha
        elif ref == f"refs/tags/{tag_name}^{{}}":
            pelado = sha
    return pelado or directo


def crear_y_empujar_tag(
    repo: Path, calver: str, destino: str, commit_sha_esperado: Optional[str] = None
) -> Tuple[bool, str]:
    """Crea un tag anotado v<calver> sobre el commit del release y lo empuja al remoto.

    `commit_sha_esperado` es el commit de merge reportado por GitHub; si no se
    indica, se usa el tip de `origin/<destino>`. Valida que un tag preexistente
    (local o remoto) apunte al mismo commit para no publicar una versión que no
    corresponde al merge recién hecho.
    """
    tag_name = f"v{calver}"

    ok_fetch, err_fetch = fetch_rama(repo, destino)
    if not ok_fetch:
        return False, f"No se pudo actualizar origin/{destino}: {err_fetch}"

    commit_sha = commit_sha_esperado or sha_ref(repo, f"refs/remotes/origin/{destino}")
    if not commit_sha:
        return False, f"No se pudo resolver el SHA de origin/{destino}"
    if git(repo, "cat-file", "-e", f"{commit_sha}^{{commit}}").returncode != 0:
        return False, f"El commit {commit_sha[:7]} del merge no está disponible localmente; ejecutá git fetch origin"

    sha_local = sha_ref(repo, f"refs/tags/{tag_name}^{{commit}}")
    if sha_local:
        if sha_local != commit_sha:
            return False, (
                f"El tag {tag_name} ya existe localmente apuntando a {sha_local[:7]} y no al commit del release "
                f"({commit_sha[:7]}); usá --calver para elegir otra versión"
            )
    else:
        res_tag = git(repo, "tag", "-a", tag_name, commit_sha, "-m", f"Release {calver}")
        if res_tag.returncode != 0:
            return False, f"Fallo al crear tag {tag_name}: {detalle_error(res_tag)}"

    sha_remoto = sha_tag_remoto(repo, tag_name)
    if sha_remoto:
        if sha_remoto != commit_sha:
            return False, (
                f"El tag {tag_name} ya existe en origin apuntando a {sha_remoto[:7]} y no al commit del release "
                f"({commit_sha[:7]}); usá --calver para elegir otra versión"
            )
        return True, f"El tag {tag_name} ya estaba publicado en origin."

    res_push = git(repo, "push", "origin", tag_name)
    if res_push.returncode != 0:
        return False, f"Fallo al empujar tag {tag_name}: {detalle_error(res_push)}"

    return True, ""


# ---------------------------------------------------------------------------
# GitHub Actions
# ---------------------------------------------------------------------------

def _coincide_workflow(nombre_run: str, buscado: str) -> bool:
    return nombre_run.strip().lower() == buscado.strip().lower()


def buscar_run_despliegue(
    repo: Path,
    destino: str,
    commit_sha: Optional[str],
    workflow: Optional[str] = None,
    espera: int = 45,
) -> Optional[Dict[str, Any]]:
    """Busca el run de push disparado por el merge en `origin/<destino>`."""
    limite = time.time() + espera
    while True:
        argumentos = [
            "run", "list",
            "--branch", destino,
            "--limit", "20",
            "--json", "databaseId,name,status,conclusion,url,event,headSha",
        ]
        if commit_sha:
            argumentos += ["--commit", commit_sha]

        res = gh(repo, *argumentos)
        if res.returncode == 0 and res.stdout.strip():
            try:
                runs = json.loads(res.stdout)
            except json.JSONDecodeError:
                runs = []
            for run in runs:
                if run.get("event") != "push":
                    continue
                if commit_sha and (run.get("headSha") or "") != commit_sha:
                    continue
                if workflow and not _coincide_workflow(str(run.get("name", "")), workflow):
                    continue
                return run

        if time.time() >= limite:
            return None
        time.sleep(3)


def monitorear_workflow(repo: Path, run_id: str) -> bool:
    """Ejecuta `gh run watch` para monitorear el progreso del workflow en vivo."""
    print(c(f"  Monitoreando workflow de deploy (Run ID: {run_id})...", Color.CYAN))
    res = gh(repo, "run", "watch", str(run_id), "--exit-status", capture=False)
    return res.returncode == 0


# ---------------------------------------------------------------------------
# Modo Status
# ---------------------------------------------------------------------------

def mostrar_estado_repositorios(repos: List[RepoInfo], calver_base: str, do_fetch: bool = True) -> None:
    """Imprime un resumen de estado de todos los repositorios, sin modificar nada."""
    print("\n" + "=" * 92)
    print(c(f"  ESTADO DE SERVICIOS (CalVer base sugerido: {calver_base})", Color.BOLD))
    print("=" * 92)
    print(f"{'Servicio':<16}{'Release':<18}{'Pendientes':<13}{'Último tag':<17}Estado")
    print("-" * 92)

    hay_pendientes = 0
    for repo in repos:
        if do_fetch:
            ok_fetch, err_fetch = fetch_remoto(repo.path)
            if not ok_fetch:
                print(f"{repo.nombre:<16}{'-':<18}{'-':<13}{'-':<17}{c('ERROR fetch', Color.RED)}")
                print(f"    {c(err_fetch, Color.DIM)}")
                continue

        origen, destino, error_ramas = resolver_ramas(repo)
        etiqueta_release = f"{origen or '-'}→{destino}"
        tags = obtener_tags(repo.path, consultar_remoto=do_fetch)
        ultimo_tag = tags[-1] if tags else "-"

        if error_ramas:
            print(f"{repo.nombre:<16}{etiqueta_release:<18}{'-':<13}{ultimo_tag:<17}{c('SIN RELEASE', Color.YELLOW)}")
            print(f"    {c(error_ramas, Color.DIM)}")
            continue

        commits = obtener_commits_pendientes(repo.path, origen, destino)
        if commits is None:
            print(f"{repo.nombre:<16}{etiqueta_release:<18}{'-':<13}{ultimo_tag:<17}{c('ERROR git', Color.RED)}")
            print(f"    {c(f'no se pudo leer origin/{origen}..origin/{destino}', Color.DIM)}")
            continue

        if commits:
            hay_pendientes += 1
            calver_previsto = resolver_siguiente_calver(tags, calver_base)
            print(
                f"{repo.nombre:<16}{etiqueta_release:<18}{f'{len(commits)} commits':<13}"
                f"{ultimo_tag:<17}{c(f'Listo para Release (v{calver_previsto})', Color.YELLOW)}"
            )
        else:
            print(f"{repo.nombre:<16}{etiqueta_release:<18}{'0 commits':<13}{ultimo_tag:<17}{c('SIN CAMBIOS', Color.GREEN)}")

        divergentes = obtener_commits_divergentes(repo.path, origen, destino)
        if divergentes:
            print(
                f"    {c(f'aviso: origin/{destino} tiene {len(divergentes)} commit(s) que no están en origin/{origen}', Color.YELLOW)}"
            )

    print("-" * 92)
    if hay_pendientes:
        print(c(f"Total: {hay_pendientes} servicio(s) con cambios pendientes para release.", Color.YELLOW))
    else:
        print(c("Ningún servicio tiene cambios pendientes para release.", Color.GREEN))
    print("=" * 92 + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatiza el release y deploy de los servicios configurados en repos.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula el flujo completo sin crear PRs, hacer merges ni pushear tags.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Solo muestra el estado de commits pendientes y tags de cada servicio.",
    )
    parser.add_argument(
        "--create-pr-only",
        action="store_true",
        help="Crea los Pull Requests de release pero no los mergea ni tagea.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        "--auto",
        dest="auto",
        action="store_true",
        help="Modo automático: mergea y crea tags sin pedir confirmación interactiva.",
    )
    parser.add_argument(
        "-w",
        "--watch",
        action="store_true",
        help="Monitorea el workflow de despliegue en GitHub Actions tras el merge.",
    )
    parser.add_argument(
        "--wait-checks",
        action="store_true",
        help="Espera que los checks CI del PR pasen antes de proceder al merge.",
    )
    parser.add_argument(
        "--calver",
        "--version",
        dest="calver_override",
        help="Fuerza una versión CalVer base específica (ej. 2026.10.30).",
    )
    parser.add_argument(
        "--only",
        help="Lista coma-separada de servicios a procesar exclusivamente (ej. 'profile,gateway').",
    )
    parser.add_argument(
        "--skip",
        help="Lista coma-separada de servicios a omitir (ej. 'web-client,backoffice').",
    )
    parser.add_argument(
        "--no-tag",
        action="store_true",
        help="Omite la creación y push del tag de Git tras el merge.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Omite ejecutar git fetch origin en cada repositorio (usa el estado local actual).",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Ruta al archivo repos.json (default: .scripts/repos.json).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Flujo principal de Deploy
# ---------------------------------------------------------------------------

def main() -> int:
    configurar_salida()
    args = parse_args()

    verificar_prerrequisitos(solo_status=args.status, dry_run=args.dry_run)

    raiz = Path(__file__).resolve().parent.parent
    config_path = resolver_config_path(args.config, raiz)

    filtro_only = [x.strip() for x in args.only.split(",") if x.strip()] if args.only else None
    filtro_skip = [x.strip() for x in args.skip.split(",") if x.strip()] if args.skip else None

    if args.calver_override and not PATRON_CALVER.match(args.calver_override):
        print(c(f"ERROR: versión CalVer inválida '{args.calver_override}'. Formato esperado: YYYY.MM.DD.", Color.RED))
        return 2

    if args.config and not config_path.is_file():
        print(c(f"ERROR: no existe el archivo de configuración indicado: {config_path}", Color.RED))
        return 2

    repos = cargar_repositorios(raiz, config_path, filtro_only, filtro_skip)
    if not repos:
        print(c("No se encontraron repositorios válidos para procesar (revisá repos.json, o --only/--skip).", Color.RED))
        return 1

    calver_base = args.calver_override or obtener_calver_base()

    if args.status:
        print(c(f"Config: {config_path}", Color.DIM))
        mostrar_estado_repositorios(repos, calver_base, do_fetch=not args.no_fetch)
        return 0

    print("\n" + "=" * 92)
    modo_str = " [DRY-RUN - SIMULACIÓN]" if args.dry_run else ""
    print(c(f"  DEPLOY AUTOMATIZADO DE SERVICIOS{modo_str}", Color.BOLD))
    print(f"  Config: {config_path}")
    print(f"  Versión CalVer base: {calver_base}")
    print(f"  Repositorios ({len(repos)}): {', '.join(repo.nombre for repo in repos)}")
    print(f"  Modo: {'Automático (--auto)' if args.auto else 'Interactivo con confirmación'}")
    if args.create_pr_only:
        print("  Acción: Solo creación de PRs (--create-pr-only)")
    if args.watch:
        print("  Monitoreo: Activado (--watch)")
    print("=" * 92 + "\n")

    resumen_final: List[Tuple[str, str, str]] = []

    for idx, repo in enumerate(repos, 1):
        print(f"\n{c(f'[{idx}/{len(repos)}] Procesando servicio: {repo.nombre}', Color.BOLD)}")

        # 1. Fetch
        if not args.no_fetch:
            ok_fetch, err_fetch = fetch_remoto(repo.path)
            if not ok_fetch:
                print(c(f"  [ERROR] Falló git fetch: {err_fetch}", Color.RED))
                resumen_final.append((repo.nombre, "ERROR", f"Fallo al actualizar remoto: {err_fetch}"))
                continue

        # 2. Ramas de release
        origen, destino, error_ramas = resolver_ramas(repo)
        if error_ramas:
            print(c(f"  [OMITIDO] {error_ramas}", Color.YELLOW))
            resumen_final.append((repo.nombre, "OMITIDO", error_ramas))
            continue

        # 3. ¿Hay algo para releasear?
        commits = obtener_commits_pendientes(repo.path, origen, destino)
        if commits is None:
            detalle = f"no se pudo leer origin/{destino}..origin/{origen}"
            print(c(f"  [ERROR] {detalle}", Color.RED))
            resumen_final.append((repo.nombre, "ERROR", detalle))
            continue

        if not commits:
            print(
                c(
                    f"  [SIN CAMBIOS] origin/{origen} no tiene commits nuevos sobre origin/{destino}; no se hace release.",
                    Color.GREEN,
                )
            )
            divergentes = obtener_commits_divergentes(repo.path, origen, destino)
            if divergentes:
                print(
                    c(
                        f"  [AVISO] origin/{destino} tiene {len(divergentes)} commit(s) que no están en origin/{origen}:",
                        Color.YELLOW,
                    )
                )
                for sha, msg in divergentes[:3]:
                    print(f"     - `{sha}` {msg}")
                print(c(f"     Revisá si hace falta sincronizar {destino} -> {origen}.", Color.DIM))
            resumen_final.append((repo.nombre, "SIN CAMBIOS", f"Sin commits nuevos en origin/{origen}"))
            continue

        # 4. CalVer de este servicio
        tags = obtener_tags(repo.path, consultar_remoto=not args.no_fetch)
        calver_servicio = resolver_siguiente_calver(tags, calver_base)
        tag_servicio = f"v{calver_servicio}"

        print(c(f"  -> {len(commits)} commit(s) pendientes de {origen} a {destino}.", Color.CYAN))
        print(f"  -> Versión CalVer asignada: {c(calver_servicio, Color.CYAN)} (tag: {tag_servicio})")
        print("  -> Primeros commits:")
        for sha, msg in commits[:4]:
            print(f"     - `{sha}` {msg}")
        if len(commits) > 4:
            print(f"     ... y {len(commits) - 4} commits más.")

        # 5. PR de release (existente o nuevo)
        pr_existente, pr_error = buscar_pr_release_existente(repo.path, origen, destino)
        if pr_error:
            print(c(f"  [AVISO] No se pudo consultar PRs abiertos: {pr_error}", Color.YELLOW))

        pr_num = ""
        pr_url = ""

        if pr_existente:
            pr_num = str(pr_existente.get("number", ""))
            pr_url = str(pr_existente.get("url", ""))
            print(c(f"  [PR] Ya existe un PR de release abierto: #{pr_num} ({pr_url})", Color.CYAN))
            if str(pr_existente.get("mergeable", "")).upper() == "CONFLICTING":
                print(c("  [ERROR] El PR tiene conflictos con la rama destino; resolvelos y volvé a ejecutar.", Color.RED))
                resumen_final.append((repo.nombre, "ERROR", f"PR #{pr_num} con conflictos"))
                continue
        elif args.dry_run:
            print(c(f"  [DRY-RUN] Se crearía el PR 'Release/{calver_servicio}' ({origen} -> {destino})", Color.YELLOW))
            pr_num = "SIMULADO"
        else:
            ok_pr, num_o_err, url_o_err = crear_pr_release(
                repo.path, repo.nombre, origen, destino, calver_servicio, commits
            )
            if not ok_pr:
                print(c(f"  [ERROR] Falló la creación del PR: {url_o_err}", Color.RED))
                resumen_final.append((repo.nombre, "ERROR", f"Fallo al crear PR: {url_o_err}"))
                continue
            pr_num = num_o_err
            pr_url = url_o_err
            print(c(f"  [PR CREADO] PR #{pr_num}: {pr_url}", Color.GREEN))

        if args.create_pr_only:
            etiqueta = "SIMULADO" if args.dry_run else ("PR EXISTENTE" if pr_existente else "PR CREADO")
            resumen_final.append((repo.nombre, etiqueta, f"PR #{pr_num} ({pr_url})" if pr_url else f"PR #{pr_num}"))
            continue

        if args.dry_run:
            print(c(f"  [DRY-RUN] Se mergearía PR #{pr_num} a '{destino}' con commit 'Release/{calver_servicio}'", Color.YELLOW))
            if repo.crear_tag and not args.no_tag:
                print(c(f"  [DRY-RUN] Se crearía y empujaría el tag anotado '{tag_servicio}'", Color.YELLOW))
            if args.watch:
                print(c("  [DRY-RUN] Se monitorearía el workflow de deploy en GitHub Actions", Color.YELLOW))
            resumen_final.append((repo.nombre, "SIMULADO", f"Release {tag_servicio}"))
            continue

        # 6. Checks del PR
        if args.wait_checks:
            ok_checks, detalle_checks = esperar_checks_pr(repo.path, pr_num)
            if not ok_checks:
                print(c(f"  [AVISO] {detalle_checks} (PR #{pr_num}).", Color.YELLOW))
                if args.auto:
                    print(c("  Modo --auto: se omite el merge para no publicar un release con checks fallidos.", Color.YELLOW))
                    resumen_final.append((repo.nombre, "PR PENDIENTE", f"PR #{pr_num} con checks fallidos"))
                    continue
                respuesta = preguntar(c("  ¿Deseas continuar con el merge de todos modos? [s/N]: ", Color.BOLD))
                if respuesta is None or respuesta not in ("s", "si", "sí", "y", "yes"):
                    print(c("  Omitiendo merge para este servicio.", Color.YELLOW))
                    resumen_final.append((repo.nombre, "PR PENDIENTE", f"PR #{pr_num} con checks fallidos"))
                    continue
            elif detalle_checks:
                print(c(f"  [OK] {detalle_checks}.", Color.GREEN))

        # 7. Confirmación interactiva
        debe_mergear = args.auto
        debe_watch = args.watch

        if not args.auto:
            pregunta = (
                f"\n  ¿Mergear PR #{pr_num} de {c(repo.nombre, Color.BOLD)} a {destino} "
                f"y crear tag {c(tag_servicio, Color.CYAN)}?\n"
                "  [S/Enter] Sí | [w] Sí y monitorear CI/CD | [n] No (dejar PR abierto) | "
                "[k] Saltar servicio | [a] Abortar: "
            )
            respuesta = preguntar(c(pregunta, Color.WHITE))

            if respuesta is None or respuesta in ("a", "abort", "abortar"):
                print(c("\nOperación abortada por el usuario.", Color.RED))
                resumen_final.append((repo.nombre, "ABORTADO", "Cancelado por el usuario"))
                break
            if respuesta in ("k", "saltar", "skip"):
                print(c("  Servicio omitido.", Color.YELLOW))
                resumen_final.append((repo.nombre, "OMITIDO", f"PR #{pr_num} queda abierto"))
                continue
            if respuesta in ("n", "no"):
                print(c("  El PR queda abierto (sin merge).", Color.YELLOW))
                resumen_final.append((repo.nombre, "PR ABIERTO", f"PR #{pr_num} ({pr_url})"))
                continue
            if respuesta == "w":
                debe_mergear = True
                debe_watch = True
            elif respuesta in ("", "s", "si", "sí", "y", "yes"):
                debe_mergear = True
            else:
                print(c("  Respuesta no reconocida: el PR queda abierto.", Color.YELLOW))
                resumen_final.append((repo.nombre, "PR ABIERTO", f"PR #{pr_num} ({pr_url})"))
                continue

        if not debe_mergear:
            resumen_final.append((repo.nombre, "PR ABIERTO", f"PR #{pr_num} ({pr_url})"))
            continue

        # 8. Merge del PR
        print(c(f"  [MERGE] Mergeando PR #{pr_num} ({origen} -> {destino})...", Color.CYAN))
        head_sha = sha_ref(repo.path, f"refs/remotes/origin/{origen}")
        ok_merge, err_merge = mergear_pr(repo.path, pr_num, calver_servicio, head_sha)
        if not ok_merge:
            print(c(f"  [ERROR] Falló el merge del PR #{pr_num}: {err_merge}", Color.RED))
            if head_sha:
                print(c(f"  Si origin/{origen} cambió durante el proceso, volvé a ejecutar el script.", Color.DIM))
            resumen_final.append((repo.nombre, "ERROR", f"Fallo al mergear PR: {err_merge}"))
            continue
        print(c(f"  [MERGE OK] PR #{pr_num} mergeado exitosamente a '{destino}'.", Color.GREEN))

        # 9. Tag y push
        crear_tag = repo.crear_tag and not args.no_tag
        sha_merge = obtener_merge_commit(repo.path, pr_num)
        ok_fetch_destino, err_fetch_destino = fetch_rama(repo.path, destino)
        if ok_fetch_destino:
            sha_merge = sha_merge or sha_ref(repo.path, f"refs/remotes/origin/{destino}")
        else:
            print(c(f"  [AVISO] No se pudo actualizar origin/{destino}: {err_fetch_destino}", Color.YELLOW))

        if crear_tag:
            print(c(f"  [TAG] Creando y empujando tag {tag_servicio}...", Color.CYAN))
            ok_tag, msg_tag = crear_y_empujar_tag(repo.path, calver_servicio, destino, sha_merge)
            if not ok_tag:
                print(c(f"  [AVISO] {msg_tag}", Color.YELLOW))
                resumen_final.append((repo.nombre, "MERGEADO SIN TAG", msg_tag))
            else:
                if msg_tag:
                    print(c(f"  [TAG OK] {msg_tag}", Color.GREEN))
                else:
                    print(c(f"  [TAG OK] Tag {tag_servicio} publicado en origin.", Color.GREEN))
        else:
            print(c("  [TAG] Omitido (--no-tag o 'deploy.tag: false' en repos.json).", Color.DIM))

        # 10. Monitoreo opcional de GitHub Actions
        if debe_watch:
            print(c("  Esperando a que GitHub Actions registre el workflow de deploy...", Color.CYAN))
            run_info = buscar_run_despliegue(repo.path, destino, sha_merge, repo.workflow)
            if run_info and run_info.get("databaseId"):
                run_id = str(run_info["databaseId"])
                run_url = str(run_info.get("url", ""))
                print(c(f"  Workflow: {run_info.get('name', 'Deploy')} | {run_url}", Color.CYAN))
                if monitorear_workflow(repo.path, run_id):
                    print(c(f"  [DEPLOY OK] {repo.nombre} desplegado exitosamente.", Color.GREEN))
                    resumen_final.append((repo.nombre, "DESPLEGADO", f"Tag {tag_servicio} - CI/CD exitoso"))
                else:
                    print(c(f"  [DEPLOY ERROR] El pipeline falló en GitHub Actions: {run_url}", Color.RED))
                    resumen_final.append((repo.nombre, "DEPLOY FALLIDO", f"Revisar: {run_url}"))
            else:
                detalle = "No se pudo capturar el workflow automáticamente. Revisalo en GitHub Actions."
                print(c(f"  [AVISO] {detalle}", Color.YELLOW))
                resumen_final.append((repo.nombre, "MERGEADO", f"Tag {tag_servicio} (revisar CI en GitHub)"))
        else:
            resumen_final.append((repo.nombre, "MERGEADO", f"Tag {tag_servicio} (CI/CD disparado en background)"))

    imprimir_resumen(resumen_final)
    return 0


COLORES_RESULTADO: Dict[str, str] = {
    "DESPLEGADO": Color.GREEN,
    "MERGEADO": Color.GREEN,
    "AL DÍA": Color.GREEN,
    "SIN CAMBIOS": Color.GREEN,
    "PR CREADO": Color.CYAN,
    "PR EXISTENTE": Color.CYAN,
    "PR ABIERTO": Color.CYAN,
    "SIMULADO": Color.CYAN,
    "MERGEADO SIN TAG": Color.YELLOW,
    "SIN RELEASE": Color.YELLOW,
    "OMITIDO": Color.YELLOW,
    "ABORTADO": Color.YELLOW,
    "PR PENDIENTE": Color.YELLOW,
}


def imprimir_resumen(resumen: List[Tuple[str, str, str]]) -> None:
    """Imprime la tabla final respetando el ancho de las columnas con colores ANSI."""
    print("\n" + "=" * 92)
    print(c("  RESUMEN FINAL DE LA OPERACIÓN", Color.BOLD))
    print("=" * 92)

    if not resumen:
        print(c("  (sin acciones)", Color.DIM))
        print("=" * 92 + "\n")
        return

    ancho_nombre = max(len(nombre) for nombre, _, _ in resumen) + 2
    ancho_nombre = max(ancho_nombre, len("Servicio") + 2)
    ancho_resultado = max(len(resultado) for _, resultado, _ in resumen) + 2
    ancho_resultado = max(ancho_resultado, len("Resultado") + 2)

    print(f"{'Servicio':<{ancho_nombre}}{'Resultado':<{ancho_resultado}}Detalle")
    print("-" * 92)
    for nombre, resultado, detalle in resumen:
        color = COLORES_RESULTADO.get(resultado, Color.RED)
        print(f"{nombre:<{ancho_nombre}}{c(f'{resultado:<{ancho_resultado}}', color)}{detalle}")
    print("=" * 92 + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
