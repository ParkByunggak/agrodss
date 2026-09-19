# -*- coding: utf-8 -*-
# FILE: judge/registry.py
# ROLE: [M-8 · F 3층] 결정 등록부 — 필요 축 · 금지 축 · 판정 규칙 선언 없이는 등록되지 않는다.
#       결정의 필요 축은 격자 칸의 판정 축 안에 있어야 한다(격자와 결정이 다른 축을 말하지 않게).
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from grid import schema as grid_schema


@dataclass(frozen=True)
class Decision:
    id: str
    name: str
    required_axes: tuple[str, ...]           # 없으면 판단 불가(데이터)
    optional_axes: tuple[str, ...]           # 없어도 판단하되 등급이 내려간다
    forbidden_axes: tuple[str, ...]
    rule: str                                # 판정 규칙 — 사람이 읽는 한 문장 (코드는 judge/<id>.py)
    revisit_days: int | None                 # 재판정 주기(없으면 None)
    params: dict[str, Any] = field(default_factory=dict)   # 임계 등 — 출처를 같이 적는다
    answers_policy: str = "판단"             # 판단 | 답하지 않음


class RegistrationError(ValueError):
    pass


_REGISTRY: dict[str, Decision] = {}


def register(d: Decision) -> Decision:
    if not d.id or not d.name:
        raise RegistrationError("id · name 필수")
    if not d.rule.strip():
        raise RegistrationError(f"{d.id}: 판정 규칙 선언 없이는 등록 불가")
    if d.answers_policy == "판단" and not d.required_axes:
        raise RegistrationError(f"{d.id}: 필요 축 선언 없이는 등록 불가")
    if d.forbidden_axes is None:
        raise RegistrationError(f"{d.id}: 금지 축은 빈 튜플이라도 선언해야 한다")
    for a in d.required_axes + d.optional_axes:
        if a not in grid_schema.AXES:
            raise RegistrationError(f"{d.id}: I-4 밖 축 {a!r}")
    for a in d.forbidden_axes:
        if a not in grid_schema.AXES | grid_schema.FORBIDDEN_ONLY:
            raise RegistrationError(f"{d.id}: I-4 밖 금지 축 {a!r}")
    if set(d.required_axes) & set(d.forbidden_axes):
        raise RegistrationError(f"{d.id}: 필요 축과 금지 축이 겹친다")
    _REGISTRY[d.id] = d
    return d


def get(decision_id: str) -> Decision | None:
    return _REGISTRY.get(decision_id)


def all_decisions() -> dict[str, Decision]:
    return dict(_REGISTRY)


def check_against_grid(d: Decision, stage: dict[str, Any]) -> list[str]:
    """결정의 필요 축 ⊆ 칸의 판정 축, 결정의 금지 축 ⊇ 칸의 금지 축 — 어긋나면 사유 목록."""
    errs = []

    def _axes(v: Any) -> set[str]:
        # [코드 평가 A4] 격자는 "N/A"(해당 없음) 문자열을 허용한다 — set("N/A") 로 만들면 'N','/','A' 글자 단위로 돌아 사유가 오염됐다
        return set() if not v or isinstance(v, str) else set(v)
    req = _axes(stage.get("required_axes"))
    forb = _axes(stage.get("forbidden_axes"))
    for a in d.required_axes:
        if a not in req:
            errs.append(f"결정 {d.id} 의 필요 축 {a!r} 가 칸 '{stage.get('name')}' 의 판정 축에 없다")
    for a in forb:
        if a not in d.forbidden_axes:
            errs.append(f"칸 '{stage.get('name')}' 의 금지 축 {a!r} 를 결정 {d.id} 가 금지하지 않는다")
    return errs


# ── 등록: harvest_timing (M-10 ①) ────────────────────────────────────────────────
HARVEST_TIMING = register(Decision(
    id="harvest_timing",
    name="수확 시기",
    required_axes=("anchor",),                       # L: 정식일·품종만으로 성립
    optional_axes=("temp", "gdd", "forecast"),       # 있으면 등급이 오르고 상한 제약이 붙는다
    forbidden_axes=("humidity_air",),
    rule=("기준점 + 격자 수확 창(from_day~to_day)으로 수확 창을 낸다. 품종 미확인이면 범위 제시. "
          "예보의 일 최저기온이 params.frost_tmin_c 아래로 내려가는 날이 창 안에 있으면 상한 제약(첫 서리)을 붙인다. "
          "신뢰 등급은 쓰인 축과 격자 출처 중 가장 약한 것."),
    revisit_days=7,
    params={"frost_tmin_c": 0.0,
            "frost_tmin_c_source": "격자 위험 '첫 서리·한파' 트리거 문면(영하) — 쪽파 내한 한계는 미채움이라 0℃ 임계는 보수적 대체값(발행자 검토 대기)"},
))
