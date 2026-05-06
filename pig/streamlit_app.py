"""PIG — Streamlit 웹 UI (온보딩 · 뉴스 수집 · AI 다이제스트)."""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit Cloud 등에서 앱 엔트리 CWD가 달라도 `pig` 패키지를 찾을 수 있도록
# 저장소 루트(pig/의 부모)를 sys.path에 넣는다.
_APP_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _APP_DIR.parent
_root_str = str(_REPO_ROOT)
if _root_str not in sys.path:
    sys.path.append(_root_str)

import logging
import os
from typing import Any, Dict, List, Set

import streamlit as st

from pig.categories import ALL_MAJORS, MajorCategory
from pig.config_manager import (
    DEFAULT_CONFIG_PATH,
    UserConfig,
    load_config,
    save_config,
    validate_config,
)
from pig.pipeline import collect_and_filter, run_digest

# Streamlit 실행 시 콘솔 로그 과다 방지
logging.getLogger("pig.news_sources").setLevel(logging.WARNING)
logging.getLogger("pig.pipeline").setLevel(logging.WARNING)


def _majors_by_id() -> Dict[str, MajorCategory]:
    return {m.id: m for m in ALL_MAJORS}


def _parse_keywords(text: str) -> List[str]:
    parts: List[str] = []
    for line in text.replace(",", "\n").splitlines():
        s = line.strip()
        if s:
            parts.append(s)
    return parts


def _ensure_session() -> None:
    if "pig_cfg" not in st.session_state:
        st.session_state.pig_cfg = None
    if "pig_articles" not in st.session_state:
        st.session_state.pig_articles = []
    if "pig_digests" not in st.session_state:
        st.session_state.pig_digests = []


def _load_cfg_into_session(path: Path) -> None:
    if path.exists():
        st.session_state.pig_cfg = load_config(path)
    else:
        st.session_state.pig_cfg = None


def _render_onboarding(config_path: Path) -> None:
    st.subheader("관심사와 차단할 소음")
    st.caption("대분류 3~5개를 고르고, 세부 주제와 키워드를 입력한 뒤 저장하세요.")

    majors_map = _majors_by_id()
    major_options = [m.id for m in ALL_MAJORS]
    major_labels = {m.id: f"{m.id} — {m.tagline}" for m in ALL_MAJORS}

    existing = st.session_state.pig_cfg
    default_majors: List[str] = list(existing.selected_majors) if existing else []
    default_topics: Set[str] = set(existing.selected_topic_ids) if existing else set()
    default_interest = ", ".join(existing.interest_keywords) if existing else ""
    default_blocked = ", ".join(existing.blocked_noise_keywords) if existing else ""
    default_skill = existing.skill_level if existing else "beginner"
    default_tone = existing.tone if existing else "friendly"

    picked = st.multiselect(
        "대분류 (3~5개)",
        options=major_options,
        default=[x for x in default_majors if x in major_options],
        format_func=lambda x: major_labels.get(x, x),
    )

    topic_ids: List[str] = []
    for mid in picked:
        m = majors_map[mid]
        opts = [t.id for t in m.topics]
        labels = {t.id: f"{t.label} — {t.description[:72]}…" for t in m.topics}
        sub = st.multiselect(
            f"「{mid}」 세부 주제",
            options=opts,
            default=[t for t in default_topics if t in opts],
            format_func=lambda tid: labels.get(tid, tid),
            key=f"topics_{mid}",
        )
        topic_ids.extend(sub)

    interest_text = st.text_area(
        "관심 키워드 (쉼표 또는 줄바꿈)",
        value=default_interest,
        height=88,
        placeholder="예: ETF, 배당, 연말정산",
    )
    blocked_text = st.text_area(
        "차단할 소음 키워드",
        value=default_blocked,
        height=88,
        placeholder="예: 협찬, 광고, 낚시",
    )

    c1, c2 = st.columns(2)
    with c1:
        skill = st.selectbox(
            "숙련도",
            options=["beginner", "expert"],
            format_func=lambda x: "초보" if x == "beginner" else "전문가",
            index=0 if default_skill == "beginner" else 1,
        )
    with c2:
        tone = st.selectbox(
            "말투",
            options=["friendly", "cold"],
            format_func=lambda x: "친절함" if x == "friendly" else "냉철함",
            index=0 if default_tone == "friendly" else 1,
        )

    if st.button("설정 저장", type="primary"):
        cfg = UserConfig(
            selected_majors=picked,
            selected_topic_ids=topic_ids,
            interest_keywords=_parse_keywords(interest_text),
            blocked_noise_keywords=_parse_keywords(blocked_text),
            skill_level=skill,  # type: ignore[arg-type]
            tone=tone,  # type: ignore[arg-type]
        )
        errs = validate_config(cfg)
        if errs:
            for e in errs:
                st.error(e)
        else:
            save_config(cfg, config_path)
            st.session_state.pig_cfg = cfg
            st.success(f"저장했습니다: `{config_path}`")


