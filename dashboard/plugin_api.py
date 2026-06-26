"""Skill manage dashboard plugin API.

Mounted by Hermes dashboard at /api/plugins/skill-manage/.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
except Exception:  # Keep importable in lightweight syntax checks.
    class APIRouter:  # type: ignore
        def get(self, *_args, **_kwargs):
            return lambda fn: fn

        def post(self, *_args, **_kwargs):
            return lambda fn: fn

    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class BaseModel:  # type: ignore
        pass

try:
    from hermes_constants import get_hermes_home
except Exception:
    def get_hermes_home() -> Path:  # type: ignore[misc]
        return Path.home() / ".hermes"

router = APIRouter()

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = PLUGIN_ROOT / "state.json"
TRASH_ROOT = PLUGIN_ROOT / "trash"
CONFLICT_ROOT = TRASH_ROOT / "conflicts"
SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class SkillAction(BaseModel):
    source: str
    name: str
    confirm: str = ""
    target: str = ""
    category: str = ""
    force: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _home() -> Path:
    return Path(get_hermes_home())


def _skills_dir() -> Path:
    return _home() / "skills"


def _lock_path() -> Path:
    return _skills_dir() / ".hub" / "lock.json"


def _bundled_manifest_path() -> Path:
    return _skills_dir() / ".bundled_manifest"


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _load_state() -> Dict[str, Any]:
    data = _load_json(STATE_PATH, {"version": 1, "deleted": {}, "history": []})
    if not isinstance(data, dict):
        data = {"version": 1, "deleted": {}, "history": []}
    data.setdefault("version", 1)
    data.setdefault("deleted", {})
    data.setdefault("history", [])
    if not isinstance(data["deleted"], dict):
        data["deleted"] = {}
    if not isinstance(data["history"], list):
        data["history"] = []
    return data


def _save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _history(state: Dict[str, Any], event: Dict[str, Any]) -> None:
    event.setdefault("at", _now())
    state.setdefault("history", []).insert(0, event)
    state["history"] = state["history"][:200]


def _state_key(source: str, name: str) -> str:
    return f"{source}:{name}"


def _display_source(raw_source: str) -> str:
    if raw_source == "builtin":
        return "builtin"
    if raw_source == "local":
        return "local"
    return "hub-installed"


def _read_frontmatter(skill_md: Path) -> Dict[str, str]:
    result = {"name": skill_md.parent.name, "description": ""}
    try:
        lines = skill_md.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return result
    if lines and lines[0].strip() == "---":
        scoped = []
        for line in lines[1:80]:
            if line.strip() == "---":
                break
            scoped.append(line)
    else:
        scoped = lines[:40]
    for line in scoped:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip().strip("\"'")
        if key == "name" and value and result["name"] == skill_md.parent.name:
            result["name"] = value
        elif key == "description" and value and not result["description"]:
            result["description"] = value
    return result


def _bundled_names() -> set[str]:
    path = _bundled_manifest_path()
    names: set[str] = set()
    if not path.exists():
        return names
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" in line:
            name = line.split(":", 1)[0].strip()
            if name:
                names.add(name)
    return names


def _hub_entries() -> Dict[str, Dict[str, Any]]:
    data = _load_json(_lock_path(), {})
    installed = data.get("installed", {}) if isinstance(data, dict) else {}
    return installed if isinstance(installed, dict) else {}


def _hub_by_path() -> Dict[str, Dict[str, Any]]:
    by_path: Dict[str, Dict[str, Any]] = {}
    for name, entry in _hub_entries().items():
        if not isinstance(entry, dict):
            continue
        install_path = entry.get("install_path")
        if isinstance(install_path, str) and install_path:
            enriched = dict(entry)
            enriched.setdefault("name", name)
            by_path[install_path] = enriched
    return by_path


def _safe_target(rel_path: str) -> Path:
    root = _skills_dir().resolve()
    target = (root / rel_path).resolve()
    if target == root or not target.is_relative_to(root):
        raise HTTPException(status_code=400, detail="技能路径不安全")
    return target


def _skill_row(skill_md: Path, hub_by_path: Dict[str, Dict[str, Any]], bundled: set[str]) -> Dict[str, Any]:
    root = _skills_dir()
    skill_dir = skill_md.parent
    rel = skill_dir.relative_to(root).as_posix()
    meta = _read_frontmatter(skill_md)
    name = meta["name"]
    entry = hub_by_path.get(rel)

    if entry:
        source = "hub-installed"
        original_source = entry.get("source", "hub")
        trust_level = entry.get("trust_level", "community")
        scan_verdict = entry.get("scan_verdict", "n/a")
        identifier = entry.get("identifier", "")
        installed_at = str(entry.get("installed_at", ""))[:10]
        updated_at = str(entry.get("updated_at", ""))[:10]
    elif name in bundled:
        source = "builtin"
        trust_level = "builtin"
        scan_verdict = "bundled"
        identifier = f"bundled/{rel}"
        original_source = "builtin"
        installed_at = ""
        updated_at = ""
    else:
        source = "local"
        trust_level = "local"
        scan_verdict = "local"
        identifier = ""
        original_source = "local"
        installed_at = ""
        updated_at = ""

    category = rel.rsplit("/", 1)[0] if "/" in rel else ""
    try:
        file_count = sum(1 for path in skill_dir.rglob("*") if path.is_file())
    except OSError:
        file_count = 0

    return {
        "name": name,
        "source": source,
        "originalSource": original_source,
        "category": category,
        "installPath": rel,
        "description": meta["description"],
        "identifier": identifier,
        "trustLevel": trust_level,
        "scanVerdict": scan_verdict,
        "installedAt": installed_at,
        "updatedAt": updated_at,
        "fileCount": file_count,
    }


def _inventory_rows() -> List[Dict[str, Any]]:
    root = _skills_dir()
    if not root.exists():
        return []
    hub_by_path = _hub_by_path()
    bundled = _bundled_names()
    rows: List[Dict[str, Any]] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        if ".hub" in skill_md.parts or ".restore-backups" in skill_md.parts:
            continue
        try:
            rows.append(_skill_row(skill_md, hub_by_path, bundled))
        except Exception:
            continue
    return rows


def _find_skill(source: str, name: str) -> Dict[str, Any]:
    normalized_source = _display_source(source)
    for row in _inventory_rows():
        if row["source"] == normalized_source and name in {row["name"], Path(row["installPath"]).name}:
            return row
    raise HTTPException(status_code=404, detail=f"未找到技能：{normalized_source}:{name}")


def _backup_record(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": row["source"],
        "name": row["name"],
        "install_path": row["installPath"],
        "identifier": row.get("identifier", ""),
        "trust_level": row.get("trustLevel", ""),
        "scan_verdict": row.get("scanVerdict", ""),
        "deleted_at": _stamp(),
        "backup_dir": "",
    }


def _optional_catalog(limit: int = 80) -> List[Dict[str, Any]]:
    try:
        from tools.skills_sync import _optional_skill_index
    except Exception:
        return []
    try:
        raw = _optional_skill_index()
    except Exception:
        return []
    rows: List[Dict[str, Any]] = []
    if isinstance(raw, dict):
        iterable = raw.items()
    else:
        iterable = enumerate(raw or [])
    for key, item in iterable:
        if len(rows) >= limit:
            break
        if isinstance(item, dict):
            identifier = str(item.get("identifier") or item.get("path") or key)
            name = str(item.get("name") or Path(identifier).name)
            desc = str(item.get("description") or "")
            category = str(item.get("category") or "")
        elif isinstance(item, (list, tuple)) and item:
            identifier = str(item[0])
            name = Path(identifier).name
            desc = str(item[1]) if len(item) > 1 else ""
            category = str(item[2]) if len(item) > 2 else ""
        else:
            identifier = str(key)
            name = Path(identifier).name
            desc = ""
            category = ""
        rows.append({
            "name": name,
            "source": "optional",
            "category": category,
            "installPath": identifier,
            "description": desc,
            "identifier": identifier,
            "trustLevel": "official",
            "scanVerdict": "available",
            "status": "available",
        })
    return rows


@router.get("/inventory")
async def inventory() -> Dict[str, Any]:
    rows = _inventory_rows()
    counts: Dict[str, int] = {}
    categories: Dict[str, int] = {}
    for row in rows:
        counts[row["source"]] = counts.get(row["source"], 0) + 1
        cat = row.get("category") or "(root)"
        categories[cat] = categories.get(cat, 0) + 1
    state = _load_state()
    return {
        "ok": True,
        "skills": rows,
        "counts": counts,
        "categories": categories,
        "deleted": list(state.get("deleted", {}).values()),
        "history": state.get("history", [])[:40],
        "optional": _optional_catalog(40),
        "meta": {
            "home": str(_home()),
            "skillsDir": str(_skills_dir()),
            "generatedAt": _now(),
        },
    }


@router.get("/skill/{source}/{name}")
async def skill_detail(source: str, name: str) -> Dict[str, Any]:
    row = _find_skill(source, name)
    target = _safe_target(row["installPath"])
    skill_md = target / "SKILL.md"
    try:
        body = skill_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        body = ""
    files = []
    try:
        files = [p.relative_to(target).as_posix() for p in sorted(target.rglob("*")) if p.is_file()]
    except OSError:
        files = []
    return {"ok": True, "skill": row, "skillMd": body, "files": files[:200]}


@router.post("/delete")
async def delete_skill(action: SkillAction) -> Dict[str, Any]:
    source = action.source
    name = action.name
    if action.confirm != name:
        raise HTTPException(status_code=400, detail="确认文本必须与技能名一致")
    row = _find_skill(source, name)
    if row["source"] == "builtin":
        raise HTTPException(status_code=400, detail="当前 Dashboard 版本保护内置技能，不能删除")
    target = _safe_target(row["installPath"])
    if not target.exists():
        raise HTTPException(status_code=404, detail="技能路径不存在")

    record = _backup_record(row)
    backup_dir = TRASH_ROOT / record["source"] / record["name"] / record["deleted_at"] / Path(record["install_path"])
    backup_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(target, backup_dir)
    record["backup_dir"] = str(backup_dir)

    if row["source"] == "hub-installed":
        try:
            from tools.skills_hub import uninstall_skill
            ok, message = uninstall_skill(row["name"])
            if not ok:
                raise HTTPException(status_code=500, detail=message)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    else:
        shutil.rmtree(target)

    state = _load_state()
    state["deleted"][_state_key(record["source"], record["name"])] = record
    _history(state, {"action": "delete", **record})
    _save_state(state)
    return {"ok": True, "record": record}


@router.post("/restore")
async def restore_skill(action: SkillAction) -> Dict[str, Any]:
    source = action.source
    name = action.name
    if action.confirm != name:
        raise HTTPException(status_code=400, detail="确认文本必须与技能名一致")
    state = _load_state()
    record = state.get("deleted", {}).get(_state_key(source, name))
    if not record:
        raise HTTPException(status_code=404, detail="没有找到这个技能的删除记录")
    backup_dir = Path(record.get("backup_dir", ""))
    if not backup_dir.exists():
        raise HTTPException(status_code=404, detail="备份目录不存在")

    target = _safe_target(record["install_path"])
    if target.exists():
        conflict = CONFLICT_ROOT / source / name / _stamp() / target.name
        conflict.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(conflict))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(backup_dir, target)
    state.get("deleted", {}).pop(_state_key(source, name), None)
    _history(state, {"action": "restore", **record})
    _save_state(state)
    return {"ok": True, "record": record}


@router.post("/install")
async def install_skill(action: SkillAction) -> Dict[str, Any]:
    target = action.target or action.name
    if not target:
        raise HTTPException(status_code=400, detail="请输入安装目标")
    if action.source == "builtin":
        if not SKILL_NAME_RE.match(target):
            raise HTTPException(status_code=400, detail="重置内置技能时请输入技能名")
        try:
            from hermes_cli.skills_hub import do_reset
            do_reset(target, restore=True, console=None, skip_confirm=True)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    else:
        try:
            from hermes_cli.skills_hub import do_install
            do_install(target, category=action.category, force=action.force, console=None, skip_confirm=True)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    state = _load_state()
    _history(state, {
        "action": "install",
        "source": action.source,
        "name": target,
        "category": action.category,
        "force": action.force,
    })
    _save_state(state)
    return {"ok": True}


@router.post("/reset")
async def reset_skill(action: SkillAction) -> Dict[str, Any]:
    name = action.name or action.target
    if not name:
        raise HTTPException(status_code=400, detail="请输入要重置的技能名")
    row = _find_skill("builtin", name)
    try:
        from hermes_cli.skills_hub import do_reset
        do_reset(row["name"], restore=True, console=None, skip_confirm=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    state = _load_state()
    _history(state, {"action": "reset", "source": "builtin", "name": row["name"]})
    _save_state(state)
    return {"ok": True, "skill": row}
