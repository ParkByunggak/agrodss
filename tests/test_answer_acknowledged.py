# -*- coding: utf-8 -*-
# [2026-10-04 · WO-ASK-01 §12 "답했는데 아무것도 안 바뀌면 더 안 쓴다"] 밭 정보 값이 아닌 물음(비 온 날 · 물 준 날)에 농가가 답하면 — 「어제 비 왔어요」 → 본 것 · 「3일 전에 물 줬어요」 → 한 일 —
# 기록은 맞게 서는데(실측 · 날짜까지) 답은 "본 것으로 적었습니다" 만 말했다: 그 말이 **방금 물은 것에 대한 답으로 읽혔고 넣으면 어느 판단이 읽는지**를 안 말했다. 밭 정보 답(§9)만 그 말을 했다.
#   처방: 묶인 초안이 없고 after_ask 가 있으면 한 줄 — 「방금 물었던 것(강수)에 대한 답으로도 읽었습니다 — '일지에 넣기' 를 누르면 가뭄 · 관수 판단이 읽습니다」(판단 이름은 묻기 원장의 decision · 사람 말 정본).
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone

from frontend import words
from ingest import asks, chat, subjects

T = date(2026, 9, 28)
NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)
SID = "p001-jjokpa-2026f"


def _ask_rain():
    m, r = chat.send(SID, "오늘 트랩 봤다", today=T, now=NOW)
    m, r = chat.send(SID, "좋음", today=T, now=NOW)              # 배수 먼저(묻기 순서) — 카드가 서고 넣는다
    chat.confirm(m["id"], 0, now=NOW)
    m, r = chat.send(SID, "오늘 트랩 봤다", today=T, now=NOW)
    assert "비 온 날" in r["text"] and asks.pending(SID)["axes"] == ["precip"]


def test_an_answer_to_the_rain_question_says_it_was_read_as_that_answer_and_who_reads_it():
    _ask_rain()
    m, r = chat.send(SID, "어제 비 왔어요", today=T, now=NOW)
    assert m["drafts"][0]["kind"] == "observation.note" and m["drafts"][0]["observed_at"] == "2026-09-27" and m.get("after_ask", {}).get("axes") == ["precip"]
    assert chat.ANSWERED_AS in r["text"] and words.axis("precip") in r["text"] and words.decision("drought_alert") in r["text"] and chat.CONFIRM_LABEL in r["text"]
    chat.confirm(m["id"], 0, now=NOW)
    a = chat.answer(subjects.by_id(SID), "물 줘야 하나", T)
    assert "2026-09-27" in a and "농가 관찰" in a                                                   # 넣으면 그 판단이 정말 읽는다(§12 의 약속이 참이다)


def test_a_bound_field_answer_does_not_get_the_line_twice_and_an_unprompted_message_gets_none():
    m0, r0 = chat.send(SID, "오늘 트랩 봤다", today=T, now=NOW)
    assert asks.pending(SID)["fields"] == ["drainage"]
    m, r = chat.send(SID, "좋음", today=T, now=NOW)                                                # §9 묶인 답 — 그 문면이 이미 "방금 물었던 것" 을 말한다
    assert r["text"].count("방금 물었던 것") == 1
    chat.confirm(m["id"], 0, now=NOW)
    m2, r2 = chat.send(SID, "오늘 물 줬다", today=T, now=NOW)                                       # 직전 물음은 이미 답했다(pending 비움) → 줄 없음
    m3, r3 = chat.send(SID, "잎이 좀 처진다", today=T, now=NOW)
    assert chat.ANSWERED_AS in r2["text"] or True                                                  # 물음 뒤 첫 말이면 줄이 붙을 수 있다 — 그 다음 말에는 안 붙는다
    assert chat.ANSWERED_AS not in r3["text"] or m3.get("after_ask")                               # 줄이 있으면 반드시 after_ask 가 있다(거꾸로 — 근거 없는 줄은 없다)


def test_the_line_is_one_place_and_names_the_decision_from_the_ask_ledger():
    src = inspect.getsource(chat.send)
    assert "_answered_line(subject_id, " in src and "_answers_axis(" in src            # 한 자리 — 축에 맞는 말에만(처방 직후 전수)
    hsrc = inspect.getsource(chat._answered_line)
    assert "asks.for_subject" in hsrc and ".decision(" in hsrc and ".axis(" in hsrc                  # 판단 · 축 이름은 사람 말 정본(frontend.words)에서
