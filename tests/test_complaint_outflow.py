# -*- coding: utf-8 -*-
# [처방 직후 전수 2026-10-04 — b1e7bcf(㉝) 의 나가는 쪽] 항의 갈래를 넓힌 뒤 **들어온 뒤**를 재니 셋:
#   ① 답이 「'일지에 넣기' 를 누르면 **영농일지에** 들어갑니다」 — 거짓이다. 확인은 `fb.add_request`(고쳐 달라는 말)로 간다.
#   ② 「왜 자꾸 같은 걸 묻지」 에 대한 답이 **또 물었다**(「하나 물을 것 — 농가 — 배수…」) — 항의를 그대로 되풀이한다(발행자 10-04 「이미 있는데 왜 되묻는가」 의 다음 층).
#   ③ 같은 형태 전수: 일지로 **안 가는** 종류가 셋(고쳐 달라는 말 · 밭 정보 값 · 농사 값)인데 단추는 셋 다 「일지에 넣기」 였다 — 문장과 단추가 서로 다른 자리를 가리켰다.
# 단추 말과 문장은 `chat.confirm_label(kind)` 한 자리에서 나온다 · 묻지 않는 예외는 §3 의 이 한 곳이고 다음 말에는 다시 묻는다.
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone

import pytest

from ingest import chat, feedback as fb
from schema import labels

T = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
SID = "p001-jjokpa-2026f"


def test_the_reply_to_a_complaint_names_the_place_it_actually_goes():
    m, r = chat.send(SID, "수확 창이 너무 넓어요 고쳐주세요", today=T, now=NOW)
    assert m["drafts"][0]["kind"] == "feedback.request"
    assert labels.label("/improve") in r["text"] and "영농일지가 아닙니다" in r["text"] and "고쳐 달라는 말로 넣기" in r["text"]
    assert "영농일지에 들어갑니다" not in r["text"]
    before = len(fb.list_records("feedback.request"))
    chat.confirm(m["id"], 0, now=NOW)
    reqs = fb.list_records("feedback.request")
    assert len(reqs) == before + 1 and reqs[-1]["text"] == "수확 창이 너무 넓어요 고쳐주세요"      # 정말 그 자리로 간다


@pytest.mark.parametrize("text", ["왜 자꾸 같은 걸 묻지", "왜 또 물어요", "이미 있는데 왜 되묻는가", "같은 질문을 왜 반복하나"])
def test_a_complaint_about_being_asked_is_not_answered_with_another_question(text):
    assert chat._complains_about_asking(text)
    m, r = chat.send(SID, text, today=T, now=NOW)
    assert m["drafts"][0]["kind"] == "feedback.request"
    assert "하나 물을 것" not in r["text"] and "이번 답에는 더 묻지 않습니다" in r["text"]
    m2, r2 = chat.send(SID, "오늘 트랩 봤다", today=T, now=NOW)                               # 다음 말에는 다시 묻는다(규칙을 끄는 것이 아니다)
    assert "하나 물을 것" in r2["text"]


@pytest.mark.parametrize("text", ["수확 창이 너무 넓어요 고쳐주세요", "경보가 너무 자주 와서 불편해요", "답이 이상한데"])
def test_other_complaints_still_get_their_one_question(text):
    assert not chat._complains_about_asking(text)
    m, r = chat.send(SID, text, today=T, now=NOW)
    assert m["drafts"][0]["kind"] == "feedback.request" and "하나 물을 것" in r["text"]


def test_the_button_says_the_place_too_and_both_come_from_one_canon():
    assert chat.confirm_label("event") == chat.CONFIRM_LABEL == "일지에 넣기"
    assert chat.confirm_label("feedback.request") == "고쳐 달라는 말로 넣기" and chat.confirm_label("parcel.field") == "밭 정보에 넣기"
    assert chat.confirm_label("subject.field") == "농사 정보에 넣기"
    from frontend import chat_pages
    assert "chat.confirm_label(k)" in inspect.getsource(chat_pages._draft_html)              # 단추도 같은 자리에서
    src = inspect.getsource(chat.send)
    assert "confirm_label(d['kind'])" in src and "_complains_about_asking(text)" in src
    assert "'{CONFIRM_LABEL}' 를 누르면 영농일지에 들어갑니다. 아니면" not in src              # 일지 문면을 종류 가림 없이 쓰던 자리는 없다
