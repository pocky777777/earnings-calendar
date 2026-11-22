"""IRページから集めた日本株の決算日を、J-Quants の「決算発表予定日」と突き合わせて正誤を確かめる。

これは自分のPCで動かす確認用の道具です。
- J-Quants のデータは規約上そのまま公開できないため、結果（verify_report.md）はコミット・公開しないこと
  （.gitignore 済み）。サイトに載せるデータは引き続き各社IRページから取る。
- APIキーは環境変数 JQUANTS_API_KEY から読む。画面やファイルには出さない。

使い方（PowerShell）:
    $env:JQUANTS_API_KEY = "ダッシュボードで発行したAPIキー"
    python scripts/verify_jquants.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data" / "earnings.json"
REPORT = ROOT / "verify_report.md"
API = "https://api.jquants.com/v2/fins/earnings-date"
NEAR_DAYS = 20   # 同じ四半期の決算とみなす日数の幅


def fetch_earnings_dates(code: str, api_key: str) -> list[dict]:
    """1銘柄の決算発表予定日の公表履歴（変更・未定を含む）をすべて取る。"""
    rows, key = [], None
    while True:
        params = {"code": code}
        if key:
            params["pagination_key"] = key
        r = requests.get(API, headers={"x-api-key": api_key}, params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"{code}: HTTP {r.status_code} {r.text[:200]}")
        body = r.json()
        rows += body.get("data", [])
        key = body.get("pagination_key")
        if not key:
            return rows
        time.sleep(1)


def latest_schedule(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """(決算期末, 四半期) ごとに、最後に公表された予定日のレコードを返す（日程変更を反映するため）。"""
    best: dict[tuple[str, str], dict] = {}
    for r in sorted(rows, key=lambda r: r.get("PubDate", "")):
        best[(r.get("FYE", ""), r.get("FQName", ""))] = r
    return best


def compare(events: list[dict], schedule: dict[tuple[str, str], dict], today: date) -> list[dict]:
    """カレンダーの1社分のイベントと J-Quants の予定日を突き合わせ、行ごとの判定を返す。"""
    jq = []  # (日付 or None, 四半期, 公表日)
    for (fye, fq), r in schedule.items():
        sch = r.get("SchDate") or ""
        jq.append((date.fromisoformat(sch) if sch else None, f"{fq}（{fye}期末）", r.get("PubDate", "")))
    jq_dates = [d for d, _, _ in jq if d]
    results, used = [], set()

    for ev in sorted(events, key=lambda e: e["date"]):
        d = date.fromisoformat(ev["date"])
        near = sorted((abs((j - d).days), j) for j in jq_dates if abs((j - d).days) <= NEAR_DAYS)
        kind = ("推定" if ev["status"] == "estimated" else
                "時期のみ" if ev.get("approx") else
                "予定" if ev["status"] == "confirmed" else "実績")
        row = {"date": ev["date"], "kind": kind, "approx": ev.get("approx"), "jq": None, "result": ""}
        if not near:
            row["result"] = "照合なし（J-Quantsに該当する決算が見つからない）"
        else:
            j = near[0][1]
            used.add(j)
            row["jq"] = j.isoformat()
            if kind == "推定":
                row["result"] = ("推定が的中" if j == d else
                                 f"会社発表あり → {j.isoformat()}（IRページから取れていない可能性）"
                                 if j >= today else f"推定とずれ（実際は {j.isoformat()}）")
            elif kind == "時期のみ":
                row["result"] = f"会社は日付を発表済み → {j.isoformat()}" if j != d else "一致"
            else:
                row["result"] = "✅ 一致" if j == d else f"❌ 不一致（J-Quants: {j.isoformat()}）"
        results.append(row)

    # J-Quants にあるのにカレンダーに無い「これからの予定日」
    for d, fq, pub in jq:
        if d and d >= today and d not in used:
            results.append({"date": "—", "kind": "未掲載", "approx": None, "jq": d.isoformat(),
                            "result": f"⚠ カレンダーに無い予定日 {d.isoformat()} {fq}（{pub}公表）"})
    # 未定に変更されたもの
    for d, fq, pub in jq:
        if d is None:
            results.append({"date": "—", "kind": "未定", "approx": None, "jq": "未定",
                            "result": f"J-Quantsでは {fq} が「未定」（{pub}公表）"})
    return results


def jq_code(cid: str) -> str:
    # J-Quants は5桁（末尾0）で返す。4桁でも指定できるが、そろえておく
    return cid + "0" if len(cid) == 4 else cid


def main() -> int:
    api_key = os.environ.get("JQUANTS_API_KEY", "").strip()
    if not api_key:
        print("環境変数 JQUANTS_API_KEY を設定してください（スクリプトの先頭のコメント参照）", file=sys.stderr)
        return 2
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    by_company = defaultdict(list)
    for ev in data["events"]:
        by_company[ev["company"]].append(ev)

    lines = [f"# 決算日の照合結果（{today}・J-Quants /v2/fins/earnings-date）", "",
             "※ J-Quantsのデータを含むため公開しないこと。米国株はJ-Quantsに無いので対象外。", ""]
    totals = defaultdict(int)
    for c in data["companies"]:
        if c["market"] != "JP":
            continue
        try:
            rows = fetch_earnings_dates(jq_code(c["id"]), api_key)
        except Exception as e:  # noqa: BLE001  1社の失敗で全体を止めない
            lines += [f"## {c['name']}（{c['id']}）", f"取得エラー: {e}", ""]
            totals["取得エラー"] += 1
            continue
        res = compare(by_company[c["id"]], latest_schedule(rows), today)
        lines += [f"## {c['name']}（{c['id']}）", "", "| カレンダー | 種類 | J-Quants | 判定 |", "|---|---|---|---|"]
        for r in res:
            shown = f"{r['date']}（{r['approx']}）" if r["approx"] else r["date"]
            lines.append(f"| {shown} | {r['kind']} | {r['jq'] or '—'} | {r['result']} |")
            key = ("一致" if r["result"].startswith(("✅", "推定が的中", "一致")) else
                   "不一致" if r["result"].startswith("❌") else
                   "要確認" if r["result"].startswith(("⚠", "会社発表あり", "会社は日付")) else "その他")
            totals[key] += 1
        lines.append("")
        issues = " / ".join(r["result"] for r in res if not r["result"].startswith(("✅", "推定が的中")))
        print(f"{c['name']:12} {issues or 'すべて一致'}")
        time.sleep(1)  # レート制限に配慮

    summary = "、".join(f"{k} {v}件" for k, v in totals.items())
    lines[3:3] = [f"**集計: {summary}**", ""]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n集計: {summary}\n詳しい結果: {REPORT.relative_to(ROOT)}")
    return 1 if totals["不一致"] else 0


if __name__ == "__main__":
    sys.exit(main())
