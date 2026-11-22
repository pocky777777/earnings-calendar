"""IRページのテキストから決算発表日を取り出す（ネットワークに触れない純粋な関数だけ）。

各社のページの書き方は、2026年11月に24社を実際に調べて分かった次の形に対応している。

  (A) キーワードの直後に日付がある文
        「決算発表は10月28日」「financial results on Wednesday, October 28」「Financial Call, September 30, 2026」
  (B) 1行の中で、日付のあとに項目名が続く表やリスト（日付ごとに区切って判定する）
        「2027.02.05 第3四半期決算発表」「7月29日 決算発表 7月9日 招集通知送付」
  (C) 日付だけの行と、項目名だけの行が並ぶ一覧
        日付が先: 「Nov 3, 2026 • 2:00 pm PST」→「AMD Fiscal Third Quarter 2026 Financial Results」
        日付が後: 「Lam Research ... Earnings Conference Call」→「OCT 21, 2026 AT 2:00PM」
        どちらの順かはページで決まっているので、会社ごとの設定（date_line）で指定する
  (D) 時期だけの予定: 「2027年1月下旬 第3四半期決算発表 [予定]」

年が書かれていない日付は ①ページ内の直前の年見出し（2026 / 2026年度） ②同じ行の年つき日付
③基準日に一番近い年 の順で年を決める。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from bs4 import BeautifulSoup

KEYWORDS = {
    "ja": re.compile(r"決算発表|決算短信|四半期決算|決算説明会|業績発表|業績概況|決算概要|決算要約"),
    # 単なる "earnings" は "earnings per share" に当たるので使わない
    "en": re.compile(
        r"conference call|financial results|quarterly results|financial call|"
        r"earnings (?:call|release|announcement|conference)|"
        r"\bQ[1-4](?: 20\d{2}| FY ?\d{2,4})? earnings\b|\b[1-4]Q'\d{2} results\b|"
        r"\b(?:first|second|third|fourth)[- ]quarter (?:results|earnings)\b",
        re.I),
}
# 決算発表そのものを表す言葉（同じ日に説明会などが並ぶときの優先順位に使う）
PRIMARY = {
    "ja": re.compile(r"決算発表|業績発表|決算短信|決算概要|決算要約"),
    "en": re.compile(r"financial results|earnings (?:release|call|conference)|quarter (?:results|earnings)|financial call",
                     re.I),
}
# 決算と無関係な項目（配当・総会など）は除外する
EXCLUDE = {
    # 「第1四半期決算日」は四半期の最終日で、発表日ではない
    "ja": re.compile(r"配当|株主総会|権利確定|基準日|支払|招集通知|決算日(?!程)"),
    "en": re.compile(r"dividend|annual meeting|stockholders|transcript|risk factors", re.I),
}
# 終わった決算の記事は“予定”ではないので、過去の記録としてだけ扱う
PAST_HINT = {
    # 「当ウェブサイトへの掲載 15時30分頃を予定」のような予定の文もあるので「掲載しました」に限る
    "ja": re.compile(r"発表しました|掲載しました|決算短信〔"),
    "en": re.compile(r"\breports?\b|\bannounce[sd] (?:its )?(?:20\d{2} )?\S*[- ]?quarter|announces financial results", re.I),
}
# (A) でキーワードと日付の間にあってよい言葉。これが無いと別の項目の日付と結び付いてしまう
CONNECTOR = {
    "ja": re.compile(r"^\s*(?:の?\s*(?:日程|予定日?|日時)\s*)?(?:は|[:：])\s*$"),
    "en": re.compile(r"^\s*(?:of 20\d{2}\s+)?(?:,|on|is scheduled for|scheduled for|will be (?:held|released) on)?\s*"
                     r"(?:(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?\s*)?$", re.I),
}

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

# 「2026年10月30日」は「日」まで必須（TDKの「2026年 4月 4月28日」を4月4日と読まないため）。「2026/10/30」「2026.10.30」も可
RE_JA_FULL = re.compile(r"(20\d{2})\s*(?:年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日|[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{1,2})(?!\d))")
RE_JA_MD = re.compile(r"(?<![\d年/.])(\d{1,2})\s*月\s*(\d{1,2})\s*日")
RE_JA_APPROX = re.compile(r"(?:(20\d{2})\s*年\s*)?(\d{1,2})\s*月\s*(上旬|中旬|下旬)")
RE_EN = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b"
    r"(?:,?\s+(20\d{2})\b)?",
    re.I,
)
RE_EN_NUM = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(20\d{2})\b")   # 米国式 月/日/年
# 行頭の年の見出し: 「2026」「2026年」「2026年度 (2026年4月～2027年3月)」。「2026.10.15」は日付なので除く
RE_YEAR_HEAD = re.compile(r"^(20\d{2})\s*(年度|年)?(?=\s|$|\(|（)")
RE_TIME_JA = re.compile(r"(\d{1,2})\s*(?:[:：]\s*(\d{2})|時\s*(?:(\d{1,2})\s*分)?)")
RE_TIME_EN = re.compile(r"(?<![\d:])(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", re.I)
# 日付の行に付いてくるだけの言葉（これ以外が無ければ「日付だけの行」とみなす）
RE_DATE_LINE_NOISE = re.compile(
    r"\b(?:AT|DATE|TIME|[ECMP][SD]?T|ET|PT|MT|Pacific|Eastern|Time|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b|"
    r"[•|:：\-–,.()（）\s]|予定|頃|[月火水木金土日]", re.I)

TZ_WORDS = [
    (re.compile(r"\b(?:PST|PDT|PT)\b|Pacific", re.I), "America/Los_Angeles"),
    (re.compile(r"\b(?:EST|EDT|ET)\b|Eastern", re.I), "America/New_York"),
    (re.compile(r"\b(?:CST|CDT|CT)\b|Central", re.I), "America/Chicago"),
    (re.compile(r"\b(?:MST|MDT|MT)\b|Mountain", re.I), "America/Denver"),
]
APPROX_DAY = {"上旬": 5, "中旬": 15, "下旬": 25}


@dataclass
class Candidate:
    date: date
    time: str | None = None          # "15:30" のように現地時刻
    tz: str | None = None            # 文中に時間帯（PT / ET など）が書かれていればそれ
    label: str | None = None         # "2027年3月期 第2四半期" など
    scheduled: bool = True           # False なら「終わった決算」の記事から取れた日付
    approx: str | None = None        # 「1月下旬」のように時期だけ発表されている場合
    context: str = field(default="", repr=False)
    primary: bool = field(default=False, repr=False)


@dataclass
class Found:
    start: int
    end: int
    date: date
    approx: str | None = None


def _anchored(month: int, day: int, anchor: date) -> date | None:
    """同じ文の中に年つきの日付（例: "which ended April 26, 2026"）があれば、
    それ以降で最初に来る month/day を返す。決算発表は四半期末より後に来るため。"""
    for y in (anchor.year, anchor.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if d >= anchor:
            return d
    return None


def _infer_year(month: int, day: int, today: date) -> date | None:
    """年のない日付に、基準日に一番近い年を補う（12月に「1月30日」とあれば翌年）。"""
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    return best


@dataclass
class YearContext:
    year: int | None = None
    fiscal: bool = False             # 「2026年度」なら 1〜3月は翌年
    anchor: date | None = None       # 同じ行にある年つきの日付

    def resolve(self, month: int, day: int, today: date) -> date | None:
        if self.year is None:
            if self.anchor:
                return _anchored(month, day, self.anchor)
            return _infer_year(month, day, today)
        y = self.year + (1 if self.fiscal and month < 4 else 0)
        try:
            return date(y, month, day)
        except ValueError:
            return None


def html_to_lines(html: str) -> list[str]:
    """HTMLを“見た目の行”に近い単位のテキストに分ける。表やリストは1行=1つの<tr>/<li>にまとめる。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        tag.decompose()
    for tr in soup.find_all(["tr", "dl", "li"]):
        text = " ".join(tr.get_text(" ", strip=True).split())
        tr.replace_with(soup.new_string("\n" + text + "\n"))
    text = soup.get_text("\n")
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def normalize(line: str) -> str:
    # "Oct 21, 20261:30 PM" のように年と時刻がくっついている表示を直す
    return re.sub(r"\b(20\d{2})(?=\d{1,2}:\d{2})", r"\1 ", line)


