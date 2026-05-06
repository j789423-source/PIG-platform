"""OpenAI 기반 2차 품질 판별(깡통·낚시 글 폐기)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[misc, assignment]


@dataclass
class QualityGateResult:
    discard: bool
    reason: str


def ai_should_discard_article(
    title: str,
    body_excerpt: str,
    *,
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
) -> QualityGateResult:
    """
    키워드만 나열·답 없음·상투문·깡통 정보를 LLM이 판별.
    API 키 없으면 폐기하지 않음(통과).
    """
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key or OpenAI is None:
        return QualityGateResult(False, "OPENAI 없음, 스킵")

    client = OpenAI(api_key=key)
    excerpt = (body_excerpt or "")[:5000]
    user = f"""제목과 본문 발췌를 보고 '깡통 정보'(키워드만 반복, 구체적 수치·결론·방법 없음, 낚시성)이면 discard true.
JSON만 출력: {{"discard": true/false, "reason": "한국어 짧게"}}

제목: {title}
본문 발췌:
---
{excerpt}
---
"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You judge Korean/English clickbait and empty articles. Output JSON only.",
            },
            {"role": "user", "content": user},
        ],
        temperature=0.1,
    )
    raw = (resp.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()
    data = json.loads(raw)
    return QualityGateResult(bool(data.get("discard")), str(data.get("reason", "")))
