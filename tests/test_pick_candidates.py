"""一覧ページ＋記事ページから候補を選ぶ処理のテスト（2026-11-22 の GitHub Actions で見つかった問題）。

NVIDIA のニュース一覧では「NVIDIA Sets Conference Call for Third-Quarter Financial Results」
という見出しの横に記事の掲載日（決算の約3週間前）が並ぶ。これを決算日として拾っていた。"""
from datetime import date

from scraper.extract import extract_candidates
from scraper.update import pick_candidates

TODAY = date(2026, 11, 22)
FOLLOW = "Sets Conference Call"
LIST_URL = "https://nvidianews.nvidia.com/news?q=Sets%20Conference%20Call"
ARTICLE_URL = "https://nvidianews.nvidia.com/news/nvidia-sets-conference-call-for-third-quarter-financial-results"

LIST_LINES = [
    "October 28, 2026",
    "NVIDIA Sets Conference Call for Third-Quarter Financial Results",
    "July 29, 2026",
    "NVIDIA Sets Conference Call for Second-Quarter Financial Results",
]
ARTICLE_LINES = [
    "NVIDIA Sets Conference Call for Third-Quarter Financial Results",
    "October 28, 2026",
    "NVIDIA will host a conference call on Wednesday, November 18, 2026, at 2 p.m. PT (5 p.m. ET) "
    "to discuss its financial results for the third quarter of fiscal year 2027, which ended October 25, 2026.",
]


def _cands(lines):
    return extract_candidates(lines, "en", TODAY)


def test_list_page_headline_dates_are_not_used_when_article_has_date():
    per_page = [(LIST_URL, _cands(LIST_LINES)), (ARTICLE_URL, _cands(ARTICLE_LINES))]
    cands, used = pick_candidates(per_page, FOLLOW)
    dates = {c.date for c in cands}
    assert date(2026, 11, 18) in dates
    assert date(2026, 7, 29) not in dates  # 一覧の掲載日は使わない
    assert used == ARTICLE_URL
    assert all(c.context == ARTICLE_URL for c in cands)


def test_headline_lines_are_dropped_when_no_article_could_be_read():
    per_page = [(LIST_URL, _cands(LIST_LINES))]
    cands, used = pick_candidates(per_page, FOLLOW)
    assert cands == []
    assert used == LIST_URL


def test_without_follow_list_page_is_used_as_is():
    cands, used = pick_candidates([(LIST_URL, _cands(ARTICLE_LINES))], None)
    assert date(2026, 11, 18) in {c.date for c in cands}
    assert used == LIST_URL