RE_PERIOD_JA = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月期")
RE_QUARTER_JA = re.compile(r"第\s*([1-4])\s*四半期|(中間)")


def period_end_ja(line: str) -> date | None:
    """「2026年3月期 第3四半期」→ その四半期の最終日（2025-12-31）。
    決算はその後に発表されるので、年のない日付の年を決める手がかりになる。"""
    m = RE_PERIOD_JA.search(line)
    if not m:
        return None
    y, mo = int(m[1]), int(m[2])
    q = RE_QUARTER_JA.search(line[m.end(): m.end() + 30])
    n = 4 if not q else (2 if q[2] else int(q[1]))
    mo -= 3 * (4 - n)
    while mo <= 0:
        mo += 12
        y -= 1
    nxt = date(y + (mo == 12), mo % 12 + 1, 1)
    return nxt - timedelta(days=1)


def find_dates(line: str, lang: str, today: date, ctx: YearContext | None = None) -> list[Found]:
    """行の中の日付を、出てくる順に返す。"""
    ctx = ctx or YearContext()
    if lang == "ja":
        # 「2026年3月期 第3四半期」のように対象期間が書いてあれば、見出しの年より確か
        # （日立のように、通期決算を前の年度の見出しの下に載せるページがあるため）
        end = period_end_ja(line)
        if end:
            ctx = YearContext(anchor=end)
    full: list[Found] = []
    if lang == "ja":
        for m in RE_JA_FULL.finditer(line):
            try:
                full.append(Found(m.start(), m.end(), date(int(m[1]), int(m[2] or m[4]), int(m[3] or m[5]))))
            except ValueError:
                pass
    else:
        for m in RE_EN.finditer(line):
            if m[3]:
                try:
                    full.append(Found(m.start(), m.end(), date(int(m[3]), MONTHS[m[1][:3].lower()], int(m[2]))))
                except ValueError:
                    pass
        for m in RE_EN_NUM.finditer(line):
            try:
                full.append(Found(m.start(), m.end(), date(int(m[3]), int(m[1]), int(m[2]))))
            except ValueError:
                pass
    if ctx.year is None and full:
        ctx = YearContext(anchor=min(f.date for f in full))

    found = list(full)
    taken = lambda pos: any(f.start <= pos < f.end for f in found)  # noqa: E731
    if lang == "ja":
        for m in RE_JA_APPROX.finditer(line):
            mo = int(m[2])
            y = int(m[1]) if m[1] else None
            d = (date(y, mo, APPROX_DAY[m[3]]) if y else ctx.resolve(mo, APPROX_DAY[m[3]], today))
            if d:
                found.append(Found(m.start(), m.end(), d, approx=f"{mo}月{m[3]}"))
        for m in RE_JA_MD.finditer(line):
            if taken(m.start()):
                continue
            d = ctx.resolve(int(m[1]), int(m[2]), today)
            if d:
                found.append(Found(m.start(), m.end(), d))
    else:
        for m in RE_EN.finditer(line):
            if m[3] or taken(m.start()):
                continue
            d = ctx.resolve(MONTHS[m[1][:3].lower()], int(m[2]), today)
            if d:
                found.append(Found(m.start(), m.end(), d))
    return sorted(found, key=lambda f: f.start)