def _render_feed(config_path: Path) -> None:
    st.subheader("글로벌 뉴스 수집 · 필터")
    if not config_path.exists():
        st.warning("먼저 온보딩 탭에서 설정을 저장하세요.")
        return

    cfg = load_config(config_path)
    st.session_state.pig_cfg = cfg

    c1, c2, c3 = st.columns(3)
    with c1:
        rss_lang = st.selectbox("RSS 언어권", ["en", "ko"], index=0)
    with c2:
        use_newsapi = st.checkbox("NewsAPI 사용", value=bool(os.environ.get("NEWSAPI_KEY") or os.environ.get("NEWS_API_KEY")))
    with c3:
        fetch_body = st.checkbox("본문 HTML 가져오기", value=True)

    ai_gate = st.checkbox("OpenAI 2차 깡통 판별 (`OPENAI_API_KEY`)", value=False)

    if st.button("뉴스 수집 실행", type="primary"):
        with st.spinner("수집 및 필터링 중…"):
            articles = collect_and_filter(
                cfg,
                rss_lang=rss_lang,
                use_newsapi=use_newsapi,
                fetch_full_body=fetch_body,
                use_ai_gate=ai_gate,
            )
        st.session_state.pig_articles = articles
        st.success(f"통과 {len(articles)}건 (깡통·도메인 필터 적용)")

    articles: List[Dict[str, Any]] = st.session_state.pig_articles
    if not articles:
        st.info("수집 결과가 없습니다. 위 버튼을 눌러 실행하세요.")
        return

    for i, a in enumerate(articles):
        score = a.get("filter_score", 0)
        with st.expander(f"{i + 1}. {a.get('title', '')} (점수 {score:.2f})"):
            st.markdown(f"**출처 힌트:** {a.get('source_hint', '')}")
            st.markdown(f"**링크:** [{a.get('link', '')}]({a.get('link', '')})")
            body = (a.get("body_excerpt") or "")[:1200]
            st.text(body + ("…" if len(str(a.get("body_excerpt", ""))) > 1200 else ""))


def _render_digest(config_path: Path) -> None:
    st.subheader("뉴닉 스타일 AI 다이제스트")
    if not config_path.exists():
        st.warning("먼저 온보딩에서 설정을 저장하세요.")
        return
    if not os.environ.get("OPENAI_API_KEY"):
        st.error("`OPENAI_API_KEY` 환경 변수가 필요합니다.")
        return

    cfg = load_config(config_path)
    articles = st.session_state.pig_articles
    if not articles:
        st.warning("뉴스 큐 탭에서 먼저 수집을 실행하세요.")
        return

    top_n = st.number_input("다이제스트할 기사 수", min_value=1, max_value=10, value=3, step=1)

    if st.button("AI 다이제스트 생성", type="primary"):
        with st.spinner("OpenAI로 가공 중…"):
            out = run_digest(cfg, articles, top_n=int(top_n))
        st.session_state.pig_digests = out
        st.success("완료")

    rows = st.session_state.pig_digests
    if not rows:
        st.info("생성 결과가 없습니다.")
        return

    for item in rows:
        d = item.get("digest")
        err = item.get("digest_error")
        st.divider()
        st.markdown(f"### [{item.get('title', '')}]({item.get('link', '')})")
        if err:
            st.warning(err)
            continue
        if not d:
            continue
        st.markdown(f"#### {d.get('headline', '')}")
        st.markdown("**세 줄 요약**")
        st.markdown(d.get("summary_three_lines", ""))
        st.markdown("**왜 중요할까?**")
        st.markdown(d.get("why_it_matters", ""))
        st.markdown("**오늘의 액션**")
        st.info(d.get("action_today", ""))


def main() -> None:
    st.set_page_config(
        page_title="PIG — Personal Insight Guard",
        page_icon="🐷",
        layout="wide",
    )
    _ensure_session()

    config_path = Path(os.environ.get("PIG_CONFIG_PATH", str(DEFAULT_CONFIG_PATH)))
    if st.session_state.pig_cfg is None and config_path.exists():
        _load_cfg_into_session(config_path)

    st.title("🐷 PIG — Personal Insight Guard")
    st.caption("뉴닉처럼 친절하게, 넷플릭스처럼 정교하게.")

    tab_a, tab_b, tab_c = st.tabs(["온보딩 · 설정", "뉴스 큐", "PIG 다이제스트"])

    with tab_a:
        st.markdown(f"설정 파일: `{config_path.resolve()}`")
        _render_onboarding(config_path)

    with tab_b:
        _render_feed(config_path)

    with tab_c:
        _render_digest(config_path)


if __name__ == "__main__":
    main()
