# -*- coding: utf-8 -*-
# [문장 형태 2026-10-04 · 발행자 "분류가 명사를 보고 사람의 말은 동사와 어미가 뜻을 정한다"] 한 일 쪽의 두 빈칸 — 발행자가 세운 한 일 규칙(작업 어휘 + 한 일의 표지)은 그대로인데
# ① 목적어와 동사 사이에 부사·수량 말이 끼면 두 낱말 짝이 깨졌다(「물 한 번 줬네」 → 본 것 · 「풀 좀 뽑았다」 → 수확) ② 일지 투의 명사형 끝(풀 뽑음 · 물 줌 · 약 침)은 표지로 안 셌다.
# 처방은 두 자리 — `_fold_adverbs`(사건 어휘를 보는 한 자리 `_event_type` 안) · `_CLIPPED_DONE`(사건 갈래의 `_done_evidence` 안 · 계획 가름 `_past_ending` 에는 안 넣는다 — 「내일 물 줌」 은 계획).
from __future__ import annotations

import inspect
from datetime import date

import pytest

from ingest import chat

T = date(2026, 10, 4)


@pytest.mark.parametrize("text, et", [
    ("물 한 번 줬네", "관수"), ("물을 좀 줬다", "관수"), ("물 많이 줬다", "관수"), ("물 충분히 줬어요", "관수"), ("약 조금 쳤다", "방제"), ("약을 한 번 쳤다", "방제"),
    ("풀 좀 뽑았다", "제초"), ("풀 좀 더 뽑았다", "제초"), ("웃거름 조금 줬다", "시비"), ("트랩 다시 확인했다", "예찰"),
])
def test_an_adverb_between_object_and_verb_does_not_break_the_work_word(text, et):
    assert chat._event_type(text) == et
    d = chat.classify(text, T)[0]
    assert d["kind"] == "event" and d["type"] == et, d


@pytest.mark.parametrize("text, et", [("풀 뽑음", "제초"), ("물 줌", "관수"), ("약 침", "방제"), ("웃거름 줌", "시비"), ("종구를 심음", "파종"), ("트랩 확인함", "예찰")])
def test_a_diary_style_nominal_ending_on_a_work_word_is_a_done_thing(text, et):
    d = chat.classify(text, T)[0]
    assert d["kind"] == "event" and d["type"] == et, d


@pytest.mark.parametrize("text, kind", [
    ("내일 물 줌", "plan.farmer"), ("모레 약 침", "plan.farmer"),                     # 앞날 표지가 이긴다 — 명사형 끝은 계획 가름에 안 든다
    ("잎이 노람", "observation.note"), ("싹이 올라옴", "observation.note"), ("물 주기", "observation.note"), ("관수 시설 점검", "observation.note"),   # 작업 어휘 없음 · -기 · 명사 끝
    ("다시 심었다", "event"),                                                           # '다시' 는 보식 어휘의 일부 — 걷지 않는다(낱말 단위 · 닫힌 목록 밖 · 종류 순서는 기존 그대로)
])
def test_the_other_side_is_left_alone(text, kind):
    d = chat.classify(text, T)[0]
    assert d["kind"] == kind, d


def test_folding_is_word_level_and_in_the_one_place_every_branch_uses():
    assert chat._fold_adverbs("물 한 번 줬네") == "물 줬네" and chat._fold_adverbs("풀 좀 더 뽑았다") == "풀 뽑았다"
    assert chat._fold_adverbs("다시 심었다") == "다시 심었다" and chat._fold_adverbs("좀비") == "좀비"       # 낱말 단위 — 글자가 섞인 말은 안 걷는다
    src = inspect.getsource(chat._event_type)
    assert "_fold_adverbs(text)" in src                                                                   # 사건 어휘를 보는 한 자리
    assert "_CLIPPED_DONE.search" in inspect.getsource(chat._done_evidence) and "_CLIPPED_DONE" not in inspect.getsource(chat._past_ending)
