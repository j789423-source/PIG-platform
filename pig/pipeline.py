"""user_config 기반 수집 → 필터 → (선택) AI 요약 파이프라인."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pig.ai_quality_gate import ai_should_discard_article
from pig.categories import get_topic_by_id
from pig.config_manager import DEFAULT_CONFIG_PATH, UserConfig, load_config
from pig.news_sources import RawArticle, fetch_article_text, fetch_google_news_rss, fetch_newsapi_everything
from pig.noise_filter import is_kimchi_article
from pig.summarizer import summarize_article

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _queries_from_config(cfg: UserConfig, max_queries: int = 6) -> List[str]:
    parts: List[str] = []
    for tid in cfg.selected_topic_ids:
        t = get_topic_by_id(tid)
        if t:
            parts.append(t.label)
    parts.extend(cfg.interest_keywords)
    # 중복 제거, 순서 유지
    seen: Set[str] = set()
    out: List[str] = []
    for p in parts:
        k = p.strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out[:max_queries]


def collect_and_filter(
    cfg: UserConfig,
    *,
    rss_lang: str = "en",
    use_newsapi: bool = True,
    max_per_query: int = 12,
    fetch_full_body: bool = True,
    extra_domain_blacklist: Optional[List[str]] = None,
    extra_domain_whitelist: Optional[List[str]] = None,
    use_ai_gate: bool = False,
) -> List[Dict[str, Any]]:
    queries = _queries_from_config(cfg)
    if not queries:
        queries = cfg.selected_majors[:3] or ["finance", "technology"]

    seen_links: Set[str] = set()
    raw: List[RawArticle] = []

    ceid = "US:en" if rss_lang == "en" else "KR:ko"
    hl = "en-US" if rss_lang == "en" else "ko"
    gl = "US" if rss_lang == "en" else "KR"

    for q in queries:
        try:
            raw.extend(
                fetch_google_news_rss(q, hl=hl, gl=gl, ceid=ceid)[:max_per_query]
            )
        except Exception as e:
            logger.warning("Google RSS 실패 (%s): %s", q, e)
        if use_newsapi:
            try:
                raw.extend(
                    fetch_newsapi_everything(q, language="en" if rss_lang == "en" else "ko")[
                        : max_per_query // 2
                    ]
                )
            except Exception as e:
                logger.warning("NewsAPI 실패 (%s): %s", q, e)

    results: List[Dict[str, Any]] = []
    for art in raw:
        if art.link in seen_links:
            continue
        seen_links.add(art.link)
        body = art.summary
        if fetch_full_body:
            body = fetch_article_text(art.link) or art.summary

        fr = is_kimchi_article(
            art.title,
            body,
            art.link,
            cfg.interest_keywords + queries,
            cfg.blocked_noise_keywords,
            extra_blacklist=extra_domain_blacklist,
            extra_whitelist=extra_domain_whitelist,
        )
        if not fr.keep:
            logger.info("폐기: %s — %s", art.title[:60], fr.reasons)
            continue
        if use_ai_gate:
            gate = ai_should_discard_article(art.title, body)
            if gate.discard:
                logger.info("AI 폐기: %s — %s", art.title[:60], gate.reason)
                continue
        results.append(
            {
                "title": art.title,
                "link": art.link,
                "source_hint": art.source_hint,
                "published": art.published,
                "body_excerpt": body[:8000],
                "filter_score": fr.score,
            }
        )
    return results


def run_digest(
    cfg: UserConfig,
    articles: List[Dict[str, Any]],
    top_n: int = 3,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for a in articles[:top_n]:
        try:
            d = summarize_article(
                cfg,
                a["title"],
                a.get("source_hint") or "",
                a.get("body_excerpt") or "",
            )
            out.append({**a, "digest": d.to_dict()})
        except Exception as e:
            logger.warning("요약 스킵: %s — %s", a.get("title"), e)
            out.append({**a, "digest_error": str(e)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="PIG 뉴스 수집·필터·요약")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    ap.add_argument("--rss-lang", choices=["en", "ko"], default="en")
    ap.add_argument("--no-newsapi", action="store_true")
    ap.add_argument("--no-fetch-body", action="store_true")
    ap.add_argument("--digest", action="store_true", help="OpenAI로 요약(OPENAI_API_KEY 필요)")
    ap.add_argument(
        "--ai-gate",
        action="store_true",
        help="OpenAI 2차 깡통 판별(OPENAI_API_KEY)",
    )
    ap.add_argument("--out", type=Path, default=Path("pig_output.json"))
    args = ap.parse_args()

    cfg = load_config(args.config)
    articles = collect_and_filter(
        cfg,
        rss_lang=args.rss_lang,
        use_newsapi=not args.no_newsapi,
        fetch_full_body=not args.no_fetch_body,
        use_ai_gate=args.ai_gate,
    )
    if args.digest:
        articles = run_digest(cfg, articles)

    args.out.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("저장: %s (%d건)", args.out, len(articles))


if __name__ == "__main__":
    main()
