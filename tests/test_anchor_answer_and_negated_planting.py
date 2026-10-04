# -*- coding: utf-8 -*-
# [2026-10-04 심은 날 물음 걷기] 계획 목록(심은 날 없음)에 「심은 날(파종일 — '8월 25일에 심었다' 처럼)」 을 물은 뒤 농가가 답하는 꼴을 저장 없이 재니 둘:
#   ① 「9월 1일」 「2026-09-01」 처럼 **날짜만** 답하면 본 것(statement)으로 떨어져 심은 날이 안 선다 — 물음이 그 날짜의 뜻(파종일)을 이미 정했으니 §9 와 같은 묶기가 맞다.
#   ② 「아직 안 심었어요」 가 **파종 사건**이 됐다 — 넣으면 심은 날이 오늘로 선다(안전 축: 날짜를 세는 판단 전부가 틀린 날부터 센다). 부정 접기(§)가 동사 바로 앞에 붙는 꼴을
#      `_negated_task` 가 "안에 끼는" 꼴로만 보고 있었다(「약 안 쳤다」 는 잡고 「안 심었다」 는 놓쳤다 — 두 낱말 짝과 한 낱말 동사의 차이).
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone

import pytest

from ingest import asks, chat, subjects

T = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
ANCHOR_PEND = {"axes": ["anchor"], "fields": []}


def _planned():
    return subjects.by_id(subjects.add("쪽파", "2026 가을 2차", status="계획", parcel="p001")["id"])


@pytest.mark.parametrize("text", ["아직 안 심었어요", "안 심었다", "종구 못 심었다", "아직 안 뿌렸어요", "물 안 줬다", "약 안 쳤다"])
def test_a_negation_right_before_the_verb_is_not_a_done_event(text):
    assert chat._negated_task(text) is not None, text
    d = chat.classify(text, T)[0]
    assert d["kind"] == "decision.noncompliance", (text, d)


@pytest.mark.parametrize("text", ["비가 안 와서 물 줬다", "잎이 마르지 않게 물 줬다", "벌레가 안 보인다", "9월 1일에 심었어요"])
def test_negation_of_another_predicate_is_left_alone(text):
    d = chat.classify(text, T)[0]
    assert d["kind"] != "decision.noncompliance", (text, d)


def test_a_bare_date_answer_to_the_planting_question_is_the_planting_day_and_confirming_sets_the_anchor():
    s = _planned()
    for ans, day in (("9월 1일", "2026-09-01"), ("2026-09-01", "2026-09-01"), ("9/1", "2026-09-01"), ("9월 1일이요", "2026-09-01")):
        out = chat._drafts_from_answer(s, ans, ANCHOR_PEND)
        assert [(d["kind"], d["type"], d["observed_at"], d["why_key"]) for d in out] == [("event", "파종", day, "answers_ask_anchor")], ans
    for ans in ("아직 안 심었어요", "9월 1일에 심었어요", "다음 주에 심을 예정", "모르겠어요", "9월 1일에 물 줬어요"):
        assert chat._drafts_from_answer(s, ans, ANCHOR_PEND) == [], ans            # 말이 더 있으면 분류기가 그대로 본다(사건 · 불이행 · 계획) — 날짜만일 때만 묶는다
    m0, r0 = chat.send(s["id"], "밭 준비 중", today=T, now=NOW)
    assert "심은 날" in r0["text"] and asks.pending(s["id"])["axes"] == ["anchor"]
    m, r = chat.send(s["id"], "9월 1일", today=T, now=NOW)
    d = m["drafts"][0]
    assert d["kind"] == "event" and d["type"] == "파종" and d["observed_at"] == "2026-09-01" and "심은 날" in r["text"]
    assert not any(x.get("kind") == "observation.note" and x.get("why_key") == "statement" for x in m["drafts"])
    chat.confirm(m["id"], 0, now=NOW)
    assert subjects.by_id(s["id"])["anchor"] == "2026-09-01"


def test_a_bare_date_without_the_planting_question_pending_stays_as_it_was():
    s = _planned()
    assert chat._drafts_from_answer(s, "9월 1일", {"axes": ["precip"], "fields": []}) == []
    m, _ = chat.send(s["id"], "9월 1일", today=T, now=NOW)
    assert m["drafts"][0]["kind"] == "observation.note"


def test_the_two_fixes_live_in_their_one_place():
    src = inspect.getsource(chat._negated_task)
    assert 'norm[m.start() - 1] == "§"' in src                                       # 동사 바로 앞의 부정
    src2 = inspect.getsource(chat._drafts_from_answer)
    assert 'ax == "anchor"' in src2 and "_bare_date(text, today" in src2 and "answers_ask_anchor" in chat.PLAIN_BY_KEY
    assert "parse_day(text, today, past=True)" in inspect.getsource(chat._bare_date)        # 날짜 읽기는 분류기와 같은 정본(parse_day)
