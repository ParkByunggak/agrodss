# -*- coding: utf-8 -*-
# FILE: grid/schema.py
# ROLE: [M-4] 격자 스키마 검증기 — docs/m4_grid_schema.md §4 의 규칙을 코드로. 격자 JSON 이 이 검증을
#       통과하지 못하면 관문이 깨진다(tests/test_grid.py). 완성도(값/N-A/미채움)도 여기서 센다.
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GRID_DIR = ROOT / "data" / "grid"

# I-4 §1 — 격자가 참조할 수 있는 축. 늘리려면 I-4 문서에 한 줄 + 대장 등재가 먼저다.
AXES: frozenset[str] = frozenset({
    "daylength", "temp", "gdd", "precip", "forecast", "soil_water", "soil_chem",
    "pest_regional", "pest_history", "microclimate", "anchor", "cert",
})
FORBIDDEN_ONLY: frozenset[str] = frozenset({"humidity_air"})   # 금지 축으로만 등장 가능
PEST_AXES = {"pest_regional", "pest_history", "microclimate"}
NA = "N/A"

STAGE_FIELDS = ("window", "risks", "tasks", "required_axes", "forbidden_axes", "water",
                "variety_dependence", "unit_scope", "judge_without_variety", "capture", "decisions")
LEVELS = {"낮음", "중간", "높음"}
CONF = {"상", "중", "하"}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    filled: int = 0
    na: int = 0
    unfilled: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def completeness(self) -> dict[str, int]:
        return {"filled": self.filled, "na": self.na, "unfilled": self.unfilled}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_names() -> set[str]:
    from names import resolve as R
    return set(R.load().canonical)


def validate(unit: dict[str, Any], canonical: set[str] | None = None) -> Report:
    rep = Report()
    err = rep.errors.append
    u = unit.get("unit", {})
    canonical = canonical if canonical is not None else _canonical_names()
    for k in ("id", "crop", "kind", "anchor_kind", "source"):
        if not u.get(k):
            err(f"unit.{k} 없음")
    if u.get("crop") and u["crop"] not in canonical:
        err(f"unit.crop {u['crop']!r} 는 정본명이 아니다(names/resolve)")
    if u.get("kind") not in ("season", "variety"):
        err("unit.kind 는 season | variety")
    stages = unit.get("stages", [])
    if not stages:
        err("stages 없음")
    orders = [s.get("order") for s in stages]
    if orders != list(range(1, len(stages) + 1)):
        err(f"order 는 1부터 연속·유일이어야 한다: {orders}")
    any_shoot = False
    for s in stages:
        tag = f"stage {s.get('order')}({s.get('name')})"
        if not s.get("name"):
            err(f"{tag}: name 없음")
        if s.get("confidence") and s["confidence"] not in CONF:
            err(f"{tag}: confidence 는 상/중/하")
        # 빈칸 3종 집계
        for f in STAGE_FIELDS:
            if f not in s:
                rep.unfilled += 1
            elif s[f] == NA:
                rep.na += 1
            else:
                rep.filled += 1
        req = s.get("required_axes", [])
        forb = s.get("forbidden_axes", [])
        if req != NA:
            for a in req:
                if a not in AXES:
                    err(f"{tag}: required_axes 에 I-4 밖 축 {a!r}")
        if forb != NA:
            for a in forb:
                if a not in AXES | FORBIDDEN_ONLY:
                    err(f"{tag}: forbidden_axes 에 I-4 밖 축 {a!r}")
        if req != NA and forb != NA and set(req) & set(forb):
            err(f"{tag}: 판정 축과 금지 축이 겹친다 {set(req) & set(forb)}")
        w = s.get("window")
        if isinstance(w, dict):
            if w.get("basis") not in ("anchor", "gdd"):
                err(f"{tag}: window.basis 는 anchor | gdd")
            if not (isinstance(w.get("from_day"), int) and isinstance(w.get("to_day"), int)) or w["from_day"] > w["to_day"]:
                err(f"{tag}: window from_day <= to_day 정수")
        for r in (s.get("risks") or []) if s.get("risks") != NA else []:
            rt = f"{tag} risk {r.get('name')!r}"
            if "recoverable" not in r or r.get("alert") not in ("oversignal_ok", "confident_only"):
                err(f"{rt}: recoverable(bool) · alert(oversignal_ok|confident_only) 필수")
            elif r["recoverable"] is False and r["alert"] != "oversignal_ok":
                err(f"{rt}: 회복 불가 위험은 alert=oversignal_ok (경보 비대칭)")
            for a in r.get("axes", []):
                if a not in AXES:
                    err(f"{rt}: 축 {a!r} 는 I-4 밖")
            if r.get("parcel_correction") and not (set(r.get("axes", [])) & PEST_AXES):
                err(f"{rt}: parcel_correction 은 병해충·미기상 축이 있는 위험만")
        for t in (s.get("tasks") or []) if s.get("tasks") != NA else []:
            tt = f"{tag} task {t.get('name')!r}"
            if not isinstance(t.get("work_day"), int):
                err(f"{tt}: work_day 정수 필수")
            ld = t.get("lead_days")
            if not (isinstance(ld, dict) and "own" in ld and "rental" in ld):
                err(f"{tt}: lead_days {{own, rental}} 필수")
            m = t.get("materials")
            if not (m == NA or (isinstance(m, dict) and set(m) <= {"관행", "유기"} and m)):
                err(f"{tt}: materials 는 {{관행,유기}} dict 또는 N/A")
            rt_ = t.get("retry")
            if not (isinstance(rt_, dict) and "possible" in rt_):
                err(f"{tt}: retry {{possible, deadline_day}} 필수")
        wt = s.get("water")
        if isinstance(wt, dict):
            for k in ("demand", "deficit_sensitivity", "excess_sensitivity"):
                if wt.get(k) not in LEVELS:
                    err(f"{tag}: water.{k} 는 낮음/중간/높음")
        vd, jw = s.get("variety_dependence"), s.get("judge_without_variety")
        if vd not in (None, NA, "time_only", "traits"):
            err(f"{tag}: variety_dependence 는 time_only | traits")
        if jw not in (None, NA, "ok", "range", "no"):
            err(f"{tag}: judge_without_variety 는 ok | range | no")
        if jw == "no" and vd != "traits":
            err(f"{tag}: 품종 모르면 판단 불가인데 의존이 traits 가 아니다")
        if s.get("unit_scope") not in (None, NA, "parcel", "cultivation_unit"):
            err(f"{tag}: unit_scope 는 parcel | cultivation_unit")
        cap = s.get("capture")
        if isinstance(cap, dict) and cap.get("shoot"):
            any_shoot = True
            if not cap.get("scene"):
                err(f"{tag}: capture.shoot 이면 scene 필요")
    if stages and not any_shoot:
        err("촬영 시점 칸(capture.shoot=true)이 하나도 없다 — 영상이 상세페이지다(몰-C)")
    return rep


def load_all() -> dict[str, dict[str, Any]]:
    return {p.stem: load(p) for p in sorted(GRID_DIR.glob("*.json"))}
