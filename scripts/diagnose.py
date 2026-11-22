"""取得できない会社について、どの取得元なら GitHub Actions から読めるかを試す。

使い方（GitHub の Actions →「取得元の診断」→ Run workflow）:
    python -m scripts.diagnose

robots.txt を守り、1ページごとに3秒あけるのは通常の取得と同じ。名乗り（User-Agent）も変えない。
結果は表にして標準出力と、GitHub Actions の実行画面（Summary）に書く。データは更新しない。
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scraper import fetch
from scraper.extract import extract_candidates, find_follow_links, html_to_lines
from scraper.update import CONFIG, pick_candidates

TARGETS = Path(__file__).with_name("diagnose_targets.json")
JST = ZoneInfo("Asia/Tokyo")


def try_source(src: dict, lang: str, today: date) -> dict:
    """1つの取得元を試し、結果（読めたか・日付が取れたか）を返す。例外は外に出さない。"""
    res = {"result": "", "dates": ""}
    try:
        html = fetch.get(src["url"], render=src.get("render", False), tls_legacy=src.get("tls_legacy", False))
    except fetch.FetchError as e:
        res["result"] = "❌ " + str(e).split(": http")[0][:80]
        return res
    pages = [(src["url"], html)]
    notes = []
    if src.get("follow"):
        links = find_follow_links(html, src["follow"], src["url"])
        notes.append(f"記事{len(links)}本")
        for link in links:
            try:
                pages.append((link, fetch.get(link, render=src.get("render_follow", False),
                                              tls_legacy=src.get("tls_legacy", False))))
            except fetch.FetchError as e:
                notes.append("記事❌" + str(e)[:30])
    per_page = [(u, extract_candidates(html_to_lines(p), lang, today, date_line=src.get("date_line", "before")))
                for u, p in pages]
    cands, _ = pick_candidates(per_page, src.get("follow"))
    future = sorted({c.date for c in cands if c.date >= today})
    past = sorted({c.date for c in cands if c.date < today})
    if not cands:
        res["result"] = "⚠ 読めたが日付なし" + (f"（{'・'.join(notes)}）" if notes else "")
    else:
        res["result"] = f"✅ {len(cands)}件" + (f"（{'・'.join(notes)}）" if notes else "")
        parts = []
        if future:
            parts.append("次: " + ", ".join(d.isoformat() for d in future[:2]))
        if past:
            parts.append("直近: " + past[-1].isoformat())
        res["dates"] = " / ".join(parts)
    return res


def main() -> int:
    today = datetime.now(JST).date()
    config = {c["id"]: c for c in json.loads(CONFIG.read_text(encoding="utf-8"))["companies"]}
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))

    jobs = []
    for cid in targets["include_configured"]:
        for src in config[cid]["sources"]:
            jobs.append((cid, "今の設定", src))
    for cid in targets["render_variant_for"]:
        for src in config[cid]["sources"]:
            if not src.get("render"):
                jobs.append((cid, "今の設定", {**src, "render": True}))
    for c in targets["candidates"]:
        src = {k: v for k, v in c.items() if k not in ("id", "note", "lang")}
        jobs.append((c["id"], c["note"], src))

    rows = ["| 会社 | 試した取得元 | URL | 結果 | 取れた日付 |", "|---|---|---|---|---|"]
    for cid, note, src in jobs:
        lang = next((c.get("lang") for c in targets["candidates"] if c["url"] == src["url"] and "lang" in c),
                    config[cid]["lang"])
        r = try_source(src, lang, today)
        line = f"| {config[cid]['name']} | {note}{'（表示）' if src.get('render') else ''} | {src['url']} | {r['result']} | {r['dates']} |"
        print(line, flush=True)
        rows.append(line)
    fetch.close()

    report = f"## 取得元の診断（{today.isoformat()}）\n\n" + "\n".join(rows) + "\n"
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
