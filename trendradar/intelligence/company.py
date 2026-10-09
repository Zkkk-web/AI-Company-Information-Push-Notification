# coding=utf-8
"""Turn matched news into grounded, company-centric BD leads.

This module intentionally has no model or paid-service dependency.  It extracts
only facts present in the title, RSS summary, or explicitly supplied article
text.  Missing fields remain missing and are rendered as such.
"""

from __future__ import annotations

import hashlib
import html
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable, Dict, Iterable, List, Optional

import requests


UNKNOWN_COMPANY = "公司名称暂未确认"


@dataclass(frozen=True)
class SignalSource:
    name: str
    title: str
    url: str = ""
    time_display: str = ""


@dataclass
class CompanySignal:
    company_name: str
    level: str
    event: str
    investors: List[str] = field(default_factory=list)
    team: List[str] = field(default_factory=list)
    sources: List[SignalSource] = field(default_factory=list)
    confidence: float = 0.0
    raw_text: str = ""


_OUTLET_SUFFIX = re.compile(
    r"\s+(?:-|\||—)\s+(?:TechCrunch|Dealroom|CryptoRank|Wowtale|Law\.com|"
    r"新浪网|搜狐网|财联社|动脉网|泰伯网|电子工程专辑|21财经|SiliconANGLE).*$",
    re.IGNORECASE,
)
_SPACE = re.compile(r"\s+")
_FUNDING_WORDS = re.compile(
    r"融资|募资|投资|领投|参投|raises?|raised|nabs|lands|funding|seed|series|round|back",
    re.IGNORECASE,
)


_INVESTOR_ALIASES = [
    ("红杉资本 / Sequoia", ("Sequoia Capital", "Sequoia", "红杉资本", "红杉")),
    ("Lightspeed", ("Lightspeed", "光速创投")),
    ("a16z", ("Andreessen Horowitz", "a16z")),
    ("五源资本", ("五源资本",)),
    ("真格基金", ("真格基金", "ZhenFund")),
    ("高瓴", ("高瓴", "Hillhouse")),
    ("HSG", ("HSG",)),
    ("源码资本", ("源码资本", "Source Code Capital")),
    ("经纬创投", ("经纬创投", "Matrix Partners")),
    ("GGV / 纪源资本", ("GGV", "纪源资本")),
    ("启明创投", ("启明创投", "Qiming")),
    ("顺为资本", ("顺为资本", "Shunwei")),
    ("创新工场", ("创新工场", "Sinovation Ventures")),
    ("Accel", ("Accel",)),
    ("First Round", ("First Round",)),
    ("Hummingbird", ("Hummingbird",)),
    ("NVIDIA", ("Nvidia", "NVIDIA", "英伟达")),
    ("Samsung", ("Samsung", "三星")),
    ("腾讯", ("腾讯", "Tencent")),
    ("蚂蚁集团", ("蚂蚁", "Ant Group")),
]

_ENGLISH_STOP_NAMES = {
    "AI",
    "Exclusive",
    "Engineering AI Startup",
    "Legal Services Startup",
    "Robot Data Startup",
}


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return _SPACE.sub(" ", text).strip()


