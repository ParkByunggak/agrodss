# -*- coding: utf-8 -*-
# [발행자 진단 2026-10-04] *"내부 정합성은 높다 — 관문이 파일끼리 맞는지를 본다. 그런데 밭과 맞는지는 아무도 안 본다 … 세 경우 다 정보가 시스템 안에 있는데 답에 안 쓰였고,
# 그러고 나서 시스템은 그 정보를 또 묻는다 … 처방은 하나 — 묻기 전에 원장을 먼저 읽는 규칙, 한 곳에서. 검사도 바뀌어야 한다 — '원장에 값이 있는데 판정이 묻는다' 를
# 붉게 만드는 검사. 어제 세 건은 전부 그 한 검사의 첫 표본이다."*
#
#   거꾸로 센다 — 원장에 넣은 것이 답에 나오는가. 표본 셋(발행자 10-03~04 실사용):
#     ① 관수 사건을 원장에 넣으면 가뭄 답의 「마지막 비·관수」 가 그 날이다            (사건 → 판정 — 길은 있었다 · 넣기 전 초안은 「넣지 않은 기록 N건」 으로 보인다)
#     ② 배수 관찰을 일지에 넣으면 배수를 **묻지 않고** 밭 정보 초안(배수 → 좋음)이 선다  (관찰 → 속성 — 길이 없었다 · 발행자가 배수를 적었는데 배수를 물었다)
#     ③ 용도 선언이 일지에 있으면 용도 초안(종구 생산)이 선다 · 넣으면 재배 달력이 종구 기준 (관찰 → 속성 → 판정 — 길이 없었다 · 채팅은 결정을 몰랐다)
#   그리고 정본은 한 곳(ingest.known) — 질문 생성이 그 앞을 지나고(값을 읽으면 묻지 않는다 · 언급만이면 그 줄을 들고 묻는다), 등록부에는 쓰지 않는다(초안 → 확인).
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from frontend import words
from grid import schema as grid_schema
from ingest import asks, chat, dropped, events as ev, known, media, parcels, questions
from judge import run as judge_run
from tests.test_screen_speaks_plainly import JARGON

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
T34 = date(2026, 9, 28)
NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)
DRAIN_LINE = "밭에 나가 확인하니 고랑 물 빠짐이 잘 되고 있고, 잎 끝 황화 현상은 더 진행이 되지 않음이 확인이 되었다."
USE_LINE = "이 쪽파는 종구생산을 위한 목적이다"


def _s():
    return parcels.enrich_subject(next(s for s in media.load_subjects() if s["id"] == SID), parcels.by_id("p001"))


def _question_in(reply: str) -> str:
    return reply.split("하나 물을 것")[1] if "하나 물을 것" in reply else ""


# ── 정본 하나 — 세 층을 순서대로 ───────────────────────────────────────────────────────
def test_known_reads_attribute_first_then_the_diary_and_reads_a_value_only_when_one_word_fits():
    s = _s()
    assert known.known_field(s, "drainage") is None                                      # 속성도 일지도 없다
    ev.add_observation(SID, "고랑에 물이 좀 있다", "2026-09-26")                           # 언급만(값 못 읽음)
    k = known.known_field(s, "drainage")
    assert k and k["from"] == "observation" and k["value"] is None and k["observed_at"] == "2026-09-26"
    ev.add_observation(SID, DRAIN_LINE, "2026-09-27")                                    # 더 새 관찰 — 값이 읽힌다
    k = known.known_field(s, "drainage")
    assert k["value"] == "좋음" and k["observed_at"] == "2026-09-27" and DRAIN_LINE[:20] in k["text"]
    parcels.set_fields("p001", drainage="나쁨", overwrite=True)
    assert known.known_field(_s(), "drainage") == {"from": "attribute", "field": "drainage", "value": "나쁨"}   # 속성이 먼저
    assert known.value_in("drainage", "물이 고이지 않는다") is None                       # 좋음·나쁨 말이 둘 다 — 값으로 읽지 않는다(지어내지 않는다)
    assert known.value_in("drainage", "비 온 뒤 고랑에 물이 고인다") == "나쁨" and known.value_in("drainage", "배수는 보통") == "보통"
    assert known.value_in("use", USE_LINE) == "종구 생산" and known.value_in("use", "종구가 썩은 것 같다") is None


