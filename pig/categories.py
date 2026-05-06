"""PIG 방대한 카테고리 데이터 — 뉴닉·넷플릭스형 온보딩용."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Topic:
    """대분류 하위 주제."""

    id: str
    label: str
    description: str


@dataclass(frozen=True)
class MajorCategory:
    """최상위 카테고리 (Money / Career / Life / Tech)."""

    id: str
    label: str
    tagline: str
    topics: List[Topic] = field(default_factory=list)


# --- [Money] ---
MONEY = MajorCategory(
    id="Money",
    label="Money — 자본주의 생존 및 자산 증식",
    tagline="돈을 잃지 않게 해주는 정보에 집중합니다.",
    topics=[
        Topic(
            "money_real_estate",
            "부동산",
            "청약 전략, 재개발/재건축 분석, 경매 기초, 상가 임대차, 임장 보고서 요약",
        ),
        Topic(
            "money_stocks",
            "주식/금융",
            "국내 우량주 배당금, 미장 ETF, 금리 변동 영향, 공모주 일정, 채권 투자",
        ),
        Topic(
            "money_tax_law",
            "세금/법률",
            "증여세/상속세 절세, 연말정산, 전세사기 예방 법률, 개인사업자 부가세",
        ),
        Topic(
            "money_side_hustle",
            "N잡/부업",
            "유튜브 알고리즘 트렌드, 전자책 출판, 무인 창업, 제휴 마케팅 실무",
        ),
    ],
)

# --- [Career] ---
CAREER = MajorCategory(
    id="Career",
    label="Career — 업무 효율 및 커리어 하이",
    tagline="직장인·취준생의 시간을 벌어주는 도구와 기회.",
    topics=[
        Topic(
            "career_automation",
            "업무 자동화",
            "Python 실무, 엑셀 매크로, Cursor AI, 노션 워크스페이스",
        ),
        Topic(
            "career_job_dev",
            "이직/자기계발",
            "이력서, 면접 기출, 전문직 면허 갱신, 대학원 진학",
        ),
        Topic(
            "career_global",
            "언어/글로벌",
            "PTE/IELTS, 비즈니스 영어, 해외 취업 비자(호주/미국 등)",
        ),
        Topic(
            "career_certs",
            "자격/고시",
            "CPA·노무사 등, 공무원 시험 트렌드, IT 자격증 로드맵",
        ),
    ],
)

# --- [Life] ---
LIFE = MajorCategory(
    id="Life",
    label="Life — 웰니스 및 지속 가능한 삶",
    tagline="내 몸과 마음을 지키는 필터링.",
    topics=[
        Topic(
            "life_health",
            "헬스케어",
            "영양제 조합, 심뇌혈관 예방, 당뇨/고혈압 식단, 최신 의학 뉴스",
        ),
        Topic(
            "life_mental",
            "멘탈/심리",
            "번아웃 자가진단, 명상, 인간관계 심리학, 상담 센터 정보",
        ),
        Topic(
            "life_parenting",
            "교육/육아",
            "영유아 발달, 학군, 에듀테크, 정부 양육 지원금",
        ),
        Topic(
            "life_hobby",
            "취미/여가",
            "여행 큐레이션, 와인/위스키 입문, 캠핑, 도서 요약",
        ),
    ],
)

# --- [Tech] ---
TECH = MajorCategory(
    id="Tech",
    label="Tech — 미래 통찰 및 도구 활용",
    tagline="소외되지 않을 지식.",
    topics=[
        Topic(
            "tech_ai",
            "인공지능",
            "ChatGPT 실전 프롬프트, AI 이미지, 업무용 커스텀 GPT",
        ),
        Topic(
            "tech_future",
            "미래 기술",
            "양자 컴퓨터, 로보틱스, 우주 산업, 자율주행",
        ),
        Topic(
            "tech_security",
            "디지털 보안",
            "보이스피싱, 개인정보 보호, 가상자산 지갑",
        ),
    ],
)

ALL_MAJORS: List[MajorCategory] = [MONEY, CAREER, LIFE, TECH]

MAJOR_BY_ID: Dict[str, MajorCategory] = {m.id: m for m in ALL_MAJORS}


def get_topic_by_id(topic_id: str) -> Topic | None:
    for major in ALL_MAJORS:
        for t in major.topics:
            if t.id == topic_id:
                return t
    return None