def _clean_title(title: str) -> str:
    return _OUTLET_SUFFIX.sub("", _clean(title)).strip(" -|—")


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = _clean(value).strip(" ,，。；;:：")
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _extract_company_name(title: str, summary: str) -> tuple[str, float]:
    title = _clean_title(title)
    candidates = [title, summary]

    patterns = [
        re.compile(r"[“\"]([^”\"]{2,40})[”\"]\s*(?:完成|获|宣布|融资)"),
        re.compile(r"(?:创立|创办)([\u4e00-\u9fffA-Za-z0-9.·-]{2,24})(?=：|:|，|,|。|\s|$)"),
        re.compile(
            r"\b(?i:startup|company)\s+([A-Z][A-Za-z0-9.]+(?:\s+[A-Z][A-Za-z0-9.]+){0,3})"
            r"\s+(?i:raises?|raised|nabs|lands|announces|secures|closes)\b",
        ),
        re.compile(
            r"\b([A-Z][A-Za-z0-9.]+(?:\s+[A-Z][A-Za-z0-9.]+){0,3})"
            r"\s+(?i:raises?|raised|nabs|lands|announces|secures|closes)\b",
        ),
        re.compile(
            r"\b(?i:startup|company)\s+([A-Z][A-Za-z0-9.]+(?:\s+[A-Z][A-Za-z0-9.]+){0,3})"
            r"(?=\s*(?:-|—|\||$))",
        ),
        re.compile(r"^([A-Z][A-Za-z0-9.]+(?:\s+AI)?)['’]s\b"),
        re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z0-9.]{2,}(?:\s+AI)?)\s*(?:完成|获|宣布|拟融资|新一轮融资|斥资)"),
        re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z0-9.]{2,}(?:\s+AI)?)\s*(?:官宣|重启)[^，。；;]{0,18}(?:融资|招聘)"),
        re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z0-9.]{2,}(?:\s+AI)?)(?=重启|发布|上线|进入)"),
        re.compile(r"([\u4e00-\u9fff]{2,10}?)(?=连续完成|完成|获得|宣布)(?:连续)?(?:完成|获得|宣布)(?:超|近|新一轮|两轮|数轮)?"),
    ]

    for index, text in enumerate(candidates):
        if not text:
            continue
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            name = _clean(match.group(1)).strip("“”\"'的")
            name = re.sub(r"^(?:AI评测榜单|北京|上海|深圳)", "", name)
            if name.lower().endswith(" alum"):
                continue
            if not name or name in _ENGLISH_STOP_NAMES:
                continue
            if len(name) > 40:
                continue
            return name, 0.96 if index == 0 else 0.82

    # A standalone proper name before a financing phrase is a conservative
    # fallback for titles such as "DeepSeek新一轮融资".
    match = re.search(
        r"\b([A-Z][A-Za-z0-9.-]{2,}(?:\s+[A-Z][A-Za-z0-9.-]+){0,2})"
        r"(?=\s*(?:新一轮融资|融资|获投|拟融资))",
        title,
    )
    if match:
        return match.group(1), 0.9
    return UNKNOWN_COMPANY, 0.25


def _extract_investors(text: str) -> List[str]:
    found = []
    for canonical, aliases in _INVESTOR_ALIASES:
        matched = False
        for alias in aliases:
            if re.search(r"[A-Za-z]", alias):
                pattern = rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
                matched = bool(re.search(pattern, text, re.IGNORECASE))
            else:
                matched = alias in text
            if matched:
                break
        if matched:
            found.append(canonical)
    return _unique(found)


def _extract_team(text: str) -> List[str]:
    members = []

    for match in re.finditer(
        r"(?P<background>(?:清华|北大|港大|复旦|交大|浙大|阿里|腾讯|字节|美团|快手|"
        r"小红书|拼多多|百度|京东|华为|小米|大疆|Google|DeepMind|OpenAI|Anthropic|Meta)"
        r"[^，。:：]{0,24}?(?:教授|博士|高管|负责人|研究员|科学家))"
        r"(?P<name>[\u4e00-\u9fff]{2,4})(?:创业|创立|创办)",
        text,
        re.IGNORECASE,
    ):
        members.append(f"{match.group('name')}（创始人；{_clean(match.group('background'))}）")

    for match in re.finditer(
        r"(?:创始人|联合创始人|CEO|首席执行官)[：:\s]*([\u4e00-\u9fff]{2,4}|"
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
        text,
    ):
        members.append(f"{match.group(1)}（核心团队）")

    for match in re.finditer(
        r"(?i:founded|co-founded)\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
        text,
    ):
        members.append(f"{match.group(1)}（创始人）")

    age_match = re.search(r"(\d{1,2})-year-old founder", text, re.IGNORECASE)
    if age_match:
        members.append(f"{age_match.group(1)} 岁创始人（姓名未披露）")

    alum_match = re.search(r"\b([A-Z][A-Za-z0-9.]+)\s+alum\b", text)
    if alum_match:
        members.append(f"前 {alum_match.group(1)} 成员（姓名未披露）")

    chinese_team_match = re.search(r"站着([\u4e00-\u9fff]{2,4})(\d+)人团", text)
    if chinese_team_match:
        members.append(
            f"{chinese_team_match.group(1)}（核心人物；{chinese_team_match.group(2)} 人团队）"
        )

    return _unique(members)


