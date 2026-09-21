# -*- coding: utf-8 -*-
# [발행자 실사용 2026-09-21] 발행자가 화면에 적었다: **"오늘 스프링쿨러로 급수함"**. 화면이 답한 것은 이랬다.
#
#   관찰 초안 — 서술문 — 사건·계획·질문 어휘가 없어 관찰 메모로 제안(원문 그대로 · 종류는 확인에서 바꾼다)
#   확인 → 원장 · 다른 종류: 사건 / 계획 / 불이행 사유 / 개선 요구 / 작기 종료
#
# 발행자 물음: **"이런 답변을 보여 주는 것을 이해할 사람이 얼마나 될까?"**
#
# 두 가지가 **동시에** 틀렸다.
#
#   분류   '관수' 는 어휘에 있는데 **'급수' 가 없어** 한 일을 못 읽었다 — 한자어 동의어 누락
#   문면   원장 · 초안 · 서술문 · 어휘 · 불이행 사유 — **개발자의 말**을 그대로 농가에게 냈다
#
# 둘째가 이 트랙의 G1 세 번째 형태다(정본은 옳은데 표현 층이 배반한다). 다만 여기서는 **정본도 틀렸다** —
# 그래서 어휘를 넓히고, 사람 말 정본을 세우고, 정확한 사유는 `title` 로 내려 **잃지 않는다**.
from __future__ import annotations

import re
from datetime import date, datetime, timezone

import pytest

from frontend import chat_pages
from ingest import chat, media

T = date(2026, 9, 21)
NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)

# 화면에 나오면 안 되는 **개발자의 말**. 이것들은 원장·대장·검사의 이름이지 농가의 말이 아니다.
INTERNAL_WORDS = ("원장", "초안", "서술문", "어휘", "불이행 사유", "개선 요구", "작기 종료", "분류")


def _visible(html: str) -> str:
    """사람이 **보는** 글자만 — 태그와 속성(`title=` 포함)을 걷는다.

    [§7.1 4번] 정확한 사유는 `title` 에 일부러 남겨 두었으므로, 그것을 걷지 않으면 이 검사는 언제나 빨갛다.
    걷을 것과 볼 것을 먼저 가른다.
    """
    return re.sub(r"<[^>]*>", " ", html)


# ── 분류 ───────────────────────────────────────────────────────────────────────────
def test_the_publishers_own_sentence_is_read_as_something_done():
    """발행자가 실제로 친 문장. '급수' 가 어휘에 없어 **본 것**으로 제안됐다 — 한 일이다."""
    d = chat.classify("오늘 스프링쿨러로 급수함", T)[0]
    assert d["kind"] == "event" and d["type"] == "관수"


@pytest.mark.parametrize("text, kind", [
    ("오늘 급수함", "event"),
    ("어제 관주했다", "event"),
    ("살수 완료", "event"),
    ("급수 시설이 없다", "observation.note"),       # 한 일의 표지가 없다 — 상태 서술이다
    ("스프링쿨러가 고장났다", "observation.note"),   # 장치 이름은 한 일이 아니다(넣었으면 이것이 관수 사건이 됐다)
])
def test_the_new_words_do_not_turn_states_into_deeds(text, kind):
    """넓히면 **반대편**을 함께 본다 — 막는 것을 검사하면 통과하는 것도 검사한다."""
    assert chat.classify(text, T)[0]["kind"] == kind


# ── 문면 ───────────────────────────────────────────────────────────────────────────
def test_every_kind_has_a_word_a_farmer_uses():
    """종류가 늘면 사람 말도 함께 는다 — 한쪽만 늘면 화면이 내부 이름을 낸다."""
    assert set(chat.KIND_PLAIN) == set(chat.KIND_LABEL)
    for k, plain in chat.KIND_PLAIN.items():
        assert plain not in INTERNAL_WORDS, f"{k}: 사람 말 자리에 내부 이름이 들어 있다 — {plain}"


@pytest.mark.parametrize("kind", ["event", "observation.note", "plan.farmer", "decision.noncompliance",
                                  "feedback.request", "subject.end"])
def test_the_card_a_farmer_sees_carries_no_developer_words(kind):
    """카드에 **보이는 글자**에는 개발자의 말이 없다. 옛 판은 `why` 를 그대로 첫 줄에 냈다."""
    m = {"id": "msg_x", "subject": "s1", "drafts": [{"kind": kind, "type": "관수", "text": "t",
                                                     "why": "서술문 — 사건·계획·질문 어휘가 없어 관찰 메모로 제안", "needs": []}]}
    seen = _visible(chat_pages._draft_html(m, 0, m["drafts"][0]))
    for w in INTERNAL_WORDS:
        assert w not in seen, f"{kind}: 화면이 '{w}' 라고 말한다 — {seen.strip()[:90]}"


def test_the_exact_reason_is_kept_where_it_can_be_read_but_does_not_lead():
    """정확함을 **버리지 않는다** — 사유는 `title` 에 그대로 있고, 앞에 서지 않는다."""
    why = "서술문 — 사건·계획·질문 어휘가 없어 관찰 메모로 제안(원문 그대로 · 종류는 확인에서 바꾼다)"
    m = {"id": "msg_x", "subject": "s1", "drafts": [{"kind": "observation.note", "text": "t", "why": why, "needs": []}]}
    html = chat_pages._draft_html(m, 0, m["drafts"][0])
    assert "서술문" in html and "서술문" not in _visible(html), "사유가 사라졌거나 앞으로 나왔다"


def test_the_reasons_for_a_note_do_not_collapse_into_one_sentence():
    """관찰 메모는 **서로 다른 이유**로 나온다. 하나로 뭉개면 화면이 틀린 말을 한다 —
    '급수 시설이 없다' 에 *"관수라는 말이 없어서"* 라고 답하게 된다(있다)."""
    said = {k: chat.plain_why({"kind": "observation.note", "why_key": k}) for k in chat.PLAIN_BY_KEY}
    assert len(set(said.values())) == len(said), said
    assert chat.plain_why(chat.classify("급수 시설이 없다", T)[0]) != chat.plain_why(chat.classify("줄기가 왕성하다", T)[0])


def test_the_whole_reply_speaks_the_farmers_language(tmp_path, monkeypatch):
    """끝에서 끝까지 — 실제 발화 하나를 보내 **답변 문장**을 본다(카드만 고치고 답변을 두면 반쪽이다)."""
    monkeypatch.setenv("AGRODSS_CHAT_DIR", str(tmp_path / "chat"))
    sid = media.load_subjects()[0]["id"]
    _, r = chat.send(sid, "오늘 스프링쿨러로 급수함", today=T, now=NOW)
    for w in INTERNAL_WORDS:
        assert w not in r["text"], f"답변이 '{w}' 라고 말한다 — {r['text']}"
    assert "관수" in r["text"] and chat.CONFIRM_LABEL in r["text"]      # 무슨 일이었는지를 말한다
