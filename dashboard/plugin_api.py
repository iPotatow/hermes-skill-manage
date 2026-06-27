"""Skill manage dashboard plugin API.

Mounted by Hermes dashboard at /api/plugins/skill-manage/.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

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

BUILTIN_DESCRIPTIONS_EN: Dict[str, str] = {
    "computer-use": "Purpose: control the user's desktop in the background. Main features: screen inspection, clicks, typing, dragging, scrolling, keyboard shortcuts, and app focus. Requirements: requires the computer_use tool/cua-driver; the docs mention hermes computer-use install or enabling Computer Use. Best for tasks that must operate native desktop apps or GUI-only workflows.",
    "dogfood": "Purpose: run systematic exploratory QA on web apps. Main features: plan scope, browse pages, inspect console output, validate interactions, capture screenshots, categorize bugs, and produce reports. Requirements: requires the browser toolset and a target URL/test scope; output directory is optional. Best for pre-release checks, regressions, and finding frontend, interaction, or accessibility issues.",
    "hermes-agent": "Purpose: configure, extend, and maintain Hermes Agent. Main features: install/setup guidance, model and auth configuration, tools, skills, gateway, sessions, Cron, webhooks, profiles, troubleshooting, and contribution guidance. Requirements: requires a Hermes Agent environment; specific features may need provider credentials, platform accounts, or MCP/gateway configuration. Best for setting up Hermes, tuning configuration, debugging, plugin work, or contributing code.",
    "baoyu-infographic": "Purpose: turn text, files, URLs, or topics into infographics and visual summaries. Main features: analyze content, structure information, choose layouts and styles, and generate prompts/images. Requirements: requires an image generation tool; inputs are user-provided and generation uses layout/style references. Best for infographics, visual summaries, dense information posters, and education/product visuals.",
    "github-auth": "Purpose: configure GitHub authentication. Main features: check git/gh login, guide HTTPS tokens, SSH keys, gh auth login, Git identity, and API token setup. Requirements: requires git; gh CLI is optional; requires a GitHub account and PAT or SSH key. Best for enabling Hermes to access repos, push commits, and work with PRs, issues, and CI.",
    "github-code-review": "Purpose: review local changes or GitHub PRs. Main features: read diffs, stats, logs, inspect files, find security/quality issues, view or checkout PRs, and post comments/reviews. Requirements: requires GitHub authentication and a git repo; PR API operations need gh or GITHUB_TOKEN/curl. Best for pre-commit review, PR review, and quality/security checks.",
    "github-issues": "Purpose: create, search, triage, and manage GitHub issues. Main features: view issues, create bug/feature templates, add/remove labels, assign users, comment, close, and reopen. Requirements: requires GitHub authentication; requires a git repo with GitHub remote or an explicit repo; can use gh or GITHUB_TOKEN/curl. Best for bug tracking, request management, triage, and project maintenance.",
    "github-pr-workflow": "Purpose: manage the GitHub PR lifecycle. Main features: create branches, commit, push, open PRs, monitor CI, diagnose failures, update PRs, and merge. Requirements: requires GitHub authentication and a git repo with a GitHub remote; can use gh or git plus GITHUB_TOKEN/curl. Best for the full branch-to-PR-to-CI-to-merge workflow.",
    "github-repo-management": "Purpose: manage GitHub repositories. Main features: clone, create, fork, sync forks, view repo info, manage remotes, releases, and configuration. Requirements: requires GitHub authentication; can use gh or git plus GITHUB_TOKEN/curl. Best for project initialization, repo maintenance, fork/upstream workflows, releases, and repo configuration.",
    "obsidian": "Purpose: read and maintain an Obsidian vault. Main features: read, list, search, create, append, and edit Markdown notes, plus add wikilinks. Requirements: requires a known vault path; docs use OBSIDIAN_VAULT_PATH, falling back to ~/Documents/Obsidian Vault. Best for knowledge-base organization, note search, and creating/updating Obsidian Markdown content.",
    "hermes-agent-skill-authoring": "Purpose: author and maintain in-repo Hermes Agent SKILL.md files. Main features: frontmatter rules, placement, structure, writing quality, validation checklist, editing workflow, and pitfalls. Requirements: requires working in the Hermes Agent repo; new/edited skills should be validated and committed. Best for adding shipped skills, editing built-in skills, and keeping skill docs consistent.",
    "plan": "Purpose: create an actionable Markdown plan when execution is not requested. Main features: avoid implementation and write goals, approach, steps, files, tests, and risks under .hermes/plans/. Requirements: no obvious external dependency found; needs a writable workspace for the plan file. Best for complex task breakdowns, pre-implementation design, and handoff to later execution.",
    "simplify-code": "Purpose: review recent code changes in parallel and clean up worthwhile issues. Main features: review diff for reuse, quality, and efficiency; aggregate findings; separate safe/careful/risky fixes; verify changes. Requirements: needs a git repo with a reviewable diff; docs mention parallel subtask capability. Best for pre-commit cleanup, reducing duplication, improving quality, and spotting performance/error-handling issues.",
    "spike": "Purpose: validate an idea with disposable experiments. Main features: split into 2-5 feasibility questions, research, build runnable prototypes, and record VALIDATED/PARTIAL/INVALIDATED verdicts. Requirements: no fixed external dependency found; specific experiments may need their own libraries, tools, or web research. Best for uncertain approaches, technical comparisons, and risk validation before a real build.",
    "systematic-debugging": "Purpose: find root causes with a four-phase debugging process. Main features: build a reproducible feedback loop, read errors, inspect changes, gather evidence, analyze patterns, test falsifiable hypotheses, fix, and verify. Requirements: no fixed external dependency found; usually needs runnable tests, commands, or reproduction scripts. Best for test failures, production bugs, build failures, performance issues, and repeated failed fixes.",
    "test-driven-development": "Purpose: enforce TDD for features, fixes, and refactors. Main features: write a failing test first, verify RED, implement minimally, verify GREEN, then refactor; avoids horizontal test piles. Requirements: no fixed external dependency found; requires a runnable automated test environment. Best for new features, bug fixes, behavior changes, and high-confidence refactoring.",
}

BUILTIN_DESCRIPTION_HINTS: Dict[str, str] = {
    "airtable": "通过 Airtable REST API 管理记录，支持增删改查、筛选和 upsert。",
    "apple-notes": "通过 memo CLI 管理 Apple Notes，支持创建、搜索和编辑笔记。",
    "apple-reminders": "通过 remindctl 管理 Apple Reminders，支持添加、列出和完成提醒。",
    "architecture-diagram": "生成深色主题 SVG/HTML 架构、云和基础设施图。",
    "arxiv": "按关键词、作者、分类或 ID 搜索 arXiv 论文。",
    "ascii-art": "使用 pyfiglet、cowsay、boxes 或图片转换生成 ASCII 艺术。",
    "ascii-video": "把视频或音频转换成彩色 ASCII MP4/GIF。",
    "audiocraft-audio-generation": "使用 AudioCraft 的 MusicGen 和 AudioGen 生成音乐或音效。",
    "blogwatcher": "通过 blogwatcher-cli 监控博客和 RSS/Atom 订阅源。",
    "claude-code": "把功能开发和 PR 编码任务委托给 Claude Code CLI。",
    "claude-design": "设计一次性 HTML 产物，例如落地页、演示稿和原型。",
    "codebase-inspection": "通过 pygount 检查代码库行数、语言和比例。",
    "codex": "把功能开发和 PR 编码任务委托给 OpenAI Codex CLI。",
    "comfyui": "使用 ComfyUI 生成图片、视频和音频，并管理节点、模型和工作流。",
    "design-md": "编写、校验和导出 Google DESIGN.md token 规范文件。",
    "evaluating-llms-harness": "使用 lm-eval-harness 对 LLM 运行 MMLU、GSM8K 等基准评测。",
    "excalidraw": "生成手绘风格 Excalidraw JSON 架构图、流程图和序列图。",
    "findmy": "在 macOS 上通过 FindMy.app 跟踪 Apple 设备和 AirTag。",
    "gif-search": "通过 Tenor、curl 和 jq 搜索或下载 GIF。",
    "google-workspace": "通过 gws CLI 或 Python 操作 Gmail、Calendar、Drive、Docs 和 Sheets。",
    "heartmula": "根据歌词和标签用 HeartMuLa 生成歌曲。",
    "himalaya": "通过 Himalaya CLI 使用 IMAP/SMTP 收发和管理邮件。",
    "huggingface-hub": "通过 Hugging Face hf CLI 搜索、下载和上传模型或数据集。",
    "humanizer": "改写文本，去除 AI 腔并加入更自然的表达。",
    "imessage": "在 macOS 上通过 imsg CLI 发送和接收 iMessage/SMS。",
    "jupyter-live-kernel": "通过实时 Jupyter kernel 持续迭代 Python 代码。",
    "llama-cpp": "使用 llama.cpp 运行本地 GGUF 推理并发现 Hugging Face 模型。",
    "llm-wiki": "构建和查询互联 Markdown 知识库。",
    "manim-video": "用 Manim CE 制作数学、算法和讲解动画。",
    "maps": "通过 OpenStreetMap/OSRM 查询地理编码、POI、路线和时区。",
    "nano-pdf": "通过 nano-pdf CLI 用自然语言修改 PDF 文本、错别字和标题。",
    "node-inspect-debugger": "通过 --inspect 和 Chrome DevTools Protocol CLI 调试 Node.js。",
    "notion": "通过 Notion API 和 ntn CLI 管理页面、数据库、Markdown 和 Workers。",
    "ocr-and-documents": "使用 pymupdf、marker-pdf 等从 PDF 或扫描件提取文本。",
    "opencode": "把功能开发和 PR Review 委托给 OpenCode CLI。",
    "openhue": "通过 OpenHue CLI 控制 Philips Hue 灯、场景和房间。",
    "p5js": "创作 p5.js 生成艺术、shader、交互、3D 和浏览器视觉作品。",
    "petdex": "安装和选择 Hermes 动画 petdex mascots。",
    "polymarket": "查询 Polymarket 市场、价格、订单簿和历史数据。",
    "popular-web-designs": "参考 54 个真实设计系统的 HTML/CSS 风格样例。",
    "powerpoint": "创建、读取和编辑 .pptx 幻灯片、备注和模板。",
    "pretext": "用 @chenglou/pretext 构建文字布局、ASCII 艺术和动态排版浏览器 demo。",
    "python-debugpy": "通过 pdb REPL 和 debugpy 远程 DAP 调试 Python。",
    "requesting-code-review": "执行提交前代码审查、安全扫描、质量门禁和自动修复。",
    "research-paper-writing": "辅助撰写面向 NeurIPS、ICML、ICLR 的机器学习论文。",
    "segment-anything-model": "使用 SAM 通过点、框和 mask 做零样本图像分割。",
    "serving-llms-vllm": "使用 vLLM 部署高吞吐 LLM 服务、OpenAI API 和量化推理。",
    "sketch": "快速制作 2-3 个一次性 HTML 设计草图用于比较。",
    "songsee": "通过 CLI 分析音频频谱和 mel、chroma、MFCC 等特征。",
    "songwriting-and-ai-music": "辅助歌曲创作和 Suno AI 音乐提示词编写。",
    "teams-meeting-pipeline": "通过 Hermes CLI 操作 Teams 会议摘要流水线和 Microsoft Graph 订阅。",
    "touchdesigner-mcp": "通过 twozero MCP 控制 TouchDesigner，创建 operator、连线和实时视觉。",
    "weights-and-biases": "使用 W&B 记录机器学习实验、sweeps、模型注册和仪表盘。",
    "xurl": "通过 xurl CLI 操作 X/Twitter 发帖、搜索、私信、媒体和 v2 API。",
    "youtube-content": "把 YouTube 字幕转换成摘要、线程和博客内容。",
    "yuanbao": "操作元宝群组，支持 @mention 用户以及查询信息和成员。",
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
    data.setdefault("knownBundledSkills", {})
    if not isinstance(data["history"], list):
        data["history"] = []
    if not isinstance(data["knownBundledSkills"], dict):
        data["knownBundledSkills"] = {}
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


def _record_known_bundled(state: Dict[str, Any], bundled: List[Tuple[str, Path, str]]) -> None:
    known = state.setdefault("knownBundledSkills", {})
    changed = False
    for name, _skill_dir, install_path in bundled:
        category = str(Path(install_path).parent)
        if category == ".":
            category = ""
        existing = known.get(name)
        next_value = {
            "name": name,
            "category": category,
            "installPath": install_path,
            "firstSeenAt": _now(),
        }
        if not isinstance(existing, dict):
            known[name] = next_value
            changed = True
        else:
            merged = dict(existing)
            merged.update({key: value for key, value in next_value.items() if key != "firstSeenAt"})
            if merged != existing:
                known[name] = merged
                changed = True
    if changed:
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


def _bundled_skills() -> List[Tuple[str, Path, str]]:
    try:
        from tools.skills_sync import _compute_relative_dest, _discover_bundled_skills, _get_bundled_dir
        bundled_dir = _get_bundled_dir()
        rows = []
        for name, skill_dir in _discover_bundled_skills(bundled_dir):
            install_path = _compute_relative_dest(skill_dir, bundled_dir).relative_to(_skills_dir()).as_posix()
            rows.append((name, skill_dir, install_path))
        return rows
    except Exception:
        return []


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


def _read_skill_description(skill_dir: Path) -> str:
    try:
        from tools.skills_tool import _parse_frontmatter
        content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        frontmatter, _body = _parse_frontmatter(content)
        return str(frontmatter.get("description", "") or "")
    except Exception:
        return ""


def _builtin_description(name: str, fallback: str = "") -> str:
    if name in BUILTIN_DESCRIPTIONS:
        return BUILTIN_DESCRIPTIONS[name]
    if name in BUILTIN_DESCRIPTION_HINTS:
        return f"用途：{BUILTIN_DESCRIPTION_HINTS[name]}主要功能：见 bundled SKILL.md 文档。依赖要求：未在简介中发现明确依赖；具体以该技能文档为准。适用场景：{BUILTIN_DESCRIPTION_HINTS[name]}"
    if fallback:
        return f"用途：{fallback} 主要功能：见 bundled SKILL.md 文档。依赖要求：未在简介中发现明确依赖；具体以该技能文档为准。适用场景：需要使用该内建技能能力时。"
    return "用途：内建 Hermes 技能。主要功能：见 bundled SKILL.md 文档。依赖要求：未发现明显依赖。适用场景：需要恢复并使用该内建技能时。"


def _builtin_description_en(name: str, fallback: str = "") -> str:
    if name in BUILTIN_DESCRIPTIONS_EN:
        return BUILTIN_DESCRIPTIONS_EN[name]
    if fallback:
        return fallback
    if name in BUILTIN_DESCRIPTION_HINTS:
        return BUILTIN_DESCRIPTION_HINTS[name]
    return "Built-in Hermes skill. See bundled SKILL.md for full usage, requirements, and workflow details."


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


def _skill_row(skill: Dict[str, Any], hub: Dict[str, Dict[str, Any]], builtin: set[str], disabled: set[str], bundled_names: set[str]) -> Dict[str, Any]:
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
    elif name in builtin and name in bundled_names:
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

    description_en = skill.get("description", "") or ""
    description = description_en
    if kind == "builtin":
        description = _builtin_description(name, description_en)
        description_en = _builtin_description_en(name, description_en)

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
        "descriptionZh": description,
        "descriptionEn": description_en,
        "installedAt": installed_at,
        "updatedAt": updated_at,
    }


def _inventory_rows(bundled_names: set[str]) -> List[Dict[str, Any]]:
    hub = _hub_by_name()
    builtin = _builtin_names()
    disabled = _disabled_names()
    rows = [_skill_row(skill, hub, builtin, disabled, bundled_names) for skill in _all_skills()]
    return sorted(rows, key=lambda row: (row.get("category") or "", row["name"]))


def _split_orphaned_builtin_rows(rows: List[Dict[str, Any]], bundled_names: set[str], state: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    known = state.get("knownBundledSkills", {})
    if not isinstance(known, dict):
        return rows, []
    active: List[Dict[str, Any]] = []
    orphaned: List[Dict[str, Any]] = []
    for row in rows:
        name = row["name"]
        was_bundled = name in known
        currently_bundled = name in bundled_names
        if was_bundled and not currently_bundled and row.get("kind") in {"local", "builtin"}:
            meta = known.get(name) if isinstance(known.get(name), dict) else {}
            next_row = dict(row)
            next_row.update({
                "kind": "orphaned-builtin",
                "source": "orphaned-builtin",
                "rawSource": "orphaned-builtin",
                "trustLevel": "deprecated",
                "status": "deprecated",
                "officialStatus": "removed-upstream",
                "canRestore": False,
                "previousBuiltinPath": meta.get("installPath", row.get("installPath", "")),
            })
            orphaned.append(next_row)
        else:
            active.append(row)
    return active, sorted(orphaned, key=lambda row: (row.get("category") or "", row["name"]))


def _missing_builtin_rows(current_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    current_names = {row["name"] for row in current_rows}
    rows: List[Dict[str, Any]] = []
    for name, skill_dir, install_path in _bundled_skills():
        if name in current_names:
            continue
        category = str(Path(install_path).parent)
        if category == ".":
            category = ""
        description = _builtin_description(name, _read_skill_description(skill_dir))
        description_en = _builtin_description_en(name, _read_skill_description(skill_dir))
        rows.append({
            "name": name,
            "category": category,
            "kind": "builtin",
            "source": "builtin",
            "rawSource": "builtin",
            "trustLevel": "builtin",
            "status": "deleted",
            "installPath": install_path,
            "identifier": f"bundled/{install_path}",
            "description": description,
            "descriptionZh": description,
            "descriptionEn": description_en,
            "installedAt": "",
            "updatedAt": "",
            "canRestore": True,
        })
    return sorted(rows, key=lambda row: (row.get("category") or "", row["name"]))


def _find_skill(source: str, name: str) -> Dict[str, Any]:
    bundled = _bundled_skills()
    bundled_names = {item[0] for item in bundled}
    state = _load_state()
    rows, orphaned = _split_orphaned_builtin_rows(_inventory_rows(bundled_names), bundled_names, state)
    for row in rows + orphaned:
        if (row.get("kind") or row["source"]) == source and row["name"] == name:
            return row
    raise HTTPException(status_code=404, detail=f"未找到技能：{source}:{name}")


def _find_missing_builtin(name: str) -> Dict[str, Any]:
    bundled = _bundled_skills()
    bundled_names = {item[0] for item in bundled}
    rows = _inventory_rows(bundled_names)
    for row in _missing_builtin_rows(rows):
        if row["name"] == name:
            return row
    raise HTTPException(status_code=404, detail=f"未找到可恢复的内建技能：{name}")


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
    bundled = _bundled_skills()
    bundled_names = {item[0] for item in bundled}
    state = _load_state()
    _record_known_bundled(state, bundled)
    state = _load_state()
    rows, orphaned_builtin = _split_orphaned_builtin_rows(_inventory_rows(bundled_names), bundled_names, state)
    missing_builtin = _missing_builtin_rows(rows)
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
    return {
        "ok": True,
        "skills": rows,
        "missingBuiltinSkills": missing_builtin,
        "orphanedBuiltinSkills": orphaned_builtin,
        "counts": counts,
        "missingBuiltinCount": len(missing_builtin),
        "orphanedBuiltinCount": len(orphaned_builtin),
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


@router.post("/restore")
async def restore_builtin(action: SkillAction) -> Dict[str, Any]:
    row = _find_missing_builtin(action.name)
    try:
        from tools.skills_sync import reset_bundled_skill
        result = reset_bundled_skill(row["name"], restore=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("message", "恢复内建技能失败"))
    _clear_skill_cache()
    _history({"action": "restore", "source": "builtin", "name": row["name"]})
    return {"ok": True, "skill": row, "result": result}


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
