"""Google News RSS 및 NewsAPI 기반 글로벌 뉴스 수집."""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; PIG-NewsBot/0.1; +https://example.local/pig)"
)


@dataclass
class RawArticle:
    title: str
    link: str
    source_hint: str
    summary: str
    published: str


def _google_news_rss_url(query: str, hl: str = "en-US", gl: str = "US", ceid: str = "US:en") -> str:
    q = urllib.parse.quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


def fetch_google_news_rss(
    query: str,
    hl: str = "en-US",
    gl: str = "US",
    ceid: str = "US:en",
    timeout: int = 20,
) -> List[RawArticle]:
    url = _google_news_rss_url(query, hl=hl, gl=gl, ceid=ceid)
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: List[RawArticle] = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")
        desc_el = item.find("description")
        source_el = item.find("source")
        title = (title_el.text or "").strip() if title_el is not None else ""
        link = (link_el.text or "").strip() if link_el is not None else ""
        published = (pub_el.text or "").strip() if pub_el is not None else ""
        summary = _strip_html(desc_el.text or "") if desc_el is not None else ""
        src = (source_el.text or "").strip() if source_el is not None else ""
        if title and link:
            items.append(
                RawArticle(
                    title=title,
                    link=link,
                    source_hint=src,
                    summary=summary[:2000],
                    published=published,
                )
            )
    return items


def _strip_html(html: str) -> str:
    t = re.sub(r"<[^>]+>", " ", html)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def fetch_newsapi_everything(
    query: str,
    api_key: Optional[str] = None,
    language: str = "en",
    page_size: int = 20,
    timeout: int = 20,
) -> List[RawArticle]:
    key = api_key or os.environ.get("NEWSAPI_KEY") or os.environ.get("NEWS_API_KEY")
    if not key:
        logger.warning("NewsAPI: API 키 없음 (NEWSAPI_KEY). 건너뜀.")
        return []
    url = "https://newsapi.org/v2/everything"
    params: Dict[str, Any] = {
        "q": query,
        "language": language,
        "pageSize": page_size,
        "sortBy": "publishedAt",
        "apiKey": key,
    }
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    out: List[RawArticle] = []
    for a in data.get("articles", []) or []:
        title = (a.get("title") or "").strip()
        link = (a.get("url") or "").strip()
        summary = (a.get("description") or "") + " " + (a.get("content") or "")
        summary = summary.strip()[:2000]
        pub = (a.get("publishedAt") or "").strip()
        src = ((a.get("source") or {}) or {}).get("name") or ""
        if title and link:
            out.append(
                RawArticle(
                    title=title,
                    link=link,
                    source_hint=src,
                    summary=summary,
                    published=pub,
                )
            )
    return out


def fetch_article_text(url: str, max_chars: int = 12000, timeout: int = 15) -> str:
    """링크 HTML에서 본문 추출(경량: p 태그 텍스트 합침)."""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        logger.debug("본문 fetch 실패 %s: %s", url, e)
        return ""
    # script/style 제거
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    chunks: List[str] = []
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", html, flags=re.I | re.S):
        chunks.append(_strip_html(m.group(1)))
    text = "\n".join(chunks)
    if len(text) < 200:
        # fallback: 전체 태그 제거
        text = _strip_html(re.sub(r"(?is)<[^>]+>", " ", html))
    return text[:max_chars]
