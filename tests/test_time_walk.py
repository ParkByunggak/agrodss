# -*- coding: utf-8 -*-
# [U-35 형태 2026-10-02] 앞날 걷기 도구 — 날짜를 가로지르는 종류의 결함을 본다(pytest 는 고정 날짜 한 판정 · 걷기는 한 날짜의 화면).
# 계약: 아무것도 쓰지 않는다 · 봉투를 가공하지 않는다 · 기본 날짜는 칸 경계 앞뒤 · 수확 뒤 칸의 가뭄은 해당 없음(N/A ≠ 미채움 — 이 도구가 잡은 그 결함) ·
# '미채움' 이라 말하는 판단 불가(지식)은 격자에 그 키가 정말 없을 때만.
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path

from grid import schema as grid_schema
from ingest import media
from scripts import time_walk as tw

ROOT = Path(__file__).resolve().parent.parent


def _tree_hash(p: Path) -> dict[str, str]:
    return {f.as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(p.rglob("*")) if f.is_file()}


def test_the_walk_reads_everything_and_writes_nothing():
    s = media.load_subjects()[0]
    anchor = date.fromisoformat(s["anchor"])
    before = _tree_hash(ROOT / "data")
    rows = tw.walk(tw.default_days(anchor), only=s["id"])
    assert _tree_hash(ROOT / "data") == before
    assert len(tw.DEFAULT_OFFSETS) == 5 and {r["day"] for r in rows} == set(tw.DEFAULT_OFFSETS)
    decisions = {r["decision"] for r in rows}
    assert {"harvest_timing", "risk_alert", "drought_alert", "symptom_triage", "forecast_citation"} <= decisions
    for r in rows:
        assert r["kind"] in ("판단함", "사실 인용", "판단 불가(데이터)", "판단 불가(지식)", "해당 없음", "예측 불가", "답하지 않음", "선택지+대가"), r


def test_a_not_applicable_field_never_reads_as_unfilled_across_the_dates():
    """이 도구가 잡은 결함의 래칫 — 격자가 N/A 로 적은 칸에서 '미채움' 이라는 판단 불가(지식)이 어느 날짜에도 나오지 않는다."""
    s = media.load_subjects()[0]
    unit, _ = grid_schema.load_unit(s)
    anchor = date.fromisoformat(s["anchor"])
    rows = tw.walk(tw.default_days(anchor), only=s["id"])
    for r in rows:
        if r["kind"] == "판단 불가(지식)" and "미채움" in r["why"]:
            from grid import capture
            st = capture.stage_for_day(unit, r["day"]) or {}
            assert all(v != grid_schema.NA for v in st.values()), f"{r['date']} {r['decision']}: N/A 를 미채움으로 읽는다 — {r['why']}"
    late = [r for r in rows if r["day"] >= 71 and r["decision"] == "drought_alert"]
    assert late and all(r["kind"] == "해당 없음" for r in late)


def test_render_groups_by_date_and_names_the_sources():
    rows = [{"date": "2026-10-14", "day": 50, "subject": "x", "decision": "a", "kind": "판단함", "grade": "추정", "summary": "요약", "why": "", "notes": [],
             "status": {"forecast": "좌표 없음"}}]
    text = tw.render(rows)
    assert "===== 2026-10-14 · x · 기준점 뒤 50일 =====" in text and "forecast=좌표 없음" in text and "요약" in text
