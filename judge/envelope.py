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
    order = {g: i for i, g in enumerate(GRADES)}
    return max(grades, key=lambda g: order[g]) if grades else "추정"


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
