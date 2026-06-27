(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;

  const React = SDK.React;
  const h = React.createElement;
  const hooks = SDK.hooks || React;
  const useState = hooks.useState;
  const useEffect = hooks.useEffect;
  const useMemo = hooks.useMemo;
  const useCallback = hooks.useCallback;
  const useHostI18n = typeof SDK.useI18n === "function" ? SDK.useI18n : function () {
    return { locale: document.documentElement.lang || navigator.language || "en" };
  };

  const C = SDK.components || {};
  const Input = C.Input || function (props) { return h("input", props); };
  const Card = C.Card || function (props) { return h("section", props, props.children); };
  const CardContent = C.CardContent || function (props) { return h("div", props, props.children); };

  const API = "/api/plugins/skill-manage";
  const SOURCE_ORDER = ["all", "builtin", "hub-installed", "local"];
  const TEXT = {
    en: {
      unknownError: "Unknown error",
      sourceLabels: { all: "All", builtin: "Built-in", "hub-installed": "Community", local: "Local" },
      stats: { "hub-installed": "Community", builtin: "Built-in", local: "Local", enabled: "Enabled" },
      searchPlaceholder: "Search name",
      allCategories: "all categories",
      showDeletedBuiltin: "Show deleted built-ins",
      showDeletedBuiltinTitle: "Hidden by default; enable to show built-in skills that can be restored from the Hermes bundled source.",
      refresh: "Refresh",
      refreshing: "Refreshing",
      empty: "No matching skills",
      installedSkills: "Installed Skills",
      columns: { name: "Name", category: "Category", source: "Source", trust: "Trust", status: "Status", actions: "Actions" },
      noDescription: "No description",
      actions: { delete: "Delete", reset: "Reset", update: "Update", restore: "Restore" },
      deleting: "Deleting",
      confirmTitle: "Delete skill",
      confirmBody: function (name) { return "This permanently removes the local skill files for " + name + ". Type the skill name to confirm."; },
      confirmNameLabel: "Skill name",
      confirmPlaceholder: "Type the exact skill name",
      close: "Close",
      cancel: "Cancel",
      notices: {
        deleted: function (name) { return "Deleted: " + name; },
        reset: function (name) { return "Reset: " + name; },
        updated: function (name) { return "Updated: " + name; },
        restored: function (name) { return "Restored: " + name; },
      },
      heroKickerFallback: "Hermes skills directory",
      title: "Skill Manage",
      subtitle: "Manage Hermes skills by source; deleted built-in skills are hidden by default and can be shown when you need to restore them.",
      recentTitle: "Recent actions",
      recentHint: "Last 8 management actions",
    },
    zh: {
      unknownError: "未知错误",
      sourceLabels: { all: "全部", builtin: "内建", "hub-installed": "社区", local: "本地" },
      stats: { "hub-installed": "社区", builtin: "内建", local: "本地", enabled: "启用" },
      searchPlaceholder: "搜索名称",
      allCategories: "全部分类",
      showDeletedBuiltin: "显示已删除内建",
      showDeletedBuiltinTitle: "默认隐藏；开启后显示可从 Hermes bundled 源恢复的内建技能。",
      refresh: "刷新",
      refreshing: "刷新中",
      empty: "没有匹配的技能",
      installedSkills: "技能清单",
      columns: { name: "名称", category: "分类", source: "来源", trust: "信任", status: "状态", actions: "操作" },
      noDescription: "无简介",
      actions: { delete: "删除", reset: "重置", update: "更新", restore: "恢复" },
      deleting: "删除中",
      confirmTitle: "删除技能",
      confirmBody: function (name) { return "这会永久删除 " + name + " 的本地技能文件。请输入完整技能名确认。"; },
      confirmNameLabel: "技能名",
      confirmPlaceholder: "输入完整技能名",
      close: "关闭",
      cancel: "取消",
      notices: {
        deleted: function (name) { return "已删除：" + name; },
        reset: function (name) { return "已重置：" + name; },
        updated: function (name) { return "已更新：" + name; },
        restored: function (name) { return "已恢复：" + name; },
      },
      heroKickerFallback: "Hermes 技能目录",
      title: "技能管理",
      subtitle: "按来源管理 Hermes 技能；已删除的内建技能默认隐藏，可按需显示并恢复。",
      recentTitle: "最近操作",
      recentHint: "最近 8 条管理动作",
    },
  };

  function languageFromLocale(locale) {
    const raw = String(locale || "").toLowerCase();
    return raw.indexOf("zh") === 0 ? "zh" : "en";
  }

  function api(path, options) {
    if (SDK.fetchJSON) return SDK.fetchJSON(API + path, options);
    const opts = Object.assign({ credentials: "same-origin" }, options || {});
    if (opts.body && typeof opts.body !== "string") {
      opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
      opts.body = JSON.stringify(opts.body);
    }
    return fetch(API + path, opts).then(function (res) {
      return res.text().then(function (text) {
        if (!res.ok) throw new Error(text || res.statusText);
        return text ? JSON.parse(text) : {};
      });
    });
  }

  function cx() {
    return Array.prototype.slice.call(arguments).filter(Boolean).join(" ");
  }

  function parseError(err, text) {
    const raw = err && err.message ? String(err.message) : String(err || (text && text.unknownError) || "Unknown error");
    function stringifyDetail(detail) {
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        return detail.map(function (item) {
          if (!item || typeof item !== "object") return String(item);
          return item.msg || item.message || JSON.stringify(item);
        }).join("; ");
      }
      if (detail && typeof detail === "object") return detail.msg || detail.message || JSON.stringify(detail);
      return String(detail || raw);
    }
    try {
      const parsed = JSON.parse(raw.replace(/^\d+:\s*/, ""));
      return parsed.detail ? stringifyDetail(parsed.detail) : raw;
    } catch (_e) {
      return raw;
    }
  }

  function Button(props) {
    return h("button", Object.assign({}, props, {
      type: props.type || "button",
      className: cx("sm-btn", props.kind === "danger" && "sm-btn--danger", props.kind === "quiet" && "sm-btn--quiet", props.className),
    }), props.children);
  }

  function Pill(props) {
    return h("span", { className: cx("sm-pill", "sm-pill--" + (props.tone || "default")) }, props.children);
  }

  function sourceLabel(source, text) {
    if (text.sourceLabels[source]) return text.sourceLabels[source];
    return source;
  }

  function normalizeSource(row) {
    const kind = String(row.kind || "").toLowerCase();
    const source = String(row.source || "").toLowerCase();
    const trust = String(row.trustLevel || row.trust || "").toLowerCase();
    const raw = String(row.rawSource || row.source || "").toLowerCase();
    if (kind) return kind;
    if (source === "builtin") return "builtin";
    if (source === "local" && trust === "local") return "local";
    if (source === "hub-installed") return "hub-installed";
    if (trust === "community" || trust === "official") return "hub-installed";
    if (raw && raw !== "local" && raw !== "builtin") return "hub-installed";
    return source || "local";
  }

  function normalizeRows(rows) {
    return rows.map(function (row) {
      const kind = normalizeSource(row);
      const displaySource = row.source === "hub-installed"
        ? (row.rawSource || "hub")
        : (row.source || row.rawSource || kind);
      return Object.assign({}, row, {
        kind: kind,
        source: displaySource,
        rawSource: row.rawSource || displaySource,
        trustLevel: row.trustLevel || row.trust || (kind === "hub-installed" ? "community" : kind),
        status: row.status || (row.enabled === false ? "disabled" : "enabled"),
      });
    });
  }

  function countRows(rows) {
    return rows.reduce(function (acc, row) {
      acc[row.kind] = (acc[row.kind] || 0) + 1;
      return acc;
    }, {});
  }

  function SourceTabs(props) {
    return h("div", { className: "sm-source-tabs", "aria-label": props.text.columns.source },
      SOURCE_ORDER.map(function (source) {
        return h("button", {
          key: source,
          type: "button",
          className: cx("sm-source", props.source === source && "sm-source--active"),
          onClick: function () { props.setSource(source); },
        },
          h("span", null, sourceLabel(source, props.text))
        );
      })
    );
  }

  function StatStrip(props) {
    const items = [
      ["hub-installed", props.counts["hub-installed"] || 0, props.text.stats["hub-installed"]],
      ["builtin", props.counts.builtin || 0, props.text.stats.builtin],
      ["local", props.counts.local || 0, props.text.stats.local],
      ["enabled", props.enabled || 0, props.text.stats.enabled],
    ];
    return h("div", { className: "sm-stat-strip" },
      items.map(function (item) {
        return h("div", { className: "sm-stat", key: item[0] },
          h("span", null, item[2]),
          h("strong", null, item[1]),
          h("i", null, item[0])
        );
      })
    );
  }

  function Toolbar(props) {
    return h("div", { className: "sm-toolbar" },
      h(SourceTabs, {
        source: props.source,
        setSource: props.setSource,
        text: props.text,
      }),
      h("select", {
        className: "sm-select",
        value: props.category,
        onChange: function (e) { props.setCategory(e.target.value); },
      }, props.categories.map(function (category) {
        return h("option", { key: category, value: category }, category === "all" ? props.text.allCategories : category);
      })),
      h(Input, {
        className: "sm-input",
        value: props.query,
        onChange: function (e) { props.setQuery(e.target.value); },
        placeholder: props.text.searchPlaceholder,
      }),
      h("span", { className: "sm-result-count" }, props.filtered + " / " + props.total),
      h("label", { className: "sm-toggle", title: props.text.showDeletedBuiltinTitle },
        h("input", {
          type: "checkbox",
          checked: props.showMissingBuiltin,
          onChange: function (e) { props.setShowMissingBuiltin(e.target.checked); },
        }),
        h("span", null, props.text.showDeletedBuiltin),
        h("code", null, props.missingBuiltinCount || 0)
      ),
      h(Button, { onClick: props.onRefresh, disabled: props.loading }, props.loading ? props.text.refreshing : props.text.refresh)
    );
  }

  function DeleteConfirmDialog(props) {
    const [value, setValue] = useState("");
    const row = props.row;

    useEffect(function () {
      setValue("");
    }, [row && row.name]);

    if (!row) return null;
    const canConfirm = value === row.name && !props.busy;

    function onKeyDown(e) {
      if (e.key === "Escape") {
        if (!props.busy) props.onCancel();
        return;
      }
      if (e.key === "Enter" && canConfirm) {
        props.onConfirm(value);
      }
    }

    return h("div", {
      className: "sm-modal-backdrop",
      role: "presentation",
      onMouseDown: function (e) {
        if (!props.busy && e.target === e.currentTarget) props.onCancel();
      },
    },
      h("div", {
        className: "sm-modal",
        role: "dialog",
        "aria-modal": "true",
        "aria-labelledby": "sm-delete-title",
        onKeyDown: onKeyDown,
        onMouseDown: function (e) { e.stopPropagation(); },
      },
        h("div", { className: "sm-modal__head" },
          h("h3", { id: "sm-delete-title" }, props.text.confirmTitle),
          h("button", { type: "button", className: "sm-modal__close", onClick: props.onCancel, disabled: props.busy, "aria-label": props.text.close }, "×")
        ),
        h("p", { className: "sm-modal__body" }, props.text.confirmBody(row.name)),
        h("div", { className: "sm-modal__target" },
          h("span", null, row.name),
          h("code", null, row.kind)
        ),
        h("label", { className: "sm-modal__field" },
          h("span", null, props.text.confirmNameLabel),
          h(Input, {
            autoFocus: true,
            className: "sm-input",
            value: value,
            onChange: function (e) { setValue(e.target.value); },
            placeholder: props.text.confirmPlaceholder,
            disabled: props.busy,
          })
        ),
        h("div", { className: "sm-modal__actions" },
          h(Button, { kind: "quiet", onClick: props.onCancel, disabled: props.busy }, props.text.cancel),
          h(Button, { kind: "danger", onClick: function () { props.onConfirm(value); }, disabled: !canConfirm || props.busy }, props.busy ? props.text.deleting : props.text.actions.delete)
        )
      )
    );
  }

  function SkillsTable(props) {
    if (!props.rows.length) {
      return h("div", { className: "sm-empty" }, props.text.empty);
    }

    function run(row, action) {
      if (action === "delete") {
        props.onDeleteRequest(row);
        return;
      }
      if (action === "reset") {
        props.onAction("/reset", { source: row.kind, name: row.name }, props.text.notices.reset(row.name));
        return;
      }
      if (action === "update") {
        props.onAction("/update", { source: row.kind, name: row.name }, props.text.notices.updated(row.name));
        return;
      }
      if (action === "restore") {
        props.onAction("/restore", { source: "builtin", name: row.name }, props.text.notices.restored(row.name));
      }
    }

    return h("div", { className: "sm-table-wrap" },
      h("table", { className: "sm-table" },
        h("caption", null, props.text.installedSkills + " · " + props.rows.length),
        h("thead", null,
          h("tr", null,
            h("th", null, props.text.columns.name),
            h("th", null, props.text.columns.category),
            h("th", null, props.text.columns.source),
            h("th", null, props.text.columns.trust),
            h("th", null, props.text.columns.status),
            h("th", { className: "sm-actions-head" }, props.text.columns.actions)
          )
        ),
        h("tbody", null,
          props.rows.map(function (row) {
            const busy = props.busyKey === row.kind + ":" + row.name;
            const deleted = row.status === "deleted";
            const description = props.lang === "zh" ? (row.descriptionZh || row.description) : (row.descriptionEn || row.description);
            return h("tr", { key: row.kind + ":" + row.name },
              h("td", { className: "sm-name", title: row.installPath },
                h("strong", null, row.name),
                description ? h("span", null, description) : h("span", { className: "sm-name__empty" }, props.text.noDescription)
              ),
              h("td", { className: "sm-dim" }, row.category || ""),
              h("td", null, h(Pill, { tone: row.kind, title: row.kind }, row.source)),
              h("td", { className: "sm-dim" }, row.trustLevel || "-"),
              h("td", null, h(Pill, { tone: deleted ? "deleted" : row.status === "enabled" ? "enabled" : "disabled" }, row.status || "enabled")),
              h("td", { className: "sm-actions-cell" },
                h("div", { className: "sm-actions" },
                  deleted ? h(Button, { disabled: busy, onClick: function () { run(row, "restore"); } }, props.text.actions.restore) : null,
                  !deleted && row.kind === "builtin" ? h(Button, { disabled: busy, onClick: function () { run(row, "reset"); } }, props.text.actions.reset) : null,
                  !deleted && row.kind === "hub-installed" ? h(Button, { disabled: busy, onClick: function () { run(row, "reset"); } }, props.text.actions.reset) : null,
                  !deleted && row.kind === "hub-installed" ? h(Button, { disabled: busy, onClick: function () { run(row, "update"); } }, props.text.actions.update) : null,
                  !deleted ? h(Button, { kind: "danger", disabled: busy, onClick: function () { run(row, "delete"); } }, props.text.actions.delete) : null
                )
              )
            );
          })
        )
      )
    );
  }

  function HistoryPanel(props) {
    if (!props.history.length) return null;
    return h(Card, { className: "sm-card" }, h(CardContent, { className: "sm-card__content" },
      h("div", { className: "sm-card__head" },
        h("div", null, h("h3", null, props.text.recentTitle), h("p", null, props.text.recentHint))
      ),
      h("div", { className: "sm-history" },
        props.history.slice(0, 8).map(function (item, index) {
          return h("div", { className: "sm-history__row", key: index },
            h("strong", null, item.action || "-"),
            h("span", null, [item.source, item.name].filter(Boolean).join(" / ") || "-"),
            h("time", null, item.at || "")
          );
        })
      )
    ));
  }

  function SkillManagePage() {
    const hostI18n = useHostI18n() || {};
    const lang = languageFromLocale(hostI18n.locale);
    const text = TEXT[lang];
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [query, setQuery] = useState("");
    const [source, setSource] = useState("all");
    const [category, setCategory] = useState("all");
    const [toast, setToast] = useState(null);
    const [busyKey, setBusyKey] = useState("");
    const [pendingDelete, setPendingDelete] = useState(null);
    const [showMissingBuiltin, setShowMissingBuiltin] = useState(false);

    const load = useCallback(function () {
      setLoading(true);
      return api("/inventory").then(function (next) {
        setData(next);
        return next;
      }).catch(function (err) {
        setToast({ text: parseError(err, text), error: true });
      }).finally(function () {
        setLoading(false);
      });
    }, [text]);

    useEffect(function () { load(); }, [load]);

    function notice(text, error) {
      setToast({ text: text, error: !!error });
      setTimeout(function () { setToast(null); }, 4500);
    }

    function onAction(path, body, successText, after) {
      const key = body.source && body.name ? body.source + ":" + body.name : "";
      setBusyKey(key);
      api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(function () {
        notice(successText);
        if (after) after();
        return load();
      }).catch(function (err) {
        const message = parseError(err, text);
        if (path === "/delete" && /failed to fetch/i.test(message)) {
          return load().then(function (next) {
            if (!next || !Array.isArray(next.skills)) {
              notice(message, true);
              return;
            }
            const rows = next.skills;
            const stillExists = rows.some(function (row) {
              return (row.kind || row.source) === body.source && row.name === body.name;
            });
            if (!stillExists) {
              notice(successText);
              if (after) after();
              return;
            }
            notice(message, true);
          });
        }
        notice(message, true);
      }).finally(function () {
        setBusyKey("");
      });
    }

    const rawRows = data && data.skills ? data.skills : [];
    const rawMissingBuiltin = data && data.missingBuiltinSkills ? data.missingBuiltinSkills : [];
    const installedRows = useMemo(function () { return normalizeRows(rawRows); }, [rawRows]);
    const missingBuiltinRows = useMemo(function () { return normalizeRows(rawMissingBuiltin); }, [rawMissingBuiltin]);
    const rows = useMemo(function () {
      let next = installedRows;
      if (showMissingBuiltin) next = next.concat(missingBuiltinRows);
      return next;
    }, [installedRows, missingBuiltinRows, showMissingBuiltin]);
    const counts = useMemo(function () { return countRows(installedRows); }, [installedRows]);
    const enabledCount = installedRows.filter(function (row) { return row.status !== "disabled"; }).length;
    const categories = useMemo(function () {
      const set = new Set(["all"]);
      rows.forEach(function (row) { set.add(row.category || "(root)"); });
      return Array.from(set).sort(function (a, b) { return a === "all" ? -1 : b === "all" ? 1 : a.localeCompare(b); });
    }, [rows]);

    const filtered = useMemo(function () {
      const q = query.trim().toLowerCase();
      return rows.filter(function (row) {
        if (source !== "all" && row.kind !== source) return false;
        if (category !== "all" && (row.category || "(root)") !== category) return false;
        if (!q) return true;
        return String(row.name || "").toLowerCase().indexOf(q) >= 0;
      });
    }, [rows, query, source, category]);

    return h("div", { className: "sm-page" },
      toast ? h("div", { className: cx("sm-toast", toast.error && "sm-toast--error") }, toast.text) : null,
      h("header", { className: "sm-hero" },
        h("div", null,
          h("p", { className: "sm-kicker" }, data && data.meta ? data.meta.skillsDir : text.heroKickerFallback),
          h("h1", null, text.title),
          h("p", null, text.subtitle)
        ),
        h(StatStrip, { counts: counts, enabled: enabledCount, text: text })
      ),
      h("main", { className: "sm-main" },
        h(Toolbar, {
          query: query,
          setQuery: setQuery,
          source: source,
          setSource: setSource,
          category: category,
          setCategory: setCategory,
          categories: categories,
          total: rows.length,
          filtered: filtered.length,
          showMissingBuiltin: showMissingBuiltin,
          setShowMissingBuiltin: setShowMissingBuiltin,
          missingBuiltinCount: data ? data.missingBuiltinCount : 0,
          text: text,
          loading: loading,
          onRefresh: load,
        }),
        h(Card, { className: "sm-card sm-table-card" }, h(CardContent, { className: "sm-card__content" },
          h(SkillsTable, { rows: filtered, busyKey: busyKey, onAction: onAction, onDeleteRequest: setPendingDelete, text: text, lang: lang })
        )),
        h(HistoryPanel, { history: data && data.history ? data.history : [], text: text })
      ),
      h(DeleteConfirmDialog, {
        row: pendingDelete,
        busy: pendingDelete ? busyKey === pendingDelete.kind + ":" + pendingDelete.name : false,
        text: text,
        onCancel: function () { setPendingDelete(null); },
        onConfirm: function (confirm) {
          if (!pendingDelete) return;
          const row = pendingDelete;
          onAction("/delete", { source: row.kind, name: row.name, confirm: confirm }, text.notices.deleted(row.name), function () {
            setPendingDelete(null);
          });
        },
      })
    );
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("skill-manage", SkillManagePage);
  }
})();
