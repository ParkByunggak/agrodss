# -*- coding: utf-8 -*-
# [WO-ASK-01 §9 · 2026-10-03] 답이 올 때 그 축의 초안 — 물음이 필지 값(배수)을 겨냥했고 물은 뒤 처음 온 말에 등록부 어휘(좋음 · 보통 · 나쁨)가
# 있으면 **필지 초안**(parcel.field)을 맨 앞에 둔다. 등록부에 바로 쓰지 않는다 — 다른 초안과 같은 길(확인 → parcels.set_fields). 어휘가 없으면 초안을
# 안 짓고(지어내지 않는다), 물음 없이 온 「나쁨」 은 아무것도 아니다. 확인되면 과습 경보의 근거가 그 값을 읽고 다음 질문은 다음 후보로 넘어간다.
from __future__ import annotations

import re
from datetime import date, datetime, timezone

import pytest

from frontend import chat_pages
from ingest import asks, chat, dropped, media, parcels, questions
from judge import run as judge_run

SID = "p001-jjokpa-2026f"
T34 = date(2026, 9, 28)
NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)


def _ask_drainage():
    """스스로 묻지 않은 답 하나 → 질문 생성이 배수를 묻는다(회복 불가 1순위)."""
    _, r = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    assert "배수(좋음 · 보통 · 나쁨 중 하나)" in r["text"] and asks.pending(SID)["fields"] == ["drainage"]
    return r


def test_the_answer_to_the_drainage_question_becomes_a_parcel_draft_not_a_note():
    r = _ask_drainage()
    m, r2 = chat.send(SID, "나쁨", today=T34, now=NOW)
    d = m["drafts"][0]
    assert d["kind"] == "parcel.field" and d["field"] == "drainage" and d["value"] == "나쁨" and d["parcel"] == "p001" and d["why_key"] == "answers_ask"
    assert [x["kind"] for x in m["drafts"]] == ["parcel.field"]                      # 「나쁨」 한 토막이 '본 것' 으로도 서지 않는다
    assert m["after_ask"]["msg"] == r["id"]
    assert "밭 정보에 들어갑니다" in r2["text"] and "배수: 나쁨" in r2["text"] and "영농일지" not in r2["text"].split("하나 물을 것")[0]
    assert parcels.by_id("p001").get("drainage") is None                            # 아직 안 썼다 — 확인 전


def test_confirming_the_draft_writes_the_parcel_and_the_wet_risk_reads_it_and_the_question_moves_on():
    _ask_drainage()
    m, _ = chat.send(SID, "배수는 나쁨이에요", today=T34, now=NOW)
    rec = chat.confirm(m["id"], 0, now=NOW)
    assert rec["id"] == "parcel:p001:drainage" and rec["kind"] == "parcel" and parcels.by_id("p001")["drainage"] == "나쁨"
    saved = next(x for x in chat.list_messages(SID) if x["id"] == m["id"])
    assert saved["drafts"][0]["confirmed_ref"] == rec["id"]
    ra = next(e for e in judge_run.judgments_for(SID, today=T34) if e.decision_id == "risk_alert")
    wet = next(a for a in ra.result["alerts"] if "과습" in a["risk"])
    assert wet["drainage"] == "나쁨" and "배수 나쁨" in wet["basis"] and wet["level"] == "주의"       # 등급은 그대로(D-23 전)
    _, r3 = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    assert "배수" not in r3["text"].split("하나 물을 것")[1] and "마지막으로 비 온 날" in r3["text"]   # 다음 후보
    with pytest.raises(chat.ChatError):
        chat.confirm(m["id"], 0, now=NOW)                                                            # C7 — 초안당 한 번


def test_a_reply_without_the_vocabulary_binds_nothing_and_a_value_without_a_question_binds_nothing():
    _ask_drainage()
    m, _ = chat.send(SID, "비가 많이 왔다", today=T34, now=NOW)
    assert all(d["kind"] != "parcel.field" for d in m["drafts"]) and m["after_ask"]["axes"] == ["soil_water"]
    m2, _ = chat.send(SID, "좋음 보통 나쁨 다 아니다", today=T34, now=NOW)         # 어휘가 둘 이상 — 고르지 않는다
    assert all(d["kind"] != "parcel.field" for d in m2["drafts"])
    # 물음이 없는데 온 「나쁨」 — 아무 물음의 답도 아니다(pending 이 없다)
    asks.path().unlink()
    m3, _ = chat.send(SID, "나쁨", today=T34, now=NOW)
    assert all(d["kind"] != "parcel.field" for d in m3["drafts"]) and "after_ask" not in m3


def test_a_field_no_judgment_reads_is_never_bound_even_if_asked(monkeypatch):
    """§5-1 은 여기서도 선다 — 물음 기록이 소비자 0 인 값을 겨냥했어도(앞으로의 결함) 초안을 짓지 않고 그 사실을 남긴다."""
    dropped.clear()
    s = media.load_subjects()[0]
    out = chat._drafts_from_answer(s, "경사는 급경사", {"axes": ["soil_water"], "fields": ["slope"]})          # [2026-10-04] 필지 값 · 농사 값 한 자리로 — 물음 기록(pend) 을 그대로 받는다
    assert out == [] and any(d["where"] == asks.DROP_WHERE and d["path"].endswith("/slope") for d in dropped.all_drops())
    assert [d["field"] for d in chat._drafts_from_answer(s, "배수 보통", {"axes": ["soil_water"], "fields": ["drainage"]})] == ["drainage"]


def test_the_card_shows_the_value_in_farmer_words_and_no_date_box():
    _ask_drainage()
    m, _ = chat.send(SID, "나쁨", today=T34, now=NOW)
    html = chat_pages._draft_html(m, 0, m["drafts"][0])
    visible = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html))
    assert "밭 정보" in visible and "배수 → 나쁨" in visible and 'name="day"' not in html and chat.confirm_label("parcel.field") in html   # [2026-10-04] 단추 말도 가는 자리대로(일지가 아니다)
    assert " drainage " not in visible and 'title="drainage"' in html


def test_kinds_and_plain_words_stay_one_set():
    assert "parcel.field" in chat.KIND_PLAIN and set(chat.KIND_PLAIN) == set(chat.KIND_LABEL) and "answers_ask" in chat.PLAIN_BY_KEY
    assert "parcel.field" not in dict(chat_pages.CHOOSABLE)            # 사람이 아무 말에 '밭 정보' 를 고르지는 못한다 — 물음에 대한 답에서만 선다
