"""2026-11-23 にブラウザで表示を確認したページの本文（予定を JavaScript で読み込む IR サイト）。

GitHub Actions では予定が表示される前に読み終えて「日付が見つかりません」になっていた。
表示されたあとの本文からは、正しい日付が取れることを確かめておく。"""
from datetime import date

from scraper.extract import extract_candidates

TODAY = date(2026, 11, 23)

META = """Upcoming Events
Stay tuned for upcoming events.
Past Events
Oct 21, 20261:30 PM PT
Q3 2026 Earnings Call
Press Release (pdf)Presentation (pdf)Earnings Call Transcript (pdf)Follow Up Call Transcript (pdf)
Listen to Webcast
Aug 26, 2026
Update on Agreement with Bipartisan Attorneys General
Jul 29, 20261:30 PM PT
Q2 2026 Earnings Call
May 27, 202610:00 AM PT
2026 Annual Shareholder Meeting
Apr 29, 20262:30 PM PT
Q1 2026 Earnings Call""".split("\n")

ORACLE = """Upcoming events
 There are no events scheduled.
Archived Events
November 18, 2026
Annual Meeting of Stockholders
October 28, 2026 10:55 AM CT
Oracle Investor Day Meeting
September 10, 2026 04:00 PM CT
Q1 FY27 Earnings""".split("\n")

CREDO = """Upcoming & Recent Events
December 01, 2026
Q2 FY2027 Earnings Conference Call
Webcast
(OPENS IN NEW WINDOW)
Add to Calendar
September 10, 2026
2026 Goldman Sachs Communacopia + Technology Conference
San Francisco, California
September 01, 2026
Q1 FY2027 Earnings Conference Call""".split("\n")


def _dates(lines):
    return {c.date for c in extract_candidates(lines, "en", TODAY)}


def test_meta_earnings_calls_only():
    assert _dates(META) == {date(2026, 4, 29), date(2026, 7, 29), date(2026, 10, 21)}


def test_oracle_earnings_only_not_investor_day_or_annual_meeting():
    assert _dates(ORACLE) == {date(2026, 9, 10)}


def test_credo_upcoming_earnings_call():
    assert _dates(CREDO) == {date(2026, 9, 1), date(2026, 12, 1)}
