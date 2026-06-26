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
  const Input = C.Input || function (props) { return h("input", props); };
  const Card = C.Card || function (props) { return h("section", props, props.children); };
  const CardContent = C.CardContent || function (props) { return h("div", props, props.children); };

  const API = "/api/plugins/skill-manage";
  const SOURCE_ORDER = ["all", "builtin", "hub-installed", "local"];

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

  function confirmName(name, actionLabel) {
    const value = window.prompt(actionLabel + "需要二次确认。\n请输入技能名：" + name);
    return value === name ? value : null;
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

  function Toolbar(props) {
    return h("div", { className: "sm-toolbar" },
      h(Input, {
        className: "sm-input",
        value: props.query,
        onChange: function (e) { props.setQuery(e.target.value); },
        placeholder: "搜索 Name / Category / Source",
      }),
      h("div", { className: "sm-tabs" },
        SOURCE_ORDER.map(function (source) {
          return h("button", {
            key: source,
            type: "button",
            className: cx("sm-tab", props.source === source && "sm-tab--active"),
            onClick: function () { props.setSource(source); },
          }, source === "all" ? "all" : source, h("span", null, source === "all" ? props.total : props.counts[source] || 0));
        })
      ),
      h("select", {
        className: "sm-select",
        value: props.category,
        onChange: function (e) { props.setCategory(e.target.value); },
      }, props.categories.map(function (category) {
        return h("option", { key: category, value: category }, category === "all" ? "all categories" : category);
      })),
      h(Button, { onClick: props.onRefresh, disabled: props.loading }, props.loading ? "刷新中" : "刷新")
    );
  }

  function SkillsTable(props) {
    if (!props.rows.length) {
      return h("div", { className: "sm-empty" }, "没有匹配的技能");
    }

    function run(row, action) {
      if (action === "delete") {
        const confirm = confirmName(row.name, "删除");
        if (!confirm) return;
        props.onAction("/delete", { source: row.source, name: row.name, confirm: confirm }, "已删除：" + row.name);
        return;
      }
      if (action === "reset") {
        props.onAction("/reset", { source: row.source, name: row.name }, "已重置：" + row.name);
        return;
      }
      if (action === "update") {
        props.onAction("/update", { source: row.source, name: row.name }, "已更新：" + row.name);
      }
    }

    return h("div", { className: "sm-table-wrap" },
      h("table", { className: "sm-table" },
        h("caption", null, "Installed Skills"),
        h("thead", null,
          h("tr", null,
            h("th", null, "Name"),
            h("th", null, "Category"),
            h("th", null, "Source"),
            h("th", null, "Trust"),
            h("th", null, "Status"),
            h("th", null, "操作")
          )
        ),
        h("tbody", null,
          props.rows.map(function (row) {
            const busy = props.busyKey === row.source + ":" + row.name;
            return h("tr", { key: row.source + ":" + row.name },
              h("td", { className: "sm-name", title: row.installPath }, row.name),
              h("td", { className: "sm-dim" }, row.category || ""),
              h("td", null, h(Pill, { tone: row.source, title: row.rawSource || row.source }, row.source)),
              h("td", { className: "sm-dim" }, row.trustLevel || "-"),
              h("td", null, h(Pill, { tone: row.status === "enabled" ? "enabled" : "disabled" }, row.status || "enabled")),
              h("td", { className: "sm-actions" },
                row.source === "builtin" ? h(Button, { disabled: busy, onClick: function () { run(row, "reset"); } }, "重置") : null,
                row.source === "hub-installed" ? h(Button, { disabled: busy, onClick: function () { run(row, "reset"); } }, "重置") : null,
                row.source === "hub-installed" ? h(Button, { disabled: busy, onClick: function () { run(row, "update"); } }, "更新") : null,
                h(Button, { kind: "danger", disabled: busy, onClick: function () { run(row, "delete"); } }, "删除")
              )
            );
          })
        )
      )
    );
  }

  function InstallPanel(props) {
    const [target, setTarget] = useState("");
    const [category, setCategory] = useState("");
    const [force, setForce] = useState(false);

    function install() {
      if (!target.trim()) return;
      props.onAction("/install", {
        target: target.trim(),
        category: category.trim(),
        force: force,
      }, "已安装：" + target.trim(), function () {
        setTarget("");
      });
    }

    return h(Card, { className: "sm-card" }, h(CardContent, { className: "sm-card__content" },
      h("div", { className: "sm-card__head" },
        h("div", null, h("h3", null, "安装技能"), h("p", null, "支持 URL、owner/repo、hub 标识或 optional catalog 路径。")),
        h(Button, { disabled: !target.trim() || props.busy, onClick: install }, props.busy ? "安装中" : "安装")
      ),
      h("div", { className: "sm-install" },
        h(Input, {
          className: "sm-input",
          value: target,
          onChange: function (e) { setTarget(e.target.value); },
          placeholder: "identifier / URL / owner/repo",
        }),
        h(Input, {
          className: "sm-input",
          value: category,
          onChange: function (e) { setCategory(e.target.value); },
          placeholder: "category",
        }),
        h("label", { className: "sm-check" },
          h("input", {
            type: "checkbox",
            checked: force,
            onChange: function (e) { setForce(e.target.checked); },
          }),
          h("span", null, "force")
        )
      ),
      props.optional && props.optional.length ? h("div", { className: "sm-catalog" },
        props.optional.slice(0, 12).map(function (item) {
          return h("button", {
            key: item.identifier,
            type: "button",
            onClick: function () {
              setTarget(item.identifier);
              setCategory(item.category || "");
            },
          }, h("strong", null, item.name), h("span", null, item.identifier));
        })
      ) : null
    ));
  }

  function HistoryPanel(props) {
    if (!props.history.length) return null;
    return h(Card, { className: "sm-card" }, h(CardContent, { className: "sm-card__content" },
      h("div", { className: "sm-card__head" },
        h("div", null, h("h3", null, "最近操作"), h("p", null, "最近 8 条管理动作"))
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
    const [toast, setToast] = useState(null);
    const [busyKey, setBusyKey] = useState("");
    const [installBusy, setInstallBusy] = useState(false);

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

    function onAction(path, body, successText, after) {
      const key = body.source && body.name ? body.source + ":" + body.name : "install";
      if (key === "install") setInstallBusy(true);
      else setBusyKey(key);
      api(path, { method: "POST", body: body }).then(function () {
        notice(successText);
        if (after) after();
        return load();
      }).catch(function (err) {
        notice(parseError(err), true);
      }).finally(function () {
        setBusyKey("");
        setInstallBusy(false);
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
        return [row.name, row.category, row.source, row.trustLevel, row.status, row.rawSource]
          .join(" ").toLowerCase().indexOf(q) >= 0;
      });
    }, [rows, query, source, category]);

    return h("div", { className: "sm-page" },
      toast ? h("div", { className: cx("sm-toast", toast.error && "sm-toast--error") }, toast.text) : null,
      h("header", { className: "sm-hero" },
        h("div", null,
          h("p", { className: "sm-kicker" }, data && data.meta ? data.meta.skillsDir : "Hermes 技能目录"),
          h("h1", null, "技能管理"),
          h("p", null, "列表样式对齐 Hermes skills list，并在每个技能后提供操作列。")
        ),
        h("div", { className: "sm-summary" },
          h("strong", null, (counts["hub-installed"] || 0) + " hub-installed, " + (counts.builtin || 0) + " builtin, " + (counts.local || 0) + " local"),
          h("span", null, (data ? data.enabledCount : 0) + " enabled, " + (data ? data.disabledCount : 0) + " disabled")
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
      h(Card, { className: "sm-card" }, h(CardContent, { className: "sm-card__content" },
        h(SkillsTable, { rows: filtered, busyKey: busyKey, onAction: onAction })
      )),
      h(InstallPanel, { optional: data && data.optional ? data.optional : [], busy: installBusy, onAction: onAction }),
      h(HistoryPanel, { history: data && data.history ? data.history : [] })
    );
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("skill-manage", SkillManagePage);
  }
})();
