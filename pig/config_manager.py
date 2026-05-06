"""user_config.json 저장·로드·검증."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pig.categories import MAJOR_BY_ID, get_topic_by_id

SkillLevel = Literal["beginner", "expert"]
TonePreference = Literal["friendly", "cold"]


@dataclass
class UserConfig:
    """온보딩 결과 및 사용자 선호."""

    selected_majors: List[str]  # 3~5개: Money, Career, Life, Tech
    selected_topic_ids: List[str]  # 세부 주제 id 목록
    interest_keywords: List[str]  # 탭핑한 추가 키워드
    blocked_noise_keywords: List[str]  # 차단할 소음
    skill_level: SkillLevel
    tone: TonePreference
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserConfig":
        return cls(
            selected_majors=list(data.get("selected_majors", [])),
            selected_topic_ids=list(data.get("selected_topic_ids", [])),
            interest_keywords=list(data.get("interest_keywords", [])),
            blocked_noise_keywords=list(data.get("blocked_noise_keywords", [])),
            skill_level=data.get("skill_level", "beginner"),
            tone=data.get("tone", "friendly"),
            updated_at=str(data.get("updated_at", "")),
        )


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "user_config.json"


def validate_config(cfg: UserConfig) -> List[str]:
    """검증 오류 메시지 목록 (비어 있으면 통과)."""
    errors: List[str] = []
    n = len(cfg.selected_majors)
    if n < 3 or n > 5:
        errors.append("대분류(Money/Career/Life/Tech)는 3~5개를 선택해야 합니다.")
    for mid in cfg.selected_majors:
        if mid not in MAJOR_BY_ID:
            errors.append(f"알 수 없는 대분류: {mid}")
    for tid in cfg.selected_topic_ids:
        if get_topic_by_id(tid) is None:
            errors.append(f"알 수 없는 세부 주제 id: {tid}")
    if cfg.skill_level not in ("beginner", "expert"):
        errors.append("skill_level은 beginner 또는 expert여야 합니다.")
    if cfg.tone not in ("friendly", "cold"):
        errors.append("tone은 friendly 또는 cold여야 합니다.")
    if not cfg.selected_topic_ids and len(cfg.interest_keywords) < 1:
        errors.append("세부 주제를 1개 이상 선택하거나, 관심 키워드를 1개 이상 입력하세요.")
    return errors


def load_config(path: Optional[Path] = None) -> UserConfig:
    p = path or DEFAULT_CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"설정 파일이 없습니다: {p}")
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    return UserConfig.from_dict(data)


def save_config(cfg: UserConfig, path: Optional[Path] = None) -> None:
    cfg.updated_at = datetime.now(timezone.utc).isoformat()
    p = path or DEFAULT_CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, ensure_ascii=False, indent=2)


def merge_patch(
    path: Optional[Path] = None, **kwargs: Any
) -> UserConfig:
    """기존 파일에 부분 갱신."""
    p = path or DEFAULT_CONFIG_PATH
    if p.exists():
        cfg = load_config(p)
        d = cfg.to_dict()
    else:
        d = UserConfig(
            selected_majors=[],
            selected_topic_ids=[],
            interest_keywords=[],
            blocked_noise_keywords=[],
            skill_level="beginner",
            tone="friendly",
        ).to_dict()
    for k, v in kwargs.items():
        if k in d and v is not None:
            d[k] = v
    out = UserConfig.from_dict(d)
    save_config(out, p)
    return out
