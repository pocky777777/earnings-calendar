// 決算カレンダーの画面。data/earnings.json を読んで描画する（ライブラリなし）。
// 表示は「週間」「月間」「業界マップ」「銘柄一覧」の4つ。URLの # で切り替える。
(() => {
  "use strict";

  const DOW = ["日", "月", "火", "水", "木", "金", "土"];
  const STORE_KEY = "earnings-calendar-filters-v2";
  const VIEWS = ["week", "month", "map", "list"];
  // 毎年同じ日の祝日（月間カレンダーで赤くするだけの用途）
  const FIXED_HOLIDAYS = ["01-01", "02-11", "02-23", "04-29", "05-03", "05-04", "05-05", "08-11", "11-03", "11-23"];

  // 業界マップ: サプライチェーンの段階と、各分野の説明・イラスト
  const STAGES = [
    { step: "① 買う", cats: ["AIの買い手"], grow: 1 },
    { step: "② つなぐ・動かす", cats: ["AIサーバー・ネットワーク", "光・電線", "電力・冷却"], grow: 3 },
    { step: "③ 頭脳と記憶", cats: ["AI半導体", "メモリ・素材"], grow: 2 },
    { step: "④ つくる", cats: ["製造装置", "基板・電子部品"], grow: 2 },
  ];
  const SVG_HEAD = '<svg width="56" height="56" viewBox="0 0 64 64" fill="none" stroke="#12306e" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';
  const CAT_INFO = {
    "AIの買い手": {
      short: "AIの買い手", sub: "クラウド・AI企業",
      desc: "データセンターに投資する側。設備投資の見通しが、右側すべての需要の目安になります。",
      icon: '<path d="M18 40h30a9 9 0 0 0 0-18 13 13 0 0 0-25-3 10 10 0 0 0-5 21z" fill="#eaf0ff"/><path d="M26 46v8M38 46v8M22 54h20"/><circle cx="32" cy="30" r="4" fill="#e8711a" stroke="none"/>',
    },
    "AIサーバー・ネットワーク": {
      short: "サーバー・ネットワーク", sub: "",
      desc: "サーバーを組み立て、つなぐ会社。買い手の投資が最初に売上になる層です。",
      icon: '<rect x="16" y="8" width="32" height="48" rx="3" fill="#eaf0ff"/><path d="M16 22h32M16 36h32M30 15h12M30 29h12M30 43h12"/><circle cx="22" cy="15" r="1.6" fill="#e8711a" stroke="none"/><circle cx="22" cy="29" r="1.6" fill="#e8711a" stroke="none"/><circle cx="22" cy="43" r="1.6" fill="#e8711a" stroke="none"/>',
    },
    "光・電線": {
      short: "光・電線", sub: "",
      desc: "サーバー同士や建物をつなぐ光ファイバーと電線。",
      icon: '<path d="M6 16c12 0 12 16 26 16s14-16 26-16"/><path d="M6 24c12 0 12 16 26 16s14-16 26-16"/><path d="M6 32c12 0 12 16 26 16s14-16 26-16"/><circle cx="32" cy="32" r="5" fill="#e8711a" stroke="none"/>',
    },
    "電力・冷却": {
      short: "電力・冷却", sub: "",
      desc: "データセンターの電源と冷却設備。",
      icon: '<circle cx="40" cy="36" r="16" fill="#eaf0ff"/><path d="M40 36V24M40 36l10 6M40 36l-10 6"/><path d="M18 8l-8 16h8l-4 14 12-18h-8l6-12z" fill="#e8711a" stroke="#e8711a"/>',
    },
    "AI半導体": {
      short: "AI半導体", sub: "",
      desc: "GPUや専用チップを設計・製造する会社。",
      icon: '<rect x="16" y="16" width="32" height="32" rx="3" fill="#eaf0ff"/><rect x="25" y="25" width="14" height="14" rx="1" fill="#e8711a" stroke="none"/><path d="M24 8v8M32 8v8M40 8v8M24 48v8M32 48v8M40 48v8M8 24h8M8 32h8M8 40h8M48 24h8M48 32h8M48 40h8"/>',
    },
    "メモリ・素材": {
      short: "メモリ・素材", sub: "",
      desc: "HBMなどのメモリと、ウエハーや化学材料。",
      icon: '<path d="M12 42l20 10 20-10-20-10z" fill="#eaf0ff"/><path d="M12 34l20 10 20-10-20-10z" fill="#eaf0ff"/><path d="M12 26l20 10 20-10-20-10z" fill="#ffe6d2"/><path d="M32 16v-6"/>',
    },
    "製造装置": {
      short: "製造装置", sub: "",
      desc: "チップを作る・検査する装置。日本企業が強い分野で、チップメーカーの設備投資が売上になります。",
      icon: '<rect x="8" y="44" width="48" height="10" rx="2" fill="#eaf0ff"/><path d="M20 44V14h22v10"/><path d="M42 24l-6 8h12z" fill="#e8711a" stroke="#e8711a"/><ellipse cx="42" cy="40" rx="10" ry="3" fill="#ffe6d2"/>',
    },
    "基板・電子部品": {
      short: "基板・電子部品", sub: "",
      desc: "チップを載せる基板と、その材料・部品。",
      icon: '<rect x="8" y="12" width="48" height="40" rx="3" fill="#eaf0ff"/><rect x="24" y="24" width="16" height="16" rx="1" fill="#e8711a" stroke="none"/><path d="M14 20h10v4M14 46h10v-6M50 20H40v4M50 46H40v-6"/>',
    },
  };

  const state = {
    data: null,
    companies: {},
    view: "week",
    market: "all",            // all / JP / US
    categories: new Set(),    // 空なら全分野
    weekStart: null,          // 表示中の週の月曜日
    month: null,              // 表示中の月の1日
    selDay: null,             // 月間で選んだ日（YYYY-MM-DD）
    mapCat: "製造装置",        // null ならすべてのカテゴリ
  };

  // ---------- 小さな道具 ----------
  const $ = (id) => document.getElementById(id);
  const $$ = (sel) => [...document.querySelectorAll(sel)];
  const pad = (n) => String(n).padStart(2, "0");
  const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const todayJST = () => {
    // 見る人がどの国にいても「日本の今日」を基準にする
    const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tokyo" }).format(new Date());
    return new Date(parts + "T00:00:00");
  };
  const parse = (s) => new Date(s.slice(0, 10) + "T00:00:00");
  const md = (d) => `${d.getMonth() + 1}/${d.getDate()}`;
  const mdw = (d) => `${md(d)}（${DOW[d.getDay()]}）`;
  const fmtDate = (s) => mdw(parse(s));
  const mondayOf = (d) => addDays(d, -((d.getDay() + 6) % 7));
  // 「今週」: 土日に見たときは、これから来る次の週を今週として扱う
  const currentWeekStart = () => { const t = todayJST(); return t.getDay() % 6 === 0 ? mondayOf(addDays(t, 2)) : mondayOf(t); };
  const daysBetween = (a, b) => Math.round((b - a) / 86400000);
  const el = (tag, attrs = {}, ...children) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "html") n.innerHTML = v; // 固定のイラスト（SVG）だけに使う
      else if (k === "style") n.style.cssText = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v);
    }
    for (const c of children.flat()) if (c != null && c !== false) n.append(c);
    return n;
  };

  // ---------- 予定の扱い ----------
  // カレンダーに置く日付: 時刻が分かっていれば日本時間の日付、無ければ現地の日付
  const placeDate = (ev) => (ev.jst ? ev.jst.slice(0, 10) : ev.date);
  const timeOf = (ev) => (ev.jst ? ev.jst.slice(11, 16) : null);
  const approxShort = (ev) => ev.approx.replace(/^\d+月/, "");
  const badgeOf = (ev) =>
    ev.status === "done" ? ["発表済み", "b-done"]
      : ev.approx ? [approxShort(ev), "b-approx"]
      : ev.status === "confirmed" ? ["確定", "b-conf"]
      : ["予想", "b-est"];
  const badge = (ev) => { const [t, c] = badgeOf(ev); return el("span", { class: `badge ${c}` }, t); };
  const statusText = (ev) => {
    if (ev.status === "confirmed" && ev.approx) return `${ev.approx}（会社発表・日付は未定）`;
    return { confirmed: "確定（会社発表）", estimated: "予想（前年同期などから推定）", done: "発表済み" }[ev.status];
  };
  const whenText = (ev) => {
    if (ev.approx) return ev.approx;
    const t = timeOf(ev);
    return `${fmtDate(placeDate(ev))}${t ? " " + t : ""}`;
  };

  const companyVisible = (c, marketOnly = false) =>
    !!c && (state.market === "all" || state.market === c.market) &&
    (marketOnly || !state.categories.size || state.categories.has(c.category));
  const visible = (ev) => companyVisible(state.companies[ev.company]);

  const eventsByDay = () => {
    const by = {};
    for (const ev of state.data.events) if (visible(ev)) (by[placeDate(ev)] ||= []).push(ev);
    const rank = (e) => (e.status === "done" ? 2 : e.status === "estimated" ? 1 : 0);
    for (const k in by) by[k].sort((a, b) => rank(a) - rank(b) || (timeOf(a) || "99").localeCompare(timeOf(b) || "99"));
    return by;
  };
  const nextEventOf = (cid, today) => state.data.events
    .filter((e) => e.company === cid && e.status !== "done" && parse(placeDate(e)) >= today)
    .sort((a, b) => placeDate(a).localeCompare(placeDate(b)))[0];

  // ---------- 絞り込みの保存 ----------
  function saveFilters() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ m: state.market, c: [...state.categories] }));
    } catch { /* 保存できない環境では何もしない */ }
  }
  function loadFilters() {
    try {
      const s = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
      if (["all", "JP", "US"].includes(s?.m)) state.market = s.m;
      if (Array.isArray(s?.c)) state.categories = new Set(s.c.filter((c) => state.data.categories.includes(c)));
    } catch { /* 読めなければ初期値のまま */ }
  }

  // ---------- 共通の部品 ----------
  function pillButton(label, pressed, onclick) {
    return el("button", { type: "button", "aria-pressed": String(pressed), onclick }, label);
  }

  function renderFilters() {
    for (const box of $$("[data-filters]")) {
      const marketOnly = box.hasAttribute("data-market-only");
      const markets = el("div", { class: "filter-group", role: "group", "aria-label": "市場" },
        el("span", { class: "filter-label" }, "市場"),
        ...[["all", "すべて"], ["JP", "日本株"], ["US", "米国株"]].map(([k, label]) =>
          pillButton(label, state.market === k, () => { state.market = k; saveFilters(); renderView(); })));
      const parts = [markets];
      if (!marketOnly) {
        parts.push(el("div", { class: "filter-group", role: "group", "aria-label": "カテゴリ" },
          el("span", { class: "filter-label" }, "カテゴリ"),
          pillButton("すべて", !state.categories.size, () => { state.categories.clear(); saveFilters(); renderView(); }),
          ...state.data.categories.map((cat) => pillButton(cat, state.categories.has(cat), () => {
            state.categories.has(cat) ? state.categories.delete(cat) : state.categories.add(cat);
            saveFilters();
            renderView();
          }))));
      }
      box.replaceChildren(...parts);
    }
  }

  function renderLegends() {
    for (const box of $$("[data-legend]")) {
      box.replaceChildren(
        el("span", {}, el("span", { class: "badge b-conf" }, "確定"), "会社が発表した日付"),
        el("span", {}, el("span", { class: "badge b-est" }, "予想"), "前年同期から推定（会社発表で自動置換）"),
        el("span", {}, el("span", { class: "badge b-approx" }, "下旬"), "時期のみ発表"),
        el("span", {}, el("span", { class: "badge b-done" }, "発表済み")),
      );
    }
  }

  // 銘柄1行（週間・月間の右の一覧）
  function eventRow(ev, { withCategory = true } = {}) {
    const c = state.companies[ev.company];
    const t = timeOf(ev);
    const sub = [withCategory ? c.category : null, t ? `${t}${c.market === "US" ? "（日本時間）" : ""}` : null].filter(Boolean).join(" ・ ");
    return el("li", {}, el("button", { type: "button", class: "row", onclick: () => openDetail(ev) },
      el("div", { class: "row-main" },
        el("div", { class: "row-title" },
          el("span", { class: `code ${c.market === "US" ? "us" : ""}` }, c.id),
          el("span", { class: "name" }, c.name)),
        sub ? el("div", { class: "row-sub" }, sub) : null),
      badge(ev)));
  }

  function groupedRows(evs) {
    const jp = evs.filter((e) => state.companies[e.company].market === "JP");
    const us = evs.filter((e) => state.companies[e.company].market === "US");
    const out = [];
    if (jp.length) out.push(el("div", { class: "group-label" }, "日本株"), el("ul", { class: "row-list" }, jp.map((e) => eventRow(e))));
    if (us.length) out.push(el("div", { class: "group-label" }, "米国株"), el("ul", { class: "row-list" }, us.map((e) => eventRow(e))));
    return out;
  }

  // ---------- 週間 ----------
  function renderNext() {
    const today = todayJST();
    const list = state.data.events
      .filter((e) => e.status === "confirmed" && !e.approx && visible(e) && parse(placeDate(e)) >= today)
      .sort((a, b) => (a.jst || a.date).localeCompare(b.jst || b.date))
      .slice(0, 4);
    const ol = $("next");
    if (!list.length) {
      ol.replaceChildren(el("li", { class: "empty" }, "条件に合う確定済みの予定がありません"));
      return;
    }
    ol.replaceChildren(...list.map((ev) => {
      const c = state.companies[ev.company];
      const days = daysBetween(today, parse(placeDate(ev)));
      return el("li", {}, el("button", { type: "button", class: "next-card", onclick: () => openDetail(ev) },
        el("div", { class: "next-top" },
          el("span", { class: "mono small muted" }, c.id),
          el("span", { class: "next-days" }, days === 0 ? "今日" : `あと${days}日`)),
        el("div", { class: "next-name" }, c.name),
        el("div", { class: "next-when" }, whenText(ev), el("span", { class: "badge b-conf" }, "確定"))));
    }));
  }

  function renderWeekTabs(by) {
    const base = currentWeekStart();
    const tabs = [];
    for (let i = 0; i < 12; i++) {
      const mon = addDays(base, i * 7);
      let n = 0;
      for (let k = 0; k < 7; k++) n += (by[ymd(addDays(mon, k))] || []).length;
      tabs.push(el("button", {
        type: "button",
        "aria-pressed": String(ymd(mon) === ymd(state.weekStart)),
        onclick: () => { state.weekStart = mon; renderWeek(); },
      }, el("b", {}, i === 0 ? `今週 ${md(mon)}〜` : `${md(mon)}〜`), el("span", {}, `${n}件`)));
    }
    $("week-tabs").replaceChildren(...tabs);
  }

  function renderWeek() {
    const by = eventsByDay();
    renderNext();
    renderWeekTabs(by);
    const mon = state.weekStart;
    const today = ymd(todayJST());
    const days = [];
    for (let k = 0; k < 7; k++) {
      const d = addDays(mon, k);
      const evs = by[ymd(d)] || [];
      if (k >= 5 && !evs.length) continue; // 土日は予定があるときだけ出す
      days.push([d, evs]);
    }
    const last = days[days.length - 1][0];
    $("week-title").textContent =
      `${mon.getFullYear()}年${mon.getMonth() + 1}月${mon.getDate()}日（月）〜 ${last.getMonth() !== mon.getMonth() ? last.getMonth() + 1 + "月" : ""}${last.getDate()}日（${DOW[last.getDay()]}）`;
    $("week-board").replaceChildren(...days.map(([d, evs]) => el("div", {
      class: `week-day ${ymd(d) === today ? "is-today" : ""} ${d.getDay() % 6 === 0 ? "weekend" : ""}`,
    },
      el("div", { class: "week-day-head" }, el("span", {}, mdw(d)), evs.length ? el("span", { class: "count" }, evs.length) : null),
      el("div", { class: "week-day-body" }, evs.length ? groupedRows(evs) : el("div", { class: "empty small" }, "予定なし")))));
  }

  // ---------- 月間 ----------
  function renderMonthTabs(by) {
    const t = todayJST();
    const tabs = [];
    for (let i = 0; i < 4; i++) {
      const m = new Date(t.getFullYear(), t.getMonth() + i, 1);
      const key = ymd(m).slice(0, 7);
      const n = Object.entries(by).filter(([k]) => k.startsWith(key)).reduce((s, [, v]) => s + v.length, 0);
      const label = i === 0 || m.getMonth() === 0 ? `${m.getFullYear()}年${m.getMonth() + 1}月` : `${m.getMonth() + 1}月`;
      tabs.push(el("button", {
        type: "button",
        "aria-pressed": String(key === ymd(state.month).slice(0, 7)),
        onclick: () => setMonth(m),
      }, el("b", {}, label), el("span", {}, `${n}件`)));
    }
    $("month-tabs").replaceChildren(...tabs);
  }

  function setMonth(m) {
    state.month = new Date(m.getFullYear(), m.getMonth(), 1);
    const key = ymd(state.month).slice(0, 7);
    const today = ymd(todayJST());
    if (today.startsWith(key)) state.selDay = today;
    else {
      const by = eventsByDay();
      state.selDay = Object.keys(by).filter((k) => k.startsWith(key)).sort()[0] || `${key}-01`;
    }
    renderMonth();
  }

  function renderMonth() {
    const by = eventsByDay();
    renderMonthTabs(by);
    const first = state.month;
    $("month-title").textContent = `${first.getFullYear()}年${first.getMonth() + 1}月`;
    const today = ymd(todayJST());
    const cells = DOW.map((d, i) => el("div", { class: `dow ${i === 0 ? "sun" : i === 6 ? "sat" : ""}`, role: "columnheader" }, d));
    const start = addDays(first, -first.getDay());
    for (let i = 0; i < 42; i++) {
      const d = addDays(start, i);
      if (i === 35 && d.getMonth() !== first.getMonth()) break; // 5週で収まる月は6週目を描かない
      const key = ymd(d);
      const evs = by[key] || [];
      const other = d.getMonth() !== first.getMonth();
      const cls = ["cell", other && "other", key === today && "is-today", key === state.selDay && "selected",
        d.getDay() === 0 && "sun", d.getDay() === 6 && "sat", FIXED_HOLIDAYS.includes(key.slice(5)) && "holiday"].filter(Boolean).join(" ");
      cells.push(el("button", {
        type: "button", class: cls, role: "gridcell",
        "aria-label": `${mdw(d)} ${evs.length}社`,
        onclick: () => { state.selDay = key; if (other) state.month = new Date(d.getFullYear(), d.getMonth(), 1); renderMonth(); },
      },
        el("div", { class: "cell-top" }, el("span", { class: "cell-num" }, d.getDate()), evs.length ? el("span", { class: "count" }, evs.length) : null),
        ...evs.slice(0, 3).map((ev) => {
          const kind = ev.status === "done" ? "done" : ev.approx ? "approx" : ev.status === "confirmed" ? "conf" : "";
          return el("div", { class: `cell-name ${kind}` }, state.companies[ev.company].name);
        }),
        evs.length > 3 ? el("div", { class: "cell-more" }, `ほか${evs.length - 3}社`) : null));
    }
    $("month-grid").replaceChildren(...cells);

    const sel = state.selDay ? parse(state.selDay) : first;
    const list = by[ymd(sel)] || [];
    $("day-title").replaceChildren(...[mdw(sel), list.length ? el("span", { class: "count" }, `${list.length}社`) : null].filter(Boolean));
    $("day-list").replaceChildren(...(list.length ? groupedRows(list) : [el("li", { class: "empty" }, "この日の決算予定はありません")]));
  }

  // ---------- 業界マップ ----------
  function renderMap() {
    const today = todayJST();
    const cats = state.data.categories;
    const flow = [];
    STAGES.forEach((st, i) => {
      const present = st.cats.filter((c) => cats.includes(c));
      if (!present.length) return;
      if (flow.length) flow.push(el("div", { class: "arrow", "aria-hidden": "true" }, "→"));
      flow.push(el("div", { class: "stage", style: `flex: ${st.grow} 1 ${st.grow * 125}px` },
        el("div", { class: "stage-label" }, st.step),
        el("div", { class: "stage-cards", style: `grid-template-columns: repeat(${present.length}, minmax(0, 1fr))` },
          present.map((cat) => {
            const info = CAT_INFO[cat] || { short: cat, sub: "", icon: "" };
            const members = state.data.companies.filter((c) => c.category === cat && companyVisible(c, true));
            const soonest = members.map((c) => [c, nextEventOf(c.id, today)]).filter(([, e]) => e)
              .sort((a, b) => placeDate(a[1]).localeCompare(placeDate(b[1])))[0];
            return el("button", {
              type: "button", class: "cat-card", "aria-pressed": String(state.mapCat === cat),
              // 選択中のカードをもう一度押すと選択を外し、全銘柄を表示する
              onclick: () => { state.mapCat = state.mapCat === cat ? null : cat; renderMap(); },
            },
              el("span", { html: SVG_HEAD + info.icon + "</svg>" }),
              el("b", {}, info.short),
              el("span", {}, `${info.sub ? info.sub + " " : ""}${members.length}社`),
              soonest ? el("span", { class: "next" }, `次は ${soonest[1].approx || md(parse(placeDate(soonest[1])))} ${soonest[0].name}`) : null);
          }))));
    });
    $("flow").replaceChildren(...flow);

    // 選んだ分野の一覧とタイムライン
    const cat = state.mapCat;
    const info = cat ? CAT_INFO[cat] || { desc: "" } : { desc: "カテゴリのカードを押すと、そのカテゴリだけに絞り込めます。" };
    const stage = STAGES.find((s) => s.cats.includes(cat));
    const end = new Date(today.getFullYear(), today.getMonth() + 4, 0); // 3か月先の月末まで
    const span = daysBetween(today, end) + 1;
    const pct = (d) => Math.max(0, Math.min(100, (daysBetween(today, d) / span) * 100));

    const months = [];
    for (let m = new Date(today); m <= end; m = new Date(m.getFullYear(), m.getMonth() + 1, 1)) {
      const mEnd = new Date(m.getFullYear(), m.getMonth() + 1, 0);
      const len = daysBetween(m, mEnd < end ? mEnd : end) + 1;
      months.push([m.getMonth() === 0 || !months.length ? `${m.getFullYear()}年${m.getMonth() + 1}月` : `${m.getMonth() + 1}月`, len]);
    }

    const rows = state.data.companies.filter((c) => (!cat || c.category === cat) && companyVisible(c, true))
      .map((c) => [c, nextEventOf(c.id, today)])
      .sort((a, b) => (a[1] ? placeDate(a[1]) : "9999").localeCompare(b[1] ? placeDate(b[1]) : "9999"));

    $("cat-step").textContent = stage ? stage.step : "";
    $("cat-title").replaceChildren(cat || "すべての銘柄", el("span", { class: "count" }, `${rows.length}社`));
    $("cat-desc").textContent = info.desc;

    const head = el("div", { class: "tl-row tl-head" },
      el("div", {}, "発表日"), el("div", {}, "銘柄"), el("div", {}, "市場"), el("div", {}, "状態"),
      el("div", { class: "tl-months", style: `grid-template-columns: ${months.map(([, n]) => n + "fr").join(" ")}` },
        months.map(([label]) => el("span", {}, label))));

    const body = rows.map(([c, ev]) => {
      const track = el("div", { class: "tl-track" }, el("div", { class: "tl-today", title: "今日" }));
      if (ev) {
        if (ev.approx) {
          const d = parse(ev.date);
          const range = /上旬/.test(ev.approx) ? [1, 10] : /中旬/.test(ev.approx) ? [11, 20] : /下旬/.test(ev.approx) ? [21, 31] : [1, 31];
          const last = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
          const a = pct(new Date(d.getFullYear(), d.getMonth(), range[0]));
          const b = pct(new Date(d.getFullYear(), d.getMonth(), Math.min(range[1], last)));
          track.append(el("div", { class: "tl-span", style: `left: ${a}%; width: ${Math.max(1.5, b - a)}%` }));
        } else {
          track.append(el("div", { class: `tl-mark ${ev.status === "confirmed" ? "conf" : "est"}`, style: `left: ${pct(parse(placeDate(ev)))}%` }));
        }
      }
      const attrs = ev ? { type: "button", class: "tl-row", onclick: () => openDetail(ev) } : { class: "tl-row" };
      return el(ev ? "button" : "div", attrs,
        el("div", { class: "tl-date" }, ev ? (ev.approx || md(parse(placeDate(ev)))) : "未定"),
        el("div", { class: "row-main" },
          el("div", { class: "row-title" }, el("span", { class: `code ${c.market === "US" ? "us" : ""}` }, c.id), el("span", { class: "name" }, c.name)),
          cat ? null : el("div", { class: "row-sub" }, c.category)),
        el("div", { class: "small" }, c.market === "US" ? "米国" : "日本"),
        el("div", {}, ev ? badge(ev) : "—"),
        el("div", { class: "tl-track-wrap" }, track));
    });
    $("timeline").replaceChildren(head, ...body);
  }

  // ---------- 銘柄一覧 ----------
  function renderList() {
    const t = state.data.generated_at;
    $("updated").textContent = t
      ? `最終更新 ${new Date(t).toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" })}（日本時間）`
      : "";
    const today = todayJST();
    const head = el("tr", {}, ["コード", "銘柄", "市場", "カテゴリ", "次回の決算", "自動取得", "最終成功"].map((h) => el("th", {}, h)));
    const body = state.data.companies.filter((c) => companyVisible(c)).map((c) => {
      const st = state.data.status?.[c.id] || {};
      const next = nextEventOf(c.id, today);
      const okCell = st.ok === true ? el("span", { class: "ok", title: st.message || "" }, "成功")
        : st.ok === false ? el("span", { class: "ng", title: st.message || "" }, "失敗（前回の値を表示中）")
        : el("span", { class: "na", title: st.message || "" }, "未実行");
      return el("tr", {},
        el("td", { class: "mono" }, c.id),
        el("td", {}, el("a", { href: c.ir_url, target: "_blank", rel: "noopener" }, c.name)),
        el("td", {}, c.market === "US" ? "米国" : "日本"),
        el("td", {}, `${c.category}${c.role === "leader" ? "（けん引役）" : ""}`),
        el("td", {}, next ? [whenText(next), " ", badge(next)] : "—"),
        el("td", {}, okCell),
        el("td", {}, st.last_success ? new Date(st.last_success).toLocaleDateString("ja-JP") : "—"));
    });
    $("status").replaceChildren(el("thead", {}, head), el("tbody", {}, body));
  }

  // ---------- 詳細 ----------
  function openDetail(ev) {
    const c = state.companies[ev.company];
    const rows = [["状態", statusText(ev)], ["決算", ev.label || "—"]];
    if (ev.approx) {
      rows.push(["時期", `${ev.approx}（日付はまだ発表されていません）`]);
    } else {
      rows.push(["現地の日付", `${fmtDate(ev.date)}${ev.time ? " " + ev.time : ""}${c.market === "US" ? "（現地時間）" : ""}`]);
      if (c.market === "US") rows.push(["日本時間", ev.jst ? `${fmtDate(ev.jst)} ${timeOf(ev)}頃` : "時刻未発表"]);
    }
    if (ev.basis) rows.push(["推定の根拠", ev.basis]);
    rows.push(["カテゴリ", `${c.category}・${c.role === "leader" ? "けん引役" : "関連株"}`]);
    rows.push(["出典", el("a", { href: ev.source || c.ir_url, target: "_blank", rel: "noopener" },
      ev.status === "estimated" ? "IRページで確認する" : "出典を開く")]);
    $("detail-body").replaceChildren(
      el("p", { class: "eyebrow" }, `${c.id} ・ ${c.name_en} ・ ${c.market === "US" ? "米国" : "日本"}`),
      el("h3", { id: "detail-title" }, c.name, " ", badge(ev)),
      el("dl", {}, rows.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)])));
    $("detail").showModal();
  }

  // ---------- 画面の切り替え ----------
  function renderView() {
    for (const v of VIEWS) $(`view-${v}`).hidden = v !== state.view;
    for (const a of $$(".tabs a")) {
      if (a.dataset.view === state.view) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    }
    renderFilters();
    ({ week: renderWeek, month: renderMonth, map: renderMap, list: renderList })[state.view]();
  }

  function route() {
    const v = location.hash.replace("#", "");
    state.view = VIEWS.includes(v) ? v : "week";
    renderView();
  }

  async function load() {
    if (window.__EARNINGS_DATA__) return window.__EARNINGS_DATA__;
    const res = await fetch("data/earnings.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`データを読み込めませんでした（${res.status}）`);
    return res.json();
  }

  async function main() {
    try {
      state.data = await load();
    } catch (e) {
      $("loading").textContent = e.message;
      return;
    }
    $("loading").remove();
    state.data.categories ||= [...new Set(state.data.companies.map((c) => c.category))];
    state.companies = Object.fromEntries(state.data.companies.map((c) => [c.id, c]));
    if (state.mapCat && !state.data.categories.includes(state.mapCat)) state.mapCat = state.data.categories[0];
    $("brand-sub").textContent = `AI半導体・データセンター関連 ${state.data.companies.length}社`;
    loadFilters();
    renderLegends();

    const t = todayJST();
    state.weekStart = currentWeekStart();
    state.month = new Date(t.getFullYear(), t.getMonth(), 1);
    state.selDay = ymd(t);

    $("week-prev").addEventListener("click", () => { state.weekStart = addDays(state.weekStart, -7); renderWeek(); });
    $("week-next").addEventListener("click", () => { state.weekStart = addDays(state.weekStart, 7); renderWeek(); });
    $("week-today").addEventListener("click", () => { state.weekStart = currentWeekStart(); renderWeek(); });
    $("month-prev").addEventListener("click", () => setMonth(new Date(state.month.getFullYear(), state.month.getMonth() - 1, 1)));
    $("month-next").addEventListener("click", () => setMonth(new Date(state.month.getFullYear(), state.month.getMonth() + 1, 1)));
    $("month-today").addEventListener("click", () => setMonth(todayJST()));

    window.addEventListener("hashchange", route);
    route();
  }

  main();
})();
