"""CLI entrypoints for the skill-vault plugin."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from rich.console import Console

from hermes_cli.skills_hub import do_browse, do_install, do_list, do_repair_official, do_reset
from hermes_constants import get_hermes_home
from tools.skill_manager_tool import _find_skill
from tools.skills_guard import content_hash
from tools.skills_hub import HubLockFile, SKILLS_DIR, uninstall_skill
from tools.skills_sync import (
    _compute_relative_dest,
    _discover_bundled_skills,
    _get_bundled_dir,
    _optional_skill_index,
    _read_skill_name,
    _skill_file_list,
)

PLUGIN_ROOT = Path(__file__).resolve().parent
STATE_PATH = PLUGIN_ROOT / "state.json"
TRASH_ROOT = PLUGIN_ROOT / "trash"
CONFLICT_ROOT = TRASH_ROOT / "conflicts"


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def _console() -> Console:
    return Console()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _state_default() -> Dict[str, Any]:
    return {"version": 1, "deleted": {}}


def _state_key(source: str, name: str) -> str:
    return f"{source}:{name}"


def _load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return _state_default()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _state_default()
    if not isinstance(data, dict):
        return _state_default()
    data.setdefault("version", 1)
    data.setdefault("deleted", {})
    if not isinstance(data["deleted"], dict):
        data["deleted"] = {}
    return data


def _save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        raise FileExistsError(f"backup destination already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)


def _safe_move_aside(current: Path, source: str, name: str) -> Optional[Path]:
    """Move an existing active skill aside before we overwrite it during restore."""
    if not current.exists():
        return None
    ts = _utc_stamp()
    conflict_dir = CONFLICT_ROOT / source / name / ts / current.name
    conflict_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(current), str(conflict_dir))
    return conflict_dir


def _backup_record(
    *,
    source: str,
    name: str,
    install_path: str,
    identifier: str = "",
    trust_level: str = "local",
    scan_verdict: str = "user_request",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "source": source,
        "name": name,
        "install_path": install_path,
        "identifier": identifier,
        "trust_level": trust_level,
        "scan_verdict": scan_verdict,
        "metadata": metadata or {},
        "deleted_at": _utc_stamp(),
        "backup_dir": "",
    }


def _resolve_builtin(name: str) -> Optional[Dict[str, Any]]:
    bundled_dir = _get_bundled_dir()
    for skill_name, skill_dir in _discover_bundled_skills(bundled_dir):
        if name not in {skill_name, skill_dir.name}:
            continue
        dest = _compute_relative_dest(skill_dir, bundled_dir)
        return {
            "source": "builtin",
            "name": skill_name,
            "skill_dir": skill_dir,
            "active_dir": dest,
            "install_path": dest.relative_to(SKILLS_DIR).as_posix(),
            "identifier": f"bundled/{dest.relative_to(SKILLS_DIR).as_posix()}",
        }
    return None


def _resolve_hub(name: str) -> Optional[Dict[str, Any]]:
    lock = HubLockFile()
    entry = lock.get_installed(name)
    if not entry:
        return None
    install_path = SKILLS_DIR / Path(entry["install_path"])
    return {
        "source": entry.get("source", "hub"),
        "name": entry.get("name", name),
        "entry": entry,
        "active_dir": install_path,
        "install_path": entry["install_path"],
        "identifier": entry.get("identifier", ""),
        "trust_level": entry.get("trust_level", "community"),
        "scan_verdict": entry.get("scan_verdict", "n/a"),
    }


def _resolve_local(name: str) -> Optional[Dict[str, Any]]:
    hub = HubLockFile()
    hub_names = {entry["name"] for entry in hub.list_installed()}
    builtin_names = {skill_name for skill_name, _ in _discover_bundled_skills(_get_bundled_dir())}

    for skill_md in SKILLS_DIR.rglob("SKILL.md"):
        skill_dir = skill_md.parent
        if skill_dir.parts and any(part in {".hub", ".restore-backups"} for part in skill_dir.parts):
            continue
        skill_name = _read_skill_name(skill_md, skill_dir.name)
        if name not in {skill_name, skill_dir.name}:
            continue
        if skill_name in hub_names or skill_name in builtin_names:
            # Local source should be the non-hub, non-builtin copy.
            continue
        return {
            "source": "local",
            "name": skill_name,
            "active_dir": skill_dir,
            "install_path": skill_dir.relative_to(SKILLS_DIR).as_posix(),
            "identifier": "",
            "trust_level": "local",
            "scan_verdict": "local",
        }
    return None


def _resolve_any(name: str, source: str) -> Optional[Dict[str, Any]]:
    if source == "builtin":
        return _resolve_builtin(name)
    if source == "hub":
        return _resolve_hub(name)
    if source == "local":
        return _resolve_local(name)

    for resolver in (_resolve_builtin, _resolve_hub, _resolve_local):
        found = resolver(name)
        if found:
            return found
    return None


def _write_backup_metadata(backup_dir: Path, record: Dict[str, Any]) -> None:
    """Persist a small sidecar next to the copied tree, not inside it."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    sidecar = backup_dir.parent / "skill-vault.json"
    sidecar.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _store_delete_backup(skill_dir: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    backup_dir = TRASH_ROOT / record["source"] / record["name"] / record["deleted_at"] / Path(
        record["install_path"]
    )
    _copy_tree(skill_dir, backup_dir)
    record["backup_dir"] = str(backup_dir)
    _write_backup_metadata(backup_dir, record)
    state = _load_state()
    state["deleted"][_state_key(record["source"], record["name"])] = record
    _save_state(state)
    return record


def _restore_from_backup(record: Dict[str, Any], console: Console) -> bool:
    backup_dir = Path(record.get("backup_dir", ""))
    source = record.get("source", "local")
    name = record.get("name", "")
    install_path = record.get("install_path", "")
    target = SKILLS_DIR / Path(install_path)

    if not backup_dir.exists():
        console.print(f"[yellow]Backup missing:[/] {backup_dir}")
        return False

    # If something already exists at the target, move it out of the way first.
    _safe_move_aside(target, source, name)

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(backup_dir, target)

    if source in {"hub", "official"}:
        entry = record.get("hub_entry") or {}
        trust_level = record.get("trust_level") or entry.get("trust_level", "community")
        scan_verdict = record.get("scan_verdict") or entry.get("scan_verdict", "n/a")
        identifier = record.get("identifier") or entry.get("identifier") or f"official/{install_path}"
        metadata = dict(record.get("metadata") or {})
        metadata.update(entry.get("metadata") or {})
        lock = HubLockFile()
        lock.record_install(
            name=name,
            source=entry.get("source", source),
            identifier=identifier,
            trust_level=trust_level,
            scan_verdict=scan_verdict,
            skill_hash=content_hash(target),
            install_path=install_path,
            files=_skill_file_list(target),
            metadata=metadata,
        )

    console.print(f"[green]Restored[/] {source}:{name} → {install_path}")
    return True


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def _cmd_list(args: argparse.Namespace) -> None:
    c = _console()
    source = args.source

    if source in {"all", "builtin"}:
        c.print("\n[bold]Installed skills — builtin[/]")
        do_list(source_filter="builtin", enabled_only=False, console=c)

    if source in {"all", "hub"}:
        c.print("\n[bold]Installed skills — hub[/]")
        do_list(source_filter="hub", enabled_only=False, console=c)

    if source in {"all", "local"}:
        c.print("\n[bold]Installed skills — local[/]")
        do_list(source_filter="local", enabled_only=False, console=c)

    if source in {"all", "optional"}:
        c.print("\n[bold]Optional catalog — official[/]")
        do_browse(page=args.page, page_size=args.page_size, source="official", console=c)


def _cmd_delete(args: argparse.Namespace) -> None:
    c = _console()
    resolved = _resolve_any(args.name, args.source)
    if not resolved:
        c.print(f"[bold red]Not found:[/] {args.source}:{args.name}")
        return

    skill_dir = resolved["active_dir"]
    if not skill_dir.exists():
        c.print(f"[yellow]Already missing:[/] {resolved['source']}:{resolved['name']}")
        return

    record = _backup_record(
        source=resolved["source"],
        name=resolved["name"],
        install_path=resolved["install_path"],
        identifier=resolved.get("identifier", ""),
        trust_level=resolved.get("trust_level", "local"),
        scan_verdict=resolved.get("scan_verdict", "user_request"),
        metadata={
            "source_hint": args.source,
            "original_path": str(skill_dir),
        },
    )
    if resolved["source"] in {"hub", "official"}:
        record["hub_entry"] = resolved.get("entry", {})

    _store_delete_backup(skill_dir, record)

    if resolved["source"] in {"hub", "official"}:
        ok, message = uninstall_skill(resolved["name"])
        if not ok:
            c.print(f"[bold red]Delete failed:[/] {message}")
            return
        c.print(f"[green]Deleted[/] {resolved['source']}:{resolved['name']} (backup kept in plugin trash)")
        return

    shutil.rmtree(skill_dir)
    c.print(f"[green]Deleted[/] {resolved['source']}:{resolved['name']} (backup kept in plugin trash)")


def _cmd_restore(args: argparse.Namespace) -> None:
    c = _console()
    key = _state_key(args.source, args.name)
    state = _load_state()
    record = state.get("deleted", {}).get(key)

    if record and Path(record.get("backup_dir", "")).exists():
        if _restore_from_backup(record, c):
            return

    if args.source == "builtin":
        do_reset(args.name, restore=True, console=c, skip_confirm=True)
        return

    if args.source == "hub":
        if not record:
            c.print(f"[bold red]No backup record for hub skill:[/] {args.name}")
            return
        identifier = record.get("identifier") or f"official/{record['install_path']}"
        do_install(
            identifier,
            category=record.get("install_path", "").rsplit("/", 1)[0] if "/" in record.get("install_path", "") else "",
            force=True,
            console=c,
            skip_confirm=True,
        )
        return

    if args.source == "local":
        if not record:
            c.print(f"[bold red]No backup record for local skill:[/] {args.name}")
            return
        c.print(f"[bold red]Backup copy missing for local skill:[/] {args.name}")
        return

    c.print(f"[bold red]Unknown source:[/] {args.source}")


def _cmd_install(args: argparse.Namespace) -> None:
    c = _console()
    if args.source == "builtin":
        do_reset(args.target, restore=True, console=c, skip_confirm=True)
        return
    if args.source == "optional":
        do_install(
            args.target,
            category=args.category or "",
            force=args.force,
            console=c,
            skip_confirm=True,
        )
        return
    if args.source == "hub":
        do_install(
            args.target,
            category=args.category or "",
            force=args.force,
            console=c,
            skip_confirm=True,
        )
        return
    c.print(f"[bold red]Unknown install source:[/] {args.source}")


def _cmd_help(args: argparse.Namespace) -> None:
    _console().print(
        "[bold]skill-vault[/] — use one of: list, delete, restore, install\n"
        "Run [bold]hermes skill-vault --help[/] for the full CLI usage."
    )


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def register_cli(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        "Manage installed Hermes skills by source. Shows builtin, hub, and local "
        "skill inventories, plus the official optional catalog, and supports "
        "physical delete, restore, and install flows."
    )
    subparsers = parser.add_subparsers(dest="skill_vault_action")

    list_p = subparsers.add_parser(
        "list",
        help="List installed skills by source and show the official optional catalog",
    )
    list_p.add_argument(
        "--source",
        choices=["all", "builtin", "hub", "local", "optional"],
        default="all",
        help="Which source module to show",
    )
    list_p.add_argument("--page", type=int, default=1, help="Optional catalog page")
    list_p.add_argument("--page-size", type=int, default=20, help="Optional catalog page size")
    list_p.set_defaults(func=_cmd_list)

    delete_p = subparsers.add_parser(
        "delete",
        help="Physically delete an installed skill while keeping a local backup",
    )
    delete_p.add_argument(
        "--source",
        choices=["builtin", "hub", "local"],
        default="local",
        help="Where to look for the skill",
    )
    delete_p.add_argument("name", help="Skill name")
    delete_p.set_defaults(func=_cmd_delete)

    restore_p = subparsers.add_parser(
        "restore",
        help="Restore a previously deleted skill from plugin trash or source",
    )
    restore_p.add_argument(
        "--source",
        choices=["builtin", "hub", "local"],
        default="local",
        help="Where the skill came from",
    )
    restore_p.add_argument("name", help="Skill name")
    restore_p.set_defaults(func=_cmd_restore)

    install_p = subparsers.add_parser(
        "install",
        help="Install builtin, hub, or official optional skills",
    )
    install_p.add_argument(
        "source",
        choices=["builtin", "hub", "optional"],
        help="What kind of skill to install",
    )
    install_p.add_argument("target", help="Skill name or identifier")
    install_p.add_argument("--category", default="", help="Install into a category path")
    install_p.add_argument("--force", action="store_true", help="Reinstall even if already present")
    install_p.set_defaults(func=_cmd_install)

    parser.set_defaults(func=_cmd_help)


def skill_vault_command(args: argparse.Namespace) -> None:
    """Fallback top-level handler when the user runs `hermes skill-vault`."""
    if not hasattr(args, "skill_vault_action") or args.skill_vault_action is None:
        args = argparse.Namespace(source="all", page=1, page_size=20)
    _cmd_list(args)
