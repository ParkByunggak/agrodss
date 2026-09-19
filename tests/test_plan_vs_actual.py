# -*- coding: utf-8 -*-
# [M-10 ③] 계획(격자→날짜) · 사건 원장 · 계획 대 실제 대조 — 이행/예정/미이행/놓침/사유, 선제 발화(준비 착수일).
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from ingest import events as ev
from ingest import media
from judge import plan
from judge import plan_vs_actual as PVA

SUBJ = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
ANCHOR = date(2026, 8, 25)


def _rows(env):
    return {r["task"]: r for r in env.result["rows"]}


# ── 계획 ────────────────────────────────────────────────────────────────────────
def test_plan_from_grid_has_dates_and_cert_materials():
    unit = PVA._load_unit(SUBJ)
    ps = plan.from_unit(unit, ANCHOR, "유기")
    by = {p["task"]: p for p in ps}
    p = by["예찰(트랩 · 육안)"]
    assert p["work_date"] == "2026-09-08" and p["deadline_date"] == "2026-09-24" and p["prep_date_rental"] == "2026-09-05"
    assert p["materials"] and all("PSIS" not in m for m in p["materials"])          # 유기 갈래만
    assert [q["task"] for q in ps if q["kind"] == "plan.capture"].count("촬영") == 5   # 촬영 칸 5
    assert ps == sorted(ps, key=lambda q: q["work_day"])


# ── 사건 원장 ─────────────────────────────────────────────────────────────────────
def test_events_isolated_and_rejects_without_time():
    assert Path(os.environ["AGRODSS_EVENTS_DIR"]).resolve() != (ev.ROOT / "data" / "events").resolve()
    with pytest.raises(ev.EventError, match="대상 시각"):
        ev.add_event(SUBJ["id"], "예찰", "")
    with pytest.raises(ev.EventError, match="종류"):
        ev.add_event(SUBJ["id"], "춤", "2026-09-10")
    with pytest.raises(ev.EventError, match="형식"):
        ev.add_event(SUBJ["id"], "예찰", "어제")


def test_events_record_shape():
    r = ev.add_event(SUBJ["id"], "예찰", "2026-09-10", note="트랩 설치", now=datetime(2026, 9, 10, tzinfo=timezone.utc))
    assert r["kind"] == "event" and r["source"] == "farmer" and r["resolution"] == "cultivation_unit"
    assert r["observed_at"] == "2026-09-10" and r["recorded_at"].startswith("2026-09-10")
    assert ev.list_records(SUBJ["id"], "event")[0]["id"] == r["id"]


# ── 대조 ────────────────────────────────────────────────────────────────────────
def test_anchor_counts_as_sowing_event():
    env = PVA.judge(SUBJ, today=date(2026, 9, 19))
    assert env.kind == "판단함" and _rows(env)["밑거름 · 두둑 · 파종"]["status"] == "이행"


def test_unfulfilled_before_deadline_then_missed_after():
    r = _rows(PVA.judge(SUBJ, today=date(2026, 9, 19)))["예찰(트랩 · 육안)"]
    assert r["status"] == "미이행" and "마감까지 5일" in r["evidence"]
    env = PVA.judge(SUBJ, today=date(2026, 9, 30))
    r = _rows(env)["예찰(트랩 · 육안)"]
    assert r["status"] == "놓침" and any(a["task"] == "예찰(트랩 · 육안)" for a in env.result["ask_reason"])


def test_event_within_window_is_fulfilled():
    ev.add_event(SUBJ["id"], "예찰", "2026-09-12")
    r = _rows(PVA.judge(SUBJ, today=date(2026, 9, 30)))["예찰(트랩 · 육안)"]
    assert r["status"] == "이행" and "예찰" in r["evidence"]


def test_event_of_other_type_does_not_fulfil():
    ev.add_event(SUBJ["id"], "관수", "2026-09-12")
    assert _rows(PVA.judge(SUBJ, today=date(2026, 9, 30)))["예찰(트랩 · 육안)"]["status"] == "놓침"


def test_noncompliance_reason_closes_the_ask():
    ev.add_noncompliance(SUBJ["id"], "예찰(트랩 · 육안)", "트랩을 못 구했다", "2026-09-08")
    env = PVA.judge(SUBJ, today=date(2026, 9, 30))
    r = _rows(env)["예찰(트랩 · 육안)"]
    assert r["status"] == "사유 기록됨" and "트랩" in r["evidence"]
    assert not any(a["task"] == "예찰(트랩 · 육안)" for a in env.result["ask_reason"])


def test_capture_fulfilled_by_video_ledger():
    vids = [{"id": "vid_x", "observed_at": "2026-09-18T06:30:00+00:00"}]     # 3단계 창(9/4~9/24) 안
    rows = _rows(PVA.judge(SUBJ, today=date(2026, 9, 19), videos=vids))
    caps = [r for r in PVA.judge(SUBJ, today=date(2026, 9, 19), videos=vids).result["rows"] if r["kind"] == "plan.capture"]
    assert any(c["status"] == "이행" and "vid_x" in c["evidence"] for c in caps)
    assert any(c["status"] == "예정" for c in caps)                             # 뒤 단계 촬영은 아직


def test_prep_now_flags_rental_lead_time():
    # 예찰: work_day 14(9/8), lead rental 3 → 준비 착수일 9/5. 9/6 에는 '예정'이면서 준비일이 지났다 → 선제 발화
    env = PVA.judge(SUBJ, today=date(2026, 9, 6))
    r = _rows(env)["예찰(트랩 · 육안)"]
    assert r["status"] == "예정"
    assert any(p["task"].startswith("예찰") and p["prep_date"] == "2026-09-05" for p in env.result["prep_now"])
    env2 = PVA.judge(SUBJ, today=date(2026, 9, 3))                              # 준비일 전 — 아직 아니다
    assert not any(p["task"].startswith("예찰") for p in env2.result["prep_now"])


def test_counts_sum_to_rows_and_no_raw_layers():
    env = PVA.judge(SUBJ, today=date(2026, 9, 19))
    assert sum(env.result["counts"].values()) == len(env.result["rows"])
    assert [i.axis for i in env.inputs] == ["anchor"]


def test_not_applicable_and_data_gap():
    assert PVA.judge({"id": "x"}, today=date(2026, 9, 19)).kind == "해당 없음"
    assert PVA.judge({**SUBJ, "anchor": None}, today=date(2026, 9, 19)).kind == "판단 불가(데이터)"
