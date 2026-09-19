# -*- coding: utf-8 -*-
# FILE: judge/plan.py
# ROLE: [M-10 ③ · F 1층 계획 데이터] 격자 작업 칸 + 기준점 → 날짜가 붙은 계획(표준 방제력·작업력).
#       계획은 관측이 아니라 예정이다 — kind 로 구분하고, source 는 computed:grid.
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from grid import schema as grid_schema


def from_unit(unit: dict[str, Any], anchor: date, cert: str | None) -> list[dict[str, Any]]:
    """단위 전체 작업을 날짜로 펼친다. 자재는 인증 갈래만 싣는다(관행/유기 분리 — H)."""
    out = []
    for s in unit.get("stages", []):
        tasks = s.get("tasks")
        if tasks == grid_schema.NA or not tasks:
            continue
        for t in tasks:
            wd = int(t["work_day"])
            ld = t.get("lead_days", {}) or {}
            m = t.get("materials")
            mats = None if m == grid_schema.NA else (m.get(cert, []) if isinstance(m, dict) and cert in ("관행", "유기") else None)
            rt = t.get("retry", {}) or {}
            out.append({
                "kind": "plan.task", "source": "computed:grid", "resolution": "cultivation_unit",
                "stage": f"{s['order']}. {s['name']}", "task": t["name"],
                "work_day": wd, "work_date": (anchor + timedelta(days=wd)).isoformat(),
                "prep_date_own": (anchor + timedelta(days=wd - int(ld.get("own", 0)))).isoformat(),
                "prep_date_rental": (anchor + timedelta(days=wd - int(ld.get("rental", 0)))).isoformat(),
                "tools": t.get("tools", []), "materials": mats,
                "retry_possible": bool(rt.get("possible")),
                "deadline_day": rt.get("deadline_day"),
                "deadline_date": (anchor + timedelta(days=int(rt["deadline_day"]))).isoformat() if rt.get("deadline_day") is not None else None,
                "source_note": t.get("source", ""),
            })
        cap = s.get("capture")
        if isinstance(cap, dict) and cap.get("shoot"):
            w = s["window"]
            out.append({
                "kind": "plan.capture", "source": "computed:grid", "resolution": "cultivation_unit",
                "stage": f"{s['order']}. {s['name']}", "task": "촬영",
                "work_day": w["from_day"], "work_date": (anchor + timedelta(days=w["from_day"])).isoformat(),
                "prep_date_own": None, "prep_date_rental": None, "tools": [], "materials": None,
                "retry_possible": True, "deadline_day": w["to_day"],
                "deadline_date": (anchor + timedelta(days=w["to_day"])).isoformat(),
                "source_note": cap.get("scene", ""),
            })
    out.sort(key=lambda p: p["work_day"])
    return out
