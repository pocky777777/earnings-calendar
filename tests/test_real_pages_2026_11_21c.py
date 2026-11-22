"""2026-11-21 に追加した19社のIRページ（実際に開いて保存したテキスト）で、取り出し結果を確かめるテスト。"""
import json
from datetime import date
from pathlib import Path

import pytest

from scraper.extract import extract_candidates

TODAY = date(2026, 11, 21)
PAGES = json.loads((Path(__file__).parent / "fixtures" / "real_pages_2026-11-21c.json").read_text(encoding="utf-8"))

D = date
EXPECTED = {
    "teradyne_ir_calendar": ([D(2026, 7, 29), D(2026, 10, 28)], {}),
    # 「Third quarter earnings of 2026 on October. 28th, 2026」
    "skhynix_invitation_q3": ([D(2026, 10, 28)], {D(2026, 10, 28): {"label": "Q3"}}),
    "skhynix_invitation_q1": ([D(2026, 4, 23)], {}),
    "sandisk_events": ([D(2026, 8, 5), D(2026, 10, 29)], {D(2026, 10, 29): {"label": "Q1 FY2027"}}),
    "credo_schedules_q2": ([D(2026, 12, 1)], {D(2026, 12, 1): {"time": "14:00", "tz": "America/Los_Angeles"}}),
    "nittobo_ir_calendar": ([D(2025, 11, 6), D(2026, 2, 5), D(2026, 5, 12), D(2026, 8, 5), D(2026, 11, 5)], {}),
    "tokyoseimitsu_ir_calendar": ([D(2025, 11, 4), D(2026, 2, 6), D(2026, 5, 13), D(2026, 8, 4), D(2026, 11, 4),
                                   D(2027, 2, 15)], {D(2027, 2, 15): {"approx": "2月中旬"}}),
    "ebara_ir_events": ([D(2025, 11, 13), D(2026, 2, 13), D(2026, 5, 15), D(2026, 8, 14), D(2026, 11, 13)], {}),
    "towa_ir_calendar": ([D(2025, 11, 7), D(2026, 2, 6), D(2026, 5, 11), D(2026, 8, 6), D(2026, 11, 6)], {}),
    # 決算説明会が決算発表の翌日（8/13・2/16）にあるが、決算発表の日だけを残す
    "micronics_ir_calendar": ([D(2025, 11, 11), D(2026, 2, 13), D(2026, 5, 13), D(2026, 8, 12), D(2026, 11, 12)],
                              {}),
    "resonac_ir_top": ([D(2026, 11, 11)], {}),
    "tok_ir_calendar": ([D(2025, 11, 11), D(2026, 2, 9), D(2026, 5, 11), D(2026, 8, 6), D(2026, 11, 10)], {}),
    "jxmetals_ir_calendar": ([D(2026, 5, 11), D(2026, 8, 6), D(2026, 11, 9), D(2027, 2, 15)],
                             {D(2027, 2, 15): {"approx": "2月中旬"}}),
    # 「2026年 4月 4月28日」を4月4日と読まない
    "tdk_ir_calendar": ([D(2025, 10, 31), D(2026, 4, 28), D(2026, 7, 31), D(2026, 10, 30)],
                        {D(2026, 4, 28): {"time": "15:30"}}),
    "swcc_ir_calendar": ([D(2025, 11, 12), D(2026, 2, 9), D(2026, 5, 14), D(2026, 8, 7), D(2026, 11, 11),
                          D(2027, 2, 5)], {D(2027, 2, 5): {"approx": "2月上旬"}}),
    "mitsubishielectric_ir_top": ([D(2026, 10, 30)], {}),
    "fujielectric_ir_calendar": ([D(2026, 7, 30), D(2026, 10, 29)], {}),
    # 1行に4つの決算が並ぶ。年の無い日付は各「2026年3月期…」から年を決める
    "sakura_ir_calendar": ([D(2026, 1, 30), D(2026, 4, 27), D(2026, 7, 28), D(2026, 10, 28)], {}),
}


def test_every_captured_page_has_expectations():
    assert set(EXPECTED) == set(PAGES)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_real_page(name):
    page = PAGES[name]
    got = extract_candidates(page["lines"], page["lang"], TODAY, date_line=page.get("date_line", "before"))
    dates, checks = EXPECTED[name]
    assert [c.date for c in got] == dates
    by_date = {c.date: c for c in got}
    for d, fields in checks.items():
        for k, v in fields.items():
            assert getattr(by_date[d], k) == v, (d, k)
