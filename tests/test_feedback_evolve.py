# -*- coding: utf-8 -*-
# [M-6 · J · D-14] 되먹임 원장 · 자기개선 · 자율진화 — 요구 접수 · 예측 원장 · 대조 · 제안 · 보수 자동/확장 사람 · 검증 3/3 · 상한 배선.
from __future__ import annotations

import ast
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from ingest import events as ev
from ingest import feedback as fb
from ingest import media
from judge import evolve, run as judge_run
from judge.envelope import Envelope
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
SUBJ = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
SID = SUBJ["id"]
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)
PAY = {"window_start": "2026-10-14", "window_end": "2026-11-03", "error_days": 10}


def _pred(payload=PAY, did="harvest_timing"):
    return fb.record_prediction(SID, did, "판단함", payload, "2026-09-19", grade="추정", code_head="abc", now=NOW)


# ── 사용자 개선 요구 ───────────────────────────────────────────────────────────────
def test_request_recorded_and_rules():
    r = fb.add_request("수확 창이 너무 넓다", target="decision", target_ref="harvest_timing", subject=SID, now=NOW)
    assert r["status"] == "접수" and r["schema_version"] == sch.SCHEMA_VERSION
    with pytest.raises(fb.FeedbackError, match="비어"):
        fb.add_request("   ")
    with pytest.raises(fb.FeedbackError, match="사람"):
        fb.add_request("x", source="computed:evolve")
    r2 = fb.set_request_status(r["id"], "거부", response="근거 없음", now=NOW)
    assert r2["status"] == "거부" and fb.latest_by_id("feedback.request")[r["id"]]["status"] == "거부"


# ── 예측 원장: 바뀔 때만 ─────────────────────────────────────────────────────────────
def test_prediction_written_only_when_payload_changes():
    assert _pred() and _pred() is None
    assert _pred({**PAY, "window_end": "2026-11-05"})
    assert len(fb.list_records("feedback.prediction", SID)) == 2


# ── 측정 ─────────────────────────────────────────────────────────────────────────
def test_measure_hit_miss_and_uncomparable():
    _pred()
    assert evolve.measure(SID, date(2026, 10, 1)) == []                     # 창 안 · 수확 없음 → 아직 아무것도
    out = evolve.measure(SID, date(2026, 11, 20))
    assert out and out[0]["verdict"] == "대조 불가" and "수확 사건이 없다" in out[0]["detail"]
    h = ev.add_event(SID, "수확", "2026-10-20", now=NOW)
    out = evolve.measure(SID, date(2026, 11, 20))
    assert out[0]["verdict"] == "적중" and out[0]["actual_ref"] == h["id"]
    assert evolve.measure(SID, date(2026, 11, 20)) == []                    # 같은 판정 두 번 안 적는다


def test_measure_miss_outside_tolerance():
    _pred()
    ev.add_event(SID, "수확", "2026-12-01", now=NOW)
    out = evolve.measure(SID, date(2026, 12, 2))
    assert out[0]["verdict"] == "빗나감"


# ── 제안: 보수는 자동, 확장은 사람 ────────────────────────────────────────────────────
def test_propose_from_miss_auto_conservative_and_human_expansion():
    _pred()
    ev.add_event(SID, "수확", "2026-12-01", now=NOW)
    evolve.measure(SID, date(2026, 12, 2))
    made = evolve.propose(SID, date(2026, 12, 2))
    by_dir = {m["direction"]: m for m in made}
    assert by_dir["보수"]["status"] == "반영" and by_dir["보수"]["auto_applied"] and by_dir["보수"]["verify"]["required"] == 3
    assert by_dir["확장"]["status"] == "제안" and not by_dir["확장"]["auto_applied"]
    assert evolve.propose(SID, date(2026, 12, 2)) == []                     # 같은 출처로 두 번 안 만든다
    assert fb.active_caps(SID) and fb.active_caps(SID)[0]["target_ref"] == "harvest_timing"


def test_propose_from_request_and_noncompliance():
    r = fb.add_request("트랩 대신 육안만 하고 싶다", target="grid", subject=SID, now=NOW)
    ev.add_noncompliance(SID, "예찰(트랩 · 육안)", "트랩을 못 구했다", "2026-09-08", now=NOW)
    made = evolve.propose(SID, date(2026, 9, 19))
    origins = {m["origin"]["kind"] for m in made}
    assert origins == {"feedback.request", "decision.noncompliance"}
    assert all(m["direction"] == "확장" and m["status"] == "제안" for m in made)
    assert fb.latest_by_id("feedback.request")[r["id"]]["status"] == "검토"