def _event_type(text: str) -> str:
    if _FUNDING_WORDS.search(text):
        return "funding"
    if re.search(r"创业|创立|创办|加入|高管|founder|joins?", text, re.IGNORECASE):
        return "team"
    return "business"


def extract_company_signal(item: Dict, level: str) -> CompanySignal:
    """Extract only facts grounded in one item."""
    title = _clean_title(item.get("title", ""))
    summary = _clean(item.get("summary", ""))
    article_text = _clean(item.get("article_text", ""))
    short_evidence = "。".join(part for part in (title, summary) if part)
    company_name, confidence = _extract_company_name(title, summary)
    if company_name == UNKNOWN_COMPANY and article_text:
        company_name, article_confidence = _extract_company_name("", article_text[:6000])
        confidence = min(article_confidence, 0.72)
    investors = _extract_investors(short_evidence)
    team_evidence = short_evidence
    if article_text and company_name != UNKNOWN_COMPANY:
        sentences = re.split(r"(?<=[。！？!?])|\n+", article_text[:12000])
        company_key = company_name.casefold()
        company_sentences = [
            sentence
            for sentence in sentences
            if company_key in sentence.casefold()
        ]
        if company_sentences:
            team_evidence += "。" + "。".join(company_sentences[:8])
    team = _extract_team(team_evidence)
    all_evidence = "。".join(part for part in (title, summary, article_text) if part)
    source = SignalSource(
        name=_clean(item.get("source_name", "")) or "原始报道",
        title=title,
        url=str(item.get("url") or item.get("mobile_url") or ""),
        time_display=_clean(item.get("time_display", "")),
    )
    return CompanySignal(
        company_name=company_name,
        level=_clean(level) or "未分级",
        event=title or summary or "触发事件暂未确认",
        investors=investors,
        team=team,
        sources=[source],
        confidence=confidence,
        raw_text=all_evidence,
    )


def _normal_company_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", name.casefold())
    return normalized


def _merge_key(signal: CompanySignal) -> str:
    company = _normal_company_name(signal.company_name)
    if signal.company_name != UNKNOWN_COMPANY and company:
        # The deliverable is a company lead, not a list of articles.  Multiple
        # same-day events become evidence under one company card.
        return company
    digest = hashlib.sha1(signal.event.casefold().encode("utf-8")).hexdigest()[:16]
    return f"unknown:{digest}"


def _level_priority(level: str) -> int:
    if "重点机构" in level:
        return 0
    if level.startswith("A级"):
        return 1
    if level.startswith("B级"):
        return 2
    return 3


def merge_company_signals(signals: Iterable[CompanySignal]) -> List[CompanySignal]:
    merged: Dict[str, CompanySignal] = {}
    for signal in signals:
        key = _merge_key(signal)
        current = merged.get(key)
        if current is None:
            merged[key] = signal
            continue
        current.investors = _unique([*current.investors, *signal.investors])
        current.team = _unique([*current.team, *signal.team])
        source_keys = {(source.name, source.url, source.title) for source in current.sources}
        for source in signal.sources:
            source_key = (source.name, source.url, source.title)
            if source_key not in source_keys:
                current.sources.append(source)
                source_keys.add(source_key)
        if _level_priority(signal.level) < _level_priority(current.level):
            current.level = signal.level
        if signal.confidence > current.confidence:
            current.company_name = signal.company_name
            current.event = signal.event
            current.confidence = signal.confidence
        current.raw_text = "。".join(filter(None, (current.raw_text, signal.raw_text)))

    return sorted(
        merged.values(),
        key=lambda item: (_level_priority(item.level), item.company_name.casefold()),
    )


