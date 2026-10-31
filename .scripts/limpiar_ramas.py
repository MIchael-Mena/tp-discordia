#!/usr/bin/env python3
"""Limpia ramas locales ya mergeadas en los repos del workspace TP-Discordia.

Lee la lista de repos de repos.json (editable a mano) y, por cada repo:
  1. actualiza las refs del remoto (fetch --prune);
  2. deja el repo parado en su rama objetivo (develop o la configurada) actualizada;
  3. borra las ramas locales ya mergeadas (verificadas por ancestría);
  4. lista para revisión las ramas dudosas:
     - remota borrada y merge no detectable (típico squash-merge);
     - ramas solo locales sin mergear.

Uso:
  python limpiar_ramas.py [--dry-run] [--yes] [--force-gone] [--only a,b]
                          [--config PATH] [--root PATH]

Seguridad:
  - Nunca usa checkout -f, stash, reset ni clean.
  - Una rama solo se borra si está contenida en la rama objetivo o en origin/main.
  - Si el checkout a la rama objetivo falla, el repo se omite completo (no se
    borra ninguna rama de ese repo).

Config (repos.json):
  {
    "repos": [
      { "folder": "auth-service" },
      { "folder": "infra", "branch": "main" },
      { "folder": "text-channel", "enabled": false }
    ]
  }
  Campos por entrada:
    folder  (obligatorio) ruta relativa a la raíz (o absoluta);
    branch  (opcional)    override de la rama objetivo; si falta se autodetecta
                          (develop si existe; si no, main);
    enabled (opcional)    false = se ignora sin aviso (útil para repos no clonados);
    keep    (opcional)    nombres de ramas extra que nunca se borran.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROTEGIDAS = ("main", "develop")        # nunca se borran
CANDIDATAS_AUTO = ("develop", "main")   # orden de autodetección de la rama objetivo


def configurar_salida() -> None:
    """Fuerza UTF-8 en la salida para consolas Windows."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Ejecuta `git -C <repo> <args>` sin shell."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def ultima_linea(texto: str) -> str:
    lineas = [linea.strip() for linea in (texto or "").splitlines() if linea.strip()]
    return lineas[-1] if lineas else ""


def mensaje_relevante(texto: str) -> str:
    """Primera línea de error/fatal si existe; si no, la última línea con contenido."""
    lineas = [linea.strip() for linea in (texto or "").splitlines() if linea.strip()]
    for linea in lineas:
        if linea.startswith("error:") or linea.startswith("fatal:"):
            return linea
    return lineas[-1] if lineas else ""


def frase_commits(cantidad: int) -> str:
    plural = "s" if cantidad != 1 else ""
    return f"{cantidad} commit{plural} fuera de la base"


def existe_ref(repo: Path, ref: str) -> bool:
    return git(repo, "rev-parse", "--verify", "--quiet", ref).returncode == 0


def es_ancestro(repo: Path, rama: str, ref: str) -> bool:
    return git(repo, "merge-base", "--is-ancestor", rama, ref).returncode == 0


def info_ramas(repo: Path) -> Dict[str, Dict[str, object]]:
    """Devuelve, por rama local, si tiene upstream y si la remota está [gone]."""
    cp = git(
        repo,
        "for-each-ref",
        "--format=%(refname:short)%09%(upstream:short)%09%(upstream:track)",
        "refs/heads",
    )
    ramas: Dict[str, Dict[str, object]] = {}
    for linea in cp.stdout.splitlines():
        if not linea.strip():
            continue
        partes = linea.split("\t")
        nombre = partes[0].strip()
        upstream = partes[1].strip() if len(partes) > 1 else ""
        track = partes[2].strip() if len(partes) > 2 else ""
        ramas[nombre] = {"upstream": upstream, "gone": bool(upstream) and "[gone]" in track}
    return ramas


