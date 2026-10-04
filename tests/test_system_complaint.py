# -*- coding: utf-8 -*-
# [문장 형태 2026-10-04 · 발행자 "「왜 …는가」 → 항의" · 10-04 "되묻기 불평 → 교정 요구"] 시스템을 향한 항의가 교정 어휘(틀렸 · 고쳐 · 되묻 · 왜 또 …) 없이 오면 물음이나 본 것으로
# 떨어졌다 — 실측 22문장 중 10. 두 꼴: ① 「왜」 + 묻는 동사(묻 · 물어 · 질문 · 반복) ② 시스템 명사(답 · 화면 · 알림 · 경보 · 판정 · 제안 · 카드) + 불평 서술(이상 · 말이 안 · 엉뚱 · 안 뜬 · 깨진 · 늦).
# 경계: 밭을 향한 왜(잎이 왜 노랗나요)는 묻는 동사가 없어 물음 그대로 · '이상' 홀로는 본 것(2026-09-19 결정 그대로) · 일지 · 기록은 농가 자기 것이라 명사 목록 밖.
from __future__ import annotations

import inspect
from datetime import date

import pytest

from ingest import chat

T = date(2026, 10, 4)


@pytest.mark.parametrize("text", [
    "왜 자꾸 같은 걸 묻지", "왜 계속 묻나", "같은 질문을 왜 반복하나", "방금 답했는데 왜 또 묻나요", "왜 되묻는가",
    "답이 이상한데", "답이 이상해요", "답이 말이 안 된다", "답이 왜 이래", "이 답은 아닌 것 같다", "엉뚱한 답이다", "물어본 거랑 다른 답이다",
    "화면이 안 뜬다", "경보가 이상하다", "알림이 늦다", "카드가 안 보여요",
])
def test_a_complaint_aimed_at_the_system_is_a_correction_request(text):
    assert chat._system_complaint(text) or any(w in text for w in chat.REQ_WORDS)
    assert chat.classify(text, T)[0]["kind"] == "feedback.request", text


@pytest.mark.parametrize("text, kind", [
    ("잎이 왜 노랗나요", "question"), ("왜 안 자라나", "question"), ("왜 시들지", "question"), ("싹이 왜 안 나오나", "question"), ("비가 왜 안 오나", "question"),   # 밭을 향한 왜
    ("잎이 이상해요", "observation.note"), ("잎이 이상한데", "observation.note"), ("비료 상태가 안 좋다", "observation.note"),                                 # 시스템 명사 없는 이상
    ("일지에 적힌 대로 잎이 이상하다", "observation.note"),                                                                                                       # 일지 는 농가 것
    ("글자가 깨진다", "observation.note"),                                                                                                                      # 시스템 명사가 없으면 안 건다(닫힌 목록)
    ("오늘 물 줬다", "event"),
])
def test_the_other_side_is_left_alone(text, kind):
    assert not chat._system_complaint(text), text
    assert chat.classify(text, T)[0]["kind"] == kind, text


def test_the_rule_is_wired_before_the_question_branch_and_keeps_the_farm_work_exclusion():
    src = inspect.getsource(chat._classify)
    req_line = next(ln for ln in src.splitlines() if "_system_complaint(t)" in ln)
    assert "REQ_WORDS" in req_line and "_farm_work_not_a_request(t)" in req_line                       # 같은 한 줄 — 밭일 서술 제외도 그대로 받는다
    assert src.index("_system_complaint(t)") < src.index('"kind": "question"')                         # 항의가 물음보다 먼저
    assert "일지" not in chat._SYS_NOUNS and "기록" not in chat._SYS_NOUNS and "이상" not in chat.REQ_WORDS
