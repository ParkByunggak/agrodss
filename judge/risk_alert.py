# -*- coding: utf-8 -*-
# FILE: judge/risk_alert.py
# ROLE: [M-10 ② · 첫해 값 ②] 달력형 위험 경보 — 격자 칸의 위험을 시기(창) + 예보 신호로 판정한다.
#
# 경보 비대칭(트리 H):
#   회복 불가(alert=oversignal_ok)  창이 열리면 데이터 없이도 '주의'(달력) · 신호가 있으면 '경보'   — 오경보 감수
#   회복 가능(alert=confident_only) 신호가 임계를 넘을 때만 '경보' · 그 외엔 목록에 없다           — 확률 충분할 때만
#
# 판정 대상: 오늘이 속한 칸 + horizon_days 안에 시작하는 다음 칸. 창 밖이면 해당 없음.
# 신호는 예보(forecast) 레코드에서만 읽는다 — 예찰(pest_regional)·관측(temp) 은 원천이 붙는 대로 확장.
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from grid import schema as grid_schema
from judge import registry
from judge.envelope import AxisUse, Envelope, weakest
from judge.harvest_timing import GRID_GRADE, _load_unit

DECISION_ID = "risk_alert"

registry.register(registry.Decision(
    id=DECISION_ID,
    name="달력형 위험 경보",
    required_axes=("anchor",),
    optional_axes=("forecast", "temp", "precip"),
    forbidden_axes=("humidity_air",),
    rule=("오늘이 속한 칸과 horizon 안에 시작하는 칸의 위험을 본다. 회복 불가 위험은 창이 열리면 달력만으로 '주의', "
          "예보 신호(서리·강우·습윤 연속)가 임계를 넘으면 '경보'. 회복 가능 위험은 신호가 임계를 넘을 때만 '경보'. "
          "창을 넘긴 수확 지연은 '경보'."),
    revisit_days=1,
    params={
        "horizon_days": 7,
        "frost_tmin_c": 0.0,
        "heavy_rain_mm_horizon": 50.0,
        "wet_days_pop": 70,
        "wet_days_run": 3,
        "pest_signal_words": ("발생", "주의", "경보", "다발", "증가"),
        "pest_name_keys": {"고자리파리": ("고자리",), "파총채벌레 · 파좀나방": ("총채", "좀나방"), "노균병": ("노균",),
                           "녹병 · 잎마름병": ("녹병", "잎마름")},
        "sources": "임계 전부 보수적 대체값(격자 위험 트리거 문면에서) — 쪽파 정본 임계는 미채움, 발행자 검토 대기. "
                   "frost 0℃(영하) · 강우 50mm/7일 · 강수확률 70% 3일 연속(잎 젖음 대용) · 예찰: 병해충명이 맞고 "
                   "수준/본문에 발생·주의·경보·다발·증가 중 하나(NCPMS 필드 미확정 — 원문 기반)",
    },
))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stages_in_scope(unit: dict[str, Any], day: int, horizon: int) -> list[dict[str, Any]]:
    out = []
    for s in unit.get("stages", []):
        w = s.get("window")
        if not isinstance(w, dict):
            continue
        if w["from_day"] <= day <= w["to_day"] or day < w["from_day"] <= day + horizon:
            out.append(s)
    return out


def _signals(forecast: list[dict[str, Any]], today: date, params: dict[str, Any]) -> dict[str, Any]:
    """예보에서 신호 셋: frost(첫 영하 날) · heavy_rain(horizon 합계) · wet_run(pop≥임계 연속일)."""
    horizon = today + timedelta(days=int(params["horizon_days"]))
    frost_day, rain, run, best_run = None, 0.0, 0, 0
    for r in sorted(forecast or [], key=lambda r: r.get("for_day", "")):
        fd = r.get("for_day")
        if not fd:
            continue
        d = date.fromisoformat(fd)
        if not (today <= d <= horizon):
            continue
        v = r.get("values", {})
        tmin = v.get("tmin") if v.get("tmin") is not None else v.get("tmin_from_tmp")
        if frost_day is None and tmin is not None and tmin < float(params["frost_tmin_c"]):
            frost_day = fd
        if v.get("rain_mm") is not None:
            rain += float(v["rain_mm"])
        if (v.get("pop_max") or 0) >= int(params["wet_days_pop"]):
            run += 1
            best_run = max(best_run, run)
        else:
            run = 0
    return {"frost_day": frost_day, "rain_mm": round(rain, 1), "wet_run": best_run}