# ── 표본 ② 배수 — 일지에 있으면 묻지 않고 초안으로 ─────────────────────────────────────
def test_a_drainage_observation_in_the_diary_stops_the_question_and_raises_a_parcel_draft():
    m0, r0 = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    assert "배수(좋음 · 보통 · 나쁨 중 하나)" in _question_in(r0["text"])              # 일지가 비었을 때는 묻는다(기준선)
    assert all(d["kind"] != "parcel.field" for d in m0["drafts"])
    m1, _ = chat.send(SID, DRAIN_LINE, today=T34, now=NOW)                               # 발행자 10-03 일지 문장 → 본 것 → 넣기
    assert m1["drafts"][0]["kind"] == "observation.note"
    chat.confirm(m1["id"], 0, now=NOW)
    m2, r2 = chat.send(SID, "트랩 확인했다", today=T34, now=NOW)
    assert "배수" not in _question_in(r2["text"])                                        # 일지에 있다 — 묻지 않는다
    prop = next(d for d in m2["drafts"] if d["kind"] == "parcel.field")
    assert prop["field"] == "drainage" and prop["value"] == "좋음" and prop["why_key"] == "from_diary" and prop["parcel"] == "p001" and prop["observed_at"] == T34.isoformat()
    assert chat.plain_why(prop).startswith("일지에 이미 적힌 말에서 읽었습니다") and not [w for w in JARGON if w in chat.plain_why(prop)]
    assert parcels.by_id("p001").get("drainage") is None                                 # 등록부엔 안 썼다 — 초안이다
    m3, _ = chat.send(SID, "예찰했다", today=T34, now=NOW)
    assert all(d["kind"] != "parcel.field" for d in m3["drafts"])                        # 같은 초안이 서 있으면 다시 안 올린다
    rec = chat.confirm(m2["id"], [d["kind"] for d in m2["drafts"]].index("parcel.field"), now=NOW)
    assert rec["kind"] == "parcel" and parcels.by_id("p001")["drainage"] == "좋음"
    ra = next(e for e in judge_run.judgments_for(SID, today=T34) if e.decision_id == "risk_alert")
    wet = next(a for a in ra.result["alerts"] if "과습" in a["risk"])
    assert wet.get("drainage") == "좋음" and "배수 좋음" in wet["basis"] and "needs" not in wet   # 넣으니 판정이 읽는다 — 더 묻을 것이 없다
    _, r4 = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    assert "배수" not in _question_in(r4["text"])


def test_a_mention_without_a_readable_value_still_asks_but_carries_the_diary_line():
    ev.add_observation(SID, "고랑에 물이 좀 있다", "2026-09-26")
    _, r = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    q = _question_in(r["text"])
    assert "배수(좋음 · 보통 · 나쁨 중 하나) — 일지 2026-09-26 「고랑에 물이 좀 있다」 를 봤습니다, 어느 쪽인지" in q   # 되묻지 않고 그 줄을 들고 묻는다


# ── 표본 ③ 용도 — 일지의 선언이 속성과 다르면 초안 · 넣으면 재배 달력이 종구 기준 ─────────
def test_a_use_declaration_already_in_the_diary_raises_a_use_draft_and_confirming_switches_the_calendar():
    assert parcels.by_id("p001")["use"] == "시험 재배(자가)" and grid_schema.use_key(parcels.by_id("p001")["use"]) is None
    ev.add_observation(SID, USE_LINE, "2026-10-04")                                      # 라이브 그대로 — 이미 관찰로 들어가 있다(obs_…)
    m, r = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    prop = next(d for d in m["drafts"] if d["kind"] == "parcel.field")
    assert prop["field"] == "use" and prop["value"] == "종구 생산" and prop["why_key"] == "from_diary"
    rec = chat.confirm(m["id"], m["drafts"].index(prop), now=NOW)
    assert rec["opens"] == ["ship_or_store"] and "종구 기준으로 읽습니다" in rec["opens_line"]
    assert grid_schema.use_key(parcels.by_id("p001")["use"]) == "종구"
    envs = {e.decision_id: e for e in judge_run.judgments_for(SID, today=date(2026, 10, 19))}   # 55일째 — 수확 칸
    assert envs["ship_or_store"].kind == "해당 없음" and envs["risk_alert"].result.get("use_gap_stages")   # 결정이 채팅 길로 판정까지 닿았다
    m2, _ = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    assert all(d["kind"] != "parcel.field" for d in m2["drafts"])                        # 이미 그 용도 — 다시 안 올린다


def test_saying_the_use_in_chat_is_a_parcel_draft_not_an_observation():
    """같은 결함의 입구 쪽 — 채팅으로 들어오는 용도 선언은 처음부터 밭 정보 초안이다(관찰 원장으로 가서 다시 읽히는 길을 돌지 않는다)."""
    m, r = chat.send(SID, USE_LINE, today=T34, now=NOW)
    d = m["drafts"][0]
    assert d["kind"] == "parcel.field" and d["field"] == "use" and d["value"] == "종구 생산" and d["parcel"] == "p001" and d["why_key"] == "use_declared"
    assert "본 것이 아닙니다" in r["text"] and "밭 정보에 들어갑니다" in r["text"] and "재배 달력도 종구 기준으로 읽습니다" in r["text"]
    assert chat.classify(USE_LINE, T34)[0]["parcel"] is None                             # 재배 단위 없이 나누면 어느 밭인지 비어 있다 — send 가 채운다
    fake = {"id": "x", "grid_unit": "jjokpa-autumn"}                                      # 필지 없는 재배 단위 — 지어내지 않고 관찰 메모로(보이게)
    assert chat.classify(USE_LINE, T34, subject=fake)[0]["kind"] == "observation.note"


