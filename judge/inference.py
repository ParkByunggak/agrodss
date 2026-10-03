# -*- coding: utf-8 -*-
# FILE: judge/inference.py
# ROLE: [WO-ASK-01 §10 · §14 의 5 · 2026-10-03] 추론 고지와 고치기 — **어느 추론값을 농가에게 "고칠 수 있다" 고 말하는가**를 한 자리에서 고른다.
#
#   §10  "추론값은 쓰이는 그 자리에서 고칠 수 있다. 대상은 추론값 중 농가가 알 수 있는 것(P1)만. 농가가 알 수 없는 것(병해충 임계 · 내한 한계 — P2/P4)은
#         제외 — 답할 수 없는 요청이 매번 뜨면 ⑦이 깨진다. 침묵은 동의가 아니다 — 여러 번 보여줬는데 안 고쳤다고 확정으로 올리지 않는다.
#         승격은 셋 중 하나로만 — 농가가 명시적으로 고침 · 외부 정본 대조 · 실측."
#
#   재료는 격자 정본의 두 표지뿐이다 — source(추론인가 · grid.schema.is_inference) 와 fixable_by(누가 고칠 수 있는가 · 검증기가 추론값마다 요구한다).
#   여기서는 **고르기만** 한다 — 문장은 4층(frontend.words.fix_offer) · 고침의 입구는 '고쳐 달라는 말'(feedback.request) 그대로 · 격자 값을 바꾸는 코드는 여기 없다
#   (값은 지식 · apply_grid_value 한 명령 · 출처가 「농가 확인 날짜」 로 바뀌는 것이 승격이다 — 노출 횟수로 올리는 길은 없다).
from __future__ import annotations

from typing import Any

from grid import schema as grid_schema

FARMER = "농가"


def farmer_fixable(items: list[dict[str, Any]]) -> list[str]:
    """추론값이고 농가가 고칠 수 있는 항목의 이름 — 순서 그대로 · 같은 이름 한 번. 정본·실측 몫은 **부르지 않는다**(§10 제외)."""
    out: list[str] = []
    for it in items or []:
        if not isinstance(it, dict) or not grid_schema.is_inference(it.get("source")):
            continue
        if it.get(grid_schema.FIXABLE_BY_KEY) != FARMER:
            continue
        name = str(it.get("risk") or it.get("task") or it.get("name") or "").strip()
        if name and name not in out:
            out.append(name)
    return out
