# 技能管理

`技能管理` 是 Hermes Dashboard 插件，用来按来源查看和管理 `~/.hermes/skills`
下的技能。

## 功能

- 按来源统计和筛选技能：`builtin`、`hub-installed`、`local`
- 列表展示对齐 `hermes skills list`：`Name`、`Category`、`Source`、`Trust`、`Status`
- 每个技能后面显示操作列
- 搜索技能名称、分类、来源、信任级别和状态
- 对 `builtin` 技能执行删除和重置
- 对 `hub-installed` 技能执行删除、重置和更新
- 对 `local` 技能执行删除
- 从 hub、URL、仓库或 optional catalog 安装技能

## 操作规则

- `builtin` 删除：直接物理删除对应技能目录。
- `builtin` 重置：从 Hermes agent 内置技能来源复制并覆盖。
- `hub-installed` 删除：使用 Hermes hub 卸载流程。
- `hub-installed` 重置：按原来源标识强制重新安装。
- `hub-installed` 更新：使用 Hermes hub 更新流程。
- `local` 删除：直接物理删除对应技能目录。
- 删除操作必须二次确认，并输入完整技能名。

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

- 删除操作必须输入完整技能名确认，避免误点。
- 所有技能路径都会校验在 `~/.hermes/skills` 内，避免路径逃逸。
- 当前版本不做删除备份；删除成功后即从磁盘移除。

## 名称

- Dashboard 菜单名称：`技能管理`
- Dashboard 插件 ID：`skill-manage`
- 安装目录：`~/.hermes/plugins/skill-vault`
