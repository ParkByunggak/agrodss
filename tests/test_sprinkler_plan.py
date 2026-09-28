# -*- coding: utf-8 -*-
# [발행자 실사용 2026-09-29 06:18 · 화면 9903974] "오전에 스프링쿨러 가동 1시간한다" → 시스템은 "한 일이나 할 일을 가리키는 말이 없어 본 것으로 적었습니다",
# 발행자는 손으로 '할 일' 로 바꿔 넣었다(카드 「일지에 넣었습니다 할 일 · pln_…」 과 위 답변이 어긋나 보였다). 셋을 고친다:
#   ① 장치 + 돌리는 말(스프링쿨러 가동 · 돌 · 틀)은 관수 — 장치 이름 홀로는 여전히 아니다(2026-09-21 규율)
#   ② 문장 끝 현재·앞날 서술("…한다")은 할 일 — '오늘' 만 보고 사건으로 읽던 "오늘 급수 1시간 한다" 도
#   ③ 손으로 고른 '할 일' 의 task 가 원문 60자였다 → 작업 어휘(관수)로 · 카드가 "고르신 종류" 라고 말한다
from __future__ import annotations

from datetime import date

from frontend import chat_pages
from ingest import chat, media

TODAY = date(2026, 9, 29)


def _subject():
    return media.load_subjects()[0]


def test_device_plus_operating_verb_is_irrigation_but_the_device_alone_is_not():
    d = chat.classify("오전에 스프링쿨러 가동 1시간한다", TODAY, subject=_subject())[0]
    assert d["kind"] == "plan.farmer" and d["task"] == "관수" and d["planned_day"] == TODAY.isoformat()
    assert chat.classify("오전에 스프링클러 틀었다", TODAY)[0]["kind"] == "event" and chat.classify("오전에 스프링클러 틀었다", TODAY)[0]["type"] == "관수"
    assert chat.classify("스프링쿨러가 고장났다", TODAY)[0]["kind"] == "observation.note"          # 장치 이름 홀로는 관수가 아니다
    assert chat._event_type("급수 시설이 없다") == "관수" and chat.classify("급수 시설이 없다", TODAY)[0]["kind"] == "observation.note"   # 어휘는 있어도 표지가 없으면 관찰(09-21 그대로)


def test_a_sentence_ending_in_the_present_future_is_a_plan_not_an_event():
    assert chat.classify("오늘 급수 1시간 한다", TODAY)[0]["kind"] == "plan.farmer"                 # '오늘' 만 보고 사건으로 읽던 꼴
    assert chat.classify("오늘 물 줬다", TODAY)[0]["kind"] == "event"                                # 받침 ㅆ 한 일은 그대로
    assert chat.classify("오늘 급수 1시간 했다", TODAY)[0]["kind"] == "event"
    assert chat.classify("잎이 이상해요", TODAY)[0]["kind"] == "observation.note"                    # '해요' 는 안 걸린다
    assert chat.classify("잎이 마른다", TODAY)[0]["kind"] == "observation.note"                      # 작업 어휘 없는 'ㄴ다' 는 관찰
    assert chat.classify("잎이 노랗게 변한다", TODAY)[0]["kind"] == "observation.note"               # '…한다' 로 끝나도 작업 어휘가 없으면 관찰


def test_a_weather_word_with_no_predicate_is_a_question_even_with_a_typo_or_a_particle():
    """[발행자 2026-09-29 아침] 같은 뜻의 다섯 물음이 둘은 본 것, 셋은 날씨였다 — "오늘 날씨 어떄"(오타) · "오늘 날씨는"(조사) 이 서술로 읽혔다."""
    for q in ("오늘 날씨 어떄", "오늘 날씨는", "오늘 날씨", "내일 기온은", "비 올 확률은", "이번 주 예보", "날씨", "오늘 날씨 어때", "오늘 날씨는?"):
        d = chat.classify(q, TODAY)[0]
        assert d["kind"] == "question" and chat.topic_of(q) == "forecast_citation", (q, d)
    assert chat.classify("오늘 날씨가 좋다", TODAY)[0]["kind"] == "observation.note"                 # 서술어가 있으면 본 것
    assert chat.classify("날씨 때문에 웃거름을 못 줬다", TODAY)[0]["kind"] != "question"              # 날씨 낱말이 있어도 끝이 아니면 물음이 아니다
    assert chat.classify("트랩 확인은", TODAY)[0]["kind"] != "question"                               # 날씨 낱말이 아니면 조사 끝이라도 물음이 아니다