def detalle_commits(repo: Path, rama: str, base: str) -> Tuple[int, str]:
    """Cantidad de commits únicos de <rama> respecto de <base> y subject del último."""
    cp = git(repo, "rev-list", "--count", f"{base}..{rama}")
    try:
        cantidad = int(cp.stdout.strip() or "0")
    except ValueError:
        cantidad = 0
    cp = git(repo, "log", "-1", "--format=%s", rama)
    return cantidad, cp.stdout.strip()


def refs_base(repo: Path, objetivo: str) -> List[str]:
    """Refs contra las que se verifica si una rama está mergeada."""
    refs: List[str] = []
    for ref in (
        f"refs/remotes/origin/{objetivo}",
        "refs/remotes/origin/main",
        f"refs/heads/{objetivo}",
        "refs/heads/main",
    ):
        if ref not in refs and existe_ref(repo, ref):
            refs.append(ref)
    return refs


@dataclass
class RepoConfig:
    folder: str
    branch: Optional[str] = None
    enabled: bool = True
    keep: List[str] = field(default_factory=list)


@dataclass
class PlanRepo:
    cfg: RepoConfig
    repo: Path
    objetivo: str = ""
    borrar: List[Tuple[str, str]] = field(default_factory=list)
    revisar: List[Tuple[str, str, bool]] = field(default_factory=list)
    activas: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    omitido: Optional[str] = None


@dataclass
class ResultadoRepo:
    folder: str
    objetivo: str = ""
    actualizada: bool = False
    borradas: List[str] = field(default_factory=list)
    revisar: List[Tuple[str, str]] = field(default_factory=list)
    activas: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    omitido: Optional[str] = None


def resolver_objetivo(repo: Path, cfg: RepoConfig) -> Tuple[Optional[str], Optional[str]]:
    if cfg.branch:
        existe = existe_ref(repo, f"refs/heads/{cfg.branch}") or existe_ref(
            repo, f"refs/remotes/origin/{cfg.branch}"
        )
        if existe:
            return cfg.branch, None
        return None, f"la rama configurada '{cfg.branch}' no existe (ni local ni en origin)"
    for candidata in CANDIDATAS_AUTO:
        existe = existe_ref(repo, f"refs/remotes/origin/{candidata}") or existe_ref(
            repo, f"refs/heads/{candidata}"
        )
        if existe:
            return candidata, None
    return None, "no existe develop ni main (ni local ni en origin)"


def planificar(cfg: RepoConfig, root: Path) -> PlanRepo:
    repo = Path(cfg.folder)
    if not repo.is_absolute():
        repo = root / cfg.folder
    plan = PlanRepo(cfg=cfg, repo=repo)

    if not repo.exists():
        plan.omitido = "la carpeta no existe (¿repo todavía no clonado?)"
        return plan
    if git(repo, "rev-parse", "--git-dir").returncode != 0:
        plan.omitido = "la carpeta no es un repositorio git"
        return plan

    cp = git(repo, "fetch", "--prune", "origin")
    if cp.returncode != 0:
        plan.avisos.append("fetch --prune falló (¿sin red?); se sigue con las refs locales")

    objetivo, error = resolver_objetivo(repo, cfg)
    if not objetivo:
        plan.omitido = error or "no se pudo determinar la rama objetivo"
        return plan
    plan.objetivo = objetivo

    ramas = info_ramas(repo)
    protegidas = set(PROTEGIDAS) | {objetivo} | set(cfg.keep)
    refs = refs_base(repo, objetivo)
    base_commits = refs[0] if refs else f"refs/heads/{objetivo}"

    for rama in sorted(ramas):
        info = ramas[rama]
        if rama in protegidas:
            continue
        if any(es_ancestro(repo, rama, ref) for ref in refs):
            plan.borrar.append((rama, "mergeada"))
        elif info["gone"]:
            cantidad, ultimo = detalle_commits(repo, rama, base_commits)
            plan.revisar.append(
                (
                    rama,
                    f"remota borrada sin merge confirmado: {frase_commits(cantidad)}; último: \"{ultimo}\"",
                    True,
                )
            )
        elif not info["upstream"]:
            cantidad, ultimo = detalle_commits(repo, rama, base_commits)
            plan.revisar.append(
                (rama, f"rama solo local sin mergear: {frase_commits(cantidad)}; último: \"{ultimo}\"", False)
            )
        else:
            plan.activas.append(rama)
    return plan


