# -*- coding: utf-8 -*-
# [M-10 결정 등록] 격자가 선언한 결정 전부가 등록부에 있고 축이 맞는다 · 8 결정의 정직한 산출(해당 없음 / 지식 / 데이터 / 판단함) ·
#        시비 사건이 웃거름 상태를 바꾼다 · D-8 자가는 출하 결정 대상 아님 · 채팅 질문이 구체 결정으로 간다.
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from grid import schema as grid_schema
from ingest import chat, events as ev, media, parcels
from judge import registry, run as judge_run, stage_decisions as SD

_RAW = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
SUBJ = parcels.enrich_subject(_RAW, parcels.by_id("p001"))     # run.py 와 같은 병합 — 용도(D-8 자가)가 붙는다
SID = SUBJ["id"]
T25 = date(2026, 9, 19)          # 기준점 2026-08-25 + 25
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def _by(envs):
    return {e.decision_id: e for e in envs}


# ── 등록부 완전성 ───────────────────────────────────────────────────────────────────
def test_every_grid_decision_is_registered_and_consistent():
    unit = grid_schema.load_unit(SUBJ)[0]
    declared = {d for s in unit["stages"] for d in (s.get("decisions") or [])}
    assert declared == set(SD.IDS) | {"harvest_timing"}
    for s in unit["stages"]:
        for did in s.get("decisions") or []:
            d = registry.get(did)
            assert d is not None, f"격자가 선언한 결정 {did} 가 등록부에 없다"
            assert registry.check_against_grid(d, s) == [], did
            assert d.rule.strip() and d.required_axes and "humidity_air" in d.forbidden_axes


def test_registry_refuses_decision_without_rule_or_axes():
    with pytest.raises(registry.RegistrationError):
        registry.register(registry.Decision(id="x", name="x", required_axes=(), optional_axes=(), forbidden_axes=(), rule="r", revisit_days=None))
    with pytest.raises(registry.RegistrationError):
        registry.register(registry.Decision(id="x", name="x", required_axes=("anchor",), optional_axes=(), forbidden_axes=(), rule="  ", revisit_days=None))


# ── 산출 ────────────────────────────────────────────────────────────────────────
def test_first_farm_at_t25_kinds_are_honest():
    envs = _by(SD.judge_all(SUBJ, T25))
    assert set(envs) == set(SD.IDS)
    assert envs["sowing_window"].kind == "해당 없음" and "이미 파종" in envs["sowing_window"].result["why"]
    assert envs["base_fertilization"].kind == "해당 없음"
    assert envs["replant"].kind == "해당 없음"
    assert envs["pest_alert"].kind == "판단함" and all(a["stage"].startswith("3.") for a in envs["pest_alert"].result["alerts"])
    assert envs["top_dressing_1"].kind == "판단함" and envs["top_dressing_1"].result["status"] == "미이행"
    assert envs["top_dressing_1"].result["materials"] == ["공시 유기질 비료"] and "지식" in envs["top_dressing_1"].result["amount"]
    assert envs["top_dressing_2"].kind == "판단 불가(지식)"
    assert envs["drainage_alert"].kind == "판단함" and {a["level"] for a in envs["drainage_alert"].result["alerts"]} == {"예고"}
    assert envs["ship_or_store"].kind == "해당 없음" and "D-8" in envs["ship_or_store"].result["why"]
    for e in envs.values():
        if e.kind == "판단함":
            assert e.grade == "추정"                                       # 격자가 추론 초안 — 등급 상한


def test_top_dressing_becomes_done_with_fertilization_event():
    r = ev.add_event(SID, "시비", "2026-09-17", note="웃거름", now=NOW)
    e = SD.judge_top_dressing(SUBJ, "top_dressing_1", T25, evts=ev.list_records(SID))
    assert e.result["status"] == "이행" and e.result["done_refs"] == [r["id"]]
    e = SD.judge_top_dressing(SUBJ, "top_dressing_1", date(2026, 9, 12), evts=[])
    assert e.result["status"] == "예정"
    e = SD.judge_top_dressing(SUBJ, "top_dressing_1", date(2026, 9, 30), evts=[])
    assert e.kind == "해당 없음"


