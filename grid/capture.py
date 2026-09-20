# -*- coding: utf-8 -*-
# FILE: grid/capture.py
# ROLE: 격자의 '촬영 시점' 칸 → 오늘 찍을 장면. DSS→몰 허용 흐름(I-5 §1-2 "촬영 시점 알림")의 최소 구현.
#       판단이 아니다 — 기준점에서 며칠째인지와 칸의 창을 대조할 뿐이다.
from __future__ import annotations

from datetime import date
from typing import Any

from grid import schema


# [B4 · 2026-09-20] "오늘 칸"의 정본은 여기 하나다. 격자 창은 양끝 포함(from_day <= day <= to_day)이라 경계일(10 · 30 · 50 · 70)은 두 칸에
# 걸린다 — 어느 칸이 맞는지는 격자 지식(검토지 ⓓ B4)이고, 코드가 정할 일이 아니다. 답이 오기 전까지의 **약속**: 경계일은 **앞 칸**이다
# (첫 매치). 판정기마다 따로 창을 비교하면 그 약속이 갈린다(실측: stage_for_day 는 칸 3, risk_alert 는 칸 3·4). 그래서 열린 칸 전부는
# stages_open, 오늘 칸 하나는 stage_for_day — 둘 다 여기서만 창을 비교한다. B4 답이 오면 격자 데이터에서 겹침을 없애고 이 약속은 사라진다.
def is_open(window: Any, day: int) -> bool:
    return isinstance(window, dict) and window["from_day"] <= day <= window["to_day"]


def stages_open(unit: dict[str, Any], day: int) -> list[dict[str, Any]]:
    """오늘 열린 칸 전부(경계일이면 둘). 경보처럼 '열린 칸 전부'를 봐야 하는 곳이 쓴다."""
    return [s for s in unit.get("stages", []) if is_open(s.get("window"), day)]


def stage_for_day(unit: dict[str, Any], day: int) -> dict[str, Any] | None:
    """오늘 칸 하나 — 열린 칸 중 첫 번째(경계일은 앞 칸)."""
    open_ = stages_open(unit, day)
    return open_[0] if open_ else None


def hint_for(subject: dict[str, Any], today: date) -> dict[str, Any] | None:
    """subject(data/subjects.json 항목) → {day, stage, shoot, scene, window} 또는 None(격자·기준점 없음)."""
    unit_id = subject.get("grid_unit")
    anchor = subject.get("anchor")
    if not unit_id or not anchor:
        return None
    path = schema.unit_path(unit_id)
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