def imprimir_plan(planes: List[PlanRepo]) -> None:
    for plan in planes:
        print()
        print(f"===== {plan.cfg.folder} =====")
        if plan.omitido:
            print(f"  [skip] {plan.omitido}")
        else:
            origen_rama = "forzada por config" if plan.cfg.branch else "autodetectada"
            print(f"  rama objetivo: {plan.objetivo} ({origen_rama})")
            if not (plan.borrar or plan.revisar or plan.activas):
                print("  todo limpio: no hay ramas locales fuera de la base")
            if plan.borrar:
                print(f"  se borrarán ({len(plan.borrar)}):")
                for rama, motivo in plan.borrar:
                    print(f"    - {rama}  [{motivo}]")
            if plan.revisar:
                print(f"  para revisar, no se tocan ({len(plan.revisar)}):")
                for rama, motivo, _es_gone in plan.revisar:
                    print(f"    - {rama}  [{motivo}]")
            if plan.activas:
                print(f"  activas, se mantienen ({len(plan.activas)}): {', '.join(plan.activas)}")
        for aviso in plan.avisos:
            print(f"  [warn] {aviso}")


def aplicar(plan: PlanRepo, force_gone: bool) -> ResultadoRepo:
    repo = plan.repo
    resultado = ResultadoRepo(
        folder=plan.cfg.folder,
        objetivo=plan.objetivo,
        activas=list(plan.activas),
        avisos=list(plan.avisos),
    )
    print()
    print(f"===== {plan.cfg.folder} =====")

    cp = git(repo, "checkout", plan.objetivo)
    if cp.returncode != 0:
        resultado.omitido = "checkout falló (¿working tree con cambios en conflicto?)"
        detalle = mensaje_relevante(cp.stderr) or mensaje_relevante(cp.stdout)
        if detalle:
            resultado.avisos.append(detalle)
        print(f"  [skip] {resultado.omitido}")
        return resultado
    print(f"  [ok] parado en {plan.objetivo}")

    ref_remota = f"refs/remotes/origin/{plan.objetivo}"
    if not existe_ref(repo, ref_remota):
        resultado.avisos.append(f"no existe la ref {ref_remota}; no hay nada para actualizar")
        resultado.actualizada = True
    else:
        cp = git(
            repo,
            "rev-list",
            "--left-right",
            "--count",
            f"refs/heads/{plan.objetivo}...{ref_remota}",
        )
        partes = cp.stdout.split()
        adelante, atras = 0, 0
        if len(partes) >= 2:
            try:
                adelante, atras = int(partes[0]), int(partes[1])
            except ValueError:
                adelante, atras = 0, 0
        if atras == 0:
            resultado.actualizada = True
            if adelante:
                plural = "s" if adelante != 1 else ""
                resultado.avisos.append(
                    f"nota: hay {adelante} commit{plural} locales sin pushear (no se toca nada)"
                )
        elif adelante == 0:
            cp = git(repo, "pull", "--ff-only")
            if cp.returncode == 0:
                resultado.actualizada = True
            else:
                resultado.avisos.append(
                    f"pull --ff-only falló: {mensaje_relevante(cp.stderr) or mensaje_relevante(cp.stdout)}"
                )
        else:
            resultado.avisos.append(
                f"{plan.objetivo} divergió de origin/{plan.objetivo} "
                f"({adelante} locales, {atras} remotos): no se actualizó automáticamente"
            )

    refs = refs_base(repo, plan.objetivo)
    for rama, motivo in plan.borrar:
        if not any(es_ancestro(repo, rama, ref) for ref in refs):
            resultado.revisar.append(
                (rama, "cambió el estado entre el plan y la aplicación; no se borró")
            )
            continue
        cp = git(repo, "branch", "-d", rama)
        if cp.returncode != 0:
            cp = git(repo, "branch", "-D", rama)
        if cp.returncode == 0:
            resultado.borradas.append(rama)
            print(f"  [ok] borrada {rama} [{motivo}]")
        else:
            resultado.avisos.append(f"no se pudo borrar '{rama}': {ultima_linea(cp.stderr)}")

    ref_base_commits = refs[0] if refs else f"refs/heads/{plan.objetivo}"
    for rama, motivo, es_gone in plan.revisar:
        if force_gone and es_gone:
            cantidad, ultimo = detalle_commits(repo, rama, ref_base_commits)
            cp = git(repo, "branch", "-D", rama)
            if cp.returncode == 0:
                resultado.borradas.append(rama)
                print(
                    f"  [ok] [force-gone] borrada {rama}: {frase_commits(cantidad)}; "
                    f"último: \"{ultimo}\""
                )
            else:
                resultado.avisos.append(
                    f"force-gone: no se pudo borrar '{rama}': {ultima_linea(cp.stderr)}"
                )
        else:
            resultado.revisar.append((rama, motivo))

    actual = git(repo, "branch", "--show-current").stdout.strip()
    if actual and actual != plan.objetivo:
        resultado.avisos.append(
            f"atención: el repo quedó en '{actual}' y no en '{plan.objetivo}'"
        )
    return resultado


