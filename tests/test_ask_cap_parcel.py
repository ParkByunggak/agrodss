# -*- coding: utf-8 -*-
# [2026-10-04 필지 값은 필지의 것 — 묻기 쪽] 묻기 원장은 (작목, 축) 으로 센다. 배수처럼 **밭의 값**을 묻는 횟수가 작목마다 따로 서면, 쪽파 채팅에서 세 번 안 답한 배수를
# 같은 밭의 다른 작목 채팅이 세 번 더 묻는다 — 「모르겠다」 신호(반복 상한 → 멈춤)도 필지의 것이어야 한다. known 과 같은 가름: 밭 정보 값은 같은 밭 전체 · 농사 값(인증)은 작목만.
# 첫 판은 축 이름(soil_water)을 필드 이름(drainage)으로 걸러 한 건도 안 더해졌다 — 이 검사가 그것을 잡았다(물음은 axis 와 field 를 따로 든다).
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone

import pytest

from ingest import asks, parcels, questions, subjects
from judge import run as judge_run

SID = "p001-jjokpa-2026f"
T = date(2026, 9, 28)              # 칸 4 — 과습(회복 불가)이 배수를 묻는 날
NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)


def _q(sid: str, **match):
    s = parcels.enrich_subject(subjects.by_id(sid), parcels.by_id("p001"))
    envs = judge_run.judgments_for(sid, today=T)
    q = next((c for c in questions.candidates(envs, s) if all(c.get(k) == v for k, v in match.items())), None)
    return s, envs, q


def _stopped(sid: str) -> set[str]:
    return {r["axis"] for r in asks.stopped_rows() if r["subject"] == sid}


@pytest.mark.skipif(questions.REPEAT_CAP is None, reason="반복 상한이 없으면 세기만 한다")
def test_a_parcel_question_not_answered_on_one_crop_is_not_asked_again_on_the_other_crop_of_the_same_parcel():
    sid2 = subjects.add("쪽파", "2026 가을 2차", status="재배 중", parcel="p001", anchor="2026-09-01")["id"]     # 같은 밭의 둘째 작목(달력이 있어야 배수를 묻는다)
    s1, _, q1 = _q(SID, field="drainage")
    assert q1 and q1["axis"] == "soil_water"                                          # 축 이름 ≠ 필드 이름
    for i in range(questions.REPEAT_CAP):
        asks.record(SID, [q1], f"m{i}", now=NOW)                                     # 쪽파 채팅에서 세 번 물었다(답 없음)
    s2, envs2, q2 = _q(sid2, field="drainage")
    assert q2 is not None                                                            # 후보에는 있다
    top = questions.top(sid2, envs2, s2)
    assert top is None or top.get("field") != "drainage"                              # 둘째 작목은 배수를 다시 묻지 않는다
    assert "soil_water" in _stopped(SID) and "soil_water" not in _stopped(sid2)       # 멈춤은 물음이 난 작목(쪽파)의 행에 보인다 — 행이 없는 둘째 작목에는 안 쓴다(asks 규율)
    row = next(r for r in asks.stopped_rows() if r["subject"] == SID and r["axis"] == "soil_water")
    assert "같은 밭" in row["stopped"]["why"] and sid2 in row["stopped"]["why"]


@pytest.mark.skipif(questions.REPEAT_CAP is None, reason="반복 상한이 없으면 세기만 한다")
def test_a_crop_value_question_is_still_counted_per_crop():
    a = subjects.add("대파", "2026 가을", status="재배 중", parcel="p001", anchor="2026-10-01")["id"]           # 인증이 없는 두 작목 — 같은 밭
    b = subjects.add("대파", "2026 가을 2차", status="재배 중", parcel="p001", anchor="2026-10-02")["id"]
    sa, _, ca = _q(a, axis="cert")
    assert ca is not None
    for i in range(questions.REPEAT_CAP):
        asks.record(a, [ca], f"c{i}", now=NOW)                                       # 첫 작목에서 인증을 세 번 물었다
    sb, envsb, cb = _q(b, axis="cert")
    assert cb is not None
    top = questions.top(b, envsb, sb)
    assert top is not None and top["axis"] == "cert"                                 # 인증은 작목의 것 — 둘째 작목은 아직 묻는다
    assert "cert" not in _stopped(b)


def test_the_cross_parcel_count_goes_through_the_same_sibling_canon_and_keys_by_field():
    src = inspect.getsource(questions.top)
    assert "known.parcel_siblings(subject)" in src and "known.PARCEL_SHARED_FIELDS" in src       # 밭이 공유하는 값만 — 용도는 작목의 것
    assert 'q.get("field") in parcel_fields' in src                                   # 축 이름이 아니라 필드로 가른다