def _pest_signal(risk: dict[str, Any], pest: list[dict[str, Any]], params: dict[str, Any]) -> str | None:
    """예찰 레코드 중 이 위험의 병해충명과 맞고 수준/본문에 신호 어휘가 있으면 근거 문장."""
    if "pest_regional" not in set(risk.get("axes", [])) or not pest:
        return None
    keys = None
    for rname, ks in params["pest_name_keys"].items():
        if rname in risk.get("name", "") or risk.get("name", "") in rname:
            keys = ks
            break
    if not keys:
        return None
    words = params["pest_signal_words"]
    for r in pest:
        v = r.get("values", {})
        pname = v.get("pest") or ""
        if not any(k in pname for k in keys):
            continue
        blob = " ".join(x for x in (v.get("level"), v.get("text")) if x)
        if any(w in blob for w in words):
            proxy = f" (대리 작물 {r['crop_code_crop']})" if r.get("proxy_reason") else ""
            return f"예찰 {r.get('region', '?')} {r.get('observed_at', '?')} '{pname}' {blob}{proxy}"
    return None


def _risk_signal(risk: dict[str, Any], sig: dict[str, Any], params: dict[str, Any]) -> str | None:
    """이 위험에 해당하는 예보 신호가 임계를 넘으면 근거 문장, 아니면 None."""
    axes = set(risk.get("axes", []))
    name = risk.get("name", "")
    if "forecast" in axes or "temp" in axes:
        if ("서리" in name or "한파" in name) and sig["frost_day"]:
            return f"{sig['frost_day']} 예보 최저 < {params['frost_tmin_c']}℃"
    if "precip" in axes or "forecast" in axes or "soil_water" in axes:
        if ("과습" in name or "부패" in name or "장마" in name) and sig["rain_mm"] >= float(params["heavy_rain_mm_horizon"]):
            return f"{params['horizon_days']}일 예보 강수 합 {sig['rain_mm']}mm ≥ {params['heavy_rain_mm_horizon']}mm"
        if ("노균병" in name or "잎마름" in name or "녹병" in name) and sig["wet_run"] >= int(params["wet_days_run"]):
            return f"강수확률 ≥{params['wet_days_pop']}% {sig['wet_run']}일 연속(잎 젖음 대용)"
    return None