def test_expansion_adoption_is_human_only_and_schema_refuses_auto_expansion():
    it = fb.propose("feedback.request", "req_x", "grid", "창을 넓히자", "확장", subject=SID, now=NOW)
    with pytest.raises(fb.FeedbackError, match="사람만"):
        fb.set_item_status(it["id"], "채택", by="computed:evolve")
    ok = fb.set_item_status(it["id"], "채택", by="publisher", note="발행자 채택", now=NOW)
    assert ok["status"] == "채택" and ok["history"][-1]["by"] == "publisher"
    with pytest.raises(fb.FeedbackError, match="자동 적용"):
        fb.propose("feedback.request", "req_y", "grid", "x", "확장", auto_apply=True)
    with pytest.raises(sch.SchemaError, match="자동 적용"):
        sch.validate({"id": "imp_z", "kind": "improvement.item", "origin": {"kind": "x", "ref": "y"}, "target": "grid",
                      "proposal": "p", "direction": "확장", "status": "반영", "auto_applied": True, "observed_at": "2026-09-19",
                      "recorded_at": "x", "source": "computed:evolve", "resolution": "cultivation_unit"})


def test_verification_needs_three_independent_sessions():
    it = fb.propose("feedback.outcome", "out_x", "decision", "상한", "보수", subject=SID, target_ref="harvest_timing",
                    auto_apply=True, applied_ref="grade_cap", now=NOW)
    with pytest.raises(fb.FeedbackError, match="3회"):
        fb.set_item_status(it["id"], "검증", by="publisher")
    fb.record_verification(it["id"], True, "s1", now=NOW)
    with pytest.raises(fb.FeedbackError, match="독립 세션"):
        fb.record_verification(it["id"], True, "s1", now=NOW)
    fb.record_verification(it["id"], True, "s2", now=NOW)
    with pytest.raises(fb.FeedbackError, match="3회"):
        fb.set_item_status(it["id"], "검증", by="publisher")
    fb.record_verification(it["id"], True, "s3", now=NOW)
    assert fb.set_item_status(it["id"], "검증", by="publisher")["status"] == "검증"


# ── 적용(보수 상한)과 배선 ───────────────────────────────────────────────────────────
def test_apply_caps_lowers_grade_only_for_capped_decision():
    caps = [{"target_ref": "harvest_timing", "applied_ref": "grade_cap"}]
    e1 = Envelope("판단함", "harvest_timing", SID, "2026-09-19", grade="계산")
    e2 = Envelope("판단함", "risk_alert", SID, "2026-09-19", grade="계산")
    e3 = Envelope("사실 인용", "material_citation", SID, "2026-09-19")
    evolve.apply_caps(SID, [e1, e2, e3], caps=caps)
    assert e1.grade == "추정" and "[자율진화 보수]" in e1.notes[0]
    assert e2.grade == "계산" and e3.kind == "사실 인용"
    e4 = Envelope("판단함", "harvest_timing", SID, "2026-09-19", grade="계산")
    evolve.apply_caps(SID, [e4], caps=[])
    assert e4.grade == "계산"


def test_caps_pass_gate_and_apply_after_judges_in_run():
    src = (ROOT / "judge" / "run.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "all_judgments")
    loop = next(n for n in fn.body if isinstance(n, ast.For))
    order = []
    for i, st in enumerate(loop.body):
        for c in ast.walk(st):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute):
                if c.func.attr == "gate":
                    order.append(("gate", i))
                    assert "caps" in {kw.arg for kw in c.keywords}, "게이트에 caps 가 안 들어간다"
                if c.func.attr == "judge":
                    order.append(("judge", i))
                if c.func.attr == "apply_caps":
                    order.append(("apply_caps", i))
                if c.func.attr == "append":
                    order.append(("append", i))
    idx = {k: [i for n, i in order if n == k] for k in ("gate", "judge", "apply_caps", "append")}
    assert len(idx["apply_caps"]) == 1 and idx["gate"][0] < min(idx["judge"]) <= max(idx["judge"]) < idx["apply_caps"][0] < idx["append"][0]


def test_cycle_is_idempotent_and_records_predictions():
    s1 = evolve.cycle(today=date(2026, 9, 19), code_head="t")
    assert s1["predictions"] >= 1
    s2 = evolve.cycle(today=date(2026, 9, 19), code_head="t")
    assert s2["predictions"] == 0 and s2["outcomes"] == [] and s2["proposals"] == []


def test_capped_grade_reaches_envelope_through_run():
    fb.propose("feedback.outcome", "out_live", "decision", "상한", "보수", subject=SID, target_ref="risk_alert",
               auto_apply=True, applied_ref="grade_cap", now=NOW)
    for s, envs, _ in judge_run.all_judgments(today=date(2026, 9, 19)):
        e = next(x for x in envs if x.decision_id == "risk_alert")
        if e.kind == "판단함":
            assert e.grade == "추정"          # 격자가 추론 초안이라 이미 추정이면 상한은 그대로(내리지 못하는 등급은 없다)
