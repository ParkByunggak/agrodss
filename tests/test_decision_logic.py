# -*- coding: utf-8 -*-
# [코드 평가 칸 2 ⓑ 결정 논리 · 2026-09-19] B2 cert 필요 축 · B3 이행 판정 한 벌 · B5 판별 순서 · B7 mall_supply 배선 · B13 조건부·소급 작업.
from __future__ import annotations

from datetime import date, timedelta

from ingest import media, parcels
from judge import plan_vs_actual as PVA
from judge import stage_decisions as SD
from schema import records as sch

_RAW = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
SUBJ = parcels.enrich_subject(_RAW, parcels.by_id("p001"))
A = date.fromisoformat(SUBJ["anchor"])


def _evt(day: int, typ: str = "시비") -> dict:
    return {"kind": "event", "id": f"e{day}", "type": typ, "subject": SUBJ["id"], "observed_at": (A + timedelta(days=day)).isoformat(),
            "recorded_at": "2026-09-01T00:00:00", "source": "farmer", "resolution": "cultivation_unit"}


def _by(envs, did):
    return next(e for e in envs if e.decision_id == did)


def test_missing_cert_is_data_gap_not_empty_materials():
    s = {k: v for k, v in SUBJ.items() if k != "cert"}
    s["soil_chem"] = {"ph": 6.1}
    envs = SD.judge_all(s, A + timedelta(days=5), evts=[], forecast=None, pest=None, harvest=None, prescriptions=[])
    for did in ("base_fertilization",):
        e = _by(envs, did)
        assert e.kind == "판단 불가(데이터)" and e.missing[0]["axis"] == "cert", (did, e.kind, e.result)
    envs = SD.judge_all(s, A + timedelta(days=25), evts=[], forecast=None, pest=None, harvest=None, prescriptions=[])
    e = _by(envs, "top_dressing_1")
    assert e.kind == "판단 불가(데이터)" and e.missing[0]["axis"] == "cert" and "자재(None)" not in str(e.result)


def test_top_dressing_fulfilment_agrees_with_plan_vs_actual():
    # 같은 사건 · 같은 날 → 두 판정기가 같은 상태. 전에는 wd-7 하드코딩(stage) vs tol 3(plan) 로 갈렸다
    for day_evt, today_day in ((17, 25), (21, 25), (None, 25), (None, 22), (None, 15)):
        evts = [_evt(day_evt)] if day_evt is not None else []
        today = A + timedelta(days=today_day)
        td = _by(SD.judge_all(SUBJ, today, evts=evts, forecast=None, pest=None, harvest=None, prescriptions=[]), "top_dressing_1")
        row = next(r for r in PVA.judge(SUBJ, today=today, evts=evts, videos=[], reasons=[]).result["rows"] if r["task"] == "웃거름 1회")
        assert td.kind == "판단함" and td.result["status"] == row["status"], (day_evt, today_day, td.result["status"], row["status"])


def test_top_dressing_2_past_deadline_is_not_applicable_before_knowledge_gap():
    e = _by(SD.judge_all(SUBJ, A + timedelta(days=60), evts=[], forecast=None, pest=None, harvest=None, prescriptions=[]), "top_dressing_2")
    assert e.kind == "해당 없음", e.kind
    e2 = _by(SD.judge_all(SUBJ, A + timedelta(days=45), evts=[], forecast=None, pest=None, harvest=None, prescriptions=[]), "top_dressing_2")
    assert e2.kind == "판단 불가(지식)"


def test_mall_supply_reaches_layer3_subject():
    assert "mall_supply" in sch.PARCEL_FIELDS_TO_LAYER3 and "mall_supply" in sch.LAYER3_SUBJECT_FIELDS
    p = parcels.by_id("p001")
    if p.get("mall_supply") is not None:
        assert SUBJ.get("mall_supply") == p["mall_supply"]
    s = parcels.enrich_subject(_RAW, {**p, "mall_supply": False, "use": "텃밭"})
    e = _by(SD.judge_all(s, A + timedelta(days=60), evts=[], forecast=None, pest=None, harvest=None, prescriptions=[]), "ship_or_store")
    assert e.kind == "해당 없음" and "D-8" in (e.result.get("why") or "")


def test_conditional_and_pre_anchor_tasks_are_not_counted_as_missed():
    env = PVA.judge(SUBJ, today=A + timedelta(days=25), evts=[], videos=[], reasons=[])
    rows = {r["task"]: r for r in env.result["rows"]}
    assert rows["관수(건조 시)"]["status"] == "조건부"
    pre = [r for r in env.result["rows"] if r["kind"] == "plan.capture" and r["work_date"] < SUBJ["anchor"]]
    assert pre and all(r["status"] == "기록 없음" for r in pre)
    asked = {(a["task"], a["work_date"]) for a in env.result["ask_reason"]}          # 같은 이름 '촬영'이 칸마다 있어 (작업, 날짜)로 본다
    assert not any(t == "관수(건조 시)" for t, _ in asked) and not any((r["task"], r["work_date"]) in asked for r in pre)
    assert any(t == "촬영" for t, _ in asked)                                         # 기준점 뒤 놓친 촬영은 그대로 묻는다
    assert PVA._conditional("웃거름 2회(필요 시)") and not PVA._conditional("웃거름 1회") and not PVA._conditional("수확(뽑기) · 다듬기 · 세척")
