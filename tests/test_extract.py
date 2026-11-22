"""実際のIRページの書き方をまねたHTMLで、取り出し処理を確かめるテスト。
ネットワークには触れないので、GitHub Actions でもすぐ動く。"""
from datetime import date

from scraper.extract import extract_candidates, find_follow_links, html_to_lines
from scraper.update import estimate, merge, to_jst

TODAY = date(2026, 11, 19)


def cands(html, lang, today=TODAY):
    return extract_candidates(html_to_lines(html), lang, today)


def test_ja_news_list_ignores_publish_date():
    # ニュース一覧: 先頭の掲載日ではなく、文中の予定日を取る
    html = """<ul>
      <li><span>2026.10.15</span> <a>2026年度第2四半期 決算発表は10月28日(水)15:30の予定です</a></li>
      <li><span>2026.07.29</span> <a>2027年3月期 第1四半期決算短信〔IFRS〕(連結)</a></li>
      <li><span>2026.06.01</span> <a>期末配当金支払開始のお知らせ</a></li>
    </ul>"""
    got = cands(html, "ja")
    assert [c.date for c in got] == [date(2026, 7, 29), date(2026, 10, 28)]
    oct28 = got[1]
    assert oct28.time == "15:30" and oct28.scheduled
    assert got[0].scheduled is False  # 決算短信＝終わった決算


def test_ja_ir_calendar_table():
    # IRカレンダーの表: 日付セルが項目名の左にある形
    html = """<table>
      <tr><th>2027年2月5日</th><td>2027年3月期 第3四半期決算発表（予定）</td></tr>
      <tr><th>2026年10月30日</th><td>2027年3月期 第2四半期決算発表</td></tr>
      <tr><th>2026年6月19日</th><td>第63期 定時株主総会</td></tr>
    </table>"""
    got = cands(html, "ja")
    assert [c.date for c in got] == [date(2026, 10, 30), date(2027, 2, 5)]
    assert got[1].label == "2027年3月期 第3四半期"


def test_ja_month_day_without_year_rolls_to_next_year():
    html = "<p>次回の決算発表は1月29日を予定しています</p>"
    assert cands(html, "ja")[0].date == date(2027, 1, 29)


def test_en_press_release_picks_call_date_not_quarter_end():
    html = """<p>NVIDIA will host a conference call on Wednesday, Feb. 24, at 2 p.m. PT (5 p.m. ET),
      to discuss its financial results for the fourth quarter and fiscal year 2027,
      which ended Jan. 31, 2027.</p>"""
    got = cands(html, "en")
    assert len(got) == 1
    assert got[0].date == date(2027, 2, 24)
    assert got[0].time == "14:00"


def test_out_of_range_dates_are_dropped():
    html = "<li>2019年5月10日 2019年3月期 決算発表</li>"
    assert cands(html, "ja") == []


def test_follow_links():
    html = """<a href="/news/a">NVIDIA Sets Conference Call for Fourth-Quarter Financial Results</a>
              <a href="/news/b">NVIDIA Announces New GPU</a>"""
    assert find_follow_links(html, "Sets Conference Call", "https://example.com/news") == [
        "https://example.com/news/a"]


COMPANY = {"id": "6857", "tz": "Asia/Tokyo", "ir_url": "https://example.com/ir"}
US = {"id": "NVDA", "tz": "America/Los_Angeles", "ir_url": "https://example.com/nv"}


def test_merge_reschedule_and_history():
    old = [
        {"company": "6857", "date": "2026-07-29", "status": "done"},
        {"company": "6857", "date": "2027-01-27", "status": "confirmed"},
    ]
    new = cands("<li>第3四半期 決算発表は1月29日15:30の予定です</li>", "ja")
    ev = merge(old, COMPANY, new, TODAY, "now")
    dates = {e["date"]: e["status"] for e in ev}
    assert dates == {"2026-07-29": "done", "2027-01-29": "confirmed"}  # 1/27 は日程変更で置き換え


def test_merge_keeps_old_schedule_when_nothing_new():
    old = [{"company": "6857", "date": "2027-01-27", "status": "confirmed", "time": None}]
    ev = merge(old, COMPANY, [], TODAY, "now")
    assert ev[0]["status"] == "confirmed"


def test_estimate_uses_same_quarter_last_year():
    ev = [{"company": "8035", "date": d, "status": "done"} for d in ("2026-02-06", "2026-07-30")]
    tel = {"id": "8035", "tz": "Asia/Tokyo", "ir_url": "x"}
    est = [e for e in estimate(ev, tel, TODAY) if e["status"] == "estimated"]
    assert est[0]["date"] == "2027-02-05"


def test_no_estimate_when_confirmed_exists():
    ev = [{"company": "6857", "date": "2027-01-29", "status": "confirmed"},
          {"company": "6857", "date": "2026-10-28", "status": "done"}]
    assert not any(e["status"] == "estimated" for e in estimate(ev, COMPANY, TODAY))


def test_us_time_converted_to_jst():
    # 米国西海岸 2/24 14:00 → 日本時間 2/25 07:00
    assert to_jst("2027-02-24", "14:00", "America/Los_Angeles") == "2027-02-25T07:00"


# ---------- 実際のページ（2026-11-19に取得）から作ったテスト ----------
import json
from pathlib import Path

REAL = json.loads((Path(__file__).parent / "fixtures" / "real_pages.json").read_text(encoding="utf-8"))


def real(name):
    fx = REAL[name]
    return extract_candidates(fx["lines"], fx["lang"], TODAY)


def test_real_advantest_years_come_from_table_headings():
    # 日付セルに年が無く、年は表の左端の結合セル（2026 / 2027）にしかない
    got = {c.date: c.label for c in real("advantest_ir_calendar_2026-11-19")}
    assert date(2026, 1, 28) in got and date(2027, 1, 28) not in got
    assert got[date(2026, 10, 28)] == "2026年度第2四半期"
    assert date(2026, 7, 31) not in got  # 同じ行の「定時株主総会」は拾わない
    assert date(2026, 7, 9) not in got   # 同じ行の「招集通知送付」も拾わない


def test_real_tel_has_next_quarter():
    got = {c.date: c.label for c in real("tel_ir_calendar_2026-11-19")}
    assert got[date(2027, 2, 5)] == "2027年3月期第3四半期"
    assert got[date(2026, 10, 30)] == "2027年3月期第2四半期"


def test_real_nvidia_year_from_quarter_end_in_same_sentence():
    q1 = real("nvidia_sets_conference_call_q1fy27")
    assert [c.date for c in q1] == [date(2026, 5, 20)]  # 2027年ではない
    q3 = real("nvidia_sets_conference_call_q3fy27")
    assert [(c.date, c.time, c.label) for c in q3] == [(date(2026, 11, 17), "14:00", "Q3 FY2027")]


def test_keyword_then_unrelated_date_is_not_paired():
    html = "<li>決算発表 7月9日 招集通知送付</li>"
    assert cands(html, "ja") == []


def test_estimate_avoids_japanese_holiday():
    # 前年同期 2026-02-12(木) の52週後は 2027-02-11(木・建国記念の日) → 前の営業日 2/10 にずらす
    ev = [{"company": "6525", "date": d, "status": "done"} for d in ("2026-02-12", "2026-11-09")]
    co = {"id": "6525", "tz": "Asia/Tokyo", "ir_url": "x", "market": "JP"}
    est = [e for e in estimate(ev, co, date(2026, 11, 21)) if e["status"] == "estimated"]
    assert est[0]["date"] == "2027-02-10"
