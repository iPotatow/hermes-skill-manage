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

  const C = SDK.components || {};
  const Button = C.Button || function (props) { return h("button", props, props.children); };
  const Input = C.Input || function (props) { return h("input", props); };
  const Card = C.Card || function (props) { return h("section", props, props.children); };
  const CardContent = C.CardContent || function (props) { return h("div", props, props.children); };

  const API = "/api/plugins/skill-manage";
  const SOURCE_ORDER = ["all", "builtin", "hub-installed", "local"];
  const SOURCE_LABEL = {
    all: "全部",
    builtin: "builtin",
    "hub-installed": "hub-installed",
    local: "local",
  };

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

  function parseError(err) {
    const raw = err && err.message ? String(err.message) : String(err || "未知错误");
    try {
      const parsed = JSON.parse(raw.replace(/^\d+:\s*/, ""));
      return parsed.detail || raw;
    } catch (_e) {
      return raw;
    }
  }

  function sourceLabel(source) {
    return SOURCE_LABEL[source] || source || "-";
  }

  function short(text, n) {
    text = text || "";
    return text.length > n ? text.slice(0, n - 1) + "..." : text;
  }

  function Stat(props) {
    return h("div", { className: "sm-stat" },
      h("div", { className: "sm-stat__label" }, props.label),
      h("div", { className: "sm-stat__value" }, props.value),
      props.hint ? h("div", { className: "sm-stat__hint" }, props.hint) : null
    );
  }

  function StatusPill(props) {
    return h("span", { className: cx("sm-pill", "sm-pill--" + String(props.tone || "default")) }, props.children);
  }

  function ActionButton(props) {
    const className = cx("sm-btn", props.kind === "danger" && "sm-btn--danger", props.kind === "quiet" && "sm-btn--quiet", props.className);
    return h("button", Object.assign({}, props, { className: className, type: props.type || "button" }), props.children);
  }

  function Toolbar(props) {
    return h("div", { className: "sm-toolbar" },
      h("div", { className: "sm-search" },
        h(Input, {
          className: "sm-input",
          value: props.query,
          onChange: function (e) { props.setQuery(e.target.value); },
          placeholder: "搜索技能名称、路径、描述、来源标识",
        })
      ),
      h("div", { className: "sm-tabs", role: "tablist" },
        SOURCE_ORDER.map(function (source) {
          return h("button", {
            key: source,
            type: "button",
            className: cx("sm-tab", props.source === source && "sm-tab--active"),
            onClick: function () { props.setSource(source); },
          }, sourceLabel(source), h("span", null, source === "all" ? props.total : props.counts[source] || 0));
        })
      ),
      h("select", {
        className: "sm-select",
        value: props.category,
        onChange: function (e) { props.setCategory(e.target.value); },
      }, props.categories.map(function (cat) {
        return h("option", { key: cat, value: cat }, cat === "all" ? "全部分类" : cat);
      })),
      h(ActionButton, { onClick: props.onRefresh, disabled: props.loading }, props.loading ? "刷新中" : "刷新")
    );
  }

  function SkillList(props) {
    if (!props.rows.length) {
      return h("div", { className: "sm-empty" },
        h("strong", null, "没有匹配的技能"),
        h("span", null, "调整搜索或筛选条件后再试。")
      );
    }
    return h("div", { className: "sm-list" },
      props.rows.map(function (row) {
        const selected = props.selected && props.selected.source === row.source && props.selected.name === row.name;
        return h("button", {
          key: row.source + ":" + row.installPath,
          type: "button",
          className: cx("sm-row", selected && "sm-row--selected"),
          onClick: function () { props.onOpen(row); },
        },
          h("div", { className: "sm-row__main" },
            h("div", { className: "sm-row__title" },
              h("strong", null, row.name),
              h(StatusPill, { tone: row.source }, sourceLabel(row.source))
            ),
            h("div", { className: "sm-row__desc" }, short(row.description || "暂无描述", 140)),
            h("div", { className: "sm-row__path" }, row.installPath)
          ),
          h("div", { className: "sm-row__meta" },
            h("span", null, row.trustLevel || "-"),
            h("span", null, row.scanVerdict || "-")
          )
        );
      })
    );
  }

  function DetailPanel(props) {
    const row = props.row;
    const detail = props.detail;
    const [confirm, setConfirm] = useState("");
    const [busy, setBusy] = useState("");

    useEffect(function () { setConfirm(""); setBusy(""); }, [row && row.name]);

    if (!row) {
      return h("aside", { className: "sm-side sm-side--empty" },
        h("div", { className: "sm-empty" },
          h("strong", null, "选择一个技能"),
          h("span", null, "右侧会显示来源、文件、SKILL.md 和可用操作。")
        )
      );
    }

    function runDelete() {
      setBusy("delete");
      api("/delete", {
        method: "POST",
        body: { source: row.source, name: row.name, confirm: confirm },
      }).then(function () {
        props.notice("已删除并备份：" + row.name);
        props.onChanged();
      }).catch(function (err) {
        props.notice(parseError(err), true);
      }).finally(function () { setBusy(""); });
    }

    function runReset() {
      setBusy("reset");
      api("/reset", {
        method: "POST",
        body: { source: "builtin", name: row.name },
      }).then(function () {
        props.notice("已重置内置技能：" + row.name);
        props.onChanged();
      }).catch(function (err) {
        props.notice(parseError(err), true);
      }).finally(function () { setBusy(""); });
    }

    function reinstall() {
      if (!row.identifier) return;
      setBusy("install");
      api("/install", {
        method: "POST",
        body: { source: "hub-installed", target: row.identifier, category: row.category || "", force: true },
      }).then(function () {
        props.notice("已重新安装：" + row.name);
        props.onChanged();
      }).catch(function (err) {
        props.notice(parseError(err), true);
      }).finally(function () { setBusy(""); });
    }

    const canDelete = row.source !== "builtin";
    const canReset = row.source === "builtin";
    const canReinstall = row.source === "hub-installed" && row.identifier;

    return h("aside", { className: "sm-side" },
      h("div", { className: "sm-side__head" },
        h("div", null,
          h("div", { className: "sm-eyebrow" }, row.source),
          h("h2", null, row.name)
        ),
        h(ActionButton, { kind: "quiet", onClick: props.onClose, "aria-label": "关闭详情" }, "关闭")
      ),
      h("div", { className: "sm-detail-grid" },
        h("div", null, h("span", null, "分类"), h("strong", null, row.category || "(root)")),
        h("div", null, h("span", null, "文件"), h("strong", null, String(row.fileCount || 0))),
        h("div", null, h("span", null, "信任"), h("strong", null, row.trustLevel || "-")),
        h("div", null, h("span", null, "扫描"), h("strong", null, row.scanVerdict || "-"))
      ),
      h("div", { className: "sm-field" },
        h("label", null, "安装路径"),
        h("code", null, row.installPath)
      ),
      h("div", { className: "sm-field" },
        h("label", null, "来源标识"),
        h("code", null, row.identifier || "-"),
        row.originalSource && row.originalSource !== row.source
          ? h("small", null, "原始来源：" + row.originalSource)
          : null
      ),
      h("p", { className: "sm-desc" }, row.description || "frontmatter 中没有描述。"),
      h("div", { className: "sm-actions" },
        canReset ? h(ActionButton, { onClick: runReset, disabled: busy === "reset" }, busy === "reset" ? "重置中" : "从内置源重置") : null,
        canReinstall ? h(ActionButton, { onClick: reinstall, disabled: busy === "install" }, busy === "install" ? "安装中" : "强制重新安装") : null
      ),
      canDelete ? h("div", { className: "sm-danger" },
        h("div", null,
          h("strong", null, "删除技能"),
          h("p", null, "删除前会复制一份到插件 trash 目录。输入完整技能名后才能执行。")
        ),
        h("div", { className: "sm-confirm" },
          h(Input, {
            className: "sm-input",
            value: confirm,
            onChange: function (e) { setConfirm(e.target.value); },
            placeholder: row.name,
          }),
          h(ActionButton, {
            kind: "danger",
            disabled: busy === "delete" || confirm !== row.name,
            onClick: runDelete,
          }, busy === "delete" ? "删除中" : "删除")
        )
      ) : null,
      h("div", { className: "sm-section-title" }, "SKILL.md"),
      h("pre", { className: "sm-code" }, detail && detail.skillMd ? detail.skillMd : "加载中..."),
      h("div", { className: "sm-section-title" }, "文件列表"),
      h("div", { className: "sm-files" },
        detail && detail.files && detail.files.length
          ? detail.files.slice(0, 120).map(function (file) { return h("span", { key: file }, file); })
          : h("span", null, "暂无文件列表")
      )
    );
  }

  function InstallPanel(props) {
    const [target, setTarget] = useState("");
    const [category, setCategory] = useState("");
    const [force, setForce] = useState(false);
    const [busy, setBusy] = useState(false);

    function install() {
      if (!target.trim()) return;
      setBusy(true);
      api("/install", {
        method: "POST",
        body: { source: "hub-installed", target: target.trim(), category: category.trim(), force: force },
      }).then(function () {
        props.notice("安装完成：" + target.trim());
        setTarget("");
        props.onChanged();
      }).catch(function (err) {
        props.notice(parseError(err), true);
      }).finally(function () { setBusy(false); });
    }

    return h(Card, { className: "sm-card" }, h(CardContent, { className: "sm-card__content" },
      h("div", { className: "sm-card__head" },
        h("div", null, h("h3", null, "安装技能"), h("p", null, "支持 URL、owner/repo、hub 标识或 optional catalog 路径。")),
        h(ActionButton, { onClick: install, disabled: busy || !target.trim() }, busy ? "安装中" : "安装")
      ),
      h("div", { className: "sm-install" },
        h(Input, {
          className: "sm-input",
          value: target,
          onChange: function (e) { setTarget(e.target.value); },
          placeholder: "来源标识、URL、owner/repo 或可选技能路径",
        }),
        h(Input, {
          className: "sm-input",
          value: category,
          onChange: function (e) { setCategory(e.target.value); },
          placeholder: "分类目录，例如 software-development",
        }),
        h("label", { className: "sm-check" },
          h("input", {
            type: "checkbox",
            checked: force,
            onChange: function (e) { setForce(e.target.checked); },
          }),
          h("span", null, "覆盖已存在技能")
        )
      ),
      props.optional && props.optional.length ? h("div", { className: "sm-catalog" },
        props.optional.slice(0, 12).map(function (item) {
          return h("button", {
            type: "button",
            key: item.identifier,
            onClick: function () {
              setTarget(item.identifier);
              setCategory(item.category || "");
            },
          }, h("strong", null, item.name), h("span", null, item.identifier));
        })
      ) : null
    ));
  }

  function RecoveryPanel(props) {
    const [confirm, setConfirm] = useState({});
    if (!props.deleted.length) return null;
    return h(Card, { className: "sm-card" }, h(CardContent, { className: "sm-card__content" },
      h("div", { className: "sm-card__head" },
        h("div", null, h("h3", null, "删除备份"), h("p", null, "从 trash 备份恢复已删除技能。")),
        h(StatusPill, { tone: "local" }, props.deleted.length + " 个")
      ),
      h("div", { className: "sm-recovery" },
        props.deleted.map(function (record) {
          const key = record.source + ":" + record.name;
          const value = confirm[key] || "";
          return h("div", { className: "sm-recovery__row", key: key },
            h("div", null, h("strong", null, record.name), h("span", null, record.source + " / " + record.install_path)),
            h(Input, {
              className: "sm-input",
              value: value,
              placeholder: record.name,
              onChange: function (e) {
                const next = Object.assign({}, confirm);
                next[key] = e.target.value;
                setConfirm(next);
              },
            }),
            h(ActionButton, {
              disabled: value !== record.name,
              onClick: function () {
                api("/restore", {
                  method: "POST",
                  body: { source: record.source, name: record.name, confirm: value },
                }).then(function () {
                  props.notice("已恢复：" + record.name);
                  props.onChanged();
                }).catch(function (err) { props.notice(parseError(err), true); });
              },
            }, "恢复")
          );
        })
      )
    ));
  }

  function HistoryPanel(props) {
    if (!props.history.length) return null;
    return h(Card, { className: "sm-card" }, h(CardContent, { className: "sm-card__content" },
      h("div", { className: "sm-card__head" },
        h("div", null, h("h3", null, "最近操作"), h("p", null, "插件记录最近 40 条管理动作。"))
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
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [query, setQuery] = useState("");
    const [source, setSource] = useState("all");
    const [category, setCategory] = useState("all");
    const [selected, setSelected] = useState(null);
    const [detail, setDetail] = useState(null);
    const [toast, setToast] = useState(null);

    const load = useCallback(function () {
      setLoading(true);
      return api("/inventory").then(function (next) {
        setData(next);
      }).catch(function (err) {
        setToast({ text: parseError(err), error: true });
      }).finally(function () {
        setLoading(false);
      });
    }, []);

    useEffect(function () { load(); }, [load]);

    function notice(text, error) {
      setToast({ text: text, error: !!error });
      setTimeout(function () { setToast(null); }, 4500);
    }

    function open(row) {
      setSelected(row);
      setDetail(null);
      api("/skill/" + encodeURIComponent(row.source) + "/" + encodeURIComponent(row.name)).then(function (next) {
        setDetail(next);
      }).catch(function (err) {
        notice(parseError(err), true);
      });
    }

    const rows = data && data.skills ? data.skills : [];
    const counts = data && data.counts ? data.counts : {};
    const categories = useMemo(function () {
      const set = new Set(["all"]);
      rows.forEach(function (row) { set.add(row.category || "(root)"); });
      return Array.from(set).sort(function (a, b) { return a === "all" ? -1 : b === "all" ? 1 : a.localeCompare(b); });
    }, [rows]);

    const filtered = useMemo(function () {
      const q = query.trim().toLowerCase();
      return rows.filter(function (row) {
        if (source !== "all" && row.source !== source) return false;
        if (category !== "all" && (row.category || "(root)") !== category) return false;
        if (!q) return true;
        return [row.name, row.source, row.originalSource, row.category, row.installPath, row.description, row.identifier]
          .join(" ").toLowerCase().indexOf(q) >= 0;
      });
    }, [rows, query, source, category]);

    function refreshAfterChange() {
      load().then(function () {
        if (selected) open(selected);
      });
    }

    return h("div", { className: "sm-page" },
      toast ? h("div", { className: cx("sm-toast", toast.error && "sm-toast--error") }, toast.text) : null,
      h("header", { className: "sm-hero" },
        h("div", null,
          h("p", { className: "sm-kicker" }, data && data.meta ? data.meta.skillsDir : "Hermes 技能目录"),
          h("h1", null, "技能管理"),
          h("p", null, "按 builtin、hub-installed、local 管理 Hermes skills。")
        ),
        h("div", { className: "sm-stats" },
          h(Stat, { label: "总数", value: rows.length, hint: "已安装技能" }),
          h(Stat, { label: "builtin", value: counts.builtin || 0, hint: "随 Hermes 同步" }),
          h(Stat, { label: "hub-installed", value: counts["hub-installed"] || 0, hint: "Hub 安装" }),
          h(Stat, { label: "local", value: counts.local || 0, hint: "本地维护" })
        )
      ),
      h(Toolbar, {
        query: query,
        setQuery: setQuery,
        source: source,
        setSource: setSource,
        category: category,
        setCategory: setCategory,
        categories: categories,
        counts: counts,
        total: rows.length,
        loading: loading,
        onRefresh: load,
      }),
      h("main", { className: "sm-grid" },
        h("section", { className: "sm-primary" },
          h(Card, { className: "sm-card sm-card--list" }, h(CardContent, { className: "sm-card__content" },
            h("div", { className: "sm-card__head" },
              h("div", null, h("h3", null, "技能清单"), h("p", null, loading ? "正在读取技能目录" : "当前显示 " + filtered.length + " 个技能"))
            ),
            h(SkillList, { rows: filtered, selected: selected, onOpen: open })
          )),
          h(InstallPanel, {
            optional: data && data.optional ? data.optional : [],
            notice: notice,
            onChanged: refreshAfterChange,
          }),
          h(RecoveryPanel, {
            deleted: data && data.deleted ? data.deleted : [],
            notice: notice,
            onChanged: refreshAfterChange,
          }),
          h(HistoryPanel, { history: data && data.history ? data.history : [] })
        ),
        h(DetailPanel, {
          row: selected,
          detail: detail,
          notice: notice,
          onClose: function () { setSelected(null); setDetail(null); },
          onChanged: refreshAfterChange,
        })
      )
    );
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("skill-manage", SkillManagePage);
  }
})();
