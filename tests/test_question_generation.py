# -*- coding: utf-8 -*-
# [WO-ASK-01 §3 · §14 의 4 · 2026-10-03] 질문 생성 — 판정이 이미 말한 빈자리에서 **하나**를 골라 묻는다.
#
#   1순위  위험 경보의 회복 불가 위험이 근거에 못 실은 값(alert.needs_field — 배수)        §3 "회복 불가 먼저"
#   2순위  판단 불가(데이터)의 요구 항목 — 농가 몫 먼저, 발행자 몫 뒤
#   문장은 judge.need 가 만든 것 그대로(§2 · §5-1 관문을 같은 자리에서 지난다) · 한 번에 하나 · 반복 상한(§8)은 값이라 None(세기만)
#   답이 스스로 묻지 않은 send 의 끝에 붙고 묻기 원장에 센다 · 못 만들면 답은 나가고 dropped 「질문 생성」 에 보인다(검토 §3-ⓑ).
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from ingest import asks, chat, dropped, media, parcels, questions
from judge import run as judge_run
from judge.envelope import Envelope

SID = "p001-jjokpa-2026f"
T34 = date(2026, 9, 28)        # 칸 4 열림 — 과습(회복 불가)이 배수를 못 읽고 · 가뭄은 판단 불가(데이터) precip(농가) · 밑거름은 창 지남
NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)


def _envs(today=T34):
    return judge_run.judgments_for(SID, today=today)


# ── 후보와 순서 ──
def test_the_unrecoverable_risks_missing_value_comes_first_then_farmer_asks_then_publisher_asks():
    c = questions.candidates(_envs())
    assert [q["axis"] for q in c][:2] == ["soil_water", "precip"], [q["axis"] for q in c]
    first = c[0]
    assert first["decision"] == "risk_alert" and first["field"] == "drainage" and first["priority"] == 0
    assert "배수(좋음 · 보통 · 나쁨 중 하나)" in first["who_can_fill"] and "밭 정보 화면" in first["who_can_fill"] and "회복 불가" in first["who_can_fill"]
    assert all(q["priority"] <= 3 for q in c) and [q["priority"] for q in c] == sorted(q["priority"] for q in c)
    assert len({q["axis"] for q in c}) == len(c)                                 # 같은 축은 한 번


def test_the_same_axis_asked_by_several_judgments_is_one_candidate():
    """심은 날은 아홉 판정이 요구한다 — 후보에는 한 번(첫 것)이고, 다른 축은 그대로 남는다."""
    from judge.need import need, need_anchor
    a1 = Envelope("판단 불가(데이터)", "harvest_timing", SID, "2026-09-28T00:00:00", missing=[need_anchor("수확 창을 센다")])
    a2 = Envelope("판단 불가(데이터)", "replant", SID, "2026-09-28T00:00:00", missing=[need_anchor("보식 때를 센다")])
    a3 = Envelope("판단 불가(데이터)", "drought_alert", SID, "2026-09-28T00:00:00", missing=[need("precip", "농가", "비 온 날", "chat", "날수를 센다")])
    c = questions.candidates([a1, a2, a3])
    assert [q["axis"] for q in c] == ["anchor", "precip"] and c[0]["decision"] == "harvest_timing"


def test_once_drainage_is_on_the_parcel_the_next_question_moves_on():
    parcels.set_fields("p001", drainage="나쁨", overwrite=True)
    q = questions.top(SID, _envs())
    assert q and q["axis"] == "precip" and q["who_can_fill"].startswith("농가 — 마지막으로 비 온 날")


def test_a_value_no_judgment_reads_is_never_asked_and_the_refusal_is_visible():
    """§5-1 은 여기서도 선다 — 경보가 소비자 0 인 필지 값을 요구해도(앞으로 생길 수 있는 결함) 묻지 않고 그 사실을 남긴다."""
    dropped.clear()
    e = Envelope("판단함", "risk_alert", SID, "2026-09-28T00:00:00", grade="추정",
                 result={"alerts": [{"risk": "x", "stage": "4. y", "level": "주의", "recoverable": False, "needs_field": "slope"}]})
    assert questions.candidates([e]) == []
    assert any(d["where"] == questions.DROP_WHERE and d["path"] == "risk_alert/slope" for d in dropped.all_drops())