class _ReadableHTMLParser(HTMLParser):
    """Small dependency-free fallback for article/team evidence."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocked = 0
        self._primary = 0
        self._capture = 0
        self._primary_parts: List[str] = []
        self._fallback_parts: List[str] = []

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag in {"script", "style", "nav", "footer", "svg", "noscript"}:
            self._blocked += 1
        if tag in {"article", "main"}:
            self._primary += 1
        if tag in {"p", "h1", "h2", "li"}:
            self._capture += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "svg", "noscript"} and self._blocked:
            self._blocked -= 1
        if tag in {"p", "h1", "h2", "li"} and self._capture:
            self._capture -= 1
            target = self._primary_parts if self._primary else self._fallback_parts
            target.append("\n")
        if tag in {"article", "main"} and self._primary:
            self._primary -= 1

    def handle_data(self, data: str) -> None:
        if not self._blocked and self._capture:
            text = _clean(data)
            if text:
                target = self._primary_parts if self._primary else self._fallback_parts
                target.append(text)

    def text(self) -> str:
        primary = _clean(" ".join(self._primary_parts))
        if len(primary) >= 120:
            return primary
        return _clean(" ".join(self._fallback_parts))


def extract_readable_text(html_content: str, max_chars: int = 12000) -> str:
    parser = _ReadableHTMLParser()
    parser.feed(html_content[:2_000_000])
    return parser.text()[:max_chars]


def fetch_article_text(url: str, timeout: int = 8, max_chars: int = 12000) -> str:
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/129 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return ""
        return extract_readable_text(response.text, max_chars=max_chars)
    except (requests.RequestException, ValueError):
        return ""


def _format_source(source: SignalSource) -> str:
    label = source.name or "原始报道"
    if source.url:
        return f"[{label}]({source.url})"
    return label


def _format_signal(signal: CompanySignal, index: int) -> str:
    investors = "、".join(signal.investors) if signal.investors else "暂未从公开报道确认"
    team = "；".join(signal.team) if signal.team else "暂未从公开报道确认"
    sources = "、".join(_format_source(source) for source in signal.sources[:4])
    if len(signal.sources) > 4:
        sources += f" 等 {len(signal.sources)} 个来源"
    return (
        f"{index}. **公司：** {signal.company_name}\n"
        f"   - **级别：** {signal.level}\n"
        f"   - **触发事件：** {signal.event}\n"
        f"   - **资方：** {investors}\n"
        f"   - **团队：** {team}\n"
        f"   - **来源：** {sources or '暂未提供'}\n"
    )


def _collect_stats(report_stats: Optional[list], rss_stats: Optional[list]) -> tuple[list, int]:
    items = []
    seen = set()
    source_count = 0
    for stat in [*(report_stats or []), *(rss_stats or [])]:
        level = _clean(stat.get("word", ""))
        for title in stat.get("titles", []):
            source_count += 1
            key = str(title.get("url") or title.get("title") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            items.append((level, title))
    return items, source_count


def build_company_intelligence_batches(
    report_stats: Optional[list],
    rss_stats: Optional[list],
    *,
    batch_size: int = 29000,
    fetch_full_text: bool = False,
    article_fetcher: Callable[[str], str] = fetch_article_text,
) -> List[str]:
    """Build app-bot-safe Markdown batches from matched news."""
    collected, source_count = _collect_stats(report_stats, rss_stats)
    if not collected:
        return []

    working_items = [(level, dict(item)) for level, item in collected]
    signals = [extract_company_signal(item, level) for level, item in working_items]
    if fetch_full_text:
        pending_indexes = [
            index
            for index, signal in enumerate(signals)
            if not signal.team or signal.company_name == UNKNOWN_COMPANY
        ]
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(pending_indexes)))) as executor:
            futures = {
                executor.submit(
                    article_fetcher,
                    str(working_items[index][1].get("url") or ""),
                ): index
                for index in pending_indexes
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    article_text = future.result()
                except Exception:
                    article_text = ""
                if not article_text:
                    continue
                level, working = working_items[index]
                working["article_text"] = article_text
                signals[index] = extract_company_signal(working, level)

    merged = merge_company_signals(signals)
    header = (
        "🚀 **大厂幼年体 · BD 公司情报**\n\n"
        f"共 **{len(merged)} 家公司/线索**，由 {source_count} 条候选新闻合并。"
        "所有字段只使用公开报道中的明确证据；未披露内容会标记为“暂未确认”。\n\n"
    )
    blocks = [_format_signal(signal, index) for index, signal in enumerate(merged, start=1)]
    batches: List[str] = []
    current = header
    for block in blocks:
        candidate = current + block + "\n"
        if len(candidate.encode("utf-8")) > batch_size and current != header:
            batches.append(current.rstrip())
            current = header + block + "\n"
        else:
            current = candidate
    if current.strip():
        batches.append(current.rstrip())
    return batches
