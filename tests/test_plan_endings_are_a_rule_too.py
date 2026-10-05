# -*- coding: utf-8 -*-
# [처방 직후 전수 2026-10-05 · §7.5] 종결 의문 어미를 어미 규칙으로 옮긴 직후 *"같은 형태가 다른 갈래에도 있는가"* 를 세니 **계획 갈래가 같은 병**이었다 — 그것도 두 겹으로:
#   ① 어휘가 **두 벌**이었다(`PLAN_WORDS` 튜플과 `_PLAN_RE` 정규식이 예정 · 할 것 · 할게 · 해야겠 · 할 생각을 겹쳐 들고 있었다 — §7.1 "판정과 처방은 단일 정본")
#   ② 그 어휘가 **'하다' 꼴 조각**이라 다른 동사에서 안 걸렸다: 「내일 물 줄 것」 · 「모레 약 칠 것」 · 「비료 줄게」 · 「약 칠게」 가 **본 것**으로 떨어졌다(농가 계획이 안 선다)
#   ③ 포함 검사라 **추측**까지 계획으로 만들었다: 「비가 오겠다」 · 「잎이 노랗겠다」 · 「힘들겠다」 · 「모르겠다」 · 「물이 부족할 것 같다」 → 계획
#      (확인하면 **농가가 말하지 않은 할 일**이 계획 원장에 들어가고 계획 대 실제가 그것을 이행·놓침으로 센다 — 되먹임까지 오염된다)
# 가르는 표지는 어미가 아니라 **의지**다: 같은 「-겠다」 가 의지(물 줘야겠다)와 추측(비가 오겠다)에 다 쓰이고, 같은 「것 같다」 가 의지(웃거름 해야 할 것 같다)와
# 추측(물이 부족할 것 같다)에 다 쓰인다 → 추측 꼴은 **작업 어휘나 의지 표지(야겠 · 야 할)가 있을 때만** 계획이다(이 파일의 「문장 끝 서술은 작업 어휘가 있을 때만」 과 같은 축).
# 그리고 의지 어미를 일반화하자 **선언을 가로챘다**(말뭉치 래칫이 둘 다 잡았다 — 「이번 작기는 팔 것이다」 용도 선언 · 「이번 작기 끝낼게요」 작기 종료) → 선언이 앞선다.
from __future__ import annotations

import inspect
from datetime import date

import pytest

from ingest import chat

T = date(2026, 10, 5)

# 소스가 **이름하지 않는** 동사들로만 센다 — 조각 목록을 되읽으면 "목록이 전부인가" 를 못 묻는다
WILLING = ["내일 물 줄 것", "모레 약 칠 것", "다음 주에 종구 심을 것", "비료 줄게", "약 칠게", "물 줄 것이다", "주말에 고랑 손볼 것입니다", "종구 캘 것"]
GUESSING = ["비가 오겠다", "잎이 노랗겠다", "힘들겠다", "모르겠다", "물이 부족할 것 같다", "잎이 마를 것 같다", "올해는 춥겠다"]


@pytest.mark.parametrize("text", WILLING)
def test_an_intent_ending_the_source_never_names_is_a_plan(text):
    assert chat._plan_ending(text), text
    assert chat.classify(text, T)[0]["kind"] == "plan.farmer", text


@pytest.mark.parametrize("text", GUESSING)
def test_a_guess_is_not_a_plan(text):
    """추측은 할 일이 아니다 — 확인하면 농가가 말하지 않은 계획이 원장에 들어간다."""
    assert chat.classify(text, T)[0]["kind"] != "plan.farmer", text


@pytest.mark.parametrize("text", ["약을 쳐야겠다", "내일 물 줘야겠다", "9월 25일에 웃거름 해야 할 것 같다", "방제할 것 같다", "다음 주에 트랩 확인하겠습니다",
                                  # [주입 C 가 드러낸 갈래 — 미검사였다] 작업 어휘가 없고 **의지 표지만** 있는 말. 위 다섯은 어휘 정본이나 작업 어휘로 먼저
                                  # 걸려서 의지 표지 가지가 한 번도 안 밟혔다(가드가 사실상 사문이었다). 이 둘이 그 가지를 밟는다
                                  "고랑 손봐야 할 것 같다", "이랑을 다시 만들어야 할 것 같다"])
