# -*- coding: utf-8 -*-
# [처방 직후 전수 2026-10-05 · 같은 병의 **세 번째** 자리] 물음 어미 · 계획 어미를 규칙으로 옮긴 뒤 같은 형태를 또 세니 **작업 어휘**(`EVENT_SYNONYMS`)가 남아 있었다 —
# 동사 꼴이 거의 다 **과거**였다(「약 쳤」 · 「물 줬」 · 「캤」 · 「보냈」). 그래서 같은 일을 앞날·의지로 말하면 작업 종류가 **아무것도** 안 걸렸다:
#   「약 쳐야겠다」 · 「내일 물 줘야겠다」 · 「종구 캘 것」 → 종류 없음. 종류가 없으면 ① 할 일 초안의 `task` 가 **문장 전체**가 되고
#   ② 계획표 줄과 못 잇는다(`_plan_row_for` 는 종류의 말로 격자 줄을 찾는다 — 그러면 계획 대 실제가 그 할 일을 아무 줄에도 못 붙인다).
# 손으로 꼴을 더한 흔적이 이미 있었다(「물 준다」 를 앞날 서술용으로 따로 적어 두었다) — 하나씩 더하는 길은 끝이 없다는 증거다.
# 처방: **어간을 적고 활용은 규칙이 만든다**(`chat.conjugations`). 이 검사가 고정하는 것은 ① 규칙이 옛 손 목록을 **다시 만들어 낸다**(옮기는 것이 안전하다는 증거) ·
# ② 소스가 이름하지 않는 꼴도 걸린다 · ③ 짧은 꼴이 엉뚱한 말에 안 걸린다(캘린더 · 캠페인) · ④ 한 말을 두 목록에 적지 않는다.
from __future__ import annotations

from datetime import date

import pytest

from ingest import chat

T = date(2026, 10, 5)

# 2026-10-05 이전에 **손으로** 적혀 있던 동사 꼴 전부 — 규칙이 이 꼴을 다 만들어야 옮기는 것이 안전하다(migration 의 증거)
HAND_WRITTEN_BEFORE = {
    "파종": ("심었",), "정식": ("옮겨 심", "옮겨심"),
    "방제": ("약 쳤", "약을 쳤", "약쳤", "뿌렸", "약 침", "약을 침", "약침"),
    "관수": ("물 줬", "물을 줬", "물줬", "물 주었", "물 줌", "물줌", "물을 줌", "물 준다", "물을 준다", "물주었", "물을 주었"),
    "제초": ("풀 뽑", "풀뽑", "김매", "풀을 뽑"),
    "예찰": ("살펴봤", "둘러봤", "살펴보았", "둘러보았"),
    "보식": ("다시 심", "다시심"), "배수": ("물 빼", "물빼"),
    "수확": ("캤", "캐냈", "뽑았", "다듬었", "거뒀", "거두었"),
    "납품": ("보냈", "출하했"), "정리": ("정리했", "정비했", "걷었"),
}


@pytest.mark.parametrize("ty", sorted(HAND_WRITTEN_BEFORE))
def test_the_rule_reproduces_every_form_that_used_to_be_written_by_hand(ty):
    now = chat.EVENT_SYNONYMS[ty]
    gone = [w for w in HAND_WRITTEN_BEFORE[ty] if not any(w in n or n in w for n in now)]
    assert gone == [], f"{ty}: 규칙이 옛 꼴을 못 만든다 — {gone}"


# 소스가 **이름하지 않는** 꼴(어간만 적혀 있다) — 목록을 되읽으면 "목록이 전부인가" 를 못 묻는다
@pytest.mark.parametrize("text,ty", [
    ("약 쳐야겠다", "방제"), ("모레 약 칠 것", "방제"), ("내일 물 줘야겠다", "관수"), ("내일 물 줄 것", "관수"),
    ("종구 캘 것", "수확"), ("비닐 정리할 것", "정리"), ("다음 주에 밭 둘러볼 것", "예찰"), ("고랑 물 뺄 것", "배수"),
    ("다음 주에 종구 심을 것", "파종"), ("풀 뽑을 것", "제초"), ("내일 몰에 보낼 것", "납품"),
])
def test_the_same_work_said_as_a_plan_gets_its_type(text, ty):
    assert chat._event_type(text) == ty, text