# ── 표본 ① 관수 — 사건은 판정이 원장에서 읽는다(길은 있었다) · 넣기 전은 보인다 ─────────────
def test_an_irrigation_event_in_the_ledger_is_the_last_wet_day_and_an_unconfirmed_one_is_named():
    T = date(2026, 10, 3)
    m, _ = chat.send(SID, "9월 25일에 관수했다", today=T, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)
    chat.send(SID, "오늘 물 줬다", today=T, now=NOW)                                       # 초안만
    dr = chat.answer(_s(), "가뭄이 심한데 물 줘야 하나요", T)
    assert "마지막 비·관수 2026-09-25" in dr and "아직 일지에 넣지 않은 관수 기록 1건" in dr
    m2 = next(x for x in chat.list_messages(SID) if x["text"] == "오늘 물 줬다")
    chat.confirm(m2["id"], 0, now=NOW)
    assert "2026-10-03(관수)" in chat.answer(_s(), "가뭄이 심한데 물 줘야 하나요", T)       # 넣으면 그 날이다


# ── 전수 — 농가 몫 요구 축마다 「넣으면 안 묻는가」 (발행자 "하나씩 고치면 다음 주에 넷째 다섯째가 또 나온다") ───────────────────────
# 요구 문장 전수(judge/*.py 의 need(… "농가" …)): 심은 날(anchor) · 인증(cert) · 납품 계획일(plan.target_date) · 본 것(observation — 보식·증상) · 마지막 비/관수(precip) ·
# 배수(drainage · 경보 needs) — 여기 전부. 용도는 묻지 않는 값(선언만)이라 위 표본으로. 각각: 비어서 묻는 것을 먼저 보고(기준선), 원장·속성에 넣은 뒤 그 축의 질문이 없음을 본다.
import pytest
from ingest import subjects


def _axes(sid: str, s: dict, today: date) -> set[str]:
    return {q["axis"] for q in questions.candidates(judge_run.judgments_for(sid, today=today), subject=s)}


def _subject(sid: str) -> dict:
    return parcels.enrich_subject(subjects.by_id(sid), parcels.by_id("p001"))


def _new_subject(**kw) -> str:
    """심은 날·인증이 없는 계획 재배 단위 — 같은 필지의 다른 작기(기본값 없음 · 지어내지 않는다)."""
    return subjects.add("쪽파", "2027 가을", status="계획", parcel="p001", **kw)["id"]      # 가을 — 재배 달력이 있어야 심은 날을 묻는다(봄은 달력이 없어 지식 쪽으로 간다)


@pytest.mark.parametrize("axis, put_in", [
    ("anchor", lambda sid, T: (lambda m: chat.confirm(m["id"], 0, now=NOW))(chat.send(sid, "8월 25일에 심었다", today=T, now=NOW)[0])),
    ("cert", lambda sid, T: (lambda m: chat.confirm(m["id"], 0, now=NOW))(chat.send(sid, "이 밭은 유기 인증을 받았다", today=T, now=NOW)[0])),
])
def test_a_planned_subject_stops_asking_an_axis_once_the_ledger_has_it(axis, put_in):
    sid = _new_subject()
    assert axis in _axes(sid, _subject(sid), T34), f"{axis}: 비어 있는데 묻지 않는다 — 기준선이 아니다"
    rec = put_in(sid, T34)
    assert rec.get("opens") and rec.get("opens_line", "").startswith("이것으로 ")                      # §12 — 넣은 직후 연 판단을 말한다
    s2 = _subject(sid)
    assert (s2.get("anchor") == "2026-08-25") if axis == "anchor" else (s2.get("cert") == "유기")
    assert axis not in _axes(sid, s2, T34), f"{axis}: 원장에 있는데 묻는다"