def find_time(text: str, lang: str) -> str | None:
    if lang == "ja":
        m = RE_TIME_JA.search(text)
        if m and int(m[1]) < 24:
            return f"{int(m[1]):02d}:{(m[2] or m[3] or '0').zfill(2)}"
        return None
    m = RE_TIME_EN.search(text)
    if not m or int(m[1]) > 12:
        return None
    h = int(m[1]) % 12 + (12 if m[3].lower() == "p" else 0)
    return f"{h:02d}:{m[2] or '00'}"


def find_tz(text: str) -> str | None:
    for rx, tz in TZ_WORDS:
        if rx.search(text):
            return tz
    return None


RE_LABEL_JA = re.compile(
    r"20\d{2}年\d{1,2}月期\s*(?:第\s*\d\s*四半期|中間期?|通期|本決算|期末)?|20\d{2}年度\s*(?:第\s*\d\s*四半期|通期)?|"
    r"第\s*\d\s*四半期"
)
QUARTER_EN = {"first": 1, "second": 2, "third": 3, "fourth": 4}


def find_label(text: str, lang: str) -> str | None:
    if lang == "ja":
        m = RE_LABEL_JA.search(text)
        return " ".join(m.group(0).split()) if m else None
    # "third quarter of fiscal year 2027" → "Q3 FY2027" / "Q4 2026" / "3Q'26" → "Q3 2026"
    m = re.search(r"\b([1-4])Q'(\d{2})\b", text)
    if m:
        return f"Q{m[1]} 20{m[2]}"
    q = re.search(r"\b(first|second|third|fourth)[- ]quarter|\bQ([1-4])\b", text, re.I)
    fy = re.search(r"fiscal (?:year )?(20\d{2})|\bFY ?(20\d{2}|\d{2})\b", text, re.I)
    year = re.search(r"\bQ[1-4] (20\d{2})\b|\b(20\d{2})[- ](?:first|second|third|fourth)|"
                     r"quarter (20\d{2})\b", text, re.I)
    if not q:
        return None
    n = QUARTER_EN[q[1].lower()] if q[1] else int(q[2])
    if fy:
        y = fy[1] or fy[2]
        return f"Q{n} FY{y if len(y) == 4 else '20' + y}"
    if year:
        return f"Q{n} {year[1] or year[2] or year[3]}"
    return f"Q{n}"


