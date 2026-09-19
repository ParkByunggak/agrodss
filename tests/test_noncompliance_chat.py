# -*- coding: utf-8 -*-
# [발행자 2026-09-20 "쪽파 포장에는 웃거름 주지 않고 수분공급만 표면이 마르지 않게 해 줌. 그 근거는 토양검증 상태를 기준으로 함"]
# 사건 어휘 + 부정 = 불이행 사유(사건이 아니다). 발행자: "쪽파는 하나의 사례 — 같은 유형의 작목 전부에 적용되는 로직" →
#   작업 종류는 EVENT_SYNONYMS(작목 공통) · 계획 작업명·계획일은 그 재배 단위의 계획표(격자)에서 잇는다 · 판정은 계획 대 실제와 단계 결정이
#   같은 키(작업명 · 계획일)로 본다. 여기서는 웃거름(시비)과 제초 두 종류로 잰다 — 한 종류만 통과하면 쪽파 전용 분기가 숨을 수 있다.
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from frontend import chat_pages
from ingest import chat, events as ev, media, parcels
from judge import plan_vs_actual, run as judge_run, stage_decisions as SD

SID = "p001-jjokpa-2026f"
T = date(2026, 9, 19)
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)
SENTENCE = "쪽파 포장에는 웃거름 주지 않고 수분공급만 표면이 마르지 않게 해 줌. 그 근거는 토양검증 상태를 기준으로 함"
ROOT = Path(__file__).resolve().parent.parent


def _subject():
    raw = [s for s in media.load_subjects() if s["id"] == SID][0]
    return parcels.enrich_subject(raw, parcels.by_id("p001"))


def test_negated_task_is_noncompliance_not_event_and_practice_becomes_optional_note():
    d = chat.classify(SENTENCE, T)
    assert [x["kind"] for x in d] == ["decision.noncompliance", "observation.note"]
    assert d[0]["task_type"] == "시비" and d[0]["reason"] == SENTENCE and d[0]["needs"] == ["planned_day"]   # 분류기는 재배 단위를 모른다
    assert d[1]["text"] == SENTENCE and "선택" in d[1]["why"]
    assert chat.classify("방제는 하지 않았다, 벌레가 없어서", T)[0]["task_type"] == "방제"
    assert [x["kind"] for x in chat.classify("제초 생략했다", T)] == ["decision.noncompliance"]        # '했다' 어미는 대신 한 일이 아니다
    assert ev.list_records(SID) == []                                                                  # 분류는 원장에 안 쓴다


def test_send_attaches_plan_row_of_this_subject_for_any_task_type():
    m, r = chat.send(SID, SENTENCE, today=T, now=NOW)
    d = m["drafts"][0]
    assert d["planned_task"] == "웃거름 1회" and d["planned_day"] == "2026-09-16" and d["needs"] == [] and "계획표" in d["why"]
    assert "불이행 사유" in r["text"] and "초안 1) 불이행 사유 · 2) 관찰" in r["text"]
    m2, _ = chat.send(SID, "제초 생략했다", today=T, now=NOW)                    # 다른 종류 — 같은 로직이 그 종류의 계획표 줄을 찾는다
    assert m2["drafts"][0]["planned_task"] == "제초" and m2["drafts"][0]["planned_day"] == "2026-09-14"
    m3, _ = chat.send(SID, "약 안 쳤다", today=T, now=NOW)                        # 계획표에 방제 줄이 없다 — 지어내지 않고 계획일을 묻는다
    assert m3["drafts"][0]["planned_task"] == "방제" and m3["drafts"][0]["needs"] == ["planned_day"]


