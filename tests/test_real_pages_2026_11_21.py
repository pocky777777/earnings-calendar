"""2026-11-21 に各社のIRページを実際に開いて保存したテキストで、取り出し結果を確かめるテスト。
期待値は、ページを人の目で見て書いたもの。サイトの作りが変わって取れなくなったら、ここで気づける。"""
import json
from datetime import date
from pathlib import Path

import pytest

from scraper.extract import extract_candidates

TODAY = date(2026, 11, 21)
PAGES = json.loads((Path(__file__).parent / "fixtures" / "real_pages_2026-11-21.json").read_text(encoding="utf-8"))

D = date
# ページ名: (取れるべき日付の一覧, 日付ごとの追加チェック)
EXPECTED = {
    "lasertec_ir_calendar_rendered": ([D(2026, 1, 30), D(2026, 4, 30), D(2026, 8, 6), D(2026, 10, 30)], {}),
    "disco_ir_calendar": ([D(2027, 1, 28)], {D(2027, 1, 28): {"time": "16:00"}}),
    "screen_ir_calendar": ([D(2025, 10, 31), D(2026, 1, 30), D(2026, 5, 13), D(2026, 7, 28), D(2026, 10, 30),
                            D(2027, 1, 25)], {D(2027, 1, 25): {"approx": "1月下旬"}}),
    "kokusai_ir_calendar_rendered": ([D(2025, 11, 11), D(2026, 2, 12), D(2026, 5, 13), D(2026, 8, 6), D(2026, 11, 9)],
                                     {D(2026, 11, 9): {"time": "14:00"}}),
    "softbankg_ir_calendar": ([D(2025, 11, 11), D(2026, 2, 12), D(2026, 5, 13), D(2026, 8, 6), D(2026, 11, 10)], {}),
    "socionext_ir_calendar": ([D(2025, 10, 31), D(2026, 1, 30), D(2026, 4, 28), D(2026, 7, 29), D(2026, 10, 28)], {}),
    "renesas_financial_calendar": ([D(2025, 10, 30), D(2026, 2, 5), D(2026, 4, 24), D(2026, 7, 31), D(2026, 10, 29)],
                                   {}),
    "kioxia_ir_calendar": ([D(2025, 11, 13), D(2026, 2, 12), D(2026, 5, 15), D(2026, 7, 31), D(2026, 10, 30)],
                           {D(2026, 10, 30): {"label": "2027年3月期 第2四半期"}}),
    # 「第1四半期決算日」（四半期の最終日）は拾わない
    "shinetsu_ir_calendar": ([D(2026, 1, 27), D(2026, 4, 28), D(2026, 7, 24), D(2026, 10, 27)], {}),
    "sumco_ir_calendar_rendered": ([D(2025, 11, 11), D(2026, 2, 10), D(2026, 5, 12), D(2026, 8, 6), D(2026, 11, 11)],
                                   {D(2026, 11, 11): {"time": "15:30", "scheduled": True}}),
    "amd_ir_calendar": ([D(2026, 8, 4), D(2026, 11, 3)],
                        {D(2026, 11, 3): {"time": "14:00", "tz": "America/Los_Angeles", "label": "Q3 2026"}}),
    "broadcom_events": ([D(2026, 12, 9)], {D(2026, 12, 9): {"time": "17:00", "tz": "America/New_York"}}),
    "tsmc_financial_calendar": ([D(2026, 1, 15), D(2026, 4, 16), D(2026, 7, 16), D(2026, 10, 15)],
                                {D(2026, 10, 15): {"label": "Q3 2026"}}),
    "asml_quarterly_results": ([D(2026, 10, 14)], {}),
    "amat_events": ([D(2026, 8, 13), D(2026, 11, 12)], {}),
    # タイトルの「後」に日付の行が来るページ
    "lam_events": ([D(2026, 1, 28), D(2026, 4, 22), D(2026, 7, 29), D(2026, 10, 21)], {}),
    "kla_ir_calendar": ([D(2026, 7, 28), D(2026, 10, 28)], {D(2026, 10, 28): {"label": "Q1 FY2027"}}),
    "micron_events_rendered": ([D(2026, 9, 30)], {}),
    "microsoft_investor_home": ([D(2026, 10, 28)], {D(2026, 10, 28): {"label": "Q1 FY2027"}}),
    "alphabet_announces_date_q3": ([D(2026, 10, 28)], {D(2026, 10, 28): {"time": "13:30"}}),
    # 「Oct 21, 20261:30 PM」のように年と時刻がくっついた表示
    "meta_events_rendered": ([D(2026, 7, 29), D(2026, 10, 21)], {D(2026, 10, 21): {"time": "13:30"}}),
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
