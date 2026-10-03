# -*- coding: utf-8 -*-
# [발행자 실사용 2026-10-04] *"고르신 종류(처음 제안과 다릅니다) · obs_… 이미 있는데 왜 되묻는가?"* — 둘이 틀렸다.
#   ① 종류를 고른 뒤에도 처음 답("… 본 것으로 적었습니다 · 아니면 아래에서 다르게 고르시면 됩니다")이 그대로 보여 **되묻는 것**으로 읽혔다 — "고르는 동작이
#      아무것도 안 바꾸는 것처럼 보이면 사람이 고르기를 멈춘다"(발행자 — 셋 중 가장 급하다). 기록은 고쳐 쓰지 않고 화면이 그 자리에 선택 확인을 낸다.
#   ② 그 항의 자체가 또 관찰로 분류됐다 — 「왜 … 는가」 꼴의 시스템 항의가 교정 어휘에 없었다.
from __future__ import annotations

import html as _html
from datetime import date, datetime, timezone

from frontend import chat_pages
from ingest import chat, media

SID = "p001-jjokpa-2026f"
T = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
COMPLAINT = "고르신 종류(처음 제안과 다릅니다) · obs_93e9b4b67856 이미 있는데 왜 되묻는가?"


def _s():
    return next(s for s in media.load_subjects() if s["id"] == SID)


def _visible(page: str) -> str:
    import re
    return _html.unescape(re.sub(r"<[^>]*>", " ", page))


def test_after_choosing_a_kind_the_thread_shows_the_choice_not_the_first_guidance():
    m, r = chat.send(SID, "어제 그거 있잖아", today=T, now=NOW)
    assert m["drafts"][0]["kind"] == "observation.note" and chat.PLAIN_BY_KEY["statement"] in r["text"]
    before = _visible(chat_pages.thread_main(_s(), T))
    assert chat.PLAIN_BY_KEY["statement"] in before                                      # 고르기 전 — 처음 안내가 보인다(맞다)
    chat.choose_kind(m["id"], "event", today=T)
    page = chat_pages.thread_main(_s(), T)
    seen = _visible(page)
    assert chat.PLAIN_BY_KEY["statement"] not in seen                                   # 고른 뒤 — 처음 안내는 화면에서 사라진다
    assert "종류를 고르셨습니다 — 한 일. 처음 제안은 지웠습니다." in seen and chat.CONFIRM_LABEL in seen
    assert "고르신 종류입니다 — 처음 제안은 지웠습니다" in seen                             # 초안 카드도 선택 확인
    assert _html.escape(r["text"]) in page                                               # 원문 기록은 title 에 남는다(보낸 때의 기록 — 고쳐 쓰지 않는다)
    stored = next(x for x in chat.list_messages(SID) if x["id"] == r["id"])
    assert stored["text"] == r["text"]                                                   # 원장은 그대로(append-only)
    chat.confirm(m["id"], 0, day="2026-10-03", event_type="관수", now=NOW)
    seen2 = _visible(chat_pages.thread_main(_s(), T))
    assert "고르신 종류(한 일)로 넣었습니다 — 처음 제안은 지웠습니다." in seen2 and chat.PLAIN_BY_KEY["statement"] not in seen2


def test_a_message_whose_kind_was_not_chosen_keeps_its_reply():
    m, r = chat.send(SID, "오늘 물 줬다", today=T, now=NOW)
    assert chat_pages.chosen_reply(m) is None and chat_pages.chosen_reply(None) is None
    assert r["text"] in _visible(chat_pages.thread_main(_s(), T))


def test_the_complaint_is_a_fix_request_and_a_field_question_with_why_stays_a_question():
    m, r = chat.send(SID, COMPLAINT, today=T, now=NOW)
    assert m["drafts"][0]["kind"] == "feedback.request" and chat.PLAIN_BY_KEY["statement"] not in r["text"]
    for t in ("왜 또 묻나요", "이미 있는데 왜 다시 묻습니까", "같은 걸 되묻네요"):
        assert chat.classify(t, T)[0]["kind"] == "feedback.request", t
    for t in ("잎이 왜 노랗나요", "왜 비가 안 오지", "물을 왜 줘야 하나"):
        assert chat.classify(t, T)[0]["kind"] == "question", t                            # 밭을 향한 「왜」 는 물음 그대로
