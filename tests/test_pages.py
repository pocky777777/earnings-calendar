"""会社ごとのページ（scraper/pages.py）のテスト。ネットワークは使わない。"""
from datetime import date

from scraper.pages import build

TODAY = date(2026, 11, 24)
DATA = {
    "generated_at": "2026-11-24T12:20:00Z",
    "categories": ["製造装置", "AI半導体"],
    "companies": [
        {"id": "6857", "name": "アドバンテスト", "name_en": "Advantest", "market": "JP", "role": "related",
         "category": "製造装置", "tz": "Asia/Tokyo", "ir_url": "https://example.com/ir"},
        {"id": "NVDA", "name": "エヌビディア", "name_en": "NVIDIA", "market": "US", "role": "leader",
         "category": "AI半導体", "tz": "America/Los_Angeles", "ir_url": "https://example.com/nv"},
        {"id": "7735", "name": "SCREEN", "name_en": "SCREEN", "market": "JP", "role": "related",
         "category": "製造装置", "tz": "Asia/Tokyo", "ir_url": "https://example.com/sc"},
    ],
    "events": [
        {"company": "6857", "date": "2026-10-28", "time": "15:30", "jst": "2026-10-28T15:30",
         "label": "2026年度第2四半期", "status": "done", "source": "https://example.com/ir/cal"},
        {"company": "6857", "date": "2027-01-27", "time": None, "jst": None, "label": None,
         "status": "estimated", "basis": "前年同期（2026-01-28）と同じ時期と推定", "source": "https://example.com/ir"},
        {"company": "NVDA", "date": "2027-02-24", "time": "14:00", "jst": "2027-02-25T07:00",
         "label": "Q4 FY2027", "status": "confirmed", "source": "https://example.com/pr"},
        {"company": "7735", "date": "2027-01-26", "time": None, "jst": None, "label": None,
         "status": "confirmed", "approx": "1月下旬", "source": "https://example.com/sc/cal"},
    ],
}


def test_build_writes_company_pages_index_and_sitemap(tmp_path):
    out = tmp_path / "c"
    build(DATA, TODAY, out=out, docs=tmp_path)
    adv = (out / "6857.html").read_text(encoding="utf-8")
    assert "<title>アドバンテスト（6857）の決算発表日｜次回は2027年1月27日（予想）" in adv
    assert "推定の根拠：前年同期" in adv
    assert "2026年10月28日（水）" in adv            # 過去の決算
    assert 'href="7735.html"' in adv and "1月下旬" in adv   # 同じ分野の会社へのリンク
    nv = (out / "NVDA.html").read_text(encoding="utf-8")
    assert "2027年2月25日（木） 07:00（日本時間）" in nv
    assert "現地 2月24日 14:00" in nv
    assert "（確定）" in nv
    sc = (out / "7735.html").read_text(encoding="utf-8")
    assert "次回は1月下旬（時期のみ発表）" in sc
    index = (out / "index.html").read_text(encoding="utf-8")
    assert index.count('.html">') >= 3
    sm = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "c/NVDA.html" in sm and "<lastmod>2026-11-24</lastmod>" in sm


def test_removed_company_page_is_deleted(tmp_path):
    out = tmp_path / "c"
    out.mkdir()
    (out / "OLD.html").write_text("old", encoding="utf-8")
    build(DATA, TODAY, out=out, docs=tmp_path)
    assert not (out / "OLD.html").exists()


def test_page_text_is_escaped(tmp_path):
    data = {**DATA, "companies": [{**DATA["companies"][0], "name": "A<b>&C"}] + DATA["companies"][1:]}
    build(data, TODAY, out=tmp_path / "c", docs=tmp_path)
    assert "A&lt;b&gt;&amp;C" in (tmp_path / "c" / "6857.html").read_text(encoding="utf-8")
