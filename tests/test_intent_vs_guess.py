# -*- coding: utf-8 -*-
# [2026-10-05 ⓒⓓ — 같은 병의 마지막 두 얼굴] 「어미를 어휘 조각으로 세던」 계열의 끝. 남아 있던 둘:
#   ⓒ 「-려고」 가 의도(물 주려고)와 **추측**(비가 오려고 한다 · 잎이 마르려고 한다 · 해가 지려고 한다)에 같이 쓰이는데 무조건 할 일이었다.
#   ⓓ 추측 가름이 `bool(et)` 였다 — 작업 **이름**만 들어도 의지로 세어 「올해는 수확이 적겠다」 · 「비료가 모자라겠다」 · 「올해 파종이 늦겠다」 가 할 일이 됐다.
# 둘 다 **가를 재료가 없어서** 등재해 둔 것이고, 활용을 규칙으로 만든 뒤 재료가 생겼다 — 「물 주려고」 가 작업 어휘로 읽히고(의도), 작업 이름마다 「…하」 어간을 두어
# 이름과 **동사 꼴**이 갈린다(「수확이」 vs 「수확할」). 가름은 한 자리씩: `_INTENT_RE` 는 의지가 있을 때만 · 추측 가름(`willing`)은 **동사 꼴**이나 의지 표지로만 선다.
#
# ⓓ를 재는 도중 **네 번째 얼굴**이 나왔다: 「올해는 수확이 적겠다」 가 할 일도 아니고 **사건**(한 일)이었다 — `_done_evidence` 가 받침 ㅆ 를 그대로 세어 의지·추측의
# 「겠」 까지 과거로 읽었다(`_past_ending` 은 같은 정본으로 이미 겠을 뺐는데 이 갈래만 안 뺐다 — 같은 물음에 두 답). 할 일로 잘못 가는 것보다 나쁘다:
# **하지도 않은 작업이 원장에 들어가고 계획 대 실제가 그것을 이행으로 센다**(되먹임까지). 그 자리도 공유 정본으로 갈랐다.
from __future__ import annotations

from datetime import date

import pytest

from ingest import chat

T = date(2026, 10, 5)


@pytest.mark.parametrize("text", ["물 주려고", "약 치려고", "종구 심으려고", "내일 웃거름 주려고요", "비닐 정리하려고", "웃거름 주려고", "트랩 확인하려고"])
def test_an_intent_ending_with_a_work_word_is_a_plan(text):
    """「-려고」 가 의도인지 추측인지는 **작업 어휘가 서는가**로 가른다 — 그것이 서려면 활용을 읽어야 했다(전에는 「물 주려고」 의 종류가 None 이었다)."""
    assert chat.work_type(text) is not None, text
    assert chat.classify(text, T)[0]["kind"] == "plan.farmer", text


@pytest.mark.parametrize("text", ["비가 오려고 한다", "잎이 마르려고 한다", "해가 지려고 한다"])
def test_the_same_ending_without_a_work_word_is_a_guess_not_a_plan(text):
    """추측은 할 일이 아니다 — 확인하면 농가가 말하지 않은 계획이 원장에 들어간다."""
    assert chat.work_type(text) is None, text
    assert chat.classify(text, T)[0]["kind"] != "plan.farmer", text


@pytest.mark.parametrize("text", ["올해는 수확이 적겠다", "비료가 모자라겠다", "올해 파종이 늦겠다", "트랩이 모자라겠다"])
def test_a_work_name_alone_is_not_an_intention(text):
    """작업 **이름**은 의지가 아니다 — 그 이름이 든 추측이 할 일(옛 판) · 심지어 **한 일**(그 전 판)로 적혔다."""
    assert chat.work_type(text) is not None and not chat.work_said_as_verb(text), text
    assert chat.classify(text, T)[0]["kind"] == "observation.note", text


@pytest.mark.parametrize("text", ["수확할 것 같다", "방제할 것 같다", "약을 쳐야겠다", "9월 25일에 웃거름 해야 할 것 같다"])
def test_the_same_work_in_a_verb_form_is_still_a_plan(text):
    """반대편 — 이름과 동사 꼴을 가를 때 동사 꼴까지 버리면 농가 계획이 사라진다."""
    assert chat.classify(text, T)[0]["kind"] == "plan.farmer", text


@pytest.mark.parametrize("text,kind", [("다음 주에 트랩 확인하겠습니다", "plan.farmer"), ("비가 오겠습니다", "observation.note")])
def test_the_polite_will_form_needs_a_work_word(text, kind):
    """「-겠습니다」 는 거의 언제나 의지지만(확인하겠습니다) 작업 어휘가 없으면 예보다(비가 오겠습니다)."""
    assert chat.classify(text, T)[0]["kind"] == kind, text


@pytest.mark.parametrize("text", ["올해는 수확이 적겠다", "비료가 모자라겠다", "비가 오겠다", "트랩 확인하겠습니다"])
def test_the_will_ssang_is_never_read_as_a_done_marker(text):
    """**네 번째 얼굴** — 「겠」 의 받침 ㅆ 를 과거로 세면 하지도 않은 작업이 원장에 들어간다(계획 대 실제가 이행으로 센다)."""
    assert not chat._done_evidence(text), text
    assert chat.classify(text, T)[0]["kind"] != "event", text


@pytest.mark.parametrize("text", ["오늘 물 줬다", "어제 웃거름 줬어요", "9월 10일 방제", "방제 완료", "오늘 스프링쿨러로 급수함", "아침에 포장을 보니 징후 없다"])
def test_a_real_done_marker_still_makes_an_event(text):
    """반대편 — 과거의 ㅆ 와 완료 표현은 그대로 한 일이다(가르면서 한 일을 같이 버리면 일지가 빈다)."""
    assert chat._done_evidence(text), text
    assert chat.classify(text, T)[0]["kind"] == "event", text


def test_the_two_judgements_on_the_will_ssang_agree():
    """같은 물음(「이 ㅆ 가 과거인가」)에 두 답을 두지 않는다 — 두 갈래가 같은 정본을 쓴다(§7.1)."""
    import inspect
    assert "_WILL_SSANG" in inspect.getsource(chat._done_evidence)
    assert "_NOT_PAST_SSANG" in inspect.getsource(chat._past_ending)
    for t in ("올해는 수확이 적겠다", "모르겠다", "확인하겠습니다"):
        assert not chat._done_evidence(t) and not chat._past_ending(t), t
