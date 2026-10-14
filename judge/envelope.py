# -*- coding: utf-8 -*-
# FILE: judge/envelope.py
# ROLE: [I-1] 3층 산출의 공통 봉투와 8종. 4층이 받는 유일한 형태.
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

KINDS = (
    "판단함", "선택지+대가", "사실 인용",
    "판단 불가(데이터)", "판단 불가(지식)", "해당 없음", "예측 불가", "답하지 않음",
)
GRADES = ("계산", "관측", "추정")   # E 3분류 — 가장 약한 축이 전체 등급


def weakest(grades: list[str]) -> str:
    # [대리값 전수 2026-09-20] 빈 목록에 '추정' 을 돌려주던 자리 — 축이 하나도 없는데 등급을 지어낸다(대리값 금지).
    # 축 없이 '판단함' 은 성립하지 않으므로 값을 메우지 않고 깨뜨린다(봉투 __post_init__ 가 종류를 깨뜨리는 것과 같은 급).
    if not grades:
        raise ValueError("등급을 셀 축이 없다 — 빈 목록에 등급을 지어내지 않는다")
    order = {g: i for i, g in enumerate(GRADES)}
    return max(grades, key=lambda g: order[g])


@dataclass
class AxisUse:
    """봉투의 inputs 항목 — 무엇을 썼는지. 값은 싣지 않는다(4층 격리)."""
    axis: str
    observed_at: str | None
    source: str
    resolution: str
    grade: str                       # 계산 | 관측 | 추정


@dataclass
class Envelope:
    kind: str
    decision_id: str
    subject: str
    as_of: str
    inputs: list[AxisUse] = field(default_factory=list)
    missing: list[dict[str, str]] = field(default_factory=list)      # [{axis, who_can_fill}]
    caps: list[dict[str, str]] = field(default_factory=list)         # 상한 제약 [{name, basis}]
    revisit_at: str | None = None
    consumer_visible: bool = False
    grade: str | None = None                                         # 판단함에서만
    result: dict[str, Any] = field(default_factory=dict)             # 종류별 본문(값·오차 폭·후보·인용문…)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"봉투 종류가 아니다: {self.kind!r}")
        if self.kind == "판단함" and self.grade not in GRADES:
            raise ValueError("판단함은 신뢰 등급이 필요하다")
        if self.kind != "판단 불가(데이터)" and self.missing:
            raise ValueError("missing 은 판단 불가(데이터)에서만 채운다")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# 읽은 기록의 **수** — 판단이 그 기록을 셌다는 장부이지 판단이 바뀐 것이 아니다(계획 대 실제가 싣는다)
COUNTERS: tuple[str, ...] = ("events_used", "videos_used", "reasons_used")


def reading_face(e: Envelope) -> dict[str, Any]:
    """판단이 **읽은 것으로 바뀌는 면** — 봉투에서 낸 시각(as_of)과 읽은 기록 수(COUNTERS)를 뺀 것.

    [앞날 걷기 2026-10-14 W-19] 「누르면 판단이 읽습니다」 의 근거가 봉투 **전부**를 대조한 표였다 — 그러면 읽은 사건 수 하나만 바뀌어도 「읽는다」 가 되어,
    용도 「종구 생산」 에서 넣어도 아무것도 안 바뀌는 수확 기록에 그 약속을 했다. 넣은 셈으로 다시 낸 판단과 이 면을 대조한다(답 문장만 보면 근거 · 메모에만
    실리는 값 — 배수 등급 — 을 놓친다 · 봉투 전부를 보면 장부를 읽음으로 센다)."""
    d = e.to_dict()
    d.pop("as_of", None)
    d["result"] = {k: v for k, v in (d.get("result") or {}).items() if k not in COUNTERS}
    return d