def parsear_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Limpia ramas locales ya mergeadas en los repos de TP-Discordia."
    )
    parser.add_argument("--dry-run", action="store_true", help="muestra el plan sin modificar nada local")
    parser.add_argument("--yes", action="store_true", help="no pedir confirmación")
    parser.add_argument(
        "--force-gone",
        action="store_true",
        help="borra también las ramas con remota borrada y merge no detectable (squash)",
    )
    parser.add_argument("--only", default="", help="procesar solo estas carpetas (separadas por coma)")
    parser.add_argument("--config", default="", help="ruta a repos.json (default: <root>/repos.json)")
    parser.add_argument("--root", default="", help="raíz del workspace (default: carpeta del script)")
    return parser.parse_args(argv)


def cargar_config(config_path: Path) -> List[RepoConfig]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("repos"), list):
        raise ValueError("el JSON debe tener la forma { \"repos\": [ { \"folder\": ... }, ... ] }")
    entradas: List[RepoConfig] = []
    problemas: List[str] = []
    for indice, item in enumerate(data["repos"], start=1):
        if not isinstance(item, dict) or not item.get("folder"):
            problemas.append(f"entrada #{indice}: falta el campo obligatorio 'folder'")
            continue
        keep = item.get("keep", [])
        if not isinstance(keep, list):
            problemas.append(f"entrada #{indice} ({item.get('folder')}): 'keep' debe ser una lista")
            continue
        entradas.append(
            RepoConfig(
                folder=str(item["folder"]),
                branch=str(item["branch"]) if item.get("branch") else None,
                enabled=bool(item.get("enabled", True)),
                keep=[str(x) for x in keep],
            )
        )
    if problemas:
        raise ValueError("; ".join(problemas))
    return entradas


def imprimir_resumen(resultados: List[ResultadoRepo]) -> None:
    print()
    print("RESUMEN")
    total_borradas = 0
    total_revisar = 0
    omitidos = 0
    for res in resultados:
        if res.omitido:
            omitidos += 1
            print(f"  {res.folder}: [skip] {res.omitido}")
            for aviso in res.avisos:
                print(f"      [warn] {aviso}")
            continue
        total_borradas += len(res.borradas)
        total_revisar += len(res.revisar)
        estado = f"parado en {res.objetivo}"
        if not res.actualizada:
            estado += " (no actualizada; ver aviso)"
        partes = [estado]
        if res.borradas:
            partes.append(f"borradas: {len(res.borradas)} -> {', '.join(res.borradas)}")
        if res.revisar:
            partes.append(f"para revisar: {', '.join(rama for rama, _ in res.revisar)}")
        if res.activas:
            partes.append(f"activas: {len(res.activas)}")
        print(f"  {res.folder}: " + " | ".join(partes))
        for aviso in res.avisos:
            print(f"      [warn] {aviso}")
    print()
    print(
        f"Total: {len(resultados)} repos | {total_borradas} ramas borradas | "
        f"{total_revisar} para revisar | {omitidos} omitidos"
    )


