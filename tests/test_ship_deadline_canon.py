# -*- coding: utf-8 -*-
# [B6 코드 쪽 · 2026-09-20] 출하 마감(칸 5 retry.deadline_day)이 격자에 없으면 63 을 기본값으로 메우던 것(하드코딩 · 대리값 금지 위반) → 지식 미비.
# 그리고 격자 자체 모순(출하 마감 63 < 수확 창 끝 70)은 지식 결함(검토지 ⓓ B6)이라 여기서 고치지 않되, 봉투가 그 사실을 말한다.
# B6 답이 오면 격자 데이터 한 수정으로 끝난다 — 코드에 63 이 없어야 그렇다(래칫).
from __future__ import annotations

import copy
import re
from datetime import date
from pathlib import Path

from ingest import media, parcels
from judge import harvest_timing, stage_decisions as SD

ROOT = Path(__file__).resolve().parent.parent
_RAW = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
SUBJ = {**parcels.enrich_subject(_RAW, parcels.by_id("p001")), "use": "몰 납품", "mall_supply": True}
T25 = date(2026, 9, 19)


def test_contradiction_is_reported_not_silently_capped_and_deadline_comes_from_grid():
    h = harvest_timing.judge(SUBJ, today=T25)
    e = SD.judge_ship_or_store(SUBJ, T25, targets=[{"kind": "plan.target_date", "target_date": "2026-11-10"}], harvest=h)
    assert e.kind == "판단함" and e.result["ship_deadline_day"] == 63                   # 격자 값(칸 5 retry.deadline_day)
    assert e.caps and "63" in e.caps[0]["basis"]
    assert any("격자 자체 모순(B6)" in n and "63" in n and "70" in n for n in e.notes)  # 모순을 봉투가 말한다


def test_missing_grid_deadline_is_a_knowledge_gap_not_a_default(monkeypatch):
    unit = copy.deepcopy(harvest_timing._load_unit(SUBJ))
    for s in unit["stages"]:
        for t in s.get("tasks", []):
            if "출하" in t.get("name", ""):
                t.pop("retry", None)
    monkeypatch.setattr(SD, "_load_unit", lambda subject: unit)
    h = harvest_timing.judge(SUBJ, today=T25)
    e = SD.judge_ship_or_store(SUBJ, T25, targets=[{"kind": "plan.target_date", "target_date": "2026-11-10"}], harvest=h)
    assert e.kind == "판단 불가(지식)" and "마감" in e.result["why"]


def test_no_literal_ship_deadline_in_judge_code():
    src = (ROOT / "judge" / "stage_decisions.py").read_text(encoding="utf-8")
    body = src[src.index("def judge_ship_or_store"):src.index("def judge_all")]
    code = "\n".join(ln.split("#", 1)[0] for ln in body.splitlines())
    assert not re.search(r"\b63\b", code), "출하 마감 리터럴 — 격자(칸 5 retry.deadline_day)가 정본"
