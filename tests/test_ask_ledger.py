# -*- coding: utf-8 -*-
# [WO-ASK-01 §8 · §9 · 검토 §2-④ · 2026-10-03] 묻기 원장 + 직전 물음(pending) — send 에서만.
#
# 지시서 §8 "같은 것 두 번 안 묻는다 · 반복 상한 · 유효기간" 과 §9 "답이 올 때 그 축의 초안" 은 **무엇을 언제 몇 번 물었는지**가 남아 있어야
# 선다. 요구 문장(판단 불가(데이터)의 missing)이 농가에게 나가는 것은 이미 물은 것이다 — 질문 생성(§3)이 서기 전에도.
# 검토 §2-④ 의 규율: 원장은 **send(저장 길)에만** 붙는다. answer(저장 없는 길)에 붙으면 자기 점검 화면이 열 때마다 원장을 더럽힌다.
# 거부와 통과를 둘 다 본다 — send 는 센다 · answer 는 안 센다. 기록 실패는 답을 막지 않되 보이게(dropped) 남는다(§13-3 ↔ fail-open 금지).
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from frontend import chat_pages, words
from ingest import asks, chat, dropped, media

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
TODAY = date(2026, 9, 28)              # 기준점 후 34일 — 칸 4 · 가뭄 임계 7일 · 격리 환경엔 비 기록도 관측도 없어 판단 불가(데이터) precip
Q = "가뭄이 심한데 물 줘야 하나요"       # 물음으로 분류되고 가뭄 판단으로 간다(topic_of → drought_alert)
NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)


def _subject():
    return media.load_subjects()[0]


# ── send 는 센다 ──
def test_a_sent_question_that_asks_is_counted_and_becomes_the_pending_ask():
    m, r = chat.send(SID, Q, today=TODAY, now=NOW)
    rows = asks.for_subject(SID)
    assert [x["axis"] for x in rows] == ["precip"] and rows[0]["count"] == 1 and rows[0]["decision"] == "drought_alert"
    assert rows[0]["last_msg"] == r["id"] and rows[0]["first_at"] == rows[0]["last_at"] and "어디서:" in rows[0]["who_can_fill"]
    assert asks.pending(SID) == {"axes": ["precip"], "msg": r["id"], "at": rows[0]["last_at"]}
    assert "after_ask" not in m                                              # 물음 자체는 답이 아니다


def test_asking_again_counts_up_in_one_row():
    chat.send(SID, Q, today=TODAY, now=NOW)
    _, r2 = chat.send(SID, Q, today=TODAY, now=NOW)
    rows = asks.for_subject(SID)
    assert len(rows) == 1 and rows[0]["count"] == 2 and rows[0]["last_msg"] == r2["id"] and asks.pending(SID)["msg"] == r2["id"]


# ── 물은 뒤 처음 온 말 ──
def test_the_first_message_after_a_question_is_tied_to_it_and_clears_pending():
    _, r = chat.send(SID, Q, today=TODAY, now=NOW)
    m2, r2 = chat.send(SID, "어제 비가 왔다", today=TODAY, now=NOW)
    assert m2["after_ask"] == {"axes": ["precip"], "msg": r["id"]}
    row = next(x for x in asks.for_subject(SID) if x["axis"] == "precip")
    assert row["replies"] == 1 and row["replied_msg"] == m2["id"] and row["replied_to"] == r["id"]
    saved = next(x for x in chat.list_messages(SID) if x["id"] == m2["id"])     # 원장에도 남았다(화면이 읽는 것은 원장)
    assert saved.get("after_ask") == m2["after_ask"]
    # [§3 2026-10-03] 스스로 묻지 않은 답에는 질문 하나가 붙는다(ingest.questions) — 그래서 pending 은 비지 않고 **그 새 물음**으로 바뀐다
    assert "하나 물을 것 — " in r2["text"] and asks.pending(SID)["msg"] == r2["id"] and asks.pending(SID)["axes"] == ["soil_water"]
    m3, _ = chat.send(SID, "풀 뽑았다", today=TODAY, now=NOW)                   # 그 다음 말은 새 물음 뒤다 — precip 의 답 수는 그대로
    assert m3["after_ask"]["msg"] == r2["id"] and row["replies"] == 1 == next(x for x in asks.for_subject(SID) if x["axis"] == "precip")["replies"]


# ── answer 는 안 센다(자기 점검의 길) ──
def test_answer_alone_writes_nothing():
    s = _subject()
    for _ in range(3):
        text, asked = chat.answer_with_asks(s, Q, TODAY)
        assert asked and asked[0]["axis"] == "precip" and chat.answer(s, Q, TODAY) == text
    assert not asks.path().exists() and asks.pending(SID) is None and asks.for_subject(SID) == []


def test_the_ledger_is_only_written_from_send():
    """호출형 래칫 — record · mark_replied 를 부르는 자리는 chat.send 본문뿐(answer 쪽에 붙으면 자기 점검이 쓴다)."""
    src = (ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")
    body = src[src.index("\ndef send("):]
    body = body[:body.index("\ndef ", 10)]
    for call in ("asks.record(", "asks.mark_replied("):
        assert src.count(call) == 1 and call in body, call
    ans = src[src.index("\ndef answer_with_asks("):]
    ans = ans[:ans.index("\ndef ", 10)]
    assert "asks." not in ans


# ── 실패는 답을 막지 않되 보이게 ──
def test_a_broken_ledger_does_not_block_the_reply_but_is_visible():
    asks.path().parent.mkdir(parents=True, exist_ok=True)
    asks.path().write_text("{not json", encoding="utf-8")
    dropped.clear()
    _, r = chat.send(SID, Q, today=TODAY, now=NOW)
    assert r["text"].startswith(f"[{words.said('판단 불가(데이터)')}]")        # 답은 나갔다
    assert any(d["where"] == asks.DROP_WHERE and "asks.json" in d["path"] for d in dropped.all_drops())
    assert asks.path().read_text(encoding="utf-8") == "{not json"           # 깨진 파일을 덮어쓰지 않는다(고치면 바로 읽힌다)
    m2, _ = chat.send(SID, "어제 비가 왔다", today=TODAY, now=NOW)            # 답 쪽도 같다
    assert "after_ask" not in m2


# ── 화면 ──
def test_the_panel_shows_what_was_asked_in_farmer_words():
    s = _subject()
    assert "물은 것" not in chat_pages.thread_panel(s, TODAY)
    chat.send(SID, Q, today=TODAY, now=NOW)
    chat.send(SID, Q, today=TODAY, now=NOW)
    html = chat_pages.thread_panel(s, TODAY)
    visible = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html))              # 태그를 걷으면 공백이 겹친다 — 사람이 보는 글자만
    assert "물은 것 1" in visible, visible[:600]
    assert f"{words.axis('precip')} 2번" in visible and 'title="precip"' in html
    assert " precip " not in visible                                           # 정확한 축 이름은 title 에만
    asks.path().write_text("[]", encoding="utf-8")
    assert "물은 것을 못 읽었다" in chat_pages.thread_panel(s, TODAY)


def test_the_ledger_file_lives_in_the_chat_folder_and_is_json_with_two_keys():
    chat.send(SID, Q, today=TODAY, now=NOW)
    assert asks.path().parent == chat.chat_dir()
    doc = json.loads(asks.path().read_text(encoding="utf-8"))
    assert set(doc) == {"asks", "pending"} and set(doc["asks"]) == {f"{SID}|precip"}
