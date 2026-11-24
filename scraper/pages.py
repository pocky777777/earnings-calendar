"""会社ごとの決算発表日のページ（docs/c/<id>.html）と、その一覧・サイトマップを作る。

カレンダー本体（docs/index.html）は JavaScript で表示するので、検索エンジンには中身が伝わりにくい。
そこで、毎晩の更新のあとに会社ごとの「◯◯の決算発表日」という普通の HTML ページを書き出し、
「会社名 決算発表日」のような検索で見つけてもらえるようにする。データは earnings.json だけを使う。

使い方:
    python -m scraper.pages
"""
from __future__ import annotations

import html
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DATA = DOCS / "data" / "earnings.json"
OUT = DOCS / "c"
SITE = "https://pocky777777.github.io/earnings-calendar/"
BRAND = "ひとくち決算カレンダー"
YOUTUBE = "https://www.youtube.com/@hitokuchi_kessan"
JST = ZoneInfo("Asia/Tokyo")
DOW = "月火水木金土日"

# 業界マップと同じ分野の説明（docs/app.js の CAT_INFO と合わせる）
CAT_DESC = {
    "AIの買い手": "データセンターに投資する側。設備投資の見通しが、ほかの分野の需要の目安になります。",
    "AIサーバー・ネットワーク": "サーバーを組み立て、つなぐ会社。買い手の投資が最初に売上になる分野です。",
    "光・電線": "サーバー同士や建物をつなぐ光ファイバーと電線の会社です。",
    "電力・冷却": "データセンターの電源と冷却設備の会社です。",
    "AI半導体": "GPUや専用チップを設計・製造する会社です。",
    "メモリ・素材": "HBMなどのメモリと、ウエハーや化学材料の会社です。",
    "製造装置": "チップを作る・検査する装置の会社。日本企業が強い分野です。",
    "基板・電子部品": "チップを載せる基板と、その材料・部品の会社です。",
}

