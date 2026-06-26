"""Skill manage dashboard plugin API.

Mounted by Hermes dashboard at /api/plugins/skill-manage/.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
except Exception:
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


class SkillAction(BaseModel):
    source: str = ""
    name: str = ""
    confirm: str = ""
    target: str = ""
    category: str = ""
    force: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _home() -> Path:
    return Path(get_hermes_home())


def _skills_dir() -> Path:
    return _home() / "skills"


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _load_state() -> Dict[str, Any]:
    data = _load_json(STATE_PATH, {"version": 1, "history": []})
    if not isinstance(data, dict):
        data = {"version": 1, "history": []}
    data.setdefault("version", 1)
    data.setdefault("history", [])
    if not isinstance(data["history"], list):
        data["history"] = []
    return data


def _save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _history(event: Dict[str, Any]) -> None:
    state = _load_state()
    event.setdefault("at", _now())
    state.setdefault("history", []).insert(0, event)
    state["history"] = state["history"][:200]
    _save_state(state)


def _clear_skill_cache() -> None:
    try:
        from agent.prompt_builder import clear_skills_system_prompt_cache
        clear_skills_system_prompt_cache(clear_snapshot=True)
    except Exception:
        pass


def _hub_by_name() -> Dict[str, Dict[str, Any]]:
    try:
        from tools.skills_hub import HubLockFile
        return {entry["name"]: entry for entry in HubLockFile().list_installed()}
    except Exception:
        return {}


def _builtin_names() -> set[str]:
    try:
        from tools.skills_sync import _read_manifest
        return set(_read_manifest())
    except Exception:
        return set()


def _disabled_names() -> set[str]:
    try:
        from agent.skill_utils import get_disabled_skill_names
        return set(get_disabled_skill_names())
    except Exception:
        return set()


def _all_skills() -> List[Dict[str, Any]]:
    try:
        from tools.skills_tool import _find_all_skills
        return list(_find_all_skills(skip_disabled=True))
    except Exception:
        return []


def _safe_target(rel_path: str) -> Path:
    root = _skills_dir().resolve()
    target = (root / rel_path).resolve()
    if target == root or not target.is_relative_to(root):
        raise HTTPException(status_code=400, detail="技能路径不安全")
    return target


def _normalize_path(path_value: Any, name: str, category: str) -> str:
    if isinstance(path_value, str) and path_value:
        try:
            path = Path(path_value)
            root = _skills_dir().resolve()
            if path.is_absolute():
                return path.resolve().relative_to(root).as_posix()
        except Exception:
            pass
    return f"{category}/{name}" if category else name


def _skill_row(skill: Dict[str, Any], hub: Dict[str, Dict[str, Any]], builtin: set[str], disabled: set[str]) -> Dict[str, Any]:
    name = skill["name"]
    category = skill.get("category", "") or ""
    hub_entry = hub.get(name)
    skill_md_path = skill.get("skill_md_path") or skill.get("path") or ""
    install_path = _normalize_path(skill_md_path, name, category)

    if hub_entry:
        kind = "hub-installed"
        source = hub_entry.get("source", "hub")
        trust = hub_entry.get("trust_level", "community")
        identifier = hub_entry.get("identifier", "")
        installed_at = str(hub_entry.get("installed_at", ""))[:10]
        updated_at = str(hub_entry.get("updated_at", ""))[:10]
    elif name in builtin:
        kind = "builtin"
        source = "builtin"
        trust = "builtin"
        identifier = f"bundled/{install_path}"
        installed_at = ""
        updated_at = ""
    else:
        kind = "local"
        source = "local"
        trust = "local"
        identifier = ""
        installed_at = ""
        updated_at = ""

    return {
        "name": name,
        "category": category,
        "kind": kind,
        "source": source,
        "rawSource": source,
        "trustLevel": "official" if source == "official" else trust,
        "status": "disabled" if name in disabled else "enabled",
        "installPath": install_path,
        "identifier": identifier,
        "description": skill.get("description", "") or "",
        "installedAt": installed_at,
        "updatedAt": updated_at,
    }


def _inventory_rows() -> List[Dict[str, Any]]:
    hub = _hub_by_name()
    builtin = _builtin_names()
    disabled = _disabled_names()
    rows = [_skill_row(skill, hub, builtin, disabled) for skill in _all_skills()]
    return sorted(rows, key=lambda row: (row.get("category") or "", row["name"]))


def _find_skill(source: str, name: str) -> Dict[str, Any]:
    for row in _inventory_rows():
        if (row.get("kind") or row["source"]) == source and row["name"] == name:
            return row
    raise HTTPException(status_code=404, detail=f"未找到技能：{source}:{name}")


def _require_confirm(action: SkillAction, name: str) -> None:
    if action.confirm != name:
        raise HTTPException(status_code=400, detail="二次确认失败：确认文本必须与技能名一致")


def _optional_catalog(limit: int = 80) -> List[Dict[str, Any]]:
    try:
        from tools.skills_sync import _optional_skill_index
        raw = _optional_skill_index()
    except Exception:
        return []
    rows: List[Dict[str, Any]] = []
    iterable = raw.items() if isinstance(raw, dict) else enumerate(raw or [])
    for key, item in iterable:
        if len(rows) >= limit:
            break
        if isinstance(item, dict):
            identifier = str(item.get("identifier") or item.get("path") or key)
            name = str(item.get("name") or Path(identifier).name)
            category = str(item.get("category") or "")
        elif isinstance(item, (list, tuple)) and item:
            identifier = str(item[0])
            name = Path(identifier).name
            category = str(item[2]) if len(item) > 2 else ""
        else:
            identifier = str(key)
            name = Path(identifier).name
            category = ""
        rows.append({"name": name, "identifier": identifier, "category": category})
    return rows


@router.get("/inventory")
async def inventory() -> Dict[str, Any]:
    rows = _inventory_rows()
    counts: Dict[str, int] = {}
    enabled_count = 0
    disabled_count = 0
    categories: Dict[str, int] = {}
    for row in rows:
        kind = row.get("kind") or row["source"]
        counts[kind] = counts.get(kind, 0) + 1
        categories[row.get("category") or "(root)"] = categories.get(row.get("category") or "(root)", 0) + 1
        if row["status"] == "enabled":
            enabled_count += 1
        else:
            disabled_count += 1
    state = _load_state()
    return {
        "ok": True,
        "skills": rows,
        "counts": counts,
        "enabledCount": enabled_count,
        "disabledCount": disabled_count,
        "categories": categories,
        "history": state.get("history", [])[:40],
        "optional": _optional_catalog(40),
        "meta": {
            "home": str(_home()),
            "skillsDir": str(_skills_dir()),
            "generatedAt": _now(),
        },
    }


@router.post("/delete")
async def delete_skill(action: SkillAction) -> Dict[str, Any]:
    name = action.name
    source = action.source
    _require_confirm(action, name)
    row = _find_skill(source, name)

    if row.get("kind") == "hub-installed":
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
        target = _safe_target(row["installPath"])
        if not target.exists():
            raise HTTPException(status_code=404, detail="技能路径不存在")
        shutil.rmtree(target)

    _clear_skill_cache()
    _history({"action": "delete", "source": row.get("kind", row["source"]), "name": row["name"]})
    return {"ok": True, "skill": row}


@router.post("/reset")
async def reset_skill(action: SkillAction) -> Dict[str, Any]:
    name = action.name
    source = action.source
    row = _find_skill(source, name)

    if row.get("kind") == "builtin":
        try:
            from hermes_cli.skills_hub import do_reset
            do_reset(row["name"], restore=True, console=None, skip_confirm=True)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    elif row.get("kind") == "hub-installed":
        if not row.get("identifier"):
            raise HTTPException(status_code=400, detail="该 hub 技能缺少来源标识，无法重置")
        try:
            from hermes_cli.skills_hub import do_install
            do_install(row["identifier"], category=row.get("category", ""), force=True, console=None, skip_confirm=True)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=400, detail="本地技能不支持重置")

    _history({"action": "reset", "source": row.get("kind", row["source"]), "name": row["name"]})
    return {"ok": True, "skill": row}


@router.post("/update")
async def update_skill(action: SkillAction) -> Dict[str, Any]:
    row = _find_skill("hub-installed", action.name)
    try:
        from hermes_cli.skills_hub import do_update
        do_update(name=row["name"], console=None)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    _history({"action": "update", "source": row.get("kind", row["source"]), "name": row["name"]})
    return {"ok": True, "skill": row}


@router.post("/install")
async def install_skill(action: SkillAction) -> Dict[str, Any]:
    target = action.target or action.name
    if not target:
        raise HTTPException(status_code=400, detail="请输入安装目标")
    try:
        from hermes_cli.skills_hub import do_install
        do_install(target, category=action.category, force=action.force, console=None, skip_confirm=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    _history({
        "action": "install",
        "source": "hub-installed",
        "name": target,
        "category": action.category,
        "force": action.force,
    })
    return {"ok": True}