def _pairs_in_line(line: str, dates: list[Found], lang: str) -> list[tuple[Found, str, str, str]]:
    """1行から (日付, 判定に使う文, 時刻を探す文, ラベルを探す文) の組を取り出す。"""
    kw, conn = KEYWORDS[lang], CONNECTOR[lang]
    pairs = []
    # (A) キーワードの直後の日付（「は」「on」などでつながっているときだけ）
    for km in kw.finditer(line):
        nxt = next((f for f in dates if f.start >= km.end()), None)
        if nxt and conn.match(line[km.end(): nxt.start]):
            pairs.append((nxt, line[max(0, km.start() - 40): nxt.end], line[nxt.start: nxt.end + 60],
                          line[max(0, km.start() - 60): nxt.end + 150]))
    if pairs:
        return pairs
    # (B) 日付ごとに区切る
    for i, f in enumerate(dates):
        seg_end = dates[i + 1].start if i + 1 < len(dates) else len(line)
        seg = line[f.start: seg_end]
        pairs.append((f, seg, seg, seg))
    return pairs


def _is_date_only(line: str, dates: list[Found]) -> bool:
    if len(dates) != 1 or len(line) > 60:
        return False
    rest = line[: dates[0].start] + line[dates[0].end:]
    rest = RE_TIME_EN.sub(" ", RE_TIME_JA.sub(" ", rest))
    return len(RE_DATE_LINE_NOISE.sub("", rest)) <= 2


def extract_candidates(lines: list[str], lang: str, today: date,
                       window_days: tuple[int, int] = (-400, 200),
                       date_line: str = "before") -> list[Candidate]:
    """日付候補を集める。基準日から遠すぎる日付（古いニュース等）は捨てる。
    date_line: (C) の形で、日付だけの行が項目名の「前(before)」「後(after)」どちらにあるか。"""
    kw, ex, past = KEYWORDS[lang], EXCLUDE[lang], PAST_HINT[lang]
    ctx = YearContext()
    out: dict[date, Candidate] = {}

    def add(f: Found, text: str, time_text: str, label_text: str, context: str):
        if not kw.search(text) or ex.search(text):
            return
        if not (window_days[0] <= (f.date - today).days <= window_days[1]):
            return
        cand = Candidate(
            date=f.date,
            time=None if f.approx else find_time(time_text, lang),
            tz=find_tz(time_text),
            label=find_label(label_text, lang),
            scheduled=not past.search(text),
            approx=f.approx,
            context=context[:200],
        )
        cand.primary = bool(PRIMARY[lang].search(text))
        prev = out.get(f.date)
        # 同じ日付が複数の行にあるときは「決算発表」そのものの行を優先する（説明会・電話会議の時刻を使わない）
        score = lambda c: (c.approx is None, c.primary, c.time is not None, c.label is not None,  # noqa: E731
                           c.scheduled)
        if prev is None or score(cand) > score(prev):
            out[f.date] = cand

    lines = [normalize(l) for l in lines]
    parsed: list[tuple[str, list[Found]]] = []
    for line in lines:
        head = RE_YEAR_HEAD.match(line)
        if head:
            ctx = YearContext(int(head[1]), head[2] == "年度")
        parsed.append((line, find_dates(line, lang, today, ctx)))

    for i, (line, dates) in enumerate(parsed):
        if not dates:
            continue
        if _is_date_only(line, dates):
            # (C) 隣の「日付の無い行」が決算の項目ならその日付とみなす
            j = i + 1 if date_line == "before" else i - 1
            if 0 <= j < len(parsed) and not parsed[j][1]:
                other = parsed[j][0]
                add(dates[0], other, line, other, f"{line} {other}" if j > i else f"{other} {line}")
            continue
        if not kw.search(line):
            continue
        for f, text, time_text, label_text in _pairs_in_line(line, dates, lang):
            add(f, text, time_text, label_text, line)
    # 決算発表の行があるページでは、その前後1週間の「説明会だけ」の日付は捨てる
    # （日本マイクロニクスのように説明会を決算発表の翌日に開く会社があるため）
    primaries = [c.date for c in out.values() if c.primary]
    result = [c for c in out.values()
              if c.primary or not any(abs((c.date - p).days) <= 7 for p in primaries)]
    return sorted(result, key=lambda c: c.date)


def find_follow_links(html: str, pattern: str, base_url: str, limit: int = 3) -> list[str]:
    """一覧ページから、リンク文字が pattern に一致する記事のURLを（ページ上の順に）返す。"""
    from urllib.parse import urljoin

    soup = BeautifulSoup(html, "html.parser")
    rx = re.compile(pattern, re.I)
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        if rx.search(a.get_text(" ", strip=True)):
            u = urljoin(base_url, a["href"])
            if u not in urls:
                urls.append(u)
        if len(urls) >= limit:
            break
    return urls
