"""OpenAI로 뉴닉 스타일 요약·영향·액션 플랜."""

from __future__ import annotations

import sys
from pathlib import Path

_pig_dir = str(Path(__file__).resolve().parent)
if _pig_dir not in sys.path:
    sys.path.insert(0, _pig_dir)

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from config_manager import UserConfig

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]


@dataclass
class DigestOutput:
    headline: str
    summary_three_lines: str
    why_it_matters: str
    action_today: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headline": self.headline,
            "summary_three_lines": self.summary_three_lines,
            "why_it_matters": self.why_it_matters,
            "action_today": self.action_today,
        }


def _skill_tone_instructions(cfg: UserConfig) -> str:
    depth = (
        "초보 사용자: 전문 용어는 괄호로 짧게 풀어쓰고, 비유를 섞어 이해를 돕습니다."
        if cfg.skill_level == "beginner"
        else "전문가 사용자: 업계 관행·2차 파급까지 간결하게 깊이 있게 설명합니다."
    )
    tone = (
        "말투는 따뜻하고 친절하게, 하지만 과장 없이."
        if cfg.tone == "friendly"
        else "말투는 간결하고 냉철하게, 감정적 수사는 줄입니다."
    )
    return f"{depth}\n{tone}"


def build_digest_prompt(cfg: UserConfig, title: str, source: str, body_excerpt: str) -> str:
    interests = ", ".join(cfg.interest_keywords + cfg.selected_topic_ids[:8])
    return f"""당신은 개인화 뉴스 큐레이션 서비스 PIG의 에디터입니다.
사용자 관심사(참고): {interests}

{_skill_tone_instructions(cfg)}

아래 기사 제목·출처·본문 발췌를 바탕으로 JSON 한 개만 출력하세요. 다른 텍스트 금지.
필드:
- headline: 호기심을 자극하되 팩트를 담은 제목 (한국어)
- summary_three_lines: 정확히 3문장, 아주 쉬운 말로 핵심만
- why_it_matters: 이 뉴스가 사용자의 자산·커리어·일상에 미칠 실질적 영향
- action_today: 오늘 바로 할 수 있는 행동 한 가지 (구체적으로)

제목: {title}
출처: {source}
본문 발췌:
---
{body_excerpt[:6000]}
---
JSON 스키마: {{"headline": "...", "summary_three_lines": "...", "why_it_matters": "...", "action_today": "..."}}
"""


def summarize_article(
    cfg: UserConfig,
    title: str,
    source: str,
    body_excerpt: str,
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
) -> DigestOutput:
    if OpenAI is None:
        raise RuntimeError("openai 패키지가 설치되어 있지 않습니다. pip install openai")
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY 환경 변수를 설정하세요.")

    client = OpenAI(api_key=key)
    prompt = build_digest_prompt(cfg, title, source, body_excerpt)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You output only valid JSON for PIG digest."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.35,
    )
    raw = (resp.choices[0].message.content or "").strip()
    # 코드펜스 제거
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()
    data = json.loads(raw)
    return DigestOutput(
        headline=str(data.get("headline", "")),
        summary_three_lines=str(data.get("summary_three_lines", "")),
        why_it_matters=str(data.get("why_it_matters", "")),
        action_today=str(data.get("action_today", "")),
    )
