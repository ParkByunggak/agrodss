# -*- coding: utf-8 -*-
# [2026-09-20 시점 축 걷기] 앞으로 올 날짜들(9/24 마감일 · 9/25 마감 뒤 · 10/4 · 10/14 수확 창 시작 · 10/24 중심 · 11/3 창 끝 · 11/23 · 이듬해)에서
# 판정이 예외 없이 정직한 종류를 내고, 계획 대 실제의 셈이 맞고, 수확 창의 위치가 이전 → 안 → 지남으로 한 방향으로만 가는가.
# 걷기 검사가 실제 날짜로 판정을 봐 9/25 부터 거짓 실패할 형태를 잡은 날, 반대로 "그날이 오면 무엇이 깨지는가"를 미리 걸어 둔다(실측 2026-09-20: 예외 0).
from __future__ import annotations

from datetime import date

from judge import run as judge_run
from judge.envelope import KINDS

SID = "p001-jjokpa-2026f"
DATES = [date(2026, 9, 19), date(2026, 9, 24), date(2026, 9, 25), date(2026, 10, 4), date(2026, 10, 14), date(2026, 10, 24),
         date(2026, 11, 3), date(2026, 11, 23), date(2027, 1, 15)]


def test_every_future_date_judges_without_exception_and_counts_add_up():
    prev_missed = -1
    positions = []
    for d in DATES:
        envs = judge_run.judgments_for(SID, today=d)
        assert len(envs) == 12 and all(e.kind in KINDS for e in envs), d
        pva = next(e for e in envs if e.decision_id == "plan_vs_actual")
        assert pva.kind == "판단함", d
        c, rows = pva.result["counts"], pva.result["rows"]
        assert sum(c.values()) == len(rows), (d, c, len(rows))                     # 셈이 줄 수와 맞는다
        assert c["놓침"] >= prev_missed, d                                         # 기록이 없으면 놓침은 줄지 않는다
        prev_missed = c["놓침"]
        ht = next(e for e in envs if e.decision_id == "harvest_timing")
        assert ht.kind == "판단함", d
        positions.append(ht.result["position"])
    order = {"창 이전": 0, "창 안": 1, "창 지남": 2}
    idx = [order[p] for p in positions]
    assert idx == sorted(idx) and set(idx) == {0, 1, 2}, positions               # 이전 → 안 → 지남, 셋 다 지나간다
