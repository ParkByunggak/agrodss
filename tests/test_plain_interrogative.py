# -*- coding: utf-8 -*-
# [대파 걷기 2026-10-04] 둘째 작목(대파)이 받을 답을 걸다 나온 넷째 오분류 형태 — **물음이 '본 것' 으로 적힌다**.
#   실측: 「물 줘야 하나」 「병충해 뭐 봐야 하나」 「비료 뭐 주나」 「서리 오나」 가 쪽파 · 대파 둘 다 observation.note 초안이 되고 답은 안 나갔다
#   ("한 일이나 할 일을 가리키는 말이 없어 본 것으로 적었습니다"). 물음표 없는 물음 15 중 8(2026-09-21)과 같은 축인데 그때는 간접 의문(-는지)만 넓혔고
#   **종결 의문 어미**(-나 · -냐 · -ㅂ니까)는 남았다. 처방은 한 자리 — _classify 의 물음 한 줄에 _plain_interrogative 하나(발행자 "하나로 묶으라").
#   경계는 실측으로 — 「하나」 는 셈말(노란 포기가 하나) · 「-구나」 감탄 · 「-니까」 이유 · 「-이나」 셈.
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone

import pytest

from ingest import chat, subjects

T = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
SID = "p001-jjokpa-2026f"


@pytest.mark.parametrize("text", [
    "물 줘야 하나", "병충해 뭐 봐야 하나", "비료 뭐 주나", "서리 오나", "약 쳐야 하냐", "물을 줘야 합니까", "지금 뭐 하나", "어떻게 하나",
    "잎이 마르나", "병이 있나", "물 줬나", "비 오나요", "웃거름 줘야 합니까요", "수확 언제 하나?", "약 쳐도 됩니까",
])
def test_a_sentence_ending_in_a_plain_question_ending_is_a_question(text):
    assert chat._plain_interrogative(text), text
    assert chat.classify(text, T)[0]["kind"] == "question", text


@pytest.mark.parametrize("text", [
    "노란 포기가 하나", "잎이 노랗구나", "비가 왔으니까", "마른 포기가 둘이나", "물 주거나", "비는 왔으나", "오늘 물 줬다", "잎이 노랗다", "하나",
])
def test_the_same_tail_that_is_not_a_question_is_left_alone(text):
    assert not chat._plain_interrogative(text), text
    assert chat.classify(text, T)[0]["kind"] != "question", text


def test_the_rule_is_wired_into_the_one_question_line_of_the_classifier():
    """배선 래칫 — 호출형만(인자 표현식 · 줄 위치는 고정하지 않는다). 물음 판정은 _classify 의 한 줄이고 거기서 불려야 한다(다른 자리에 사본을 두면 다음 어미가 또 샌다)."""
    src = inspect.getsource(chat._classify)
    q_line = next(ln for ln in src.splitlines() if '"kind": "question"' in ln or "_indirect_question(t)" in ln)
    assert "_plain_interrogative(t)" in q_line and "_indirect_question(t)" in q_line
    assert src.index("_plain_interrogative(t)") < src.index("et = _event_type(t)")      # 사건 · 관찰 갈래보다 앞


def test_a_question_about_water_gets_a_judgement_not_a_diary_draft():
    m, r = chat.send(SID, "물 줘야 하나", today=T, now=NOW)
    assert m["drafts"][0]["kind"] == "question" and "본 것으로 적었습니다" not in r["text"]
    assert chat.topic_of("물 줘야 하나") == "drought_alert"
    # 재배 달력 없는 작목(대파)도 물음은 물음이다 — 답은 누가 · 어디서를 말하는 판단 불가(지식)
    sid2 = subjects.add("대파", "2026 가을", status="재배 중", parcel="p001", anchor="2026-10-01")["id"]
    m2, r2 = chat.send(sid2, "병충해 뭐 봐야 하나", today=T, now=NOW)
    assert m2["drafts"][0]["kind"] == "question" and "본 것으로 적었습니다" not in r2["text"]
    assert "재배 달력이 서면 판정이 열린다" in r2["text"] and "발행자 — 이 작목·작기의 재배 달력 만들기" in r2["text"]