def judge(subject: dict[str, Any], forecast: list[dict[str, Any]] | None = None,
          today: date | None = None, pest: list[dict[str, Any]] | None = None) -> Envelope:
    today = today or date.today()
    as_of = _now()
    sid = subject.get("id", "?")
    d = registry.get(DECISION_ID)
    unit = _load_unit(subject)
    if unit is None:
        return Envelope("해당 없음", DECISION_ID, sid, as_of, result={"why": "격자 단위가 없다"})
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", DECISION_ID, sid, as_of,
                        missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일(사건 입력)"}],
                        result={"why": "기준점(파종일)이 없다"})
    anchor_d = date.fromisoformat(anchor)
    day = (today - anchor_d).days
    horizon = int(d.params["horizon_days"])
    stages = _stages_in_scope(unit, day, horizon)
    last_to = max((s["window"]["to_day"] for s in unit["stages"] if isinstance(s.get("window"), dict)), default=None)
    if not stages and (last_to is None or day <= last_to):
        return Envelope("해당 없음", DECISION_ID, sid, as_of,
                        result={"why": f"기준점 후 {day}일 — 오늘과 {horizon}일 안에 여는 격자 칸이 없다"})
    for s in stages:
        errs = registry.check_against_grid(d, s)
        if errs:
            return Envelope("판단 불가(지식)", DECISION_ID, sid, as_of, result={"why": "결정과 칸의 축 선언이 어긋난다", "detail": errs})

    sig = _signals(forecast or [], today, d.params) if forecast else None
    alerts: list[dict[str, Any]] = []
    watched = 0
    for s in stages:
        risks = s.get("risks")
        if risks == grid_schema.NA or not risks:
            continue
        w = s["window"]
        stage_open = w["from_day"] <= day <= w["to_day"]
        for r in risks:
            unrec = r.get("recoverable") is False
            basis = (_risk_signal(r, sig, d.params) if sig else None) or _pest_signal(r, pest or [], d.params)
            if unrec:
                if basis:
                    level = "경보"
                elif stage_open:
                    level, basis = "주의", f"달력 — 칸 '{s['name']}' 창 안(예보 신호 없음, 오경보 감수)"
                else:
                    level, basis = "예고", f"달력 — 칸 '{s['name']}' 가 {w['from_day'] - day}일 뒤 열린다"
            else:
                watched += 1
                if not basis:
                    continue                       # 회복 가능 — 신호 없으면 침묵(confident_only)
                level = "경보"
            alerts.append({"risk": r["name"], "stage": f"{s['order']}. {s['name']}", "level": level,
                           "recoverable": not unrec, "policy": r.get("alert"), "basis": basis,
                           "axes": r.get("axes", []), "source": r.get("source", "")})
    # 수확 지연 — 창을 넘긴 뒤에도 경보(회복 불가)
    for s in unit["stages"]:
        w = s.get("window")
        if isinstance(w, dict) and "harvest_timing" in (s.get("decisions") or []) and day > w["to_day"]:
            alerts.append({"risk": "수확 지연", "stage": f"{s['order']}. {s['name']}", "level": "경보",
                           "recoverable": False, "policy": "oversignal_ok",
                           "basis": f"수확 창({w['from_day']}~{w['to_day']}일)을 {day - w['to_day']}일 넘겼다", "axes": ["anchor"], "source": "격자"})
    inputs = [AxisUse("anchor", anchor, subject.get("source", "farmer"), "cultivation_unit", "관측")]
    grades = ["관측", GRID_GRADE.get(unit["unit"].get("confidence", "하"), "추정")]
    notes = [f"격자 출처: {unit['unit'].get('source', '?')}", f"임계: {d.params['sources']}"]
    if forecast:
        f0 = forecast[0]
        inputs.append(AxisUse("forecast", f0.get("observed_at"), f0.get("source", "?"), f0.get("resolution", "?"), "관측"))
    else:
        notes.append("예보 없음 — 회복 불가 위험은 달력만으로 '주의', 회복 가능 위험은 판정 보류")
    if pest:
        p0 = pest[0]
        inputs.append(AxisUse("pest_regional", p0.get("observed_at"), p0.get("source", "?"), p0.get("resolution", "?"), "관측"))
        if p0.get("proxy_reason"):
            notes.append(f"예찰은 대리 작물 기준: {p0['proxy_reason']}")
    else:
        notes.append("예찰 없음 — 병해충 위험은 달력·예보만으로")
    order = {"경보": 0, "주의": 1, "예고": 2}
    alerts.sort(key=lambda a: order.get(a["level"], 9))
    return Envelope(
        "판단함", DECISION_ID, sid, as_of, inputs=inputs,
        revisit_at=(today + timedelta(days=d.revisit_days)).isoformat(), grade=weakest(grades),
        result={"days_since_anchor": day, "horizon_days": horizon, "stages": [f"{s['order']}. {s['name']}" for s in stages],
                "alerts": alerts, "watched_recoverable": watched,
                "signals": sig or {"note": "예보 없음"}},
        notes=notes,
    )
