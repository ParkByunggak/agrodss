# -*- coding: utf-8 -*-
# [문장 형태 점검 전수 2026-10-05] 발행자 지시("단문도 해석하지 못하는지 확인")로 세운 문장 목록 20줄을 재다 **내부 모순**이 나왔다 — 기대 종류를 붙이지 않고도 보이는 것이다:
#   「배수가 좋은가」 · 「가뭄인가」 · 「약을 쳐야 하는가」 는 물음인데 「관수가 필요한가」 · 「흙이 마른가」 · 「잎이 노란가」 는 **본 것**이었다. 같은 어미가 갈렸다.
#   원인: 종결 어미를 **어휘 조각 목록**(Q_WORDS)으로 세고 있었다 — 「-ㄴ가」 가 인가 · 는가 · 은가 셋만 들어 있어 같은 어미의 다른 꼴을 못 잡았다.
# 그 병의 두 번째 얼굴은 반대 방향이다 — 조각은 **포함** 검사라 문장 중간에 있어도 물음이 된다: 「오늘 할 일 다 했다」 · 「무슨 일이 있었다」 · 「언제인가 모르지만 물 줬다」.
# 처방은 한 자리씩 — ① 어미는 어미 규칙(`_plain_interrogative`)이 끝에서 본다(「-ㄴ가」 추가 · 조각 열넷 제거) ② 어휘 조각으로 서는 물음은 과거 서술로 끝나지 않을 때만.
# 이 검사가 고정하는 것은 **목록이 아니라 규칙**이다 — 어휘 목록을 비워도 어미 판정이 그대로 서는지를 본다(목록을 다시 늘리는 길로 돌아가면 깨진다).
from __future__ import annotations

import inspect
from datetime import date

import pytest

from ingest import chat

T = date(2026, 10, 5)

# 소스에 **이름이 없는** 꼴만 골랐다 — 목록에 적힌 것을 되읽으면 "목록이 전부인가" 를 못 묻는다(§7.5 "내가 세는 목록이 전부인가")
UNNAMED_QUESTIONS = [
    "관수가 필요한가", "흙이 마른가", "잎이 노란가", "물이 모자란가", "줄기가 가는가",        # -ㄴ가
    "지금 캘까", "약을 칠까", "비료를 줄까요",                                           # -ㄹ까
    "잎이 시드나", "벌레가 생기나", "지금 캡니까",                                        # -나 · -ㅂ니까
    "물을 줘야 맞는지", "지금 캐도 되는지",                                              # -는지
]


@pytest.mark.parametrize("text", UNNAMED_QUESTIONS)
def test_an_ending_the_source_never_names_is_still_a_question(text):
    assert chat._plain_interrogative(text) or chat._indirect_question(text), text
    assert chat.classify(text, T)[0]["kind"] == "question", text


@pytest.mark.parametrize("text", UNNAMED_QUESTIONS)
def test_the_ending_verdict_does_not_lean_on_the_word_list(monkeypatch, text):
    """어휘 목록을 **비워도** 어미 판정은 선다 — 그것이 "규칙으로 본다" 의 뜻이다(조각을 다시 늘리면 이 검사가 그대로 통과해 버리지 않는다)."""
    monkeypatch.setattr(chat, "Q_WORDS", ())
    assert chat.classify(text, T)[0]["kind"] == "question", text


def test_the_word_list_still_does_its_own_job(monkeypatch):
    """반대편 — 어휘(의문사 · 요청 동사)는 목록 몫이다. 목록을 비우면 이 물음들은 물음이 아니게 된다(둘의 역할이 섞여 있지 않다는 증거)."""
    lexical = ["이번 주 할 일 알려줘", "오늘 상태 어때", "약은 어디서 사나요"]
    for t in lexical:
        assert chat.classify(t, T)[0]["kind"] == "question", t
    monkeypatch.setattr(chat, "Q_WORDS", ())
    assert chat.classify("이번 주 할 일 알려줘", T)[0]["kind"] != "question"


@pytest.mark.parametrize("text", ["어제는 비가", "두 포기가", "노란 포기가 하나", "오늘 물 줬다", "배수가 좋다"])
def test_a_tail_that_only_looks_like_the_ending_is_left_alone(text):
    """「-ㄴ가」 규칙은 **받침 ㄴ + 가** 만 본다 — 조사 「가」 로 끝나는 말(비가 · 포기가)은 안 걸린다."""
    assert not chat._plain_interrogative(text), text
    assert chat.classify(text, T)[0]["kind"] != "question", text


@pytest.mark.parametrize("text", ["오늘 할 일 다 했다", "무슨 일이 있었다", "언제인가 모르지만 물 줬다", "어떻게 해야 할지 몰라서 그냥 관수했다",
                                  # [주입 D 가 드러낸 갈래 — 미검사였다] 현재 서술로 끝나는 말도 서술이다. 처음 판은 계획↔한 일 가름의 제외 목록(있 · 없)을 그대로 써서
                                  # 이 넷이 물음으로 남았고, 검사가 그 갈래를 한 번도 안 밟아 주입이 통과했다
                                  "오늘 할 일이 있다", "할 일이 없다", "무슨 일이 있다", "어디 갈 일이 없다"])
def test_a_piece_in_the_middle_does_not_turn_a_past_statement_into_a_question(text):
    """새는 쪽 — 한 일이 원장에 안 들어가고 답만 나가던 형태(빠진 쪽과 같은 급)."""
    assert chat._declarative_end(text), text
    assert chat.classify(text, T)[0]["kind"] != "question", text


@pytest.mark.parametrize("text", ["물 줬는지 알려줘", "언제 물 줬나", "관수 언제 했나", "뭘 해야 하는지 모르겠다", "언제 심을지 모르겠다", "할 일이 있나", "오늘 물 줬어?"])
def test_the_guard_never_touches_a_question_that_ends_like_a_question(text):
    """경계 — 끝을 보는 판정(물음표 · 어미 규칙)은 그 가드를 안 받는다. 「모르겠다」 는 의지·추측의 ㅆ 라 서술로 안 센다(도움을 청하는 말이다)."""
    assert chat.classify(text, T)[0]["kind"] == "question", text


def test_the_two_judgements_share_one_canon_for_the_tense_that_is_neither():
    """「겠」 은 과거도 서술도 아니다 — 두 판정이 **한 정본**을 쓴다(어휘 두 벌 금지). 있다·없다는 그쪽 물음에만 빠진다(여기서는 서술이다)."""
    assert set(chat._WILL_SSANG) <= set(chat._NOT_PAST_SSANG)
    assert "있" not in chat._WILL_SSANG and "있" in chat._NOT_PAST_SSANG


def test_the_two_jobs_are_wired_in_the_one_question_line():
    """배선 래칫 — 가드는 **어휘 경로에만** 붙는다(어미 규칙에 붙으면 「언제 물 줬나」 가 죽는다) · 과거 판정 어휘는 정본 하나를 쓴다."""
    src = inspect.getsource(chat._classify)
    line = next(ln for ln in src.splitlines() if '"kind": "question"' in ln or "_indirect_question(t)" in ln)
    assert "_declarative_end(t)" in line and "Q_WORDS" in line
    assert "_WILL_SSANG" in inspect.getsource(chat._declarative_end)          # 공유 정본을 쓴다(§7.1 — 어휘 두 벌 금지)
