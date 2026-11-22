"""2026-11-21 に追加した16社のIRページ（実際に開いて保存したテキスト）で、取り出し結果を確かめるテスト。"""
import json
from datetime import date
from pathlib import Path

import pytest

from scraper.extract import extract_candidates

TODAY = date(2026, 11, 21)
PAGES = json.loads((Path(__file__).parent / "fixtures" / "real_pages_2026-11-21b.json").read_text(encoding="utf-8"))

D = date
EXPECTED = {
    "dell_events": ([D(2026, 5, 28), D(2026, 9, 1), D(2026, 11, 24)],
                    {D(2026, 11, 24): {"time": "15:30", "tz": "America/Chicago", "label": "Q3 FY2027"}}),
    "amazon_events_rendered": ([D(2026, 4, 29), D(2026, 7, 30), D(2026, 10, 29)], {}),
    # 「Q1 FY27 Earnings」のタイトル。株主総会・投資家説明会は拾わない
    "oracle_events_rendered": ([D(2026, 9, 10)], {D(2026, 9, 10): {"label": "Q1 FY2027"}}),
    "arista_press_rendered": ([D(2026, 8, 4), D(2026, 11, 3)], {}),
    "marvell_ir_calendar": ([D(2026, 5, 27), D(2026, 8, 27), D(2026, 12, 1)],
                            {D(2026, 12, 1): {"time": "13:30", "tz": "America/Los_Angeles"}}),
    "coherent_events": ([D(2026, 2, 4), D(2026, 5, 6), D(2026, 8, 12), D(2026, 11, 4)], {}),
    "vertiv_events_rendered": ([D(2026, 4, 22), D(2026, 7, 29), D(2026, 10, 28)], {}),
    "fujikura_ir_calendar_rendered": ([D(2026, 2, 9), D(2026, 5, 14), D(2026, 8, 7), D(2026, 11, 10)],
                                      {D(2026, 11, 10): {"time": "14:00"}}),
    "furukawa_ir_event": ([D(2027, 2, 8)], {D(2027, 2, 8): {"time": "14:00", "label": "2027年3月期 第3四半期"}}),
    "sumitomo_electric_ir_calendar": ([D(2025, 10, 31), D(2026, 2, 3), D(2026, 5, 12), D(2026, 7, 31),
                                       D(2026, 10, 30)], {D(2026, 10, 30): {"time": "15:00"}}),
    "ibiden_ir_calendar": ([D(2025, 10, 30), D(2026, 2, 3), D(2026, 5, 11), D(2026, 8, 4), D(2026, 10, 29)],
                           {D(2026, 10, 29): {"time": "15:20"}}),
    # 同じ日の「電話会議 17:00」ではなく「決算発表 15:30」の時刻を使う
    "ajinomoto_ir_calendar": ([D(2025, 11, 6), D(2026, 2, 5), D(2026, 5, 7), D(2026, 8, 6), D(2026, 11, 9)],
                              {D(2026, 8, 6): {"time": "15:30"}}),
    "murata_ir_calendar": ([D(2025, 10, 31), D(2026, 2, 2), D(2026, 4, 30), D(2026, 7, 31), D(2026, 10, 30),
                            D(2027, 2, 2)], {D(2027, 2, 2): {"time": "14:00"}}),
    # 年の無い日付。通期決算（4月27日）が前の年度の見出しの下にあるが、「2026年3月期」から2026年と分かる。
    # 「1月29日 2026年3月期 第3四半期」も2027年ではなく2026年
    "hitachi_fr_library": ([D(2025, 10, 30), D(2026, 1, 29), D(2026, 4, 27), D(2026, 7, 29), D(2026, 10, 28)], {}),
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
