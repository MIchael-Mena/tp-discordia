#!/usr/bin/env python3
"""Script para automatizar el release y deploy de los servicios de TP-Discordia.

Flujo de despliegue según AGENTS.md y la arquitectura del proyecto:
  1. Identifica los repositorios en orden de dependencia (excluyendo 'infra'):
       profile -> auth-service -> server -> text-channel -> voice-calls ->
       notifications -> gateway -> web-client -> backoffice
  2. Comprueba commits pendientes entre 'origin/main' y 'origin/develop'.
  3. Calcula la versión CalVer (YYYY.MM.DD, con sufijo .1, .2 si ya existe tag hoy).
  4. Crea un Pull Request de Release (develop -> main) con resumen de cambios.
  5. Espera checks / pide confirmación interactiva para mergear a 'main'.
  6. Al mergear, crea y empuja el tag anotado 'vYYYY.MM.DD'.
  7. El push a 'main' dispara el CI/CD en GitHub Actions (tests + build ECR + SSM / Expo).
  8. Opcionalmente monitorea el workflow de despliegue en vivo (--watch).

Uso:
  python .scripts/deploy.py [OPCIONES]

Opciones principales:
  --dry-run             Simula todo el proceso sin crear PRs, merges ni tags.
  --status              Muestra el estado de cada servicio (commits pendientes y último tag).
  --create-pr-only      Solo crea los PRs de release sin mergearlos ni tagear.
  --auto, -y, --yes     Modo no interactivo: mergea y tagea automáticamente sin confirmación.
  --watch, -w           Monitorea el workflow de GitHub Actions tras el merge hasta finalizar.
  --wait-checks         Espera que los checks del PR pasen antes de mergear.
  --calver, --version V Fuerza una versión CalVer específica (ej. 2026.10.30).
  --only A,B,C          Ejecuta solo para los servicios indicados.
  --skip A,B,C          Omite los servicios indicados.
  --no-tag              No crea ni empuja el tag de Git tras el merge.
  --config PATH         Ruta al archivo repos.json (default: .scripts/repos.json).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Orden de despliegue recomendado por dependencias entre servicios:
# Datos y modelos base -> Lógica de negocio / media -> Routing -> Clientes
ORDEN_DESPLIEGUE_DEFECTO: Tuple[str, ...] = (
    "profile",        # Esquema de usuarios, migraciones Alembic
    "auth-service",   # Cuentas, sesiones, JWT
    "server",         # Servidores, canales, roles, permisos
    "text-channel",   # Mensajería e historial
    "voice-calls",    # Sesiones de voz LiveKit
    "notifications",  # Notificaciones y contadores de no leídos
    "gateway",        # Routing y relays hacia los microservicios
    "web-client",     # Cliente de usuarios Expo (Web + Android)
    "backoffice",     # Cliente de administración staff Expo
)

REPOS_EXCLUIDOS: Tuple[str, ...] = ("infra",)


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
    """Aplica color ANSI si stdout es tty o Windows soporta ANSI."""
    return f"{estilo}{texto}{Color.RESET}"


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
    return ejecutar(["gh", *args], cwd=repo, capture=capture, check=check)


# ---------------------------------------------------------------------------
# Verificaciones del entorno
# ---------------------------------------------------------------------------

def verificar_prerrequisitos(solo_status: bool = False, dry_run: bool = False) -> None:
    """Verifica que Git y GitHub CLI (gh) estén disponibles."""
    # Git
    try:
        res = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if res.returncode != 0:
            sys.exit(c("ERROR: Git no está disponible en PATH.", Color.RED))
    except FileNotFoundError:
        sys.exit(c("ERROR: Git no está instalado o no se encuentra en PATH.", Color.RED))

    # GitHub CLI
    try:
        res = subprocess.run(["gh", "--version"], capture_output=True, text=True)
        if res.returncode != 0:
            if solo_status:
                print(c("Aviso: 'gh' no está disponible en PATH.", Color.YELLOW))
                return
            sys.exit(c("ERROR: GitHub CLI (gh) no está disponible en PATH.", Color.RED))
    except FileNotFoundError:
        if solo_status:
            print(c("Aviso: 'gh' no está instalado.", Color.YELLOW))
            return
        sys.exit(
            c("ERROR: GitHub CLI (gh) no está instalado. Instálalo desde https://cli.github.com/", Color.RED)
        )

    # Auth status de gh
    res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if res.returncode != 0:
        aviso = (
            "Aviso: GitHub CLI no está autenticado o el token expiró.\n"
            "  -> Para re-autenticar, ejecuta: gh auth refresh -h github.com (o gh auth login)"
        )
        if solo_status or dry_run:
            print(c(aviso, Color.YELLOW))
        else:
            sys.exit(c(f"ERROR: {aviso}", Color.RED))


# ---------------------------------------------------------------------------
# Carga de repositorios
# ---------------------------------------------------------------------------

@dataclass
class RepoInfo:
    nombre: str
    path: Path
    branch_dev: str = "develop"
    branch_main: str = "main"
    tags_remotos: List[str] = field(default_factory=list)
    commits_pendientes: List[Tuple[str, str]] = field(default_factory=list)


def cargar_repositorios(
    raiz: Path,
    config_path: Path,
    filtro_only: Optional[List[str]] = None,
    filtro_skip: Optional[List[str]] = None,
) -> List[RepoInfo]:
    """Lee repos.json y arma la lista ordenada de repositorios a procesar."""
    repos_config = []
    if config_path.is_file():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                repos_config = data.get("repos", [])
        except Exception as e:
            print(c(f"Aviso: no se pudo leer {config_path}: {e}. Usando lista por defecto.", Color.YELLOW))

    repos_dict: Dict[str, RepoInfo] = {}

    if repos_config:
        for item in repos_config:
            if not item.get("enabled", True):
                continue
            folder = item.get("folder", "").strip()
            if not folder or folder in REPOS_EXCLUIDOS:
                continue
            repo_path = raiz / folder if not Path(folder).is_absolute() else Path(folder)
            if repo_path.is_dir() and (repo_path / ".git").exists():
                repos_dict[folder] = RepoInfo(nombre=folder, path=repo_path)
    else:
        for folder in ORDEN_DESPLIEGUE_DEFECTO:
            if folder in REPOS_EXCLUIDOS:
                continue
            repo_path = raiz / folder
            if repo_path.is_dir() and (repo_path / ".git").exists():
                repos_dict[folder] = RepoInfo(nombre=folder, path=repo_path)

    # Ordenar según ORDEN_DESPLIEGUE_DEFECTO; extras van al final antes de los clientes
    ordenados: List[RepoInfo] = []
    # 1. Los conocidos en su orden
    for nom in ORDEN_DESPLIEGUE_DEFECTO:
        if nom in repos_dict:
            ordenados.append(repos_dict.pop(nom))
    # 2. Cualquier otro no contemplado
    for repo in repos_dict.values():
        ordenados.append(repo)

    # Filtrar por --only / --skip
    if filtro_only:
        only_set = {x.strip().lower() for x in filtro_only}
        ordenados = [r for r in ordenados if r.nombre.lower() in only_set]
    if filtro_skip:
        skip_set = {x.strip().lower() for x in filtro_skip}
        ordenados = [r for r in ordenados if r.nombre.lower() not in skip_set]

    return ordenados


# ---------------------------------------------------------------------------
# CalVer y Git helpers
# ---------------------------------------------------------------------------

def obtener_calver_base(fecha: Optional[datetime.date] = None) -> str:
    """Devuelve la fecha actual en formato CalVer: YYYY.MM.DD."""
    d = fecha or datetime.date.today()
    return f"{d.year}.{d.month:02d}.{d.day:02d}"


def resolver_siguiente_calver(tags_existentes: List[str], calver_base: str) -> str:
    """Calcula la versión CalVer final considerando posibles sufijos .1, .2...

    Si 'v2026.10.30' no existe -> devuelve '2026.10.30'.
    Si 'v2026.10.30' ya existe -> busca '2026.10.30.1', '2026.10.30.2', etc.
    """
    tag_exacto = f"v{calver_base}"
    tags_set = set(tags_existentes)
    if tag_exacto not in tags_set:
        return calver_base

    micro = 1
    while f"v{calver_base}.{micro}" in tags_set:
        micro += 1
    return f"{calver_base}.{micro}"


def obtener_tags(repo: Path) -> List[str]:
    """Obtiene la lista de tags locales y remotos."""
    res = git(repo, "tag", "-l")
    tags = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    return tags


def fetch_remoto(repo: Path) -> Tuple[bool, str]:
    """Ejecuta git fetch origin --prune."""
    res = git(repo, "fetch", "origin", "--prune")
    if res.returncode != 0:
        return False, res.stderr.strip()
    return True, ""


def obtener_commits_pendientes(repo: Path, main_branch: str, dev_branch: str) -> List[Tuple[str, str]]:
    """Devuelve [(sha_corto, subject), ...] de commits en origin/develop no en origin/main."""
    rango = f"origin/{main_branch}..origin/{dev_branch}"
    res = git(repo, "log", rango, "--oneline")
    if res.returncode != 0:
        return []
    commits = []
    for linea in res.stdout.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        partes = linea.split(" ", 1)
        sha = partes[0]
        msg = partes[1] if len(partes) > 1 else ""
        commits.append((sha, msg))
    return commits


def estado_working_tree_limpio(repo: Path) -> bool:
    """Verifica si el working tree no tiene cambios pendientes locales."""
    res = git(repo, "status", "--porcelain")
    return not bool(res.stdout.strip())


# ---------------------------------------------------------------------------
# GitHub PR y Workflow helpers
# ---------------------------------------------------------------------------

def buscar_pr_release_existente(repo: Path, dev_branch: str, main_branch: str) -> Optional[Dict[str, str]]:
    """Busca si ya existe un PR abierto con head=develop y base=main."""
    res = gh(
        repo,
        "pr",
        "list",
        "--head",
        dev_branch,
        "--base",
        main_branch,
        "--state",
        "open",
        "--json",
        "number,title,url,mergeable",
    )
    if res.returncode == 0 and res.stdout.strip():
        try:
            prs = json.loads(res.stdout)
            if prs:
                return prs[0]
        except Exception:
            pass
    return None


def armar_cuerpo_pr(nombre_repo: str, calver: str, commits: List[Tuple[str, str]]) -> str:
    """Construye la descripción en Markdown del PR de Release siguiendo el estándar del equipo."""
    prs_incluidos = []
    otros_commits = []

    for sha, msg in commits:
        match = re.match(r"Merge pull request #(\d+) from (.+)", msg)
        if match:
            pr_num, rama = match.groups()
            prs_incluidos.append(f"- #{pr_num} (`{rama}`)")
        else:
            otros_commits.append(f"- `{sha}` {msg}")

    cuerpo = [
        f"Release `develop → main` de `{nombre_repo}` (CalVer {calver}).",
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
    cuerpo.append(f"**Deploy:** merge a `main` dispara el pipeline CI/CD (tests + build ECR + deploy SSM / Expo).")
    cuerpo.append(f"Tag asociado: `v{calver}`.")

    return "\n".join(cuerpo)


def crear_pr_release(
    repo: Path,
    nombre_repo: str,
    dev_branch: str,
    main_branch: str,
    calver: str,
    commits: List[Tuple[str, str]],
) -> Tuple[bool, str, str]:
    """Crea el PR en GitHub. Devuelve (éxito, número/url, mensaje_error)."""
    titulo = f"Release/{calver}"
    cuerpo = armar_cuerpo_pr(nombre_repo, calver, commits)

    res = gh(
        repo,
        "pr",
        "create",
        "--base",
        main_branch,
        "--head",
        dev_branch,
        "--title",
        titulo,
        "--body",
        cuerpo,
    )
    if res.returncode == 0:
        url = res.stdout.strip()
        # Extrae número del URL
        m = re.search(r"/pull/(\d+)", url)
        num = m.group(1) if m else url
        return True, num, url
    return False, "", res.stderr.strip()


def esperar_checks_pr(repo: Path, pr_num: str) -> bool:
    """Espera a que los status checks requeridos del PR finalicen exitosamente."""
    print(c(f"  Esperando checks CI para el PR #{pr_num}...", Color.CYAN))
    res = gh(repo, "pr", "checks", pr_num, "--watch", capture=False)
    return res.returncode == 0


def mergear_pr(repo: Path, pr_num: str, calver: str) -> Tuple[bool, str]:
    """Mergea el PR usando 'gh pr merge --merge' (merge commit estándar, nunca borra rama)."""
    subject = f"Release/{calver}"
    res = gh(
        repo,
        "pr",
        "merge",
        pr_num,
        "--merge",
        "--subject",
        subject,
    )
    if res.returncode == 0:
        return True, ""
    return False, res.stderr.strip()


def crear_y_empujar_tag(repo: Path, calver: str) -> Tuple[bool, str]:
    """Crea un tag anotado v<calver> en el HEAD de origin/main y lo empuja al remoto."""
    tag_name = f"v{calver}"
    # Actualizar ref local de main
    git(repo, "fetch", "origin", "main")

    res_sha = git(repo, "rev-parse", "origin/main")
    if res_sha.returncode != 0:
        return False, f"No se pudo resolver SHA de origin/main: {res_sha.stderr.strip()}"
    commit_sha = res_sha.stdout.strip()

    # Crear tag anotado
    msg = f"Release {calver}"
    res_tag = git(repo, "tag", "-a", tag_name, commit_sha, "-m", msg)
    if res_tag.returncode != 0:
        # Si el tag ya existe localmente, reintentar forzándolo si apunta al mismo commit
        if "already exists" in res_tag.stderr:
            pass
        else:
            return False, f"Fallo al crear tag {tag_name}: {res_tag.stderr.strip()}"

    # Empujar tag a origin
    res_push = git(repo, "push", "origin", tag_name)
    if res_push.returncode != 0:
        return False, f"Fallo al empujar tag {tag_name}: {res_push.stderr.strip()}"

    return True, ""


def buscar_run_despliegue(repo: Path, segundos_espera: int = 25) -> Optional[Dict[str, str]]:
    """Busca el workflow run en 'main' disparado recientemente por el merge."""
    import time
    for _ in range(segundos_espera // 3):
        res = gh(
            repo,
            "run",
            "list",
            "--branch",
            "main",
            "--limit",
            "1",
            "--json",
            "databaseId,name,status,conclusion,url",
        )
        if res.returncode == 0 and res.stdout.strip():
            try:
                runs = json.loads(res.stdout)
                if runs:
                    return runs[0]
            except Exception:
                pass
        time.sleep(3)
    return None


def monitorear_workflow(repo: Path, run_id: str) -> bool:
    """Ejecuta gh run watch para monitorear el progreso del workflow en vivo."""
    print(c(f"  Monitoreando workflow de deploy (Run ID: {run_id})...", Color.CYAN))
    res = gh(repo, "run", "watch", str(run_id), "--exit-status", capture=False)
    return res.returncode == 0


# ---------------------------------------------------------------------------
# Modo Status / Check
# ---------------------------------------------------------------------------

def mostrar_estado_repositorios(repos: List[RepoInfo], calver_base: str, do_fetch: bool = True) -> None:
    """Imprime un resumen de estado de todos los repositorios."""
    print("\n" + "=" * 78)
    print(c(f"  ESTADO DE SERVICIOS - TP-DISCORDIA (CalVer sugerido: {calver_base})", Color.BOLD))
    print("=" * 78)

    print(f"{'Servicio':<16} {'Pendientes':<14} {'Último Tag':<16} {'Estado'}")
    print("-" * 78)

    hay_pendientes = 0
    for repo in repos:
        if do_fetch:
            fetch_remoto(repo.path)
        commits = obtener_commits_pendientes(repo.path, repo.branch_main, repo.branch_dev)
        tags = obtener_tags(repo.path)
        ultimo_tag = tags[-1] if tags else "-"

        if commits:
            hay_pendientes += 1
            cant_str = f"{len(commits)} commits"
            calver_previsto = resolver_siguiente_calver(tags, calver_base)
            estado_str = c(f"Listo para Release (v{calver_previsto})", Color.YELLOW)
        else:
            cant_str = "0 commits"
            estado_str = c("Al día con main", Color.GREEN)

        print(f"{repo.nombre:<16} {cant_str:<14} {ultimo_tag:<16} {estado_str}")

    print("-" * 78)
    if hay_pendientes:
        print(c(f"Total: {hay_pendientes} servicio(s) con cambios pendientes para release.", Color.YELLOW))
    else:
        print(c("Todos los servicios están al día con main. No hay releases pendientes.", Color.GREEN))
    print("=" * 78 + "\n")


# ---------------------------------------------------------------------------
# Flujo principal de Deploy
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatiza el release y deploy de los servicios de TP-Discordia.",
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
        help="Coma-separada de servicios a procesar exclusivamente (ej. 'profile,gateway').",
    )
    parser.add_argument(
        "--skip",
        help="Coma-separada de servicios a omitir (ej. 'web-client,backoffice').",
    )
    parser.add_argument(
        "--no-tag",
        action="store_true",
        help="Omite la creación y push del tag de Git tras el merge.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Omite ejecutar git fetch origin en cada repositorio (usa estado local actual).",
    )
    parser.add_argument(
        "--config",
        default=".scripts/repos.json",
        help="Ruta al archivo repos.json (default: .scripts/repos.json).",
    )
    return parser.parse_args()


def main() -> None:
    configurar_salida()
    args = parse_args()

    verificar_prerrequisitos(solo_status=args.status, dry_run=args.dry_run)

    raiz = Path(__file__).resolve().parent.parent
    config_path = Path(args.config) if Path(args.config).is_absolute() else raiz / args.config

    filtro_only = [x.strip() for x in args.only.split(",")] if args.only else None
    filtro_skip = [x.strip() for x in args.skip.split(",")] if args.skip else None

    repos = cargar_repositorios(raiz, config_path, filtro_only, filtro_skip)

    if not repos:
        print(c("No se encontraron repositorios válidos para procesar.", Color.RED))
        sys.exit(1)

    calver_base = args.calver_override or obtener_calver_base()

    # Si se pide solo status:
    if args.status:
        mostrar_estado_repositorios(repos, calver_base, do_fetch=not args.no_fetch)
        return

    print("\n" + "=" * 78)
    modo_str = " [DRY-RUN - SIMULACIÓN]" if args.dry_run else ""
    print(c(f"  DEPLOY AUTOMATIZADO DE SERVICIOS - TP-DISCORDIA{modo_str}", Color.BOLD))
    print(f"  Versión CalVer Base: {calver_base}")
    print(f"  Repositorios ({len(repos)}): {', '.join(r.nombre for r in repos)}")
    print(f"  Modo: {'Automático (--auto)' if args.auto else 'Interactivo con confirmación'}")
    if args.create_pr_only:
        print("  Acción: Solo creación de PRs (--create-pr-only)")
    if args.watch:
        print("  Monitoreo: Activado (--watch)")
    print("=" * 78 + "\n")

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

        # 2. Verificar commits pendientes
        commits = obtener_commits_pendientes(repo.path, repo.branch_main, repo.branch_dev)
        if not commits:
            print(c(f"  [OK] Sin commits pendientes entre origin/{repo.branch_dev} y origin/{repo.branch_main}.", Color.GREEN))
            resumen_final.append((repo.nombre, "AL DÍA", "Sin cambios pendientes"))
            continue

        # 3. Resolver CalVer específico para este repo
        tags = obtener_tags(repo.path)
        calver_servicio = resolver_siguiente_calver(tags, calver_base)
        tag_servicio = f"v{calver_servicio}"

        print(c(f"  -> {len(commits)} commit(s) pendientes para release.", Color.YELLOW))
        print(f"  -> Versión CalVer asignada: {c(calver_servicio, Color.CYAN)} (tag: {tag_servicio})")
        print(f"  -> Primeros commits:")
        for sha, msg in commits[:4]:
            print(f"     - `{sha}` {msg}")
        if len(commits) > 4:
            print(f"     ... y {len(commits) - 4} commits más.")

        # 4. Comprobar o crear PR
        pr_existente = buscar_pr_release_existente(repo.path, repo.branch_dev, repo.branch_main)
        pr_num = ""
        pr_url = ""

        if pr_existente:
            pr_num = str(pr_existente.get("number", ""))
            pr_url = pr_existente.get("url", "")
            print(c(f"  [PR] Ya existe un PR de release abierto: #{pr_num} ({pr_url})", Color.CYAN))
        else:
            if args.dry_run:
                print(c(f"  [DRY-RUN] Se crearía PR: 'Release/{calver_servicio}' (develop -> main)", Color.YELLOW))
                pr_num = "SIMULADO"
                pr_url = f"https://github.com/fiuba-IS2-Discordia/{repo.nombre}/pull/SIMULADO"
            else:
                ok_pr, num_o_err, url_pr = crear_pr_release(
                    repo.path,
                    repo.nombre,
                    repo.branch_dev,
                    repo.branch_main,
                    calver_servicio,
                    commits,
                )
                if not ok_pr:
                    print(c(f"  [ERROR] Falló la creación del PR: {url_pr}", Color.RED))
                    resumen_final.append((repo.nombre, "ERROR", f"Fallo al crear PR: {url_pr}"))
                    continue
                pr_num = num_o_err
                pr_url = url_pr
                print(c(f"  [PR CREADO] PR #{pr_num}: {pr_url}", Color.GREEN))

        # Si el usuario solo pidió crear PRs:
        if args.create_pr_only:
            resumen_final.append((repo.nombre, "PR CREADO", f"PR #{pr_num} ({pr_url})"))
            continue

        if args.dry_run:
            print(c(f"  [DRY-RUN] Se mergearía PR #{pr_num} a 'main' con commit 'Release/{calver_servicio}'", Color.YELLOW))
            if not args.no_tag:
                print(c(f"  [DRY-RUN] Se crearía y empujaría el tag anotado '{tag_servicio}'", Color.YELLOW))
            if args.watch:
                print(c("  [DRY-RUN] Se monitorearía el workflow de deploy en GitHub Actions", Color.YELLOW))
            resumen_final.append((repo.nombre, "SIMULADO", f"Release {tag_servicio}"))
            continue

        # 5. Esperar checks si se solicitó
        if args.wait_checks:
            ok_checks = esperar_checks_pr(repo.path, pr_num)
            if not ok_checks:
                print(c(f"  [AVISO] Los checks del PR #{pr_num} no finalizaron con éxito.", Color.YELLOW))
                if not args.auto:
                    resp = input(c("  ¿Deseas continuar con el merge de todos modos? [s/N]: ", Color.BOLD)).strip().lower()
                    if resp not in ("s", "si", "y", "yes"):
                        print(c("  Omitiendo merge para este servicio.", Color.YELLOW))
                        resumen_final.append((repo.nombre, "PR PENDIENTE", f"PR #{pr_num} con checks fallidos"))
                        continue

        # 6. Confirmación de Merge (si no es modo --auto)
        debe_mergear = args.auto
        debe_watch = args.watch

        if not args.auto:
            pregunta = (
                f"\n  ¿Mergear PR #{pr_num} de {c(repo.nombre, Color.BOLD)} a main y crear tag {c(tag_servicio, Color.CYAN)}?\n"
                f"  [S] Sí | [w] Sí y monitorear CI/CD | [n] No | [s] Saltar | [a] Abortar: "
            )
            resp = input(c(pregunta, Color.WHITE)).strip().lower()

            if resp in ("a", "abort", "abortar"):
                print(c("\nOperación abortada por el usuario.", Color.RED))
                resumen_final.append((repo.nombre, "ABORTADO", "Cancelado por el usuario"))
                break
            elif resp in ("s", "saltar", "skip", "n", "no"):
                print(c("  Servicio omitido.", Color.YELLOW))
                resumen_final.append((repo.nombre, "PR ABIERTO", f"PR #{pr_num} listo para merge"))
                continue
            elif resp == "w":
                debe_mergear = True
                debe_watch = True
            elif resp in ("", "s", "si", "y", "yes"):
                debe_mergear = True

        if not debe_mergear:
            resumen_final.append((repo.nombre, "PR ABIERTO", f"PR #{pr_num} ({pr_url})"))
            continue

        # 7. Merge del PR
        print(c(f"  [MERGE] Mergeando PR #{pr_num} a main...", Color.CYAN))
        ok_merge, err_merge = mergear_pr(repo.path, pr_num, calver_servicio)
        if not ok_merge:
            print(c(f"  [ERROR] Falló el merge del PR #{pr_num}: {err_merge}", Color.RED))
            resumen_final.append((repo.nombre, "ERROR", f"Fallo al mergear PR: {err_merge}"))
            continue
        print(c(f"  [MERGE OK] PR #{pr_num} mergeado exitosamente a 'main'.", Color.GREEN))

        # 8. Tag y Push
        if not args.no_tag:
            print(c(f"  [TAG] Creando y empujando tag {tag_servicio}...", Color.CYAN))
            ok_tag, err_tag = crear_y_empujar_tag(repo.path, calver_servicio)
            if not ok_tag:
                print(c(f"  [AVISO] {err_tag}", Color.YELLOW))
            else:
                print(c(f"  [TAG OK] Tag {tag_servicio} publicado en origin.", Color.GREEN))

        # 9. Monitoreo opcional de GitHub Actions
        if debe_watch:
            print(c("  Esperando a que GitHub Actions registre el workflow de deploy...", Color.CYAN))
            run_info = buscar_run_despliegue(repo.path)
            if run_info and "databaseId" in run_info:
                run_id = str(run_info["databaseId"])
                run_url = run_info.get("url", "")
                print(c(f"  Workflow: {run_info.get('name', 'Deploy')} | {run_url}", Color.CYAN))
                ok_deploy = monitorear_workflow(repo.path, run_id)
                if ok_deploy:
                    print(c(f"  [DEPLOY OK] {repo.nombre} desplegado exitosamente.", Color.GREEN))
                    resumen_final.append((repo.nombre, "DESPLEGADO", f"Tag {tag_servicio} - CI/CD exitoso"))
                else:
                    print(c(f"  [DEPLOY ERROR] El pipeline falló en GitHub Actions: {run_url}", Color.RED))
                    resumen_final.append((repo.nombre, "DEPLOY FALLIDO", f"Revisar: {run_url}"))
            else:
                print(c("  No se pudo capturar el workflow automáticamente. Puedes revisarlo en GitHub Actions.", Color.YELLOW))
                resumen_final.append((repo.nombre, "MERGEADO", f"Tag {tag_servicio} (revisar CI en GitHub)"))
        else:
            resumen_final.append((repo.nombre, "MERGEADO", f"Tag {tag_servicio} (CI/CD disparado en background)"))

    # -----------------------------------------------------------------------
    # Resumen final
    # -----------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(c("  RESUMEN FINAL DE LA OPERACIÓN", Color.BOLD))
    print("=" * 78)
    print(f"{'Servicio':<16} {'Resultado':<16} {'Detalle'}")
    print("-" * 78)
    for nombre, resultado, detalle in resumen_final:
        if resultado in ("DESPLEGADO", "MERGEADO", "AL DÍA"):
            color_res = Color.GREEN
        elif resultado in ("PR CREADO", "PR ABIERTO", "SIMULADO"):
            color_res = Color.CYAN
        elif resultado in ("ABORTADO",):
            color_res = Color.YELLOW
        else:
            color_res = Color.RED
        print(f"{nombre:<16} {c(resultado, color_res):<25} {detalle}")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