def test_target_date_observation_and_last_wet_day_stop_their_questions_once_in_the_ledger():
    parcels.set_fields("p001", use="판매", mall_supply=True, overwrite=True)           # 출하 결정을 열어 납품 계획일을 묻게 한다
    s = _s()
    assert "plan.target_date" in _axes(SID, s, T34)
    m, _ = chat.send(SID, "10월 30일 납품 예정", today=T34, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)
    assert "plan.target_date" not in _axes(SID, _s(), T34)
    T5 = date(2026, 8, 30)                                                              # 5일째 — 보식 창 · 난 상태를 묻는다
    assert "observation" in _axes(SID, _s(), T5)
    m, _ = chat.send(SID, "듬성듬성 났다", today=T5, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)
    assert "observation" not in _axes(SID, _s(), T5)
    # [전수에서 나온 것] 증상 결정은 증상 관찰이 없으면 「본 것을 한 줄 적어 주시면 원인을 좁힙니다」 를 요구 문장으로 냈고, 그것이 **아무 일도 없는 밭에** 질문으로 나갔다 —
    # 보이면 적는 것이지 묻는 값이 아니다(§3 "판정이 못 실은 값" 이 아니다). 카드에는 남되 답 끝 질문은 되지 않는다(judge.need ask=False).
    st = next(e for e in judge_run.judgments_for(SID, today=T5) if e.decision_id == "symptom_triage")
    assert st.kind == "판단 불가(데이터)" and st.missing and st.missing[0].get("ask") is False
    assert "observation" not in _axes(SID, _s(), T5)
    parcels.set_fields("p001", drainage="좋음", overwrite=True)                          # 배수가 비면 그 질문이 먼저라 비·관수 물음이 가려진다
    assert "precip" in _axes(SID, _s(), T34)
    m, _ = chat.send(SID, "9월 26일에 물 줬다", today=T34, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)
    assert "precip" not in _axes(SID, _s(), T34)


def test_a_cert_declaration_in_the_diary_raises_a_subject_draft_and_confirming_opens_the_material_judgments():
    sid = _new_subject()
    assert "cert" in _axes(sid, _subject(sid), T34)                                     # 기준선 — 비어 있으면 묻는 후보다(답 끝에는 하나만 붙으므로 후보 목록으로 본다)
    ev.add_observation(sid, "인증은 무농약이다", "2026-10-04")                             # 이미 관찰로 들어가 있다(용도와 같은 라이브 형태)
    assert "cert" not in _axes(sid, _subject(sid), T34)                                 # 일지에 있다 — 묻지 않는다(주입 B 가 처음엔 안 잡혔다 — 답 끝 한 줄만 봐서)
    m, r = chat.send(sid, "풀 뽑았다", today=T34, now=NOW)
    prop = next(d for d in m["drafts"] if d["kind"] == "subject.field")
    assert prop["field"] == "cert" and prop["value"] == "무농약" and prop["why_key"] == "from_diary" and prop["subject"] == sid
    assert "인증" not in _question_in(r["text"])
    rec = chat.confirm(m["id"], m["drafts"].index(prop), now=NOW)
    assert rec["kind"] == "subject" and subjects.by_id(sid)["cert"] == "무농약" and rec["opens"] == ["material_citation", "base_fertilization"]
    assert "자재 인용 · 밑거름" in rec["opens_line"] and "인증 값 '무농약' 을 읽습니다" in rec["opens_line"]
    m2, r2 = chat.send(sid, "인증은 유기다", today=T34, now=NOW)                          # 선언은 처음부터 농사 값 초안
    assert m2["drafts"][0]["kind"] == "subject.field" and m2["drafts"][0]["value"] == "유기" and "이 농사의 정보에 들어갑니다" in r2["text"]
    with pytest.raises(subjects.SubjectError):
        subjects.set_cert(sid, "GAP")                                                   # 어휘 밖은 등록부가 막는다
    assert subjects.cert_declared("유기질 비료를 줬다") is None and subjects.cert_declared("유기 인증과 무농약 둘 다") is None


# ── 래칫 — 정본 하나 · 질문은 그 앞을 지난다 · 쓰는 자리 0 ────────────────────────────
def test_every_question_passes_the_known_gate_and_known_never_writes():
    qsrc = (ROOT / "ingest" / "questions.py").read_text(encoding="utf-8")
    body = qsrc[qsrc.index("def _parcel_question"):qsrc.index("\ndef ", qsrc.index("def _parcel_question") + 10)]
    assert "known.known_field(" in body and "return None" in body                       # 값을 읽으면 묻지 않는다
    csrc = (ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")
    send = csrc[csrc.index("def send("):csrc.index("\ndef ", csrc.index("def send(") + 10)]
    assert "known.proposals(" in send and "questions.top(" in send and "subject=s" in send   # 초안을 올리고 · 질문 생성에 재배 단위를 넘긴다
    ksrc = (ROOT / "ingest" / "known.py").read_text(encoding="utf-8")
    assert "set_fields(" not in ksrc and "_append(" not in ksrc and "write_text(" not in ksrc   # 읽기만 — 등록부·원장에 쓰지 않는다
    assert known.proposals({"id": SID}, parcels.FIELDS_READ_BY_JUDGMENT) == []          # 필지 없는 재배 단위엔 올리지 않는다
    for text in (chat.PLAIN_BY_KEY["from_diary"], chat.PLAIN_BY_KEY["use_declared"]):
        assert not [w for w in JARGON if w in text], text and words.plain(text) == text