@pytest.mark.parametrize("text,ty", [("약 쳐야겠다", "방제"), ("내일 물 줄 것", "관수"), ("종구 캘 것", "수확")])
def test_the_plan_draft_carries_the_work_type_not_the_whole_sentence(text, ty):
    """종류가 서야 계획표 줄과 이을 수 있다(`_plan_row_for` 가 종류의 말로 격자 줄을 찾는다) — 옛 판은 `task` 가 문장 전체였다."""
    d = chat.classify(text, T)[0]
    assert d["kind"] == "plan.farmer" and d["task"] == ty, (text, d)


@pytest.mark.parametrize("text", ["캘린더에 적었다", "캠페인 전단을 받았다", "관심을 둬야겠다", "밭을 걷는다", "정리함을 샀다", "물 준비를 했다", "조심을 해야겠다"])
def test_a_short_generated_form_does_not_catch_an_unrelated_word(text):
    """짧은 꼴은 부분 문자열로 엉뚱한 말에 걸린다 — 그래서 **한 음절 어간의 ㄹ·ㅁ 꼴은 만들지 않는다**(캐 → 캘 · 캠 금지 · 「종구 캐」 처럼 두 음절 구로 적는다)."""
    assert chat._event_type(text) is None, text


def test_the_one_syllable_rule_is_what_keeps_those_out():
    assert "캘" not in chat.EVENT_SYNONYMS["수확"] and "캠" not in chat.EVENT_SYNONYMS["수확"]
    assert "종구 캘" in chat.EVENT_SYNONYMS["수확"]                      # 두 음절 구로 적으면 만든다
    assert "심을" not in chat.EVENT_SYNONYMS["파종"]                     # 「관심을 · 조심을」 에 걸린다
    # [주입 C] 첫 판은 `"함" not in conjugations("정리하")` 였다 — 목록에는 「정리함」 이 들어 있으므로 그 단언은 **언제나 참**이고 아무것도 안 지켰다(사문 단언).
    # 만들어지는 말 그대로 비교한다
    assert "정리함" not in chat.conjugations("정리하") and "정비함" not in chat.conjugations("정비하")
    assert "걷" not in chat.EVENT_VERBS["정리"]                          # 걷다(걸어가다)와 겹쳐 어간으로 두지 않았다 — 과거 꼴만 손 목록에
    assert "걷었" in chat.EVENT_NOUNS["정리"]


def test_a_word_is_not_written_in_two_lists():
    """한 말을 어간 목록과 명사 목록에 겹쳐 적지 않는다 — 겹치면 어느 쪽을 고쳐야 하는지가 흐려진다(§7.1 단일 정본)."""
    for ty, stems in chat.EVENT_VERBS.items():
        made = {w for s in stems for w in chat.conjugations(s)}
        assert not (made & set(chat.EVENT_NOUNS.get(ty, ()))), ty
    assert all(chat.EVENT_SYNONYMS[ty] for ty in chat.EVENT_SYNONYMS)


def test_the_generator_handles_each_stem_shape():
    """어간 꼴마다 한 줄씩 — 받침 있는 어간 · 모음 어간(ㅜ · ㅣ · ㅐ · ㅗ · ㅡ) · 하-어간."""
    assert {"뽑았", "뽑아야", "뽑는다"} <= set(chat.conjugations("뽑"))
    assert {"물 줬", "물 줘야", "물 준다", "물 줄", "물 줌"} <= set(chat.conjugations("물 주"))
    assert {"약 쳤", "약 쳐야", "약 친다", "약 칠", "약 침"} <= set(chat.conjugations("약 치"))
    assert {"종구 캤", "종구 캐야", "종구 캔다"} <= set(chat.conjugations("종구 캐"))
    assert {"살펴봤", "살펴봐야", "살펴볼", "살펴봄"} <= set(chat.conjugations("살펴보"))
    assert {"정리했", "정리해야", "정리할", "정리한다"} <= set(chat.conjugations("정리하"))
    assert {"거뒀", "거두었", "거둬야", "거둔다", "거둘", "거둠"} <= set(chat.conjugations("거두"))