def test_the_publishers_four_corrections_from_the_first_misclassification_count_now_classify_as_they_chose():
    """[WO-LLM-01 첫 측정 2026-09-29 08:21 KST · 발행자 PC] 농가 발화 70 · 고침 4 · 문턱 30 미달 — 그 자체가 결과(§5-2). 넷은 전부 어휘·규칙 구멍이었다."""
    assert chat.classify("오늘 상황은 줄기가 매우 왕성한 모습이다", TODAY)[0]["kind"] == "observation.note"     # 옛 '분류 안 됨' 은 이미 없다
    d = chat.classify("가을 가뭄이 심하다.\n아침에 포장을 보니 특별한 징후는 없다", TODAY)[0]
    assert d["kind"] == "event" and d["type"] == "예찰" and d["observed_at"] == TODAY.isoformat()             # 포장을 본 것 = 예찰 · '아침에' = 오늘
    d = chat.classify("오늘 물주었다", TODAY)[0]
    assert d["kind"] == "event" and d["type"] == "관수"                                                       # 띄어쓰기 없는 '물주었'
    assert chat.classify("오전에 스프링쿨러 가동 1시간한다", TODAY)[0]["kind"] == "plan.farmer"
    assert chat.classify("포장 정리는 아직", TODAY)[0]["kind"] == "observation.note"                           # '포장' 홀로는 예찰이 아니다
    d = chat.classify("내일 웃거름 준다", TODAY)[0]
    assert d["kind"] == "plan.farmer" and d["task"] == "시비" and d["planned_day"] == "2026-09-30"


def test_a_future_date_never_makes_a_done_event():
    """처방 직후 전수 — '내일 파종' 이 내일 날짜의 한 일이었다(날짜 표지 = 한 일 표지 규칙의 구멍). 오늘보다 뒤면 앞날이다."""
    for t, task, day in (("내일 파종", "파종", "2026-09-30"), ("모레 방제", "방제", "2026-10-01"), ("내일 물 준다", "관수", "2026-09-30")):
        d = chat.classify(t, TODAY)[0]
        assert d["kind"] == "plan.farmer" and d["task"] == task and d["planned_day"] == day, (t, d)
    d = chat.classify("어제 오전에 물 줬다", TODAY)[0]
    assert d["kind"] == "event" and d["type"] == "관수" and d["observed_at"] == "2026-09-28"           # 과거는 그대로
    assert chat.classify("오늘 파종", TODAY)[0]["kind"] == "event"                                     # 오늘 + 명사는 09-20 규칙 그대로 한 일


def test_a_hand_chosen_plan_gets_the_task_word_and_the_card_says_it_was_chosen(monkeypatch):
    s = _subject()
    m, _ = chat.send(s["id"], "트랩 확인은 나중에", TODAY)                          # 어휘는 있는데(예찰) 표지가 없는 서술 → 관찰 제안
    assert m["drafts"][0]["kind"] == "observation.note", m["drafts"]
    m2 = chat.choose_kind(m["id"], "plan.farmer", TODAY)
    d = m2["drafts"][0]
    assert d["kind"] == "plan.farmer" and d["task"] == "예찰" and d["why"] == chat.CHOSEN_WHY   # 원문 60자가 아니라 작업 어휘
    rec = chat.confirm(m2["id"], 0, day=TODAY.isoformat())                              # '나중에' 는 날짜가 아니다 — 확인에서 날을 준다
    m3 = chat.get_message(m2["id"])
    html = chat_pages._draft_html(m3, 0, m3["drafts"][0])
    assert chat.SAVED_LABEL in html and "고르신 종류(처음 제안과 다릅니다)" in html and rec["id"] in html
    m4, _ = chat.send(s["id"], "오늘 물 줬다", TODAY)                                  # 시스템이 정한 초안은 그 표지가 없다
    chat.confirm(m4["id"], 0)
    m5 = chat.get_message(m4["id"])
    assert "고르신 종류" not in chat_pages._draft_html(m5, 0, m5["drafts"][0])
