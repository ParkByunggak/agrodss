# -*- coding: utf-8 -*-
# [2026-10-05 ⓐ — 앞 세 묶음이 등재해 둔 자리] 용도 선언의 표지(`parcels.USE_DECLARE_WORDS`)에 「것이다 · 것입니다 · 할 생각 · 하려고 한다」 가 섞여 있었다. 그 넷은
# **의지 어미와 같은 꼴**이라 「종구 캘 것입니다」(할 일)가 용도 선언으로 읽혔다 — 확인하면 **밭의 용도가 바뀐다**(재배 달력의 기준까지 갈린다). 가장 비싼 오분류 중 하나다.
# 그때는 가를 수 없었다: 작업 어휘로 가르려 했으나 그 어휘가 과거 꼴만 들고 있어 「캘」 을 몰랐다. 활용을 규칙으로 만든 뒤 **재료가 생겼다** —
#   작업 어휘가 있으면 할 일(종구 캘 것입니다 → 수확) · 없으면 선언(이번 작기는 팔 것이다 → 판매)이다.
# 가름을 **한 자리**(`parcels.use_declared`)에 두었다 — 부르는 자리가 둘(분류 · 묻기 전 원장 읽기)이고 어느 쪽도 제 판단을 따로 적지 않는다.
# 그리고 그 둘이 **같은 답**을 받아야 한다: 분류는 이미 잰 작업 어휘를 함께 넘기고, 원장 읽기는 기본값(여기서 잰다)을 쓴다.
from __future__ import annotations

from datetime import date

import pytest

from ingest import chat, known, parcels

T = date(2026, 10, 5)


@pytest.mark.parametrize("text,ty", [("종구 캘 것입니다", "수확"), ("종구 심을 것이다", "파종"), ("내일 종구 캘 생각", "수확")])
def test_an_intent_ending_with_a_work_word_is_a_plan_not_a_use_declaration(text, ty):
    assert parcels.use_declared(text) is None, text
    d = chat.classify(text, T)[0]
    assert d["kind"] == "plan.farmer" and d["task"] == ty, (text, d)


@pytest.mark.parametrize("text,use", [("이번 작기는 팔 것이다", "판매"), ("판매할 것이다", "판매"), ("올해는 자가 소비할 것이다", "자가")])
def test_the_same_ending_without_a_work_word_is_still_a_declaration(text, use):
    """반대편 — 가를 때 선언을 같이 버리면 농가가 용도를 말할 길이 사라진다(막는 것을 검사하면 통과하는 것도 검사한다)."""
    assert parcels.use_declared(text) == use, text
    assert chat.classify(text, T)[0]["kind"] == "parcel.field", text


@pytest.mark.parametrize("text,use", [("종구용이다", "종구 생산"), ("자가 소비용이다", "자가"), ("이 쪽파는 종구생산을 위한 목적이다", "종구 생산"),
                                      ("이 밭은 몰 납품용으로 쓴다", "몰 납품")])
def test_a_real_declaration_marker_never_needs_the_work_word_test(text, use):
    """「용도 · 목적 · 위한 · 용이다 · 용으로」 는 의지 어미와 겹치지 않는다 — 작업 어휘가 있어도 선언이다(두 목록을 가른 이유)."""
    assert parcels.use_declared(text, has_work=True) == use, text
    assert parcels.use_declared(text, has_work=False) == use, text


def test_the_two_marker_lists_do_not_overlap():
    assert not set(parcels.USE_DECLARE_WORDS) & set(parcels.USE_DECLARE_TAILS)
    assert all(not any(w in tail for w in parcels.USE_DECLARE_WORDS) for tail in parcels.USE_DECLARE_TAILS)


def test_the_judgement_lives_in_one_place_and_the_callers_agree():
    """두 자리가 **같은 함수**를 부른다 — 분류는 이미 잰 작업 어휘를 넘기고(두 번 재지 않는다), 원장 읽기는 기본값으로 같은 답을 받는다."""
    import inspect
    src = inspect.getsource(chat._classify)
    assert src.count("parcels.use_declared(") == 1, "분류가 용도 가름을 두 번 묻는다 — 인자가 어긋나면 같은 말에 다른 답이 된다"
    assert "has_work=bool(et)" in src
    for text in ("종구 캘 것입니다", "이번 작기는 팔 것이다"):
        assert parcels.use_declared(text) == parcels.use_declared(text, has_work=chat.work_type(text) is not None), text


def test_a_plan_written_in_the_diary_does_not_change_the_field_use():
    """묻기 전 원장 읽기도 같은 가름을 받는다 — 일지에 적힌 **할 일** 한 줄이 밭의 용도를 바꾸면 안 된다(그 값은 재배 달력의 기준이 된다)."""
    assert known.value_in("use", "종구 캘 것입니다") is None
    assert known.mentions("use", "종구 캘 것입니다") is False
    assert known.value_in("use", "이 쪽파는 종구생산을 위한 목적이다") == "종구 생산"


def test_the_work_word_name_is_public_so_the_vocabulary_is_not_copied():
    assert chat.work_type("종구 캘 것입니다") == "수확" and chat.work_type("이번 작기는 팔 것이다") is None
    assert "chat.work_type" in __import__("inspect").getsource(parcels.use_declared)
