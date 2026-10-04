# -*- coding: utf-8 -*-
# [2026-10-04 처방 직후 전수 — ㊳ 의 결함] 「방금 물었던 것(…)에 대한 답으로도 읽었습니다」 가 **물음 뒤의 아무 말**에나 붙었다 — 배수를 물은 뒤 「오늘 대파도 심었어요」 에
# 「방금 물었던 것(토양 수분)에 대한 답으로도 읽었습니다 — 넣으면 위험 경보가 그 날을 읽습니다」 가 붙었다(거짓 — 파종 기록은 배수 물음의 답이 아니고 위험 경보는 그 날을 읽지 않는다).
# after_ask 는 "물음 뒤 처음 온 말" 을 적는 기록(§9)이고, 줄은 **그 말이 그 축의 답일 때만** 붙어야 한다: 비 온 날 물음 ← 관수 한 일 · 비 관찰 / 심은 날 물음 ← 파종·정식 한 일 / 증상 물음 ← 본 것.
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone

import pytest

from ingest import asks, chat, subjects

T = date(2026, 9, 28)
NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)
SID = "p001-jjokpa-2026f"


@pytest.mark.parametrize("axis, draft, want", [
    ("precip", {"kind": "event", "type": "관수", "text": "오늘 물 줬다"}, True),
    ("precip", {"kind": "observation.note", "text": "어제 비 왔어요"}, True),
    ("precip", {"kind": "observation.note", "text": "잎이 처진다"}, False),
    ("precip", {"kind": "event", "type": "파종", "text": "오늘 심었다"}, False),
    ("anchor", {"kind": "event", "type": "파종", "text": "9월 1일에 심었다"}, True),
    ("anchor", {"kind": "event", "type": "관수", "text": "물 줬다"}, False),
    ("observation", {"kind": "observation.note", "text": "잎 끝이 노랗다"}, True),
    ("soil_water", {"kind": "event", "type": "파종", "text": "오늘 대파도 심었어요"}, False),       # 밭 정보 값은 §9 묶기만이 답이다
    ("forecast", {"kind": "observation.note", "text": "비 왔다"}, False),                         # 발행자 몫 물음 — 농가 말이 답이 아니다
])
def test_a_message_counts_as_the_answer_only_when_it_fits_the_asked_axis(axis, draft, want):
    assert chat._answers_axis(axis, draft) is want


def test_a_planting_record_after_the_drainage_question_is_not_called_its_answer():
    m0, r0 = chat.send(SID, "오늘 트랩 봤다", today=T, now=NOW)
    assert asks.pending(SID)["axes"] == ["soil_water"]
    m, r = chat.send(SID, "오늘 대파도 심었어요", today=T, now=NOW)
    assert m["drafts"][0]["kind"] == "event" and m.get("after_ask", {}).get("axes") == ["soil_water"]      # 물음 뒤 첫 말이라는 기록은 남는다(§9)
    assert chat.ANSWERED_AS not in r["text"]                                                               # 그러나 답이라고 말하지 않는다


def test_a_rain_record_after_the_rain_question_still_gets_the_line():
    m0, _ = chat.send(SID, "오늘 트랩 봤다", today=T, now=NOW)
    m1, _ = chat.send(SID, "좋음", today=T, now=NOW)
    chat.confirm(m1["id"], 0, now=NOW)
    m2, r2 = chat.send(SID, "오늘 트랩 봤다", today=T, now=NOW)
    assert asks.pending(SID)["axes"] == ["precip"]
    m, r = chat.send(SID, "그저께 비 왔어요", today=T, now=NOW)
    assert chat.ANSWERED_AS in r["text"]


def test_the_relevance_gate_sits_in_the_one_line_site():
    src = inspect.getsource(chat.send)
    assert "_answers_axis(" in src and "_answered_line(subject_id, " in src
