# -*- coding: utf-8 -*-
# FILE: grid/capture.py
# ROLE: 격자의 '촬영 시점' 칸 → 오늘 찍을 장면. DSS→몰 허용 흐름(I-5 §1-2 "촬영 시점 알림")의 최소 구현.
#       판단이 아니다 — 기준점에서 며칠째인지와 칸의 창을 대조할 뿐이다.
from __future__ import annotations

from datetime import date
from typing import Any

from grid import schema


def stage_for_day(unit: dict[str, Any], day: int) -> dict[str, Any] | None:
    for s in unit.get("stages", []):
        w = s.get("window")
        if isinstance(w, dict) and w["from_day"] <= day <= w["to_day"]:
            return s
    return None


def hint_for(subject: dict[str, Any], today: date) -> dict[str, Any] | None:
    """subject(data/subjects.json 항목) → {day, stage, shoot, scene, window} 또는 None(격자·기준점 없음)."""
    unit_id = subject.get("grid_unit")
    anchor = subject.get("anchor")
    if not unit_id or not anchor:
        return None
    path = schema.GRID_DIR / f"{unit_id.replace('-', '_')}.json"
    if not path.exists():
        return None
    unit = schema.load(path)
    day = (today - date.fromisoformat(anchor)).days
    s = stage_for_day(unit, day)
    if s is None:
        return {"day": day, "stage": None, "shoot": False, "scene": "", "window": None}
    cap = s.get("capture") if isinstance(s.get("capture"), dict) else {}
    return {
        "day": day,
        "stage": f"{s['order']}. {s['name']}",
        "shoot": bool(cap.get("shoot")),
        "scene": cap.get("scene", ""),
        "window": (s["window"]["from_day"], s["window"]["to_day"]),
    }
