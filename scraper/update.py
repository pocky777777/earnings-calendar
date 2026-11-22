"""決算予定日を各社IRページから集めて docs/data/earnings.json を更新する。

使い方:
    python -m scraper.update            # 取得して更新
    python -m scraper.update --dry-run  # 取得結果を表示するだけ（ファイルは書かない）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import fetch
from .extract import Candidate, extract_candidates, find_follow_links, html_to_lines

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "companies.json"
DATA = ROOT / "docs" / "data" / "earnings.json"
JST = ZoneInfo("Asia/Tokyo")


# ---------- 取得 ----------

def collect(company: dict, today: date) -> tuple[list[Candidate], str, str]:
    """sources を順に試し、(候補, 使ったURL, メッセージ) を返す。全部失敗したら FetchError。"""
    errors = []
    for src in company["sources"]:
        try:
            html = fetch.get(src["url"], render=src.get("render", False), tls_legacy=src.get("tls_legacy", False))
            pages = [(src["url"], html)]
            if src.get("follow"):
                # 一覧ページは表示が必要でも、記事ページ自体は普通のHTMLで読めることが多い
                for link in find_follow_links(html, src["follow"], src["url"]):
                    try:
                        pages.append((link, fetch.get(link, render=src.get("render_follow", False),
                                                      tls_legacy=src.get("tls_legacy", False))))
                    except fetch.FetchError as e:
                        # 記事が1本読めなくても、他の記事や一覧ページで続ける
                        print(f"    記事を読めませんでした: {e}", file=sys.stderr)
            per_page: list[tuple[str, list[Candidate]]] = []
            for url, page in pages:
                found = extract_candidates(html_to_lines(page), company["lang"], today,
                                           date_line=src.get("date_line", "before"))
                per_page.append((url, found))
            cands, used = pick_candidates(per_page, src.get("follow"))
            if cands:
                return cands, used, f"{len(cands)}件の日付を取得"
            errors.append(f"{src['url']}: 決算の日付が見つかりません")
        except fetch.FetchError as e:
            errors.append(str(e))
    raise fetch.FetchError(" / ".join(errors))


# ---------- データの合成（ネットワークなしでテストできる部分） ----------

def pick_candidates(per_page: list[tuple[str, list[Candidate]]], follow: str | None) -> tuple[list[Candidate], str]:
    """ページごとの候補から、使う候補と出典URLを選ぶ。per_page の先頭は一覧ページ。
    follow がある場合、一覧ページに並ぶ「◯◯ Sets Conference Call」などの見出しの日付は
    記事の掲載日であって決算日ではない。そこで記事ページから日付が取れたら記事の分だけを使い、
    取れなかったときだけ、見出し（follow に一致する行）を除いた一覧ページの日付を使う。"""
    list_url, list_cands = per_page[0]
    if follow:
        articles = [(u, cs) for u, cs in per_page[1:] if cs]
        if articles:
            chosen = [(u, c) for u, cs in articles for c in cs]
            used = articles[0][0]
        else:
            rx = re.compile(follow, re.I)
            chosen = [(list_url, c) for c in list_cands if not rx.search(c.context)]
            used = list_url
    else:
        chosen = [(list_url, c) for c in list_cands]
        used = list_url
    for url, c in chosen:
        c.context = url  # どのページから取れたかを出典として残す
    return [c for _, c in chosen], used



def to_jst(d: str, t: str | None, tz: str) -> str | None:
    if not t:
        return None
    local = datetime.fromisoformat(f"{d}T{t}").replace(tzinfo=ZoneInfo(tz))
    return local.astimezone(JST).strftime("%Y-%m-%dT%H:%M")


def merge(events: list[dict], company: dict, cands: list[Candidate], today: date, now: str) -> list[dict]:
    """1社分の取得結果を既存のイベントに混ぜる。
    - 過去の日付は「実績(done)」として履歴に残す（消さない）
    - 未来の予定が新しく取れたら、その会社の未来の予定はそれで置き換える（日程変更に対応）
    - 取れなかった場合は既存の予定をそのまま残す"""
    cid, tz = company["id"], company["tz"]
    mine = [e for e in events if e["company"] == cid and e["status"] != "estimated"]
    others = [e for e in events if e["company"] != cid]
    by_date = {e["date"]: e for e in mine}

    future_new = {c.date.isoformat(): c for c in cands if c.date >= today and c.scheduled}
    if future_new:
        by_date = {k: v for k, v in by_date.items() if date.fromisoformat(k) < today}

    for c in cands:
        key = c.date.isoformat()
        if c.date >= today and not c.scheduled:
            continue
        ev = by_date.get(key, {"company": cid, "date": key})
        ev.update({
            "time": c.time or ev.get("time"),
            # 時刻に「PT」「ET」などが添えてあればそれを使う（会社の所在地と違うことがある）
            "tz": c.tz or ev.get("tz") or tz,
            "label": c.label or ev.get("label"),
            "status": "confirmed" if c.date >= today else "done",
            "approx": c.approx,
            "source": c.context or ev.get("source"),
            "checked_at": now,
        })
        by_date[key] = ev

    for ev in by_date.values():
        if ev["status"] == "confirmed" and date.fromisoformat(ev["date"]) < today:
            ev["status"] = "done"
        ev["jst"] = to_jst(ev["date"], ev.get("time"), ev.get("tz") or tz)

    return others + sorted(by_date.values(), key=lambda e: e["date"])


# 日付が毎年同じ日本の祝日（推定日がここに当たったら前の営業日にずらす）
JP_FIXED_HOLIDAYS = {(1, 1), (1, 2), (1, 3), (2, 11), (2, 23), (4, 29), (5, 3), (5, 4), (5, 5),
                     (8, 11), (11, 3), (11, 23), (12, 31)}


def business_day_on_or_before(d: date, market: str) -> date:
    while d.weekday() >= 5 or (market == "JP" and (d.month, d.day) in JP_FIXED_HOLIDAYS):
        d -= timedelta(days=1)
    return d


def estimate(events: list[dict], company: dict, today: date) -> list[dict]:
    """確定した次回予定が無い会社に、過去の実績から「推定」の日付を1つ付ける。"""
    cid = company["id"]
    events = [e for e in events if not (e["company"] == cid and e["status"] == "estimated")]
    mine = [e for e in events if e["company"] == cid]
    if any(e["status"] == "confirmed" for e in mine):
        return events
    history = sorted(date.fromisoformat(e["date"]) for e in mine if e["status"] == "done")
    if not history:
        return events
    target = history[-1] + timedelta(days=91)
    while target < today:
        target += timedelta(days=91)
    basis = "前回の決算から約3か月ごとと推定"
    for d in history:
        same_q = d + timedelta(days=364)  # 52週後＝前年と同じ曜日
        if abs((same_q - target).days) <= 25 and same_q >= today:
            target, basis = same_q, f"前年同期（{d.isoformat()}）と同じ時期と推定"
    moved = business_day_on_or_before(target, company.get("market", "JP"))
    if moved != target and moved >= today:
        target, basis = moved, basis + "（休日を避けて前の営業日に）"
    events.append({
        "company": cid, "date": target.isoformat(), "time": None, "tz": company["tz"], "jst": None,
        "label": None, "status": "estimated", "basis": basis, "source": company["ir_url"],
        "checked_at": None,
    })
    return events


# ---------- メイン ----------

def run(dry_run: bool = False, today: date | None = None) -> int:
    today = today or datetime.now(JST).date()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    data = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"events": [], "status": {}}
    events, status = data.get("events", []), data.get("status", {})

    failures = 0
    for company in config["companies"]:
        cid = company["id"]
        try:
            cands, used, msg = collect(company, today)
            events = merge(events, company, cands, today, now)
            status[cid] = {"ok": True, "message": msg, "source": used, "checked_at": now,
                           "last_success": now}
            print(f"[OK]   {company['name']}: " + ", ".join(
                f"{c.date}{'' if c.scheduled else '(実績)'}" for c in cands))
        except fetch.FetchError as e:
            failures += 1
            prev = status.get(cid, {})
            status[cid] = {"ok": False, "message": str(e), "checked_at": now,
                           "last_success": prev.get("last_success")}
            print(f"[FAIL] {company['name']}: {e}", file=sys.stderr)
        events = estimate(events, company, today)
    fetch.close()

    # 設定から外した会社のデータは残さない
    ids = {c["id"] for c in config["companies"]}
    events = [e for e in events if e["company"] in ids]
    status = {k: v for k, v in status.items() if k in ids}

    out = {
        "generated_at": now,
        "categories": config.get("categories", []),
        "companies": [{k: v for k, v in c.items() if k not in ("sources", "lang")}
                      for c in config["companies"]],
        "events": sorted(events, key=lambda e: (e["date"], e["company"])),
        "status": status,
    }
    if dry_run:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        DATA.parent.mkdir(parents=True, exist_ok=True)
        DATA.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"更新しました: {DATA.relative_to(ROOT)}（失敗 {failures} 社）")
    # 全社失敗のときだけ異常終了にする（1社の失敗でサイト更新を止めない）
    return 1 if failures == len(config["companies"]) else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    sys.exit(run(ap.parse_args().dry_run))
