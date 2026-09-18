# -*- coding: utf-8 -*-
# [M-4 · M-9] 격자 스키마 — 거부(I-4 밖 축 · 축 겹침 · 회복 불가인데 경보 약함 · 촬영 칸 없음 · 순서)와
# 통과(쪽파 가을 격자가 검증을 지난다 · 문서 동기 · 회복 불가 칸이 먼저 채워졌다).
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

from grid import schema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_grid_doc as bg  # noqa: E402

JJ = schema.GRID_DIR / "jjokpa_autumn.json"


@pytest.fixture
def unit():
    return schema.load(JJ)


# ── 통과 ──────────────────────────────────────────────────────────────────────
def test_jjokpa_autumn_validates(unit):
    rep = schema.validate(unit)
    assert rep.ok, rep.errors


def test_axes_constant_matches_i4():
    assert len(schema.AXES) == 12 and "humidity_air" not in schema.AXES


def test_unrecoverable_risks_filled_first(unit):
    # M-7 원칙: 회복 불가 위험은 전부 트리거·축·출처가 채워져 있다
    for s in unit["stages"]:
        for r in (s.get("risks") or []) if s.get("risks") != schema.NA else []:
            if r["recoverable"] is False:
                assert r.get("trigger") and r.get("axes") and r.get("source"), r["name"]
                assert r["alert"] == "oversignal_ok"


def test_first_capture_scene_is_current_stage(unit):
    # 오늘(T+24)이 속한 칸은 촬영 칸이다 — I-7 첫 촬영이 격자와 맞물린다
    s = [s for s in unit["stages"] if s["window"]["from_day"] <= 24 <= s["window"]["to_day"]]
    assert s and s[0]["capture"]["shoot"] is True


def test_harvest_stage_answers_harvest_timing_with_range(unit):
    h = [s for s in unit["stages"] if "harvest_timing" in s.get("decisions", [])]
    assert len(h) == 1 and h[0]["judge_without_variety"] == "range"


def test_materials_split_by_cert(unit):
    for s in unit["stages"]:
        for t in (s.get("tasks") or []) if s.get("tasks") != schema.NA else []:
            m = t["materials"]
            assert m == schema.NA or set(m) == {"관행", "유기"}, t["name"]


def test_completeness_counts_three_kinds(unit):
    rep = schema.validate(unit)
    assert rep.filled > 0 and rep.na > 0          # '해당없음' 이 실제로 쓰였다(6단계)
    assert rep.unfilled == 0                        # 칸 필드 수준 미채움은 0 — 미채움은 값 안에 '미채움' 으로 표기됨


def test_doc_in_sync(unit):
    assert bg.build(unit) == (ROOT / "docs" / "grid_jjokpa_autumn.md").read_text(encoding="utf-8")


# ── 거부 ──────────────────────────────────────────────────────────────────────
def _mut(unit, fn):
    u = copy.deepcopy(unit)
    fn(u)
    return schema.validate(u)


def test_reject_axis_outside_i4(unit):
    rep = _mut(unit, lambda u: u["stages"][0]["required_axes"].append("moon_phase"))
    assert any("I-4 밖" in e for e in rep.errors)


def test_reject_forbidden_only_axis_as_required(unit):
    rep = _mut(unit, lambda u: u["stages"][0]["required_axes"].append("humidity_air"))
    assert not rep.ok


def test_reject_required_forbidden_overlap(unit):
    rep = _mut(unit, lambda u: u["stages"][0]["forbidden_axes"].append("temp"))
    assert any("겹친다" in e for e in rep.errors)


def test_reject_unrecoverable_with_weak_alert(unit):
    def f(u):
        u["stages"][0]["risks"][0]["alert"] = "confident_only"
    rep = _mut(unit, f)
    assert any("경보 비대칭" in e for e in rep.errors)


def test_reject_no_capture_cell(unit):
    def f(u):
        for s in u["stages"]:
            s["capture"] = {"shoot": False, "scene": ""}
    rep = _mut(unit, f)
    assert any("촬영 시점 칸" in e for e in rep.errors)


def test_reject_bad_order(unit):
    rep = _mut(unit, lambda u: u["stages"][1].__setitem__("order", 5))
    assert any("order" in e for e in rep.errors)


def test_reject_non_canonical_crop(unit):
    rep = _mut(unit, lambda u: u["unit"].__setitem__("crop", "취나물"))   # 이명 — 정본은 참취
    assert any("정본명" in e for e in rep.errors)


def test_reject_no_judgment_without_traits(unit):
    def f(u):
        u["stages"][4]["judge_without_variety"] = "no"   # variety_dependence 는 time_only
    rep = _mut(unit, f)
    assert any("traits" in e for e in rep.errors)


def test_reject_parcel_correction_without_pest_axis(unit):
    def f(u):
        u["stages"][0]["risks"][0]["parcel_correction"] = True   # axes: anchor/temp/forecast
    rep = _mut(unit, f)
    assert any("parcel_correction" in e for e in rep.errors)
