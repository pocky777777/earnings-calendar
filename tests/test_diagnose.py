"""診断スクリプトが、読めた・拒否された・日付なしを正しく書き分けるか（ネットワークなし）。"""
from datetime import date

from scraper import fetch
from scripts import diagnose

TODAY = date(2026, 11, 23)
PAGE = "<html><body><p>December 01, 2026</p><p>Q2 FY2027 Earnings Conference Call</p></body></html>"


def test_try_source_reports_ok_denied_and_empty(monkeypatch):
    def fake_get(url, render=False, tls_legacy=False):
        if "denied" in url:
            raise fetch.FetchError(f"HTTP 403: {url}")
        if "empty" in url:
            return "<html><body><p>No events</p></body></html>"
        return PAGE

    monkeypatch.setattr(fetch, "get", fake_get)
    ok = diagnose.try_source({"url": "https://example.com/ok"}, "en", TODAY)
    assert ok["result"].startswith("✅") and "2026-12-01" in ok["dates"]
    ng = diagnose.try_source({"url": "https://example.com/denied"}, "en", TODAY)
    assert ng["result"].startswith("❌") and "403" in ng["result"]
    empty = diagnose.try_source({"url": "https://example.com/empty"}, "en", TODAY)
    assert empty["result"].startswith("⚠")
