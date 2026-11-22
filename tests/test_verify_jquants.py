"""J-Quants との照合ロジックのテスト（APIには接続しない。レコードは仕様どおりの形の作り物）。"""
from datetime import date

from scripts.verify_jquants import compare, latest_schedule

TODAY = date(2026, 11, 21)


def rec(pub, sch, fq, fye="0331"):
    return {"PubDate": pub, "SchDate": sch, "FQName": fq, "FYE": fye, "Code": "80350"}


def test_latest_schedule_reflects_change():
    rows = [rec("2026-09-30", "2026-10-29", "2Q"), rec("2026-10-10", "2026-10-30", "2Q")]
    assert latest_schedule(rows)[("0331", "2Q")]["SchDate"] == "2026-10-30"


def test_compare_match_mismatch_and_missing():
    rows = [rec("2026-06-30", "2026-07-30", "1Q"), rec("2026-09-30", "2026-10-30", "2Q"),
            rec("2026-11-20", "2027-02-05", "3Q")]
    events = [
        {"date": "2026-07-30", "status": "done"},          # 一致
        {"date": "2026-10-29", "status": "done"},          # 1日ずれ → 不一致
        {"date": "2027-02-04", "status": "estimated"},     # 推定だが会社は発表済み
    ]
    res = compare(events, latest_schedule(rows), TODAY)
    assert res[0]["result"] == "✅ 一致"
    assert res[1]["result"].startswith("❌") and res[1]["jq"] == "2026-10-30"
    assert res[2]["result"].startswith("会社発表あり → 2027-02-05")


def test_compare_reports_dates_missing_from_calendar_and_undecided():
    rows = [rec("2026-11-20", "2027-01-28", "3Q"), rec("2026-11-21", "", "FY")]
    res = compare([], latest_schedule(rows), TODAY)
    assert any(r["result"].startswith("⚠ カレンダーに無い予定日 2027-01-28") for r in res)
    assert any("未定" in r["result"] for r in res)
