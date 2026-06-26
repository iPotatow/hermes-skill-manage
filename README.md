# Skill manage（技能管理）

`Skill manage（技能管理）` 是 Hermes Dashboard 插件，用来按来源查看和管理
`~/.hermes/skills` 下的技能。

## 功能

- 按来源统计和筛选技能：`builtin`、`hub-installed`、`local`
- 按分类目录筛选技能
- 搜索技能名称、路径、描述和来源标识
- 查看技能详情、`SKILL.md` 内容和文件列表
- 对 `builtin` 技能执行重置
- 对 `hub-installed` 技能执行强制重新安装
- 删除非内置技能，并自动备份到插件的 `trash/` 目录
- 从删除备份恢复技能
- 从 hub、URL、仓库或 optional catalog 安装技能

## Dashboard 文件

```text
~/.hermes/plugins/skill-vault/
└── dashboard/
    ├── manifest.json
    ├── plugin_api.py
    └── dist/
        ├── index.js
        └── style.css
```

启动 Dashboard：

```bash
hermes dashboard --port 9119
```

如果只修改了前端静态文件，可以让 Dashboard 重新扫描：

```bash
curl http://127.0.0.1:9119/api/dashboard/plugins/rescan
```

如果修改了 `dashboard/plugin_api.py`，需要重启 Dashboard，后端路由才会重新挂载。

## 安全策略

- `builtin` 技能在当前 Dashboard 版本中禁止删除。
- 删除操作必须输入完整技能名确认。
- 非内置技能删除前会复制到 `trash/`，可在 Dashboard 中恢复。
- 所有技能路径都会校验在 `~/.hermes/skills` 内，避免路径逃逸。

## 名称

- Dashboard 菜单名称：`技能管理`
- Dashboard 插件 ID：`skill-manage`
- 安装目录：`~/.hermes/plugins/skill-vault`