# ── send 에 붙는다 · 원장에 센다 ──
def test_a_reply_that_did_not_ask_gets_one_question_and_the_ledger_counts_it():
    m, r = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    assert r["text"].count("하나 물을 것 — ") == 1 and "배수(좋음 · 보통 · 나쁨 중 하나)" in r["text"]
    rows = asks.for_subject(SID)
    assert [x["axis"] for x in rows] == ["soil_water"] and rows[0]["decision"] == "risk_alert" and rows[0]["count"] == 1
    assert asks.pending(SID) == {"axes": ["soil_water"], "msg": r["id"], "at": rows[0]["last_at"], "fields": ["drainage"]}   # fields — §9 답 묶기가 읽는다


def test_a_reply_that_already_asked_does_not_get_a_second_question():
    _, r = chat.send(SID, "가뭄이 심한데 물 줘야 하나요", today=T34, now=NOW)      # 판단 불가(데이터) — 그 답이 이미 precip 을 묻는다
    assert "하나 물을 것" not in r["text"] and [x["axis"] for x in asks.for_subject(SID)] == ["precip"]


def test_the_question_text_is_the_canonical_requirement_sentence():
    _, r = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    tail = r["text"].split("하나 물을 것 — ", 1)[1]
    assert tail.startswith("농가 — ") and "어디서:" in tail and "왜 지금:" in tail
    for t in ("python", ".env", "_KEY"):
        assert t not in tail


# ── 반복 상한 — 발행자 값 3(추론 표시) ──
def test_the_default_cap_is_the_publishers_three_and_is_marked_as_inference():
    """[발행자 2026-10-03 "반복 상한 3 … 전부 추론 표시로"] 값은 하나(REPEAT_CAP) · 출처에 추론이 적혀 있고 그 출처가 멈춤 기록까지 간다."""
    assert questions.REPEAT_CAP == 3 and questions.REPEAT_CAP_SOURCE.startswith("발행자 2026-10-03 — 추론")      # 표지는 머리에(뒤의 설명 문장과 겹치지 않게 — §7.1 4번)
    for _ in range(4):
        chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    by = {x["axis"]: x for x in asks.for_subject(SID)}
    assert by["soil_water"]["count"] == 3 and "추론" in by["soil_water"]["stopped"]["why"] and by["precip"]["count"] == 1


# ── 반복 상한(값이 오면) ──
def test_without_a_cap_the_same_question_repeats_and_only_counts(monkeypatch):
    monkeypatch.setattr(questions, "REPEAT_CAP", None)
    for _ in range(3):
        chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    row = asks.for_subject(SID)[0]
    assert row["axis"] == "soil_water" and row["count"] == 3 and "stopped" not in row


def test_with_a_cap_the_axis_is_skipped_and_the_stop_is_written_to_the_ledger(monkeypatch):
    monkeypatch.setattr(questions, "REPEAT_CAP", 1)
    _, r1 = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    _, r2 = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    assert "배수" in r1["text"] and "배수" not in r2["text"] and "마지막으로 비 온 날" in r2["text"]     # 다음 후보로 넘어간다
    by = {x["axis"]: x for x in asks.for_subject(SID)}
    assert by["soil_water"]["count"] == 1 and "반복 상한 1회" in by["soil_water"]["stopped"]["why"] and by["precip"]["count"] == 1


# ── 실패는 답을 막지 않되 보이게 ──
def test_question_generation_failure_does_not_block_the_reply_but_is_visible(monkeypatch):
    dropped.clear()

    def boom(*a, **k):
        raise RuntimeError("판정이 터졌다")
    monkeypatch.setattr(judge_run, "judgments_for", boom)
    m, r = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    assert r["text"] and "하나 물을 것" not in r["text"]
    assert any(d["where"] == questions.DROP_WHERE and "판정이 터졌다" in d["why"] for d in dropped.all_drops())
    assert asks.for_subject(SID) == []


def test_answer_still_writes_nothing():
    s = media.load_subjects()[0]
    chat.answer(s, "풀 뽑았다", T34)
    chat.answer(s, "가뭄이 심한데 물 줘야 하나요", T34)
    assert not asks.path().exists()


@pytest.mark.parametrize("today", [date(2026, 9, 1), date(2026, 9, 21), date(2026, 10, 20), date(2026, 11, 20)])
def test_on_any_day_the_top_question_if_any_is_a_canonical_sentence(today):
    q = questions.top(SID, _envs(today))
    if q is not None:
        assert "어디서:" in q["who_can_fill"] and "왜 지금:" in q["who_can_fill"] and q["axis"] and q["decision"]