def test_confirm_each_draft_once_and_judgments_read_the_reason_before_deadline():
    m, _ = chat.send(SID, SENTENCE, today=T, now=NOW)
    rec = chat.confirm(m["id"], 0, now=NOW)
    assert rec["kind"] == "decision.noncompliance" and rec["planned_task"] == "웃거름 1회" and rec["planned_day"] == "2026-09-16"
    with pytest.raises(chat.ChatError, match="이미 확인된 초안"):
        chat.confirm(m["id"], 0, now=NOW)                                       # C7 — 초안당 한 번
    assert chat.pending_drafts(SID) and chat.pending_drafts(SID)[0][1] == 1     # 둘째 초안은 아직 열려 있다
    note = chat.confirm(m["id"], 1, now=NOW)
    assert note["kind"] == "observation.note" and chat.pending_drafts(SID) == []
    mm = chat.get_message(m["id"])
    assert mm["confirmed_refs"] == [rec["id"], note["id"]] and [x["confirmed_ref"] for x in mm["drafts"]] == [rec["id"], note["id"]]
    # 3층 — 마감(09-24) 전인데도 '미이행'이 아니라 '사유 기록됨'. 단계 결정과 계획 대 실제가 같은 줄을 같은 상태로 본다
    e = SD.judge_top_dressing(_subject(), "top_dressing_1", T, evts=ev.list_records(SID))
    assert e.result["status"] == "사유 기록됨" and e.result["reason_ref"] == rec["id"] and "사유: 쪽파 포장에는" in e.result["summary"]
    p = next(x for x in judge_run.judgments_for(SID, today=T) if x.decision_id == "plan_vs_actual")
    row = next(r for r in p.result["rows"] if r["task"] == "웃거름 1회")
    assert row["status"] == "사유 기록됨" and row["evidence"] == SENTENCE and p.result["counts"]["사유 기록됨"] == 1
    assert p.result["counts"]["미이행"] == 3                                        # 전에는 4 (T+25 실측 대장: 미이행 4)


def test_legacy_message_level_confirmation_still_refuses_and_choose_kind_paths():
    m, _ = chat.send(SID, "오늘 물 줬다", today=T, now=NOW)
    rec = chat.confirm(m["id"], 0, now=NOW)
    old = dict(chat.get_message(m["id"]))
    old["drafts"] = [{k: v for k, v in d.items() if k != "confirmed_ref"} for d in old["drafts"]]   # 표지 없는 옛 기록 형태
    assert chat.confirmed_ref(old, 0) == rec["id"]
    m2, _ = chat.send(SID, "특별한 일 없음", today=T, now=NOW)
    assert chat.choose_kind(m2["id"], "observation.note", today=T)["drafts"][0]["observed_at"] == T.isoformat()   # 전에는 NameError
    d = chat.choose_kind(m2["id"], "decision.noncompliance", today=T)["drafts"][0]
    assert d["kind"] == "decision.noncompliance" and d["needs"] == ["planned_day"]
    assert ("decision.noncompliance", "불이행 사유") in chat_pages.CHOOSABLE


def test_screen_renders_each_draft_and_planned_task_input():
    m, _ = chat.send(SID, SENTENCE, today=T, now=NOW)
    h0, h1 = chat_pages._draft_html(m, 0, m["drafts"][0]), chat_pages._draft_html(m, 1, m["drafts"][1])
    assert 'name="planned_task" value="웃거름 1회"' in h0 and 'value="2026-09-16"' in h0 and "불이행 사유" in h0
    assert 'name="planned_task"' not in h1 and 'name="i" value="1"' in h1
    chat.confirm(m["id"], 0, now=NOW)
    m = chat.get_message(m["id"])
    assert "원장에 들어감" in chat_pages._draft_html(m, 0, m["drafts"][0]) and "원장에 들어감" not in chat_pages._draft_html(m, 1, m["drafts"][1])


def test_wiring_ratchets_no_crop_branch_and_one_key():
    src = (ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")
    body = src[src.index("def _negated_task"):src.index("def _damage_risk")]
    assert "쪽파" not in body and "웃거름" not in body and "EVENT_SYNONYMS" in body               # 작목 · 작업 리터럴 없음 — 공통 어휘로만
    send = src[src.index("def send("):src.index("def request_improvement")]
    assert "_attach_plan(subject_id, classify(" in send                                            # 계획표 잇기가 send 경로에 있다
    conf = src[src.index("def confirm("):src.index("def confirmed_ref(")]
    assert "confirmed_ref(m, draft_index)" in conf and "ev.add_noncompliance(" in conf
    sd = (ROOT / "judge" / "stage_decisions.py").read_text(encoding="utf-8")
    td = sd[sd.index("def judge_top_dressing"):sd.index("def judge_ship_or_store")]
    assert "plan_vs_actual.reason_for(" in td                                                       # 단계 결정도 같은 키 함수
    pva = (ROOT / "judge" / "plan_vs_actual.py").read_text(encoding="utf-8")
    j = pva[pva.index("def judge("):]
    assert j.index("reason_for(reasons") < j.index('status = "예정"')                              # 사유가 예정·미이행보다 먼저
    assert re.search(r"def reason_for\(reasons.*task.*work_date", pva)
