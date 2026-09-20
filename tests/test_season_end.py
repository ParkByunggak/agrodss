# -*- coding: utf-8 -*-
# [시점 걷기 2026-09-20] 작기 종료 — 시즌이 끝난 뒤에도 계획 대 실제가 '놓침 — 사유를 묻는다'를 계속 냈다(재배 단위가 '재배 중'인 채, 상태를 바꾸는 길이
# set_anchor 뿐). 채팅 "작기 종료" → 초안 → 확인 → 등록부 '종료' + 종료일 → 그날 뒤 계획은 '종료 뒤'(놓침 아님 · 사유 안 묻음) · 수확 지연 경보 없음.
# 시스템이 대신 닫지 않는다 — 확인이 부른다.
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from frontend import chat_pages
from ingest import chat, subjects
from judge import run as judge_run

SID = "p001-jjokpa-2026f"
NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


def _pva(today):
    return next(e for e in judge_run.judgments_for(SID, today=today) if e.decision_id == "plan_vs_actual")


def test_end_declaration_closes_the_plan_after_that_day_and_nothing_before_it():
    before = _pva(date(2026, 11, 23)).result["counts"]
    assert before["놓침"] == 12 and before["종료 뒤"] == 0                              # 시점 걷기 실측: 11/23 놓침 12
    m, r = chat.send(SID, "11월 3일 쪽파 재배 종료", today=date(2026, 11, 6), now=NOW)
    d = m["drafts"][0]
    assert d["kind"] == "subject.end" and d["ended_at"] == "2026-11-03" and "작기 종료" in r["text"]
    assert subjects.by_id(SID).get("status") != "종료"                                # 확인 전엔 아무것도 안 바뀐다
    rec = chat.confirm(m["id"], 0, now=NOW)
    s = subjects.by_id(SID)
    assert rec["kind"] == "subject" and s["status"] == "종료" and s["ended_at"] == "2026-11-03"
    after = _pva(date(2026, 11, 23))
    c = after.result["counts"]
    # 11/3 뒤의 계획은 '잔사 정리 · 후작 준비'(11/5) 하나 — 전에는 11/23 에 미이행 1 이던 줄. 놓침 12 는 그대로(종료 전 놓침은 놓침)
    assert c["종료 뒤"] == 1 and c["미이행"] == 0 and c["놓침"] == 12 and sum(c.values()) == len(after.result["rows"])
    assert all(a["work_date"] <= "2026-11-03" for a in after.result["ask_reason"])       # 종료 뒤 줄은 사유를 묻지 않는다
    assert all(r["status"] != "종료 뒤" for r in after.result["rows"] if r["work_date"] <= "2026-11-03")   # 종료 전 줄은 그대로
    side = chat_pages.sidebar(f"/c/{SID}", [], date(2026, 11, 23))
    assert 'class="pill end">종료</span>' in side and 'pill plan">종료' not in side          # 목록 배지: 종료는 계획 색이 아니다
    alerts = next(e for e in judge_run.judgments_for(SID, today=date(2026, 11, 23)) if e.decision_id == "risk_alert")
    assert all("수확 지연" not in (a.get("risk") or "") for a in (alerts.result.get("alerts") or []))   # B1: 종료면 수확 지연 경보 없음


def test_end_needs_a_day_and_is_choosable_and_reversible_only_by_registry():
    with pytest.raises(subjects.SubjectError, match="종료일"):
        subjects.set_status(SID, "종료")
    with pytest.raises(subjects.SubjectError, match="상태는"):
        subjects.set_status(SID, "끝")
    assert ("subject.end", "작기 종료") in chat_pages.CHOOSABLE
    m, _ = chat.send(SID, "오늘은 특별한 일 없음", today=date(2026, 11, 6), now=NOW)
    d = chat.choose_kind(m["id"], "subject.end", today=date(2026, 11, 6))["drafts"][0]
    assert d["kind"] == "subject.end" and d["ended_at"] == "2026-11-06"
    assert subjects.set_status(SID, "재배 중")["status"] == "재배 중" and "ended_at" not in subjects.by_id(SID)
