# -*- coding: utf-8 -*-
# [B6 코드 쪽 · 2026-09-20] 출하 마감(칸 5 retry.deadline_day)이 격자에 없으면 63 을 기본값으로 메우던 것(하드코딩 · 대리값 금지 위반) → 지식 미비.
# 그리고 격자 자체 모순(출하 마감 63 < 수확 창 끝 70)은 지식 결함(검토지 ⓓ B6)이라 여기서 고치지 않되, 봉투가 그 사실을 말한다.
# B6 답이 오면 격자 데이터 한 수정으로 끝난다 — 코드에 63 이 없어야 그렇다(래칫).
from __future__ import annotations

import copy
import re
from datetime import date
from pathlib import Path

from grid import schema as grid_schema
from ingest import media, parcels
from judge import harvest_timing, stage_decisions as SD

ROOT = Path(__file__).resolve().parent.parent
_RAW = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
SUBJ = {**parcels.enrich_subject(_RAW, parcels.by_id("p001")), "use": "몰 납품", "mall_supply": True}
T25 = date(2026, 9, 19)


def _ship_stage_and_deadline():
    unit = grid_schema.load_unit(SUBJ)[0]
    stage = SD._stage(unit, "ship_or_store")
    dl = int(next(t for t in stage["tasks"] if "출하" in t["name"])["retry"]["deadline_day"])
    return stage, dl


def test_deadline_comes_from_the_grid_whatever_its_value_is():
    """**계약** — 마감은 격자에서 온다. [미리 걷기 2026-09-20] 전에는 63 을 박아 두어, 검토지 B6 답이 오는 날 이 검사도
    손봐야 했다(대장이 "격자 한 수정으로 끝난다"고 적은 것과 어긋난다). 값이 아니라 출처를 고정한다."""
    _, want = _ship_stage_and_deadline()
    h = harvest_timing.judge(SUBJ, today=T25)
    e = SD.judge_ship_or_store(SUBJ, T25, targets=[{"kind": "plan.target_date", "target_date": "2026-11-10"}], harvest=h)
    assert e.kind == "판단함" and e.result["ship_deadline_day"] == want
    assert e.caps and str(want) in e.caps[0]["basis"]


def test_the_grid_today_still_contradicts_itself_on_b6():
    """**상태** — 지금 격자는 출하 마감 < 수확 창 끝이다(검토지 ⓓ B6 미회신). 답이 와서 모순이 풀리면 **이 검사만** 고치고,
    위 계약 검사는 그대로 선다 — 어느 쪽이 깨졌는지로 '지식이 바뀐 것'과 '계약이 무너진 것'을 가른다."""
    stage, dl = _ship_stage_and_deadline()
    assert dl < int(stage["window"]["to_day"]), "모순이 풀렸다 — 이 검사와 봉투의 모순 고지를 함께 거둔다"
    h = harvest_timing.judge(SUBJ, today=T25)
    e = SD.judge_ship_or_store(SUBJ, T25, targets=[{"kind": "plan.target_date", "target_date": "2026-11-10"}], harvest=h)
    assert any("격자 자체 모순(B6)" in n and str(dl) in n for n in e.notes)              # 모순을 봉투가 말한다


def test_missing_grid_deadline_is_a_knowledge_gap_not_a_default(monkeypatch):
    unit = copy.deepcopy(grid_schema.load_unit(SUBJ)[0])
    for s in unit["stages"]:
        for t in s.get("tasks", []):
            if "출하" in t.get("name", ""):
                t.pop("retry", None)
    # [U-23] 읽는 자리가 정본 하나가 되어 여기도 그 하나를 바꾼다 — 전에는 모듈마다 있던 `_load_unit` 을 따로 갈아 끼웠다
    monkeypatch.setattr(grid_schema, "load_unit", lambda subject: (unit, None))
    h = harvest_timing.judge(SUBJ, today=T25)
    e = SD.judge_ship_or_store(SUBJ, T25, targets=[{"kind": "plan.target_date", "target_date": "2026-11-10"}], harvest=h)
    assert e.kind == "판단 불가(지식)" and "마감" in e.result["why"]


def test_no_literal_ship_deadline_in_judge_code():
    src = (ROOT / "judge" / "stage_decisions.py").read_text(encoding="utf-8")
    body = src[src.index("def judge_ship_or_store"):src.index("def judge_all")]
    code = "\n".join(ln.split("#", 1)[0] for ln in body.splitlines())
    assert not re.search(r"\b63\b", code), "출하 마감 리터럴 — 격자(칸 5 retry.deadline_day)가 정본"
