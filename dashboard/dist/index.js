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
  const Badge = C.Badge || function (props) { return h("span", props, props.children); };

  const API = "/api/plugins/skill-manage";
  const sources = ["all", "builtin", "skills.sh", "clawhub", "local"];
  const sourceLabels = {
    all: "全部",
    builtin: "内置",
    "skills.sh": "skills.sh",
    clawhub: "clawhub",
    local: "本地",
    optional: "可选目录",
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

  function toneForSource(source) {
    if (source === "builtin") return "sv-badge sv-badge--builtin";
    if (source === "skills.sh") return "sv-badge sv-badge--hub";
    if (source === "clawhub") return "sv-badge sv-badge--claw";
    if (source === "local") return "sv-badge sv-badge--local";
    return "sv-badge";
  }

  function short(text, n) {
    text = text || "";
    return text.length > n ? text.slice(0, n - 1) + "..." : text;
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

  function Stat(props) {
    return h("div", { className: "sv-stat" },
      h("div", { className: "sv-stat-value" }, props.value),
      h("div", { className: "sv-stat-label" }, props.label)
    );
  }

  function sourceLabel(source) {
    return sourceLabels[source] || source || "-";
  }

  function Toolbar(props) {
    return h("div", { className: "sv-toolbar" },
      h("div", { className: "sv-search" },
        h(Input, {
          value: props.query,
          onChange: function (e) { props.setQuery(e.target.value); },
          placeholder: "搜索技能、路径、描述",
          className: "sv-input",
        })
      ),
      h("div", { className: "sv-segments", role: "tablist" },
        sources.map(function (source) {
          return h("button", {
            key: source,
            type: "button",
            className: cx("sv-segment", props.source === source && "sv-segment--active"),
            onClick: function () { props.setSource(source); },
          }, sourceLabel(source));
        })
      ),
      h("select", {
        className: "sv-select",
        value: props.category,
        onChange: function (e) { props.setCategory(e.target.value); },
      }, props.categories.map(function (cat) {
        return h("option", { key: cat, value: cat }, cat === "all" ? "全部分类" : cat);
      })),
      h(Button, { size: "sm", outlined: true, onClick: props.onRefresh, disabled: props.loading }, props.loading ? "刷新中" : "刷新")
    );
  }

  function SkillTable(props) {
    if (!props.rows.length) {
      return h("div", { className: "sv-empty" }, "没有匹配的技能。");
    }
    return h("div", { className: "sv-table-wrap" },
      h("table", { className: "sv-table" },
        h("thead", null, h("tr", null,
          h("th", null, "技能"),
          h("th", null, "来源"),
          h("th", null, "路径"),
          h("th", null, "信任级别"),
          h("th", null, "扫描"),
          h("th", null, "")
        )),
        h("tbody", null, props.rows.map(function (row) {
          return h("tr", { key: row.source + ":" + row.installPath },
            h("td", null,
              h("button", {
                type: "button",
                className: "sv-link",
                onClick: function () { props.onOpen(row); },
              }, row.name),
              h("div", { className: "sv-desc" }, short(row.description || "暂无描述", 120))
            ),
            h("td", null, h("span", { className: toneForSource(row.source) }, sourceLabel(row.source))),
            h("td", { className: "sv-path" }, row.installPath),
            h("td", null, row.trustLevel || "-"),
            h("td", null, row.scanVerdict || "-"),
            h("td", { className: "sv-actions-cell" },
              h(Button, { size: "sm", outlined: true, onClick: function () { props.onOpen(row); } }, "详情")
            )
          );
        }))
      )
    );
  }

  function DetailPanel(props) {
    const row = props.row;
    const detail = props.detail;
    const [confirm, setConfirm] = useState("");
    const [busy, setBusy] = useState(false);

    useEffect(function () { setConfirm(""); }, [row && row.name]);
    if (!row) {
      return h("aside", { className: "sv-detail sv-detail--empty" },
        h("div", { className: "sv-detail-title" }, "选择一个技能"),
        h("p", null, "打开一行后，可以查看 SKILL.md、文件、来源元数据和管理操作。")
      );
    }

    function runDelete() {
      setBusy(true);
      api("/delete", {
        method: "POST",
        body: { source: row.source, name: row.name, confirm: confirm },
      }).then(function () {
        props.notice("已删除 " + row.name);
        props.onRefresh();
      }).catch(function (err) {
        props.notice(parseError(err), true);
      }).finally(function () { setBusy(false); });
    }

    const protectedBuiltin = row.source === "builtin";
    return h("aside", { className: "sv-detail" },
      h("div", { className: "sv-detail-head" },
        h("div", null,
          h("div", { className: "sv-detail-kicker" }, row.source),
          h("h2", null, row.name)
        ),
        h("button", { type: "button", className: "sv-close", onClick: props.onClose, "aria-label": "关闭" }, "x")
      ),
      h("dl", { className: "sv-meta" },
        h("div", null, h("dt", null, "路径"), h("dd", null, row.installPath)),
        h("div", null, h("dt", null, "来源标识"), h("dd", null, row.identifier || "-")),
        h("div", null, h("dt", null, "文件数"), h("dd", null, String(row.fileCount || 0))),
        h("div", null, h("dt", null, "安装时间"), h("dd", null, row.installedAt || "-"))
      ),
      h("p", { className: "sv-detail-desc" }, row.description || "frontmatter 中没有描述。"),
      h("div", { className: "sv-section-title" }, "SKILL.md"),
      h("pre", { className: "sv-code" }, detail && detail.skillMd ? detail.skillMd : "加载中..."),
      h("div", { className: "sv-section-title" }, "文件"),
      h("div", { className: "sv-files" },
        detail && detail.files && detail.files.length
          ? detail.files.slice(0, 80).map(function (file) { return h("span", { key: file }, file); })
          : h("span", null, "尚未加载文件列表")
      ),
      h("div", { className: "sv-danger" },
        h("div", null,
          h("strong", null, protectedBuiltin ? "内置技能受保护" : "备份后删除"),
          h("p", null, protectedBuiltin
            ? "当前 Dashboard 版本禁止删除内置技能。"
            : "输入完整技能名后会从磁盘删除该技能，并在插件 trash 目录保留备份。")
        ),
        protectedBuiltin ? null : h("div", { className: "sv-confirm-row" },
          h(Input, {
            value: confirm,
            onChange: function (e) { setConfirm(e.target.value); },
            placeholder: row.name,
            className: "sv-input",
          }),
          h(Button, {
            size: "sm",
            disabled: busy || confirm !== row.name,
            onClick: runDelete,
            className: "sv-delete-btn",
          }, busy ? "删除中" : "删除")
        )
      )
    );
  }

  function DeletedPanel(props) {
    const [confirm, setConfirm] = useState({});
    if (!props.deleted.length) return null;
    return h(Card, { className: "sv-card" }, h(CardContent, { className: "sv-card-content" },
      h("div", { className: "sv-section-head" },
        h("h3", null, "删除备份"),
        h("span", null, props.deleted.length + " 个可恢复")
      ),
      h("div", { className: "sv-deleted-list" },
        props.deleted.map(function (record) {
          const key = record.source + ":" + record.name;
          const value = confirm[key] || "";
          return h("div", { key: key, className: "sv-deleted-row" },
            h("div", null,
              h("strong", null, record.name),
              h("span", null, record.source + " / " + record.install_path)
            ),
            h(Input, {
              value: value,
              onChange: function (e) {
                const next = Object.assign({}, confirm);
                next[key] = e.target.value;
                setConfirm(next);
              },
              placeholder: record.name,
              className: "sv-input",
            }),
            h(Button, {
              size: "sm",
              outlined: true,
              disabled: value !== record.name,
              onClick: function () {
                api("/restore", {
                  method: "POST",
                  body: { source: record.source, name: record.name, confirm: value },
                }).then(function () {
                  props.notice("已恢复 " + record.name);
                  props.onRefresh();
                }).catch(function (err) { props.notice(parseError(err), true); });
              },
            }, "恢复")
          );
        })
      )
    ));
  }

  function OptionalPanel(props) {
    const [target, setTarget] = useState("");
    const [category, setCategory] = useState("");
    const [busy, setBusy] = useState(false);
    function install() {
      if (!target.trim()) return;
      setBusy(true);
      api("/install", {
        method: "POST",
        body: { source: "optional", target: target.trim(), category: category.trim(), force: false },
      }).then(function () {
        props.notice("已提交安装请求");
        setTarget("");
        props.onRefresh();
      }).catch(function (err) {
        props.notice(parseError(err), true);
      }).finally(function () { setBusy(false); });
    }
    return h(Card, { className: "sv-card" }, h(CardContent, { className: "sv-card-content" },
      h("div", { className: "sv-section-head" },
        h("h3", null, "安装"),
        h("span", null, "Hub 或可选目录")
      ),
      h("div", { className: "sv-install-row" },
        h(Input, {
          value: target,
          onChange: function (e) { setTarget(e.target.value); },
          placeholder: "来源标识、URL、owner/repo 或可选技能路径",
          className: "sv-input",
        }),
        h(Input, {
          value: category,
          onChange: function (e) { setCategory(e.target.value); },
          placeholder: "分类目录",
          className: "sv-input sv-category-input",
        }),
        h(Button, { size: "sm", onClick: install, disabled: busy || !target.trim() }, busy ? "安装中" : "安装")
      ),
      props.optional && props.optional.length ? h("div", { className: "sv-catalog" },
        props.optional.slice(0, 10).map(function (item) {
          return h("button", {
            type: "button",
            key: item.identifier,
            onClick: function () {
              setTarget(item.identifier);
              setCategory(item.category || "");
            },
          },
            h("strong", null, item.name),
            h("span", null, item.identifier)
          );
        })
      ) : null
    ));
  }

  function SkillVaultPage() {
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
        return [row.name, row.source, row.category, row.installPath, row.description, row.identifier]
          .join(" ").toLowerCase().indexOf(q) >= 0;
      });
    }, [rows, query, source, category]);

    const counts = data && data.counts ? data.counts : {};
    return h("div", { className: "sv-page" },
      toast ? h("div", { className: cx("sv-toast", toast.error && "sv-toast--error") }, toast.text) : null,
      h("header", { className: "sv-header" },
        h("div", null,
          h("p", { className: "sv-kicker" }, data && data.meta ? data.meta.skillsDir : "Hermes 技能目录"),
          h("h1", null, "Skill manage（技能管理）"),
          h("p", null, "按来源、分类、信任状态和安装路径管理 Hermes 技能。")
        ),
        h("div", { className: "sv-stats" },
          h(Stat, { value: rows.length, label: "已安装" }),
          h(Stat, { value: counts.builtin || 0, label: "内置" }),
          h(Stat, { value: (counts["skills.sh"] || 0) + (counts.clawhub || 0), label: "Hub" }),
          h(Stat, { value: counts.local || 0, label: "本地" })
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
        onRefresh: load,
        loading: loading,
      }),
      h("main", { className: "sv-main" },
        h("section", { className: "sv-left" },
          h(Card, { className: "sv-card" }, h(CardContent, { className: "sv-card-content sv-card-content--table" },
            h("div", { className: "sv-section-head" },
              h("h3", null, "技能清单"),
              h("span", null, loading ? "加载中" : "显示 " + filtered.length + " 个")
            ),
            h(SkillTable, { rows: filtered, onOpen: open })
          )),
          h(DeletedPanel, {
            deleted: data && data.deleted ? data.deleted : [],
            onRefresh: load,
            notice: notice,
          }),
          h(OptionalPanel, {
            optional: data && data.optional ? data.optional : [],
            onRefresh: load,
            notice: notice,
          })
        ),
        h(DetailPanel, {
          row: selected,
          detail: detail,
          onClose: function () { setSelected(null); setDetail(null); },
          onRefresh: load,
          notice: notice,
        })
      )
    );
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("skill-manage", SkillVaultPage);
  }
})();
