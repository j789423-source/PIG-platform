"""온보딩: 3~5개 대분류, 세부 주제, 키워드 탭핑, 숙련도·말투."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_pig_dir = str(Path(__file__).resolve().parent)
if _pig_dir not in sys.path:
    sys.path.insert(0, _pig_dir)

from typing import List

from categories import ALL_MAJORS, MajorCategory
from config_manager import UserConfig, save_config, validate_config


def _prompt_line(msg: str, default: str = "") -> str:
    try:
        s = input(f"{msg}" + (f" [{default}]" if default else "") + ": ").strip()
    except EOFError:
        s = ""
    return s or default


def _parse_csv(s: str) -> List[str]:
    parts = re.split(r"[,，、\n]+", s)
    return [p.strip() for p in parts if p.strip()]


def _multiselect_majors() -> List[str]:
    print("\n=== 대분류 선택 (3~5개, 번호 공백으로 구분, 예: 1 2 4) ===\n")
    for i, m in enumerate(ALL_MAJORS, 1):
        print(f"  {i}. [{m.id}] {m.label}")
        print(f"      {m.tagline}\n")
    raw = _prompt_line("번호 입력")
    idxs = {int(x) for x in raw.split() if x.isdigit()}
    chosen: List[str] = []
    for i, m in enumerate(ALL_MAJORS, 1):
        if i in idxs:
            chosen.append(m.id)
    return chosen


def _topics_for_majors(major_ids: List[str]) -> List[MajorCategory]:
    mid = set(major_ids)
    return [m for m in ALL_MAJORS if m.id in mid]


def _multiselect_topics(majors: List[MajorCategory]) -> List[str]:
    print("\n=== 세부 주제 선택 (번호 여러 개) ===\n")
    flat: List[tuple[str, str]] = []
    n = 1
    mapping: dict[int, str] = {}
    for m in majors:
        print(f"--- {m.id} ---")
        for t in m.topics:
            print(f"  {n}. {t.label} — {t.description[:60]}…")
            mapping[n] = t.id
            flat.append((t.id, t.label))
            n += 1
        print()
    raw = _prompt_line("번호 입력 (공백 구분)")
    ids: List[str] = []
    for x in raw.split():
        if x.isdigit():
            k = int(x)
            if k in mapping:
                ids.append(mapping[k])
    return ids


def run_onboarding(config_path: Path | None = None) -> UserConfig:
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  PIG — Personal Insight Guard  온보딩                    ║")
    print("║  뉴닉처럼 친절하게, 넷플릭스처럼 정교하게.               ║")
    print("╚══════════════════════════════════════════════════════════╝")

    majors = _multiselect_majors()
    major_topics = _topics_for_majors(majors)
    topic_ids = _multiselect_topics(major_topics)

    print("\n=== 관심 키워드 (쉼표로 구분, 탭핑) ===")
    interests = _parse_csv(_prompt_line("예: 배당주, 금리, 연말정산"))

    print("\n=== 차단할 소음 (키워드/주제, 쉼표로 구분) ===")
    blocked = _parse_csv(_prompt_line("예: 광고, 협찬, 알림톡"))

    print("\n=== 숙련도 ===\n  1. 초보 (beginner)\n  2. 전문가 (expert)")
    sk = _prompt_line("번호", "1")
    skill: str = "expert" if sk == "2" else "beginner"

    print("\n=== 말투 선호 ===\n  1. 친절함 (friendly)\n  2. 냉철함 (cold)")
    tn = _prompt_line("번호", "1")
    tone: str = "cold" if tn == "2" else "friendly"

    cfg = UserConfig(
        selected_majors=majors,
        selected_topic_ids=topic_ids,
        interest_keywords=interests,
        blocked_noise_keywords=blocked,
        skill_level=skill,  # type: ignore[arg-type]
        tone=tone,  # type: ignore[arg-type]
    )
    errs = validate_config(cfg)
    if errs:
        print("\n[!] 설정 검증 실패:")
        for e in errs:
            print(f"  - {e}")
        print("\n다시 실행해 주세요.\n")
        sys.exit(1)

    save_config(cfg, config_path)
    out = config_path or Path("user_config.json")
    print(f"\n[OK] 저장 완료: {out.resolve()}\n")
    return cfg


def main() -> None:
    run_onboarding()


if __name__ == "__main__":
    main()