def main(argv=None) -> int:
    configurar_salida()
    args = parsear_args(argv)

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent
    if not root.exists():
        print(f"[error] la raíz indicada no existe: {root}")
        return 1
    config_path = Path(args.config) if args.config else root / "repos.json"
    if not config_path.exists():
        print(f"[error] no se encontró la configuración: {config_path}")
        print("        creá repos.json junto al script (o pasá --config PATH).")
        return 1
    try:
        entradas = cargar_config(config_path)
    except Exception as exc:
        print(f"[error] repos.json inválido: {exc}")
        return 1

    if args.only:
        queridas = {s.strip().rstrip("/\\") for s in args.only.split(",") if s.strip()}
        por_nombre = {entrada.folder: entrada for entrada in entradas}
        for nombre in sorted(queridas):
            if nombre not in por_nombre:
                print(f"[warn] --only: '{nombre}' no está en repos.json")
            elif not por_nombre[nombre].enabled:
                print(f"[warn] --only: '{nombre}' está deshabilitado en repos.json")
        entradas = [entrada for entrada in entradas if entrada.folder in queridas]

    activas_cfg = [entrada for entrada in entradas if entrada.enabled]
    if not activas_cfg:
        print("No hay repos habilitados para procesar (revisá repos.json o --only).")
        return 0

    print("PLAN DE LIMPIEZA" + (" (dry-run)" if args.dry_run else ""))
    planes = [planificar(entrada, root) for entrada in activas_cfg]
    imprimir_plan(planes)

    total_borrar = sum(len(plan.borrar) for plan in planes if not plan.omitido)
    total_revisar = sum(len(plan.revisar) for plan in planes if not plan.omitido)
    total_omitidos = sum(1 for plan in planes if plan.omitido)
    print()
    print(
        f"Plan: {len(planes)} repos | {total_borrar} ramas a borrar | "
        f"{total_revisar} para revisar | {total_omitidos} omitidos"
    )

    if args.dry_run:
        print("[dry-run] No se modificó nada local (solo se actualizaron refs remotas).")
        return 0

    if not args.yes:
        extra_gone = 0
        if args.force_gone:
            extra_gone = sum(
                1
                for plan in planes
                if not plan.omitido
                for _rama, _motivo, es_gone in plan.revisar
                if es_gone
            )
        mensaje = f"¿Aplicar la limpieza? Se borrarán {total_borrar} ramas"
        if extra_gone:
            mensaje += f" + {extra_gone} con --force-gone"
        mensaje += " y cada repo quedará en su rama objetivo. [y/N]: "
        try:
            respuesta = input(mensaje).strip().lower()
        except EOFError:
            respuesta = ""
        if respuesta not in ("y", "yes", "s", "si", "sí"):
            print("Cancelado: no se modificó nada local.")
            return 0

    resultados: List[ResultadoRepo] = []
    for plan in planes:
        if plan.omitido:
            resultados.append(
                ResultadoRepo(
                    folder=plan.cfg.folder,
                    objetivo=plan.objetivo,
                    avisos=list(plan.avisos),
                    omitido=plan.omitido,
                )
            )
            continue
        resultados.append(aplicar(plan, args.force_gone))

    imprimir_resumen(resultados)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print("Cancelado (Ctrl+C). No se continuó con el resto.")
        sys.exit(130)
