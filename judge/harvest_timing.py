# -*- coding: utf-8 -*-
# FILE: judge/harvest_timing.py
# ROLE: [M-10 ① · 첫해 값 ①] 수확 시기 판단 — I-1 §3 판별 순서를 그대로 밟는다.
#
#   등록됐는가 → 답하지 않음인가 → 해당하는가 → 격자 칸이 채워졌는가 → 필요 축이 있는가 →
#   예측 불가인가 → 선택지형인가 → 사실 인용인가 → 판단함
#
# 지식 미비가 데이터 미비보다 앞이다 — "입력하면 된다"고 말해 놓고 입력해도 답이 안 나오면 안 된다.
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from grid import schema as grid_schema
from judge import registry
from judge.envelope import AxisUse, Envelope, weakest

DECISION_ID = "harvest_timing"
GRID_GRADE = {"상": "관측", "중": "추정", "하": "추정"}   # 격자 출처 확신 → 등급. 추론 초안은 '추정'을 넘지 못한다


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_unit(subject: dict[str, Any]) -> dict[str, Any] | None:
    uid = subject.get("grid_unit")
    if not uid:
        return None
    p = grid_schema.GRID_DIR / f"{uid.replace('-', '_')}.json"
    return grid_schema.load(p) if p.exists() else None


def _harvest_stage(unit: dict[str, Any]) -> dict[str, Any] | None:
    for s in unit.get("stages", []):
        if DECISION_ID in (s.get("decisions") or []):
            return s
    return None


def judge(subject: dict[str, Any], forecast: list[dict[str, Any]] | None = None,
          obs: list[dict[str, Any]] | None = None, today: date | None = None,
          variety_known: bool = False) -> Envelope:
    """subject: data/subjects.json 항목. forecast/obs: ingest.kma 레코드(없으면 None — 키 없음 등)."""
    today = today or date.today()
    as_of = _now()
    sid = subject.get("id", "?")
    d = registry.get(DECISION_ID)
    if d is None:
        raise RuntimeError("harvest_timing 이 등록되지 않았다")

    # 1~2. 등록됨 · 정책은 '판단'
    # 3. 해당하는가 — 격자 단위와 수확 칸이 있어야 이 결정이 적용된다
    unit = _load_unit(subject)
    stage = _harvest_stage(unit) if unit else None
    if unit is None or stage is None:
        return Envelope("해당 없음", DECISION_ID, sid, as_of,
                        result={"why": "이 재배 단위에는 수확 시기 결정이 적용되는 격자 칸이 없다"})

    # 4. 격자 칸이 채워졌는가 (지식) — 창이 없으면 데이터를 채워도 답이 안 나온다
    w = stage.get("window")
    if not isinstance(w, dict) or w == grid_schema.NA:
        return Envelope("판단 불가(지식)", DECISION_ID, sid, as_of,
                        result={"why": f"격자 칸 '{stage.get('name')}' 의 수확 창(window)이 아직 안 채워졌다",
                                "who": "격자 채우기(M-9) — 우리가 아직 안 만들었다"})
    consistency = registry.check_against_grid(d, stage)
    if consistency:
        return Envelope("판단 불가(지식)", DECISION_ID, sid, as_of,
                        result={"why": "결정 등록과 격자 칸의 축 선언이 어긋난다", "detail": consistency})

    # 5. 필요 축 — anchor
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", DECISION_ID, sid, as_of,
                        missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일(사건 입력)"}],
                        result={"why": "기준점(파종일)이 없다"})
    anchor_d = date.fromisoformat(anchor)
    inputs = [AxisUse("anchor", anchor, subject.get("source", "farmer"), "cultivation_unit", "관측")]
    grades = ["관측", GRID_GRADE.get(unit["unit"].get("confidence", "하"), "추정")]
    notes = [f"격자 출처: {unit['unit'].get('source', '?')}"]

    # 6~8. 예측 불가 아님 · 선택지형 아님 · 사실 인용 아님 → 판단함
    start = anchor_d + timedelta(days=w["from_day"])
    end = anchor_d + timedelta(days=w["to_day"])
    half = (w["to_day"] - w["from_day"]) / 2
    center = anchor_d + timedelta(days=round((w["from_day"] + w["to_day"]) / 2))
    jw = stage.get("judge_without_variety")
    if not variety_known and jw == "range":
        notes.append("품종 미확인 — 범위로 제시(격자 judge_without_variety=range)")
    day = (today - anchor_d).days
    position = "창 이전" if today < start else ("창 안" if today <= end else "창 지남")

    # 선택 축: 예보 → 상한 제약(첫 서리)
    caps: list[dict[str, str]] = []
    degraded: list[str] = []
    if forecast:
        thr = float(d.params["frost_tmin_c"])
        for r in forecast:
            v = r.get("values", {})
            tmin = v.get("tmin") if v.get("tmin") is not None else v.get("tmin_from_tmp")
            fd = r.get("for_day")
            if tmin is not None and fd and tmin < thr and start <= date.fromisoformat(fd) <= end + timedelta(days=0):
                caps.append({"name": "첫 서리 예보", "basis": f"{fd} 예보 최저 {tmin}℃ < {thr}℃ — 수확 앞당김 판단(격자 위험 '첫 서리·한파')"})
        if forecast:
            f0 = forecast[0]
            inputs.append(AxisUse("forecast", f0.get("observed_at"), f0.get("source", "?"), f0.get("resolution", "?"), "관측"))
    else:
        degraded.append("forecast")
    if obs:
        o0 = obs[-1]
        inputs.append(AxisUse("temp", o0.get("observed_at"), o0.get("source", "?"), o0.get("resolution", "?"), "관측"))
    else:
        degraded.append("temp")
    if degraded:
        notes.append("선택 축 없음: " + ", ".join(degraded) + " — 등급은 격자 출처 기준, 상한 제약 없음")

    return Envelope(
        "판단함", DECISION_ID, sid, as_of, inputs=inputs, caps=caps,
        revisit_at=(today + timedelta(days=d.revisit_days)).isoformat() if d.revisit_days else None,
        grade=weakest(grades),
        result={
            "window_start": start.isoformat(), "window_end": end.isoformat(), "center": center.isoformat(),
            "error_days": half, "days_since_anchor": day, "position": position,
            "basis": f"기준점 {anchor}({unit['unit'].get('anchor_kind')}) + 격자 창 {w['from_day']}~{w['to_day']}일",
            "final_say": "잎 길이·상태는 농가 관찰이 최종 심급(격자 수확 작업 출처)",
        },
        notes=notes,
    )
