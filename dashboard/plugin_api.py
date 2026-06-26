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

BUILTIN_DESCRIPTIONS: Dict[str, str] = {
    "computer-use": "用途：在后台操控用户桌面应用。主要功能：截图识别、点击、输入、拖拽、滚动、快捷键和应用聚焦。依赖要求：需要 computer_use 工具/cua-driver；文档提到可用 hermes computer-use install 安装或启用 Computer Use。适用场景：处理真实桌面应用、非网页界面或必须通过 GUI 完成的操作。",
    "dogfood": "用途：对 Web 应用做系统化探索测试。主要功能：规划测试范围、浏览页面、检查控制台、交互验证、截图取证、分类问题并生成报告。依赖要求：需要 browser 工具集和目标 URL/测试范围；输出目录可选。适用场景：发布前验收、回归测试、发现前端交互和可访问性问题。",
    "hermes-agent": "用途：配置、扩展和维护 Hermes Agent。主要功能：提供安装、模型、认证、工具、技能、网关、会话、Cron、Webhook、Profile、排障和贡献指引。依赖要求：需要 Hermes Agent 环境；具体功能可能需要对应 provider 凭据、平台账号或 MCP/网关配置。适用场景：搭建 Hermes、调整配置、排查问题、开发插件或贡献代码。",
    "baoyu-infographic": "用途：把文本、文件、URL 或主题转成信息图/可视化摘要。主要功能：分析内容、结构化信息、选择布局和风格、生成提示词与图片。依赖要求：需要图像生成工具；输入来源由用户提供，生成时会使用布局/风格参考文件。适用场景：制作信息图、视觉总结、高密度信息大图和教学/产品可视化。",
    "github-auth": "用途：配置 GitHub 认证。主要功能：检查 git/gh 登录状态，指导 HTTPS Token、SSH Key、gh auth login、Git 身份和 API Token 配置。依赖要求：需要 git；可选 gh CLI；需要 GitHub 账号、PAT 或 SSH Key。适用场景：让 Hermes 能访问仓库、提交推送、处理 PR、Issue 和 CI。",
    "github-code-review": "用途：审查本地改动或 GitHub PR。主要功能：读取 diff、stat、log，逐文件检查，发现安全/质量问题，查看 PR、checkout PR、发表评论或正式 review。依赖要求：需要 GitHub 认证并在 git 仓库内；PR API 操作需要 gh 或 GITHUB_TOKEN/curl。适用场景：提交前自查、PR 评审、质量和安全问题排查。",
    "github-issues": "用途：创建、搜索、分类和管理 GitHub Issue。主要功能：查看 Issue、创建 Bug/Feature 模板、增删标签、分配人员、评论、关闭或重开。依赖要求：需要 GitHub 认证；需要在带 GitHub remote 的 git 仓库内或显式指定仓库；可使用 gh 或 GITHUB_TOKEN/curl。适用场景：缺陷跟踪、需求管理、Issue 分流和项目维护。",
    "github-pr-workflow": "用途：管理 GitHub PR 生命周期。主要功能：创建分支、提交、推送、创建 PR、监控 CI、诊断失败、更新 PR 和合并流程。依赖要求：需要 GitHub 认证并在带 GitHub remote 的 git 仓库内；可使用 gh 或 git + GITHUB_TOKEN/curl。适用场景：从开发分支到 PR、CI、评审和合并的完整协作流程。",
    "github-repo-management": "用途：管理 GitHub 仓库。主要功能：克隆、创建、fork、同步 fork、查看仓库信息、管理远程仓库、发布和配置。依赖要求：需要 GitHub 认证；可使用 gh，也可使用 git + GITHUB_TOKEN/curl。适用场景：初始化项目、维护仓库、处理 fork/upstream、发布版本和仓库配置。",
    "obsidian": "用途：读写和维护 Obsidian vault 笔记。主要功能：读取、列出、搜索、创建、追加、定向编辑 Markdown 笔记并添加 wikilink。依赖要求：需要已知 vault 路径；文档约定可用 OBSIDIAN_VAULT_PATH，未设置时使用 ~/Documents/Obsidian Vault。适用场景：整理知识库、检索笔记、生成或更新 Obsidian Markdown 内容。",
    "hermes-agent-skill-authoring": "用途：编写和维护 Hermes Agent 仓库内的 SKILL.md。主要功能：说明 frontmatter 规则、目录放置、结构、写作质量、验证清单、编辑流程和常见陷阱。依赖要求：需要在 Hermes Agent 仓库内操作；创建/编辑后需要按文档验证并提交。适用场景：新增可随 Hermes 发布的技能、修改内置技能、统一技能文档质量。",
    "plan": "用途：在只需要计划时生成可执行的 Markdown 计划。主要功能：禁止执行实现，只检查上下文并把目标、方案、步骤、文件、测试、风险写入 .hermes/plans/。依赖要求：未发现明显外部依赖；需要有可写工作区用于保存计划文件。适用场景：复杂需求拆解、实现前设计、交给后续执行者或子任务使用。",
    "simplify-code": "用途：并行审查近期代码改动并清理值得修复的问题。主要功能：按复用、质量、效率三个方向审查 diff，聚合发现，区分安全/谨慎/高风险修复并验证。依赖要求：需要可获取待审查 diff 的 git 仓库；文档提到使用并行子任务能力。适用场景：提交前清理、减少重复、改善代码质量和发现性能/错误处理问题。",
    "spike": "用途：用一次性实验验证想法是否可行。主要功能：拆分 2-5 个可验证问题，做必要研究，构建可运行原型，记录 VALIDATED/PARTIAL/INVALIDATED 结论。依赖要求：未发现固定外部依赖；具体实验可能需要相应库、工具或网络资料。适用场景：不确定方案、比较技术路线、正式实现前验证风险。",
    "systematic-debugging": "用途：用四阶段流程定位技术问题根因。主要功能：建立可复现反馈环、读取错误、检查变更、收集证据、分析模式、形成可证伪假设、修复并验证。依赖要求：未发现固定外部依赖；通常需要能运行相关测试、命令或复现脚本。适用场景：测试失败、生产 Bug、构建失败、性能问题和多次修复无效的故障。",
    "test-driven-development": "用途：用 TDD 约束功能、修复和重构。主要功能：先写失败测试、确认 RED、写最小实现、确认 GREEN、再重构，并避免一次性横向堆测试。依赖要求：未发现固定外部依赖；需要项目具备可运行的自动化测试环境。适用场景：新增功能、Bug 修复、行为变更和需要高信心重构的开发工作。",
}


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

    description = skill.get("description", "") or ""
    if kind == "builtin":
        description = BUILTIN_DESCRIPTIONS.get(name, description)

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
        "description": description,
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
