# -*- coding: utf-8 -*-
# [2026-10-04 실측 · WO-ASK-01 §9 의 지점 판] 시스템이 물은 것에 농가가 **한 낱말로 답하면** 그 답이 물음에 묶여야 한다("답했는데 아무것도 안 바뀌면 더 안 쓴다" — §12).
#   실측: 인증을 물은 뒤 「무농약」 「유기」 「관행」 → 본 것(§9 묶기는 필지 값만 알았다) · 배수를 물은 뒤 「배수는 좋아요」 「물 잘 빠져요」 → 본 것(등록부 글자 「좋음」 만 묶였다 —
#   일지 읽기(known.value_in)는 그 말을 좋음으로 읽는데 답 묶기는 다른 사본을 썼다 — 어휘 두 벌).
#   처방: `_drafts_from_answer` 한 자리 — 필지 값은 known.value_in · 농사 값(인증)은 CERT_WORDS · 둘 이상/없음은 안 짓는다(「인증은 없어요」 를 관행으로 읽지 않는다) ·
#   일지 말로 읽은 값은 **짧은 답**일 때만(발행자 10-03 일지 줄은 본 것으로 남는다 — 일지에 들어가고 카드는 known 이 올린다).
#   검사의 주의: 농가 말 한 마디마다 답이 다음 물음을 하나 더 세므로(상한 3) 같은 물음을 두 번 넘게 돌리지 않는다 — 단위는 함수로, 끝에서 끝까지는 한 번.
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone

from ingest import asks, chat, parcels, subjects

T = date(2026, 10, 4)
T28 = date(2026, 9, 28)
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
SID = "p001-jjokpa-2026f"
CERT_PEND = {"axes": ["cert"], "fields": []}
DRAIN_PEND = {"axes": ["soil_water"], "fields": ["drainage"]}
DIARY_LINE = "밭에 나가 확인하니 고랑 물 빠짐이 잘 되고 있고, 잎 끝 황화 현상은 더 진행이 되지 않음이 확인이 되었다."


def _daepa():
    return subjects.by_id(subjects.add("대파", "2026 가을", status="재배 중", parcel="p001", anchor="2026-10-01")["id"])


def test_cert_answers_bind_to_the_cert_question_and_nothing_is_invented():
    s = _daepa()
    for ans, want in (("무농약", "무농약"), ("무농약이요", "무농약"), ("유기", "유기"), ("관행이에요", "관행"), ("유기 인증 받았어요", "유기")):
        out = chat._drafts_from_answer(s, ans, CERT_PEND)
        assert [(d["kind"], d["field"], d["value"], d["why_key"]) for d in out] == [("subject.field", "cert", want, "answers_ask_subject")], ans
    for ans in ("인증은 없어요", "유기인지 무농약인지 모르겠다", "아직 안 정했어요"):
        assert chat._drafts_from_answer(s, ans, CERT_PEND) == [], ans                                      # 없음 · 둘 — 지어내지 않는다(「없어요」 를 관행으로 안 읽는다)
    assert chat._drafts_from_answer(s, "무농약", {"axes": ["forecast"], "fields": []}) == []                 # 인증을 묻지 않았으면 안 묶는다


def test_end_to_end_the_cert_answer_is_the_first_draft_speaks_of_the_crop_not_the_parcel_and_confirming_sets_it():
    s = _daepa()
    m0, r0 = chat.send(s["id"], "오늘 물 줬다", today=T, now=NOW)
    assert "인증 유형" in r0["text"] and asks.pending(s["id"])["axes"] == ["cert"]
    m, r = chat.send(s["id"], "무농약이요", today=T, now=NOW)
    d = m["drafts"][0]
    assert d["kind"] == "subject.field" and d["field"] == "cert" and d["value"] == "무농약"
    assert "이 농사의 정보" in r["text"] and "밭 정보에 들어가" not in r["text"]                           # 농사 값 — 밭 정보가 아니다
    assert not any(x.get("kind") == "observation.note" and x.get("why_key") == "statement" for x in m["drafts"])   # 답 한 토막이 본 것으로도 서지 않는다
    chat.confirm(m["id"], 0, now=NOW)
    assert subjects.by_id(s["id"])["cert"] == "무농약"
    m2, r2 = chat.send(s["id"], "오늘 물 줬다", today=T, now=NOW)
    assert "인증 유형" not in r2["text"]                                                                       # 더 묻지 않는다


def test_drainage_answers_are_read_with_the_diary_words_but_a_long_diary_line_stays_an_observation():
    s = parcels.enrich_subject(subjects.by_id(SID), parcels.by_id("p001"))
    for ans, want in (("배수는 좋아요", "좋음"), ("물 잘 빠져요", "좋음"), ("좋음", "좋음"), ("고랑에 물이 고여요", "나쁨"), ("보통이에요", "보통"), ("배수 나쁨", "나쁨")):
        out = chat._drafts_from_answer(s, ans, DRAIN_PEND)
        assert [(d["kind"], d["field"], d["value"]) for d in out] == [("parcel.field", "drainage", want)], ans
    assert chat._drafts_from_answer(s, "좋기도 하고 나쁘기도 해요", DRAIN_PEND) == []                        # 둘 걸림
    assert chat._drafts_from_answer(s, DIARY_LINE, DRAIN_PEND) == []                                       # 긴 일지 줄 — 본 것으로 남는다(known 이 일지에서 카드를 올린다)
    assert chat._drafts_from_answer(s, "배수 좋음. 그리고 잎 끝이 노랗고, 벌레가 보인다", DRAIN_PEND)[0]["value"] == "좋음"   # 등록부 말 그대로가 있으면 길어도 묶는다(§9 원 규칙)


def test_end_to_end_a_colloquial_drainage_answer_becomes_the_parcel_card():
    m0, r0 = chat.send(SID, "오늘 트랩 봤다", today=T28, now=NOW)
    assert "배수(좋음" in r0["text"] and asks.pending(SID)["fields"] == ["drainage"]
    m, r = chat.send(SID, "물 잘 빠져요", today=T28, now=NOW)
    d = m["drafts"][0]
    assert d["kind"] == "parcel.field" and d["field"] == "drainage" and d["value"] == "좋음" and "밭 정보에 들어가" in r["text"]


def test_without_a_pending_question_a_bare_word_is_not_bound():
    s = _daepa()
    m, _ = chat.send(s["id"], "무농약", today=T, now=NOW)
    assert not any(x.get("kind") == "subject.field" for x in m["drafts"])                                   # 물은 적이 없으면 선언 어휘(인증 …)가 있어야 한다


def test_the_binding_is_one_place_and_reads_values_with_the_diary_canon():
    src = inspect.getsource(chat._drafts_from_answer)
    assert "known.value_in(f, text)" in src and "subjects.CERT_WORDS" in src and "known.SUBJECT_AXES" in src and "_short_answer(text)" in src
    assert "_drafts_from_answer(s, text, pend, today)" in inspect.getsource(chat.send)
    assert "answers_ask_subject" in chat.PLAIN_BY_KEY
    assert not chat._short_answer(DIARY_LINE) and chat._short_answer("배수는 좋아요")
