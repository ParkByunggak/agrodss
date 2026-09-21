# -*- coding: utf-8 -*-
# [발행자 2026-09-21] "분류 안 됨 — 종류를 고른다 … **이는 사용자에게 묻는 것은 옳지 않다.** 질문의 내용을 분석하고
#   시스템에서 어떻게 분류할 것인지를 확정해야 할 것이다."
#
# 2026-09-19 에 같은 말을 듣고 **규칙**은 고쳤다(서술문 → 관찰 메모 제안). 그런데 **묻는 화면**은 그대로 남아 있었다 —
# 규칙이 못 고르는 입력이 하나라도 생기면 화면이 다시 사람에게 물었다. 규칙을 고치고 물음을 안 치운 것이다.
# 여기서 고정하는 것은 어휘가 아니라 **구조**다: 무엇이 들어와도 종류는 시스템이 정한다. 사람은 제안된 초안의
# '다른 종류' 로 고친다 — 그것은 묻는 것이 아니라 고치는 것이다.
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from frontend import chat_pages
from ingest import chat, media

ROOT = Path(__file__).resolve().parent.parent
SID = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]["id"]
TODAY = date(2026, 9, 21)

HARD = ["그냥", "음", "ㅋㅋ", "...", "1", "밭", "오늘", "쪽파", "?", "!!", "저기요", "아 그거",
        "어제 그거 있잖아", "비료", "abc", "ㅇㅇ", "네", "아니요", "글쎄", "음... 그러니까",
        "쪽파를 현재 관리해야 할 항목들을 알려줘요", "ㅏㅏㅏ", "🙂", "。", "-"]


@pytest.mark.parametrize("text", HARD)
def test_the_system_always_decides_a_kind(text):
    drafts = chat.classify(text, TODAY)
    assert drafts, f"{text!r}: 규칙이 종류를 못 정했다 — 사람에게 넘기지 않기로 했다"
    assert drafts[0]["kind"] in dict(chat_pages.CHOOSABLE) or drafts[0]["kind"] == "question", drafts


def test_send_never_answers_by_asking_the_person_to_classify():
    me, sys_ = chat.send(SID, "어제 그거 있잖아", today=TODAY)
    assert me.get("drafts"), "초안 없이 보냈다"
    assert "골라" not in (sys_ or {}).get("text", "") and "분류 안 됨" not in (sys_ or {}).get("text", "")


def test_a_blank_utterance_is_refused_not_turned_into_a_question():
    for blank in ("", "   ", "\t", "\n"):
        with pytest.raises(chat.ChatError):
            chat.send(SID, blank, today=TODAY)


def test_no_screen_asks_the_person_which_kind_it_is():
    """래칫 — 화면 어디에도 '종류를 고른다' 물음이 없다. 있는 것은 제안된 초안의 '다른 종류'(고치는 길)뿐이다."""
    for py in sorted((ROOT / "frontend").glob("*.py")):
        src = py.read_text(encoding="utf-8")
        code = "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())
        assert "분류 안 됨" not in code, f"{py.name}: 사람에게 분류를 묻는 문면이 남아 있다"
    body = (ROOT / "frontend" / "chat_pages.py").read_text(encoding="utf-8")
    # [발행자 2026-09-21 문면] 말 자체는 이제 `chat` 의 정본에서 온다 — 여기서 볼 것은 **고치는 길이 화면에 있는가**다.
    # 문면을 박아 두면 말을 다듬을 때마다 이 래칫이 거짓으로 깨진다(오늘 세 번째 같은 형태였다).
    assert "OTHER_KIND_LABEL" in body and "/choose" in body, "고치는 길까지 없애면 안 된다 — 시스템 판정을 사람이 바꿀 수 있어야 한다"


def test_the_kind_can_still_be_changed_by_the_person():
    """경계 — 묻지 않는 것과 못 고치는 것은 다르다(게이트가 막던 것을 남긴다)."""
    me, _ = chat.send(SID, "어제 그거 있잖아", today=TODAY)
    assert me["drafts"][0]["kind"] == "observation.note"
    chat.choose_kind(me["id"], "event", today=TODAY)
    m = next(x for x in chat.list_messages(SID) if x["id"] == me["id"])
    assert m["drafts"][0]["kind"] == "event"


def test_if_the_rules_ever_come_back_empty_send_still_decides_instead_of_asking(monkeypatch):
    """미검사 가드를 덮는다 — 지금은 규칙이 늘 무언가를 내므로 이 자리는 안 닿는다. 그래도 **닿으면 묻지 않는다**가
    이 자리의 약속이다(규칙이 넓어질 때 조용히 물음으로 되돌아가지 않게)."""
    monkeypatch.setattr(chat, "classify", lambda text, today: [])
    me, sys_ = chat.send(SID, "규칙이 못 고르는 말", today=TODAY)
    assert me["drafts"] and me["drafts"][0]["kind"] == "observation.note"
    assert me["drafts"][0]["text"] == "규칙이 못 고르는 말"          # 내용은 원문 그대로 — 지어내지 않는다
    assert "골라" not in sys_["text"] and "분류 안 됨" not in sys_["text"]
    m = next(x for x in chat.list_messages(SID) if x["id"] == me["id"])
    assert m["drafts"], "원장에도 초안이 남아야 화면에서 확인할 수 있다"