def test_the_same_ending_with_an_intent_mark_or_a_work_word_is_still_a_plan(text):
    """반대편 — 추측 꼴을 거를 때 **의지**를 같이 거르면 농가 계획이 사라진다(막는 것을 검사하면 통과하는 것도 검사한다)."""
    assert chat.classify(text, T)[0]["kind"] == "plan.farmer", text


@pytest.mark.parametrize("text,kind", [("이번 작기는 팔 것이다", "parcel.field"), ("이번 작기 끝낼게요", "subject.end"),
                                       ("종구용이다", "parcel.field"), ("이 쪽파는 종구생산을 위한 목적이다", "parcel.field")])
def test_a_declaration_comes_before_an_intent_ending(text, kind):
    """선언(용도 · 작기 종료)은 의지 어미보다 앞선다 — 작기 종료는 확인하면 그 재배 단위를 닫으므로 잘못 걸릴 때의 대가가 가장 크다.

    **못 가른 것은 못 가른다고 적어 둔다**: `parcels.USE_DECLARE_WORDS` 가 「것이다 · 것입니다 · 할 생각」 을 **선언의 표지**로 들고 있어서
    「종구 캘 것입니다」(할 일)도 용도 선언으로 읽힌다 — 두 뜻이 같은 어미를 쓴다. 작업 어휘로 가르려 했지만 `_event_type` 이 「캘」 을
    모른다(그 어휘도 활용 조각 목록이다 — 같은 병의 세 번째 자리 · 등재). 그래서 이 줄은 주장하지 않는다(종류는 확인에서 바꾼다).
    """
    assert chat.classify(text, T)[0]["kind"] == kind, text


@pytest.mark.parametrize("text", ["고랑을 깊게", "물을 적게", "잎이 노란 것", "이게 더 좋은 것"])
def test_a_tail_that_only_looks_like_the_intent_ending_is_left_alone(text):
    """「-ㄹ게 · -ㄹ 것」 규칙은 **받침 ㄹ** 만 본다 — 「깊게」(ㅍ) · 「적게」(ㄱ) · 「노란 것」(ㄴ)은 안 걸린다.

    [주입 G] 첫 판의 이 줄은 「늦게 심었다」 처럼 **끝이 게가 아닌** 말이라 받침 가지를 한 번도 안 밟았다 — 주입이 통과했다.
    경계 검사는 그 가지에 **닿는** 입력으로 써야 한다(미검사 가드와 같은 축 · §7.1 3번).
    """
    assert not chat._plan_ending(text), text
    assert chat.classify(text, T)[0]["kind"] != "plan.farmer", text


def test_there_is_one_canon_for_plan_wording_not_two():
    """옛 `PLAN_WORDS` 튜플은 정규식 정본으로 합쳤다 — 되살리면 두 벌이 되고, 두 벌은 언젠가 어긋난다(§7.1)."""
    assert not hasattr(chat, "PLAN_WORDS"), "어휘 두 벌이 돌아왔다"
    src = inspect.getsource(chat._classify)
    # [2026-10-05] 첫 판은 `said_plan =` 가 든 **한 물리 줄**을 잡았다 — 식이 세 줄로 늘자 깨졌다(검사 대상은 하나도 안 바뀌었는데).
    # 거리가 아니라 **구조**로 자른다: 대입이 시작된 자리에서 다음 문장(`if `)까지가 그 식이다(§7.5 "창을 고정하지 않는다")
    block = src[src.index("said_plan = "):]
    block = block[:block.index("\n    if ")]
    assert "_plan_ending(t)" in block and "_GUESS_TAIL_RE" in block                # 어미 규칙과 추측 가름이 그 한 식에서 선다
    assert "_end_declared(t)" in src                                               # 종료 선언 조건은 두 자리가 같은 함수를 쓴다


def test_the_end_declaration_condition_is_shared_not_copied():
    assert chat._end_declared("이번 작기 끝낼게요")
    assert not chat._end_declared("작기 끝나기 전에 웃거름 줄게")                      # 종속절은 선언이 아니다 — 그 말은 계획이다
    assert chat.classify("작기 끝나기 전에 웃거름 줄게", T)[0]["kind"] == "plan.farmer"
