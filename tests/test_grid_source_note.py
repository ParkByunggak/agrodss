# -*- coding: utf-8 -*-
# [2026-10-01 전수 · 발행자 규율 "출처가 추론이면 그 표시가 답까지 간다"(D-20)] 격자는 '추론 초안 2026-09-18 · 발행자 검토 대기 · 확신 중' 인데
# 그 사실을 답(메모)에 싣는 판정기가 셋(수확 시기 · 계획 대 실제 · 위험 경보)뿐이었고 칸 결정 일곱은 안 실었다(실측 2026-10-01 00:25 UTC).
# 계약: 격자 출처 한 줄은 정본 하나(grid.schema.source_note) · 격자를 읽어 판단함을 내는 모든 판정기가 그것을 메모에 싣는다 · 화면은 사람 말(재배 달력 출처).
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from frontend import words
from grid import schema as grid_schema
from ingest import media
from judge import stage_decisions as SD

ROOT = Path(__file__).resolve().parent.parent
GRID_READERS = ("judge/stage_decisions.py", "judge/harvest_timing.py", "judge/plan_vs_actual.py", "judge/risk_alert.py")


def _unit():
    s = media.load_subjects()[0]
    unit, miss = grid_schema.load_unit(s)
    assert miss is None
    return s, unit


def test_the_source_line_is_one_canon_and_says_source_and_confidence():
    s, unit = _unit()
    line = grid_schema.source_note(unit)
    assert line.startswith("격자 출처: ") and unit["unit"]["source"] in line and f"확신 {unit['unit']['confidence']}" in line
    assert "추론 초안" in line                                                                   # 지금 격자의 상태 — 답이 이것을 말해야 한다
    assert grid_schema.source_note({}) == "격자 출처: ? · 확신 ?"                                   # 비어도 깨지지 않고 비었다고 말한다
    for rel in GRID_READERS:
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "격자 출처:" not in src, f"{rel}: 격자 출처 문면을 제 손으로 만든다 — 정본 하나(grid.schema.source_note)"
        assert "grid_schema.source_note(" in src, f"{rel}: 정본을 안 부른다"


def test_every_judged_envelope_in_stage_decisions_carries_the_grid_source():
    """구조로 자른다(함수 본문) — 판단함을 내는 함수마다 source_note 호출이 그 본문 안에 있다. 위임(_delegate_risk)은 위험 경보의 메모를 그대로 받는다."""
    src = (ROOT / "judge" / "stage_decisions.py").read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=def )", src)
    judged = [b for b in blocks if 'Envelope("판단함"' in b]
    assert len(judged) >= 7, "판단함을 내는 함수가 줄었다 — 전수를 다시 센다"
    for b in judged:
        name = b.split("(")[0].replace("def ", "")
        assert "grid_schema.source_note(" in b or "notes=list(r.notes)" in b, f"{name}: 판단함에 격자 출처가 없다"


def test_the_judged_answers_actually_carry_it(tmp_path, monkeypatch):
    s, unit = _unit()
    today = date.fromisoformat(s["anchor"]) + timedelta(days=36)                              # 칸 4(30~50)
    line = grid_schema.source_note(unit)
    e = SD.judge_sowing_window(s, date.fromisoformat(s["anchor"]) - timedelta(days=3))
    assert e.kind == "판단함" and line in e.notes
    e = SD.judge_symptom_triage(s, date.fromisoformat(s["anchor"]) + timedelta(days=24),
                                [{"id": "o", "text": "잎 끝이 노랗다", "observed_at": (date.fromisoformat(s["anchor"]) + timedelta(days=24)).isoformat()}])
    assert e.kind == "판단함" and e.notes[0] == line
    wet = {"id": "r", "text": "어제 비가 왔다", "observed_at": (today - timedelta(days=3)).isoformat()}
    e = SD.judge_drought_alert(s, today, evts=[], observations=[wet])
    assert e.kind == "판단함" and e.notes[0] == line
    e = SD.judge_drainage_alert(s, today)                                                       # 칸 4 카드(36일째 열린 칸) — 병해충 카드는 칸 3 이라 그날 해당 없음
    assert e.kind == "판단함" and line in e.notes                                                # 위임 — 위험 경보의 메모가 그대로 온다
    assert "재배 달력 출처: " in words.plain(line) and "격자" not in words.plain(line)             # 화면은 사람 말
