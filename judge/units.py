# -*- coding: utf-8 -*-
# FILE: judge/units.py
# ROLE: [U-23 2026-09-21] 격자를 못 읽은 **사유**(2층 어휘)를 **봉투 종류**(3층)로 옮기는 자리 하나.
#
# 왜 한 자리인가 — 전에는 소비자 일곱이 각자 `해당 없음`("격자 단위가 없다")을 지어 냈다. 문장이 일곱 벌이면
# 고칠 때 여섯 곳이 남는다(§7.5 지점 축에서 세 번 겪었다). 종류·문장·`missing` 을 여기서만 정한다.
#
#   unlinked    격자가 안 이어짐      판단 불가(지식)   격자 정본이 서면 열린다
#   no_file     가리키는 파일 없음    판단 불가(지식)   정본 미작성이거나 이름이 어긋났다
#   unreadable  있는데 못 읽음        판단 불가(데이터) **고치면 바뀐다** — 그래서 missing 을 채울 수 있다
#
# I-1 §2-6 으로 잰 결과다: 해당 없음은 *"아무리 채워도 안 바뀐다"* 인데 셋 다 **격자가 오면 바뀐다**.
# 'unreadable' 만 데이터인 이유는 고치는 대상이 **이미 있는 파일**이기 때문이다(U-21 처방 정본과 같은 가름).
from __future__ import annotations

from grid import schema as grid_schema
from judge.envelope import Envelope

MISS_KIND: dict[str, str] = {
    "unlinked": "판단 불가(지식)",
    "no_file": "판단 불가(지식)",
    "unreadable": "판단 불가(데이터)",
}

# 사유 갈래가 늘면 **여기서 깨진다** — 기본값으로 메우면 새 갈래가 조용히 옛 종류를 입는다(대리값 금지).
assert set(MISS_KIND) == set(grid_schema.REASONS), f"격자 사유 갈래와 봉투 종류 표가 어긋난다: {grid_schema.REASONS}"


def envelope_for(miss: grid_schema.UnitMiss, decision_id: str, sid: str, as_of: str) -> Envelope:
    """격자를 못 읽었을 때 그 결정이 내는 봉투. **해당 없음을 내지 않는다** — 할 일이 아니었던 것이 아니다."""
    kind = MISS_KIND[miss.reason]
    missing = [{"axis": "격자 정본", "who_can_fill": miss.fixer}] if kind == "판단 불가(데이터)" else []
    return Envelope(kind, decision_id, sid, as_of, missing=missing,
                    result={"why": miss.why, "summary": miss.summary, "grid_unit_miss": miss.reason})
