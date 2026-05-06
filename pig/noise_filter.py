"""깡통 정보 필터: 키워드 밀도, 상투문구, 도메인 신뢰도."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set
from urllib.parse import urlparse

# 광고·낚시성 블로그 등 (소문자 호스트 suffix 매칭)
DEFAULT_DOMAIN_BLACKLIST: Set[str] = {
    "tistory.com",
    "blog.me",
    "wordpress.com",
    "medium.com",  # 품질 편차 큼 — 필요 시 화이트리스트로 예외
    "brunch.co.kr",
    "velog.io",  # 기술 블로그 혼재 — 프로젝트에서 끄거나 화이트리스트로 보완
}

# 공신력·우선 매체 (호스트 키워드 또는 정확 호스트)
DEFAULT_DOMAIN_WHITELIST_HINTS: Set[str] = {
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "bbc.com",
    "bbc.co.uk",
    "apnews.com",
    "nytimes.com",
    "washingtonpost.com",
    "theguardian.com",
    "economist.com",
    "cnbc.com",
    "marketwatch.com",
    "sec.gov",
    "treasury.gov",
    "imf.org",
    "worldbank.org",
    "oecd.org",
    "gov.uk",
    "go.kr",
    "korea.kr",
    "yna.co.kr",
    "chosun.com",
    "joins.com",
    "hani.co.kr",
    "mk.co.kr",
}

# 국문 '깡통' 상투 표현 (답 없이 끝나는 글)
FLUFF_PHRASES_KO = [
    "알아보겠습니다",
    "알아 보겠습니다",
    "자세한 내용은",
    "참고하시기 바랍니다",
    "궁금하시다면",
    "많은 관심 부탁",
    "글을 마칩니다",
    "이상입니다",
    "함께해요",
    "좋아요와 구독",
]

FLUFF_PHRASES_EN = [
    "read more",
    "click here",
    "sign up for",
    "subscribe to",
    "this article will",
    "stay tuned",
    "to be continued",
]

# 숫자·날짜·퍼센트 등 '팩트' 신호
FACT_PATTERN = re.compile(
    r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\b\d{4}\b|\d+%|\$\s*\d+)"
)


@dataclass
class FilterResult:
    keep: bool
    score: float  # 높을수록 신뢰·품질
    reasons: List[str]


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def host_blacklisted(url: str, extra_blacklist: Optional[Iterable[str]] = None) -> bool:
    host = _host(url)
    if not host:
        return True
    bl = set(DEFAULT_DOMAIN_BLACKLIST)
    if extra_blacklist:
        bl.update(h.lower() for h in extra_blacklist)
    for suffix in bl:
        if host == suffix or host.endswith("." + suffix):
            return True
    return False


def host_whitelist_bonus(url: str, extra_whitelist: Optional[Iterable[str]] = None) -> float:
    host = _host(url)
    hints = set(DEFAULT_DOMAIN_WHITELIST_HINTS)
    if extra_whitelist:
        hints.update(w.lower() for w in extra_whitelist)
    for h in hints:
        if host == h or host.endswith("." + h):
            return 0.35
    return 0.0


def _tokenize(text: str) -> List[str]:
    t = text.lower()
    t = re.sub(r"[^\w\s가-힣]", " ", t)
    return [w for w in t.split() if len(w) > 1]


def _keyword_occurrences(text: str, kw: str) -> int:
    """짧은 영어 키워드는 단어 경계(토큰 일치)만 세고, 긴 키워드는 부분 문자열로 센다."""
    k = kw.strip().lower()
    if len(k) < 2:
        return 0
    low = text.lower()
    # 짧은 라틴 키워드(≤5자): 'ETF'가 'left'에 걸리지 않도록 토큰 일치만
    if len(k) <= 5 and re.match(r"^[a-z0-9]+$", k):
        tokens = _tokenize(text)
        return sum(1 for w in tokens if w == k)
    # 한글·구문: 부분 문자열(최대 30회까지 세기 — 성능)
    n = 0
    start = 0
    while True:
        i = low.find(k, start)
        if i == -1:
            break
        n += 1
        if n >= 30:
            break
        start = i + max(1, len(k) // 2)
    return n


def keyword_repeat_score(text: str, keywords: Sequence[str]) -> tuple[float, str]:
    """관심 키워드가 의미 없이 과도 반복되면 높은 점수(나쁨)."""
    if not keywords:
        return 0.0, ""
    tokens = _tokenize(text)
    n = len(tokens)
    if not n:
        return 0.0, ""
    worst_kw = ""
    worst_ratio = 0.0
    max_repeat = 0
    for kw in keywords:
        k = kw.strip().lower()
        if len(k) < 2:
            continue
        occ = _keyword_occurrences(text, kw)
        max_repeat = max(max_repeat, occ)
        ratio = occ / max(n, 1)
        if ratio > worst_ratio:
            worst_ratio = ratio
            worst_kw = kw
    penalty = 0.0
    if max_repeat >= 10:
        penalty = min(1.0, 0.15 + (max_repeat - 10) * 0.05)
    # 토큰 대비 반복 비율(짧은 키워드는 ratio가 과대평가되기 쉬워 가중치 완화)
    return min(1.0, worst_ratio * 5 + penalty), worst_kw


def fluff_ratio(text: str) -> float:
    low = text.lower()
    hits = 0
    for p in FLUFF_PHRASES_KO + FLUFF_PHRASES_EN:
        if p.lower() in low:
            hits += 1
    return min(1.0, hits * 0.12)


def fact_density(text: str) -> float:
    """짧은 글 대비 팩트(수치 등) 비율."""
    if not text or len(text) < 80:
        return 0.0
    m = len(FACT_PATTERN.findall(text))
    return min(1.0, m / max(len(text) / 400, 1))


def is_kimchi_article(
    title: str,
    body: str,
    link: str,
    interest_keywords: Sequence[str],
    blocked_keywords: Sequence[str],
    extra_blacklist: Optional[Iterable[str]] = None,
    extra_whitelist: Optional[Iterable[str]] = None,
) -> FilterResult:
    """
    깡통 정보 판별.
    - 블랙리스트 도메인 → 즉시 폐기
    - 차단 키워드 포함 → 폐기
    - 키워드 밀도 과다 또는 팩트 부족+상투문구 과다 → 폐기
    """
    reasons: List[str] = []
    full = f"{title}\n{body}"

    if host_blacklisted(link, extra_blacklist):
        return FilterResult(False, 0.0, ["블랙리스트 도메인"])

    for bk in blocked_keywords:
        if bk and bk.lower() in full.lower():
            return FilterResult(False, 0.0, [f"차단 키워드 포함: {bk}"])

    score = 0.45
    score += host_whitelist_bonus(link, extra_whitelist)

    rep_score, worst_kw = keyword_repeat_score(full, interest_keywords)
    worst_occ = _keyword_occurrences(full, worst_kw) if worst_kw else 0
    if rep_score > 0.55 or worst_occ >= 10:
        return FilterResult(
            False,
            score,
            [f"키워드 과다 반복 의심 (밀도/반복): {worst_kw or interest_keywords}"],
        )

    fluff = fluff_ratio(full)
    facts = fact_density(full)
    score += facts * 0.4
    score -= fluff * 0.35

    if len(body) < 120 and facts < 0.08:
        # RSS 요약만 있을 때는 제목·요약 합쳐 팩트 신호 완화
        title_facts = fact_density(title)
        if title_facts < 0.06:
            reasons.append("본문 짧고 팩트 신호 부족")
            score -= 0.18
        else:
            score += 0.06

    if fluff > 0.35 and facts < 0.12:
        return FilterResult(False, score, ["상투 표현 위주, 구체 수치·결론 부족"])

    if facts < 0.06 and len(body) > 400 and fluff > 0.2:
        return FilterResult(False, score, ["결론·수치·방법론 부족(깡통 패턴)"])

    keep = score >= 0.35
    if not keep:
        reasons.append(f"종합 점수 미달 ({score:.2f})")
    return FilterResult(keep, max(0.0, score), reasons if not keep else ["통과"])