STATUS = {
    "confirmed": ("確定", "b-conf", "会社が発表した日付です。"),
    "estimated": ("予想", "b-est", "会社がまだ日程を出していないため、過去の発表日から出した目安です。会社が発表すると自動で置き換わります。"),
    "done": ("発表済み", "b-done", ""),
}


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def jp_date(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日（{DOW[d.weekday()]}）"


def place(ev: dict) -> date:
    """カレンダーに置く日付。時刻が分かっていれば日本時間の日付、なければ現地の日付。"""
    return date.fromisoformat((ev.get("jst") or ev["date"])[:10])


def when_text(ev: dict, company: dict) -> str:
    """「2027年1月27日（水）15:30」のような表示。米国株は日本時間を書き、現地の日付も添える。"""
    if ev.get("approx"):
        return esc(ev["approx"])
    d = place(ev)
    t = (ev.get("jst") or "")[11:16]
    s = jp_date(d) + (f" {t}" if t else "")
    if company["market"] == "US":
        local = date.fromisoformat(ev["date"])
        s += "（日本時間）" if t else ""
        s += f"<br><span class=\"muted small\">現地 {local.month}月{local.day}日{(' ' + ev['time']) if ev.get('time') else ''}</span>"
    return s


def badge(ev: dict) -> str:
    if ev.get("approx") and ev["status"] != "done":
        return '<span class="badge b-approx">時期のみ</span>'
    label, cls, _ = STATUS[ev["status"]]
    return f'<span class="badge {cls}">{label}</span>'


def next_event(events: list[dict], today: date) -> dict | None:
    future = [e for e in events if e["status"] != "done" and place(e) >= today]
    return min(future, key=place) if future else None


def page_shell(title: str, description: str, canonical: str, body: str, depth: str = "../") -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="icon" href="{depth}favicon.svg" type="image/svg+xml">
  <meta name="theme-color" content="#12306e">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="{BRAND}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:image" content="{SITE}og.png">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="stylesheet" href="{depth}style.css">
</head>
<body>
  <header class="site-header">
    <div class="wrap header-row">
      <a class="brand" href="{depth}">
        <span class="brand-name">{BRAND}</span>
        <span class="brand-sub">AI半導体・データセンター関連の決算予定日</span>
      </a>
      <nav class="tabs" aria-label="ページの移動">
        <a href="{depth}#week">週間</a>
        <a href="{depth}#month">月間</a>
        <a href="{depth}#map">業界マップ</a>
        <a href="{depth}c/">会社一覧</a>
        <a href="{YOUTUBE}" class="yt-link" target="_blank" rel="noopener">YouTube</a>
      </nav>
    </div>
  </header>
  <main class="wrap main company-page">
{body}
  </main>
  <footer class="site-footer">
    <div class="wrap">
      <p>日付は各社のIRページから毎晩自動で取得しています（一部の会社は会社の発表を確認して手入力）。会社の都合で変わることがあるので、最終確認は出典でお願いします。投資の助言ではありません。</p>
      <p><a href="{YOUTUBE}" target="_blank" rel="noopener">YouTube「ひとくち決算」</a>で、決算から見る値動きを短い動画で解説しています。</p>
    </div>
  </footer>
</body>
</html>
"""


def company_page(c: dict, events: list[dict], peers: list[tuple[dict, dict | None]], today: date, generated: str) -> str:
    code = c["id"]
    name = c["name"]
    nxt = next_event(events, today)
    past = sorted([e for e in events if e["status"] == "done" or place(e) < today], key=place, reverse=True)
    market = "米国株" if c["market"] == "US" else "日本株"

    if nxt:
        head_date = nxt.get("approx") or jp_date(place(nxt)).split("（")[0]
        state = "時期のみ発表" if nxt.get("approx") else STATUS[nxt["status"]][0]
        title = f"{name}（{code}）の決算発表日｜次回は{head_date}（{state}）｜{BRAND}"
        desc = (f"{name}（{code}）の次回の決算発表日は{head_date}（{state}）。"
                f"{c['category']}の{market}。過去の決算発表日と、同じ分野の会社の予定もまとめています。")
    else:
        title = f"{name}（{code}）の決算発表日｜{BRAND}"
        desc = f"{name}（{code}）の決算発表日。{c['category']}の{market}。"

    # 次回の決算
    if nxt:
        note = STATUS[nxt["status"]][2]
        if nxt.get("approx"):
            note = "会社が時期だけを発表しています。日付が決まると自動で置き換わります。"
        basis = f'<p class="muted small">推定の根拠：{esc(nxt["basis"])}</p>' if nxt.get("basis") else ""
        src_label = "IRページで確認する" if nxt["status"] == "estimated" else "出典（会社の発表）"
        next_html = f"""
      <section class="panel next-box" aria-labelledby="next-h">
        <div class="panel-head"><h2 id="next-h">次回の決算発表</h2>{badge(nxt)}</div>
        <div class="next-body">
          <p class="next-date">{when_text(nxt, c)}</p>
          <p class="muted small">{esc(nxt.get("label") or "")}</p>
          <p>{esc(note)}</p>
          {basis}
          <p><a href="{esc(nxt.get("source") or c["ir_url"])}" target="_blank" rel="noopener">{src_label}</a></p>
        </div>
      </section>"""
    else:
        next_html = """
      <section class="panel next-box"><div class="next-body"><p>次回の決算発表日はまだ分かっていません。</p></div></section>"""

    rows = "".join(
        f"<tr><td>{jp_date(place(e))}</td><td>{esc(e.get('label') or '—')}</td>"
        f"<td>{('<a href=\"' + esc(e['source']) + '\" target=\"_blank\" rel=\"noopener\">出典</a>') if e.get('source') else '—'}</td></tr>"
        for e in past[:8]
    )
    past_html = f"""
      <section class="panel" aria-labelledby="past-h">
        <div class="panel-head"><h2 id="past-h">過去の決算発表日</h2></div>
        <div class="scroll-x"><table class="status-table"><thead><tr><th>発表日</th><th>決算</th><th>出典</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="3">まだ記録がありません</td></tr>'}</tbody></table></div>
      </section>"""

    peer_rows = "".join(
        f'<li><a href="{esc(p["id"])}.html">{esc(p["name"])}</a>'
        f'<span class="muted small">{(" " + (e.get("approx") or jp_date(place(e)))) if e else " 未定"}</span></li>'
        for p, e in peers
    )
    body = f"""    <nav class="crumbs small"><a href="../">カレンダー</a> › <a href="./">会社一覧</a> › {esc(name)}</nav>
    <h1>{esc(name)}（{esc(code)}）の決算発表日</h1>
    <p class="lead">{esc(c["name_en"])} ・ {market} ・ {esc(c["category"])}{"（業界をけん引する会社）" if c.get("role") == "leader" else ""}</p>
    <div class="company-grid">
      <div class="company-main">{next_html}
{past_html}
      </div>
      <aside class="company-side">
        <section class="panel" aria-labelledby="cat-h">
          <div class="panel-head"><h2 id="cat-h">{esc(c["category"])}</h2></div>
          <div class="next-body">
            <p>{esc(CAT_DESC.get(c["category"], ""))}</p>
            <p class="small"><a href="../#map">業界マップで流れを見る</a></p>
          </div>
        </section>
        <section class="panel" aria-labelledby="peer-h">
          <div class="panel-head"><h2 id="peer-h">同じ分野の会社の次回</h2></div>
          <ul class="peer-list">{peer_rows}</ul>
        </section>
        <section class="panel">
          <div class="next-body">
            <p class="small"><a href="{esc(c["ir_url"])}" target="_blank" rel="noopener">{esc(name)}のIRページ</a></p>
            <p class="small muted">このページの更新：{esc(generated)}（日本時間）</p>
          </div>
        </section>
      </aside>
    </div>"""
    return page_shell(title, desc, f"{SITE}c/{code}.html", body)


def index_page(data: dict, nexts: dict[str, dict | None], generated: str) -> str:
    groups = []
    for cat in data["categories"]:
        items = [c for c in data["companies"] if c["category"] == cat]
        lis = "".join(
            f'<li><a href="{esc(c["id"])}.html">{esc(c["name"])}<span class="muted small">（{esc(c["id"])}）</span></a>'
            f'<span class="small">{(nexts[c["id"]].get("approx") or jp_date(place(nexts[c["id"]]))) if nexts[c["id"]] else "未定"}'
            f'{(" " + badge(nexts[c["id"]])) if nexts[c["id"]] else ""}</span></li>'
            for c in items
        )
        groups.append(f"""
      <section class="panel" aria-labelledby="g-{esc(cat)}">
        <div class="panel-head"><h2 id="g-{esc(cat)}">{esc(cat)}</h2><span class="muted small">{len(items)}社</span></div>
        <ul class="peer-list">{lis}</ul>
      </section>""")
    body = f"""    <nav class="crumbs small"><a href="../">カレンダー</a> › 会社一覧</nav>
    <h1>会社ごとの決算発表日</h1>
    <p class="lead">AI半導体・データセンター関連の日米{len(data["companies"])}社の、次回の決算発表日の一覧です（{esc(generated)} 時点）。</p>
    <div class="index-grid">{"".join(groups)}
    </div>"""
    return page_shell(f"会社ごとの決算発表日（日米{len(data['companies'])}社）｜{BRAND}",
                      f"AI半導体・データセンター関連の日米{len(data['companies'])}社の決算発表日を、会社ごとにまとめています。",
                      f"{SITE}c/", body)


def sitemap(company_ids: list[str], lastmod: str) -> str:
    urls = [SITE, f"{SITE}c/"] + [f"{SITE}c/{cid}.html" for cid in company_ids]
    items = "\n".join(f"  <url>\n    <loc>{esc(u)}</loc>\n    <lastmod>{lastmod}</lastmod>\n  </url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}\n</urlset>\n'


def build(data: dict, today: date, out: Path = OUT, docs: Path = DOCS) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    gen_at = data.get("generated_at")
    if gen_at:
        g = datetime.fromisoformat(gen_at.replace("Z", "+00:00")).astimezone(JST)
        generated = f"{g.year}年{g.month}月{g.day}日 {g:%H:%M}"   # Windows でも動くよう %-m は使わない
    else:
        generated = f"{today.year}年{today.month}月{today.day}日"
    by_company: dict[str, list[dict]] = {}
    for e in data["events"]:
        by_company.setdefault(e["company"], []).append(e)
    nexts = {c["id"]: next_event(by_company.get(c["id"], []), today) for c in data["companies"]}

    written = []
    ids = []
    for c in data["companies"]:
        peers = [(p, nexts[p["id"]]) for p in data["companies"] if p["category"] == c["category"] and p["id"] != c["id"]]
        peers.sort(key=lambda pe: place(pe[1]) if pe[1] else date.max)
        path = out / f"{c['id']}.html"
        path.write_text(company_page(c, by_company.get(c["id"], []), peers, today, generated), encoding="utf-8")
        written.append(path)
        ids.append(c["id"])
    (out / "index.html").write_text(index_page(data, nexts, generated), encoding="utf-8")
    written.append(out / "index.html")
    # 掲載をやめた会社の古いページを消す
    for old in out.glob("*.html"):
        if old.stem not in ids and old.name != "index.html":
            old.unlink()
    (docs / "sitemap.xml").write_text(sitemap(ids, today.isoformat()), encoding="utf-8")
    return written


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    today = datetime.now(JST).date()
    written = build(data, today)
    print(f"会社ごとのページを書き出しました: {len(written)} ファイル")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