def test_replant_needs_observation_then_judges_in_window():
    t = date(2026, 9, 1)                                                     # 기준점 + 7
    e = SD.judge_replant(SUBJ, t, observations=[])
    assert e.kind == "판단 불가(데이터)" and e.missing[0]["axis"] == "observation"
    o = ev.add_observation(SID, "두둑 왼쪽이 듬성듬성 안 났다", "2026-08-31", now=NOW)
    e = SD.judge_replant(SUBJ, t, observations=[o])
    assert e.kind == "판단함" and e.result["deadline"] == "2026-09-08" and e.result["observations"] == [o["id"]]


def test_base_fertilization_in_window_needs_soil_then_knowledge():
    t = date(2026, 8, 30)
    e = SD.judge_base_fertilization(SUBJ, t)
    assert e.kind == "판단 불가(데이터)" and e.missing[0]["axis"] == "soil_chem"
    e = SD.judge_base_fertilization({**SUBJ, "soil_chem": {"ph": 6.1}}, t)
    assert e.kind == "판단 불가(지식)" and e.result["materials"] == ["완숙 퇴비", "공시 유기질 비료"]


def test_sowing_window_for_planned_subject_is_knowledge_gap():
    s = {**SUBJ, "id": "p001-쪽파-2027봄", "anchor": None}
    s.pop("anchor")
    e = SD.judge_sowing_window(s, T25)
    assert e.kind == "판단 불가(지식)"
    e = SD.judge_sowing_window(SUBJ, date(2026, 8, 20))
    assert e.kind == "판단함" and e.result["window_start"] == "2026-08-18" and e.result["window_end"] == "2026-08-25"


def test_ship_or_store_with_target_date_for_supplying_subject():
    s = {**SUBJ, "use": "몰 납품", "mall_supply": True}
    e = SD.judge_ship_or_store(s, T25, targets=[], harvest=None)
    assert e.kind == "판단 불가(데이터)" and e.missing[0]["axis"] == "plan.target_date"
    from judge import harvest_timing
    h = harvest_timing.judge(SUBJ, today=T25)
    # [미리 걷기 2026-09-20] 전에는 계획일 2026-11-10 · store_days 7 · 마감 "63" 을 박아 두었다 — 셋 다 검토지 ⓓ(W · B6)의
    # 답이 바꿀 지식이라, 답이 오는 날 이 검사까지 따라 고쳐야 했다. 계약은 **"저장 일수 = 계획일 − 수확 창 끝"이고
    # 마감은 격자에서 온다** 이므로 기대값을 판정에서 만든다. 창 뒤/앞 두 방향은 창 끝을 기준으로 잡는다.
    end = date.fromisoformat(h.result["window_end"])
    late, early = (end + timedelta(days=7)).isoformat(), (end - timedelta(days=14)).isoformat()
    e = SD.judge_ship_or_store(s, T25, targets=[{"kind": "plan.target_date", "target_date": late}], harvest=h)
    assert e.kind == "판단함" and e.result["store_days"] == 7
    assert e.caps and str(e.result["ship_deadline_day"]) in e.caps[0]["basis"]
    e = SD.judge_ship_or_store(s, T25, targets=[{"kind": "plan.target_date", "target_date": early}], harvest=h)
    assert e.result["store_days"] < 0 and "출하(저장 없이)" in e.result["summary"] and not e.caps


# ── 배선 · 채팅 ────────────────────────────────────────────────────────────────────
def test_run_emits_twelve_envelopes_and_chat_routes_specific_questions():
    envs = judge_run.judgments_for(SID, today=T25)
    assert len(envs) == 12 and {e.decision_id for e in envs} >= set(SD.IDS)
    assert chat.topic_of("웃거름 줘야 하나?") == "top_dressing_1"
    assert chat.topic_of("보식해야 하나?") == "replant"
    assert chat.topic_of("출하할까 저장할까?") == "ship_or_store"
    assert chat.topic_of("벌레 걱정되는데 괜찮나?") == "pest_alert"
    _, r = chat.send(SID, "웃거름 줘야 하나?", today=T25, now=NOW)
    assert r["text"].startswith("[판단함]") and "미이행" in r["text"] and "정본 대기" in r["text"]
