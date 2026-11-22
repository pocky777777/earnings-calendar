"""IRページの取得。robots.txt を守り、1ページごとに間をあけて相手サイトに負担をかけない。

render=True の会社は、ページの中身を JavaScript で後から表示しているため、
ヘッドレスブラウザ（Playwright）で人が見るのと同じ状態まで表示してから読む。
"""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

USER_AGENT = "earnings-calendar-bot/0.2 (+https://github.com/YOUR_NAME/earnings-calendar)"
WAIT_SECONDS = 3.0
TIMEOUT = 25

_robots: dict[str, urllib.robotparser.RobotFileParser] = {}
_last_request = 0.0
_browser = None   # Playwright のブラウザ（必要になった時だけ起動）
_pw = None


class FetchError(Exception):
    pass


def _allowed(url: str) -> bool:
    p = urlparse(url)
    root = f"{p.scheme}://{p.netloc}"
    if root not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(root + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            ok = r.status_code == 200 and "html" not in r.headers.get("content-type", "")
            rp.parse(r.text.splitlines() if ok else [])
        except requests.RequestException:
            rp.parse([])  # robots.txt が読めない場合は制限なしとして扱う（一般的な慣習）
        _robots[root] = rp
    return _robots[root].can_fetch(USER_AGENT, url)


def _wait_turn():
    global _last_request
    wait = WAIT_SECONDS - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def _get_plain(url: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"},
                         timeout=TIMEOUT)
    except requests.RequestException as e:
        raise FetchError(f"接続できませんでした: {e}") from e
    if r.status_code != 200:
        raise FetchError(f"HTTP {r.status_code}: {url}")
    r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
    return r.text


def _get_rendered(url: str) -> str:
    global _browser, _pw
    try:
        from playwright.sync_api import Error as PwError, sync_playwright
    except ImportError as e:
        raise FetchError("render=True の会社には playwright が必要です（pip install playwright && "
                         "playwright install chromium）") from e
    if _browser is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch()
    page = _browser.new_page(user_agent=USER_AGENT, locale="ja-JP")
    try:
        resp = page.goto(url, wait_until="networkidle", timeout=TIMEOUT * 1000)
        if resp is not None and resp.status != 200:
            raise FetchError(f"HTTP {resp.status}: {url}")
        page.wait_for_timeout(1500)  # 後から差し込まれる部品を少し待つ
        return page.content()
    except PwError as e:
        raise FetchError(f"表示できませんでした: {e}") from e
    finally:
        page.close()


def get(url: str, render: bool = False) -> str:
    if not _allowed(url):
        raise FetchError(f"robots.txt で禁止されているため取得しません: {url}")
    _wait_turn()
    return _get_rendered(url) if render else _get_plain(url)


def close():
    global _browser, _pw
    if _browser is not None:
        _browser.close()
        _pw.stop()
        _browser = _pw = None
