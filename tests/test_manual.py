"""手入力ファイル（manual_dates.json）の読み込みと反映のテスト。"""
import json
from datetime import date

from scraper.update import load_manual, merge, estimate

TODAY = date(2026, 11, 23)
NOW = "2026-11-23T12:00:00Z"
AVGO = {"id": "AVGO", "tz": "America/Los_Angeles", "market": "US", "ir_url": "https://investors.broadcom.com/"}


def test_load_and_merge_manual_date(tmp_path):
    f = tmp_path / "manual_dates.json"
    f.write_text(json.dumps({"dates": [{
        "company": "AVGO", "date": "2026-12-09", "time": "14:00", "tz": "America/Los_Angeles",
        "label": "Q4 FY2026", "source": "https://example.com/pr"}]}), encoding="utf-8")
    manual = load_manual(f)
    events = merge([], AVGO, manual["AVGO"], TODAY, NOW)
    ev = events[0]
    assert ev["status"] == "confirmed"
    assert ev["jst"] == "2026-12-10T07:00"          # 太平洋時間 14:00 は日本時間で翌朝 7:00
    assert ev["source"] == "https://example.com/pr"
    assert ev["label"] == "Q4 FY2026"
    # 確定日があれば推定は付けない
    assert [e["status"] for e in estimate(events, AVGO, TODAY)] == ["confirmed"]


def test_missing_file_is_empty(tmp_path):
    assert load_manual(tmp_path / "none.json") == {}


def test_repository_manual_file_is_valid():
    from scraper.update import CONFIG, MANUAL
    ids = {c["id"]: c for c in json.loads(CONFIG.read_text(encoding="utf-8"))["companies"]}
    for cid, cands in load_manual(MANUAL).items():
        assert ids[cid].get("manual"), f"{cid} は companies.json で manual になっていない"
        assert all(c.context.startswith("https://") for c in cands), "出典URLが必要"
