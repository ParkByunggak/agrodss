# -*- coding: utf-8 -*-
# [U-40 · 발행자 실사용 2026-10-03] "이전에 관수를 일지에서 날짜별로 알려줘요" → 가뭄 판정이 나갔다. *"답이 틀렸습니다. 둘이 겹쳤습니다. 라우팅 … 조회입니다 …
# 동사가 아니라 명사로 라우팅하고 있습니다. '관수'가 보이면 가뭄 … 조회는 '알려줘 · 보여줘 · 언제 … 했나' 같은 동사와 시제로 가야 합니다."*
#
#   조회 = 판단이 아니라 기록 그대로(사실 인용 축) · 판정 어휘보다 **앞**에 선다(순서가 처방) · 사건 종류로 원장을 걸러 최근 먼저 · 없으면 없다고 ·
#   아직 일지에 넣지 않은 것이 있으면 그것도 말한다. 둘째 관찰 — 오늘 관수가 가뭄 답에 안 반영: 초안 미확인인지 배선인지 — 가뭄 답이 「넣지 않은 관수 기록 N건」 을
#   말하면 그 갈림이 화면에서 보인다. 거부와 통과를 둘 다 본다: 판단을 묻는 관수 물음은 그대로 가뭄 판정 · 한 일은 사건 그대로.
from __future__ import annotations

from datetime import date, datetime, timezone

from frontend import words
from ingest import asks, chat, media

SID = "p001-jjokpa-2026f"
T = date(2026, 10, 3)
NOW = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)
Q = "이전에 관수를 일지에서 날짜별로 알려줘요"


def _s():
    return media.load_subjects()[0]


def test_lookup_questions_route_to_the_lookup_not_to_a_judgment():
    for q in (Q, "관수 언제 했나", "방제 기록 보여줘", "일지에서 관수 날짜 알려줘", "뭐 했는지 일지 보여줘"):
        assert chat.classify(q, T)[0]["kind"] == "question" and chat.topic_of(q) == chat.LOOKUP_ID, q
    assert chat.lookup_of(Q) == "관수" and chat.lookup_of("방제 기록 보여줘") == "방제" and chat.lookup_of("뭐 했는지 일지 보여줘") == "전체"
    # 반대편 — 판단을 묻는 것과 한 일은 그대로
    assert chat.topic_of("가뭄이 심한데 물 줘야 하나요") == "drought_alert" and chat.lookup_of("가뭄이 심한데 물 줘야 하나요") is None
    assert chat.classify("관수했다", T)[0]["kind"] == "event" and chat.lookup_of("관수했다") is None
    assert chat.lookup_of("잎이 노랗게 보여") is None                                     # '보여' 홀로는 관찰


def test_the_lookup_answers_with_the_records_newest_first_and_says_it_is_not_a_judgment():
    s = _s()
    cite = words.said("사실 인용")
    assert chat.answer(s, Q, T) == f"[{cite}] 일지에 관수 기록이 없습니다. 판단이 아니라 기록을 그대로 찾은 것입니다."
    for text in ("9월 20일에 관수했다", "9월 25일에 관수했다", "9월 22일에 방제했다"):
        m, _ = chat.send(SID, text, today=T, now=NOW)
        chat.confirm(m["id"], 0, now=NOW)
    a, asked = chat.answer_with_asks(s, Q, T)
    assert asked == [] and a.startswith(f"[{cite}] 일지의 관수 기록 2건 — 최근 먼저\n2026-09-25 관수") and "\n2026-09-20 관수" in a
    assert "방제" not in a                                                              # 종류로 거른다 — 관수 물음에 방제가 섞이지 않는다
    assert "방제 기록 1건" in chat.answer(s, "방제 기록 보여줘", T)
    assert a.rstrip().endswith("판단이 아니라 기록을 그대로 찾은 것입니다.") and "무강수" not in a       # 가뭄 판정 문면이 아니다
    whole = chat.answer(s, "뭐 했는지 일지 보여줘", T)
    assert "한 일 기록 3건" in whole


def test_unconfirmed_irrigation_is_named_in_both_the_lookup_and_the_drought_answer():
    s = _s()
    m, _ = chat.send(SID, "9월 25일에 관수했다", today=T, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)
    chat.send(SID, "오늘 물 줬다", today=T, now=NOW)                                   # 초안만 — 넣기를 안 눌렀다(발행자 관찰의 갈림 ①)
    assert [d["type"] for d in chat.unconfirmed_of(SID, "관수")] == ["관수"]
    lk = chat.answer(s, Q, T)
    assert "아직 일지에 넣지 않은 관수 기록 1건" in lk and chat.CONFIRM_LABEL in lk
    dr = chat.answer(s, "가뭄이 심한데 물 줘야 하나요", T)
    assert dr.startswith(f"[{words.said('판단함')}]") and "마지막 비·관수 2026-09-25" in dr and "아직 일지에 넣지 않은 관수 기록 1건" in dr
    # 넣으면 두 줄 다 사라지고 판단이 읽는다(갈림이 배선이 아니라 초안이었다는 것을 화면이 말한다)
    m2 = next(x for x in chat.list_messages(SID) if x["text"] == "오늘 물 줬다")
    chat.confirm(m2["id"], 0, now=NOW)
    assert "넣지 않은" not in chat.answer(s, Q, T) and "2026-10-03 관수" in chat.answer(s, Q, T)
    dr2 = chat.answer(s, "가뭄이 심한데 물 줘야 하나요", T)
    assert "넣지 않은" not in dr2 and "2026-10-03(관수)" in dr2


def test_a_lookup_through_answer_writes_nothing_and_through_send_is_a_citation():
    s = _s()
    chat.answer(s, Q, T)
    assert not asks.path().exists()                                                       # 저장 없는 길 — 조회도 아무것도 안 쓴다
    _, r = chat.send(SID, Q, today=T, now=NOW)
    assert r["text"].startswith(f"[{words.said('사실 인용')}] 일지에 관수 기록이 없습니다")       # 저장 길 — 답 끝에 질문 하나가 붙는 것은 §3 그대로
