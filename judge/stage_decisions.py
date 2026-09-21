# -*- coding: utf-8 -*-
# FILE: judge/stage_decisions.py
# ROLE: [M-10 결정 등록] 격자 칸이 선언한 결정 중 남은 8건 — sowing_window · base_fertilization · replant · pest_alert ·
#       top_dressing_1 · top_dressing_2 · drainage_alert · ship_or_store. 등록부에 규칙·축을 선언하고 판정한다.
#
#   정직성: 정본이 없는 것은 판단 불가(지식)로, 입력이 없는 것은 판단 불가(데이터)로 낸다. 값을 지어내지 않는다.
#   · base_fertilization / top_dressing 의 **양**은 처방 정본(토양검정 처방 기준)이 격자에 도착하지 않았다 → 지식 미비.
#   · pest_alert / drainage_alert 는 risk_alert 의 봉투를 그 칸으로 잘라 낸다(같은 규칙, 다른 결정 id — 두 벌 로직 금지).
#   · ship_or_store 는 D-8(이번 작기 자가) 이면 해당 없음, 납품 계획일이 없으면 데이터 미비.
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from judge import plan_vs_actual, registry, risk_alert
from judge.envelope import AxisUse, Envelope, weakest
from judge.harvest_timing import GRID_GRADE, _load_unit

FORB = ("humidity_air",)
SELF_USE_WORDS = ("자가", "시험")
REPLANT_WORDS = ("결주", "빈", "안 났", "안났", "드문", "듬성", "성글", "출현 불량", "안 올라")
TOP_DRESSING_EVENT = "시비"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stage(unit: dict[str, Any], decision_id: str) -> dict[str, Any] | None:
    for s in unit.get("stages", []):
        if decision_id in (s.get("decisions") or []):
            return s
    return None


def _task(stage: dict[str, Any], key: str) -> dict[str, Any] | None:
    tasks = stage.get("tasks")
    if not isinstance(tasks, list):
        return None
    return next((t for t in tasks if key in t.get("name", "")), None)


def _deadline_day(task: dict[str, Any] | None) -> int | None:
    """격자 작업의 마감(일). 없으면 None — **창 끝으로 메우지 않는다**.

    [대리값 전수 2026-09-20] B6 에서 출하 마감의 기본값 63 을 없앴는데, 같은 지식(retry.deadline_day)을 읽는
    자리가 넷이었고 처방은 한 곳에만 닿아 있었다(§7.5 지점 축). 나머지 셋은 `stage["window"]["to_day"]` 로
    메우고 있었다 — 리터럴이 아니라 **식**이라 직전 회차의 숫자 축 전수가 못 봤다. 읽는 법을 한 벌로 세운다.
    """
    d = ((task or {}).get("retry") or {}).get("deadline_day")
    return int(d) if d is not None else None


def _no_deadline(did: str, sid: str, as_of: str, task_name: str) -> Envelope:
    return Envelope("판단 불가(지식)", did, sid, as_of,
                    result={"why": f"격자 작업 '{task_name}' 에 마감(retry.deadline_day)이 없다 — 창 끝으로 지어내지 않는다",
                            "summary": f"{task_name} 마감 미채움"})


def _need_cert(did: str, sid: str, as_of: str) -> Envelope:
    """[코드 평가 B2] cert 는 시비 결정의 필요 축 — 없으면 판단 불가(데이터). 전에는 mats.get(None, []) 로 빈 자재를 들고 '판단함'이 나갔다."""
    return Envelope("판단 불가(데이터)", did, sid, as_of,
                    missing=[{"axis": "cert", "who_can_fill": "농가 — 인증 유형(유기 · 무농약 · 관행) 을 재배 단위에"}],
                    result={"why": "인증 유형(cert)이 없다 — 자재 갈래를 정할 수 없다", "summary": "인증 유형 대기"})


def _grid_grade(unit: dict[str, Any]) -> str:
    return GRID_GRADE.get(unit["unit"].get("confidence", "하"), "추정")


def _anchor_inputs(subject: dict[str, Any], anchor: str) -> list[AxisUse]:
    return [AxisUse("anchor", anchor, subject.get("source", "farmer"), "cultivation_unit", "관측")]


# ── 등록 ─────────────────────────────────────────────────────────────────────────
_R = registry.register
SOWING_WINDOW = _R(registry.Decision(
    id="sowing_window", name="파종 창", required_axes=("anchor",), optional_axes=("temp",), forbidden_axes=FORB,
    rule="기준점(파종일)이 있으면 격자 칸 1 의 창(anchor 상대)을 날짜로 낸다. 창을 지났으면 해당 없음(이미 파종). "
         "기준점이 없는 계획 목록에는 달력 기준 적기가 정본에 없으므로 판단 불가(지식).", revisit_days=None,
    params={"source": "격자 jjokpa-autumn 칸 1 window"}))
BASE_FERTILIZATION = _R(registry.Decision(
    id="base_fertilization", name="밑거름", required_axes=("anchor", "soil_chem", "cert"), optional_axes=(), forbidden_axes=FORB,
    rule="밑거름 창(칸 1, 파종 마감일까지) 안에서만 산다. 토양검정 값(soil_chem)이 없으면 판단 불가(데이터). "
         "값이 있어도 시비량 처방 정본이 격자에 없으면 판단 불가(지식) — 양을 지어내지 않는다. 자재는 인증 갈래만 인용.", revisit_days=None,
    params={"source": "격자 칸 1 tasks[밑거름] materials · 처방 정본 미도착"}))
REPLANT = _R(registry.Decision(
    id="replant", name="보식", required_axes=("anchor",), optional_axes=("soil_water", "temp"), forbidden_axes=FORB,
    rule="발아·출현 창(칸 2) 안에서, 농가 관찰(결주·출현 불량)이 있으면 마감일까지 보식을 권고한다(판단함). "
         "관찰이 없으면 판단 불가(데이터) — 출현 상태는 농가 관찰이 최종 심급. 창 밖이면 해당 없음.", revisit_days=1,
    # [두 층 불일치 2026-09-21] 이 결정은 "관찰이 없으면 판단 불가(데이터)" 라고 **이미 선언하고 있었는데**, 계획 대 실제는
    # 같은 작업을 '놓침 — 사유를 묻는다' 로 냈다. 한 작업에 두 층이 다른 답을 한 것이다. 원인은 '조건부' 라는 사실이
    # **격자 작업명의 괄호 표기**("관수(건조 시)")에만 실려 있었고 '보식' 이라는 이름에는 그 표기가 없었다는 것 — 곧 조건
    # 여부가 작업명 문자열에만 있는 **두 벌 진실**이었다. 조건을 여기 선언하면 두 층이 같은 것을 읽는다(계획 대 실제는
    # registry 만 import 하므로 순환이 없다 — import 방향은 stage_decisions → plan_vs_actual 이다).
    params={"words": REPLANT_WORDS, "source": "격자 칸 2 tasks[보식] retry.deadline_day",
            "conditional_task": "보식",                       # 이 격자 작업은 조건부다 — 안 했다고 놓친 것이 아니다
            "condition": "결주·출현 불량 관찰(농가)",            # 무엇이 채워져야 조건이 서는가
            "condition_source": "농가 — 출현 상태 한 줄(채팅 관찰: 결주 · 듬성 · 안 났다)"}))
PEST_ALERT = _R(registry.Decision(
    id="pest_alert", name="병해충 경보(칸 3)", required_axes=("anchor",), optional_axes=("pest_regional", "temp", "precip", "microclimate"),
    forbidden_axes=FORB, rule="risk_alert 와 같은 규칙(비대칭 경보)을 칸 3 의 위험에만 적용해 낸다. 칸이 horizon 밖이면 해당 없음.",
    revisit_days=1, params={"delegate": "risk_alert", "stage_order": 3}))
TOP_DRESSING_1 = _R(registry.Decision(
    id="top_dressing_1", name="웃거름 1회", required_axes=("anchor", "cert"), optional_axes=("temp", "precip"), forbidden_axes=FORB,
    rule="칸 3 작업 '웃거름 1회'의 작업일·마감일을 날짜로 내고, 창 안 시비 사건이 있으면 이행, 작업일이 지났는데 없으면 미이행, "
         "아직이면 예정. 자재는 인증 갈래만. 양은 처방 정본 미도착 — 판단 불가(지식)로 병기.", revisit_days=1,
    params={"task_key": "웃거름 1회", "stage_order": 3, "event_type": TOP_DRESSING_EVENT}))
TOP_DRESSING_2 = _R(registry.Decision(
    id="top_dressing_2", name="웃거름 2회(필요 시)", required_axes=("anchor", "cert"), optional_axes=("temp", "precip", "soil_water"), forbidden_axes=FORB,
    rule="'필요 시' 의 필요 여부 판정 규칙이 격자에 미채움 — 판단 불가(지식). 창·자재만 사실로 낸다.", revisit_days=None,
    params={"task_key": "웃거름 2회", "stage_order": 4}))
DRAINAGE_ALERT = _R(registry.Decision(
    id="drainage_alert", name="배수 경보(칸 4)", required_axes=("anchor",), optional_axes=("forecast", "precip", "soil_water"),
    forbidden_axes=FORB, rule="risk_alert 와 같은 규칙을 칸 4 의 위험(과습·부패 — 회복 불가)에만 적용해 낸다. 칸이 horizon 밖이면 해당 없음.",
    revisit_days=1, params={"delegate": "risk_alert", "stage_order": 4}))
SHIP_OR_STORE = _R(registry.Decision(
    id="ship_or_store", name="출하 또는 저장", required_axes=("anchor",), optional_axes=("forecast", "temp"), forbidden_axes=FORB,
    rule="필지 용도가 자가·시험(D-8)이면 해당 없음. 납품 계획일(plan.target_date, 농가만)이 없으면 판단 불가(데이터). "
         "있으면 수확 창 끝과 계획일의 간격을 저장 일수로 내고, 칸 5 '출하 또는 단기 저장' 마감(63일)을 넘기면 상한 제약.", revisit_days=7,
    params={"source": "격자 칸 5 tasks[출하 또는 단기 저장] retry.deadline_day"}))

IDS = ("sowing_window", "base_fertilization", "replant", "pest_alert", "top_dressing_1", "top_dressing_2", "drainage_alert", "ship_or_store")


# ── 판정 ─────────────────────────────────────────────────────────────────────────
def _base(subject: dict[str, Any], did: str, today: date):
    """공통 앞부분 — (unit, stage, anchor_date, day) 또는 즉시 돌려줄 봉투."""
    sid = subject.get("id", "?")
    as_of = _now()
    unit = _load_unit(subject)
    if unit is None:
        return None, Envelope("해당 없음", did, sid, as_of, result={"why": "격자 단위가 없다"})
    stage = _stage(unit, did)
    if stage is None:
        return None, Envelope("해당 없음", did, sid, as_of, result={"why": "이 결정을 선언한 격자 칸이 없다"})
    d = registry.get(did)
    errs = registry.check_against_grid(d, stage)
    if errs:
        return None, Envelope("판단 불가(지식)", did, sid, as_of, result={"why": "결정과 칸의 축 선언이 어긋난다", "detail": errs})
    return (unit, stage, sid, as_of), None


def _dates(anchor_d: date, stage: dict[str, Any]) -> tuple[date, date]:
    w = stage["window"]
    return anchor_d + timedelta(days=w["from_day"]), anchor_d + timedelta(days=w["to_day"])


def judge_sowing_window(subject, today: date) -> Envelope:
    ctx, env = _base(subject, "sowing_window", today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(지식)", "sowing_window", sid, as_of,
                        result={"why": "격자 파종 창은 기준점 상대(anchor -7~0일)라 파종 전 목록에는 달력 기준 적기가 정본에 없다",
                                "summary": "달력 기준 파종 적기 정본 없음 — 농사로 재배기술 대조(M-15) 뒤"})
    a = date.fromisoformat(anchor)
    day = (today - a).days
    s, e = _dates(a, stage)
    if day > stage["window"]["to_day"]:
        return Envelope("해당 없음", "sowing_window", sid, as_of, result={"why": f"이미 파종됨(기준점 {anchor}, {day}일 경과)", "summary": f"이미 파종됨 — 기준점 {anchor}"})
    return Envelope("판단함", "sowing_window", sid, as_of, inputs=_anchor_inputs(subject, anchor), grade=weakest(["관측", _grid_grade(unit)]),
                    result={"window_start": s.isoformat(), "window_end": e.isoformat(), "summary": f"파종 창 {s} ~ {e}(격자 칸 1)"})


def _prescription(prescriptions: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """필지 처방 레코드 중 success 인 최신 것. 표준 시비량(national)은 여기 안 온다 — 필지값이 아니라서 처방으로 안 쓴다."""
    ok = [p for p in (prescriptions or []) if p.get("kind") == "reference.fertilizer_prescription" and p.get("status") == "success" and p.get("values")]
    return sorted(ok, key=lambda p: p.get("fetched_at") or "")[-1] if ok else None


def _prescription_input(p: dict[str, Any]) -> AxisUse:
    return AxisUse("soil_chem", p.get("observed_at"), p["source"], p["resolution"], "관측")


def _amounts(p: dict[str, Any], prefix: str) -> str:
    v, u = p.get("values", {}), p.get("units", {})
    parts = [f"{lab} {v[k]}{u.get(k, '')}" for k, lab in ((f"{prefix}_n", "N"), (f"{prefix}_p2o5", "P₂O₅"), (f"{prefix}_k2o", "K₂O")) if k in v]
    return " · ".join(parts)


def judge_base_fertilization(subject, today: date, prescriptions: list[dict[str, Any]] | None = None) -> Envelope:
    ctx, env = _base(subject, "base_fertilization", today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", "base_fertilization", sid, as_of, missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일"}], result={"why": "기준점이 없다"})
    a = date.fromisoformat(anchor)
    day = (today - a).days
    t = _task(stage, "밑거름")
    deadline = _deadline_day(t)
    if deadline is None:
        return _no_deadline("base_fertilization", sid, as_of, "밑거름")
    if day > deadline:
        return Envelope("해당 없음", "base_fertilization", sid, as_of,
                        result={"why": f"밑거름 창(파종 마감 {deadline}일)을 지났다 — 이후는 웃거름", "summary": "창 지남 — 웃거름 결정으로"})
    if not subject.get("soil_chem"):
        return Envelope("판단 불가(데이터)", "base_fertilization", sid, as_of,
                        missing=[{"axis": "soil_chem", "who_can_fill": "농가 — 토양검정(python -m ingest.fertilizer <주소>, 키 투입) 또는 성적서 값"}],
                        result={"why": "토양검정 값이 없다", "summary": "토양검정 값 대기"})
    cert = subject.get("cert")
    if not cert:
        return _need_cert("base_fertilization", sid, as_of)
    mats = (t or {}).get("materials")
    m = mats.get(cert, []) if isinstance(mats, dict) else []
    p = _prescription(prescriptions)
    if p is None:
        return Envelope("판단 불가(지식)", "base_fertilization", sid, as_of,
                        result={"why": "시비량 처방 정본(흙토람 FrtlzrUse — 검정값 기반)이 아직 이 필지에 없다 — 양을 지어내지 않는다. python -m ingest.fertilizer <주소> 로 받는다",
                                "materials": m, "summary": f"자재 갈래({cert}): {', '.join(m) or '없음'} · 양은 정본 대기"})
    # [M-15 ⑥] 처방 정본 도착 — 기비 N·P·K 와 퇴비(kg/10a). 유기 갈래는 화학비료가 아니라 **목표 양분량**으로 읽는다(자재 환산 규칙은 정본 없음)
    v = p.get("values", {})
    compost = {k: v[k] for k in ("compost_cattle", "compost_pig", "compost_chicken", "compost_mixed") if k in v}
    notes = [f"출처: {p['source']} · 조회 {str(p.get('fetched_at', ''))[:10]} · 작물코드 {p.get('crop_code')}"]
    if cert == "유기":
        notes.append("유기 갈래: N·P·K 는 목표 양분량 — 공시 유기질 비료·퇴비로 환산하는 규칙은 정본 없음(지식 미비, 자재 성분표로 사람이 환산)")
    return Envelope("판단함", "base_fertilization", sid, as_of, inputs=_anchor_inputs(subject, anchor) + [_prescription_input(p)],
                    grade=weakest(["관측", _grid_grade(unit)]),
                    result={"pre": _amounts(p, "pre"), "compost_kg_10a": compost, "materials": m, "values": v, "units": p.get("units", {}),
                            "summary": f"기비 {_amounts(p, 'pre') or '값 없음'} · 퇴비 {', '.join(f'{k} {val}' for k, val in compost.items()) or '없음'} (kg/10a) · 자재({cert}) {', '.join(m) or '없음'}"},
                    notes=notes)


def judge_replant(subject, today: date, observations: list[dict[str, Any]] | None = None) -> Envelope:
    ctx, env = _base(subject, "replant", today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", "replant", sid, as_of, missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일"}], result={"why": "기준점이 없다"})
    a = date.fromisoformat(anchor)
    day = (today - a).days
    t = _task(stage, "보식")
    deadline = _deadline_day(t)
    if deadline is None:
        return _no_deadline("replant", sid, as_of, "보식")
    w0 = stage["window"]["from_day"]
    if day < w0 or day > deadline:
        return Envelope("해당 없음", "replant", sid, as_of, result={"why": f"보식 창({w0}~{deadline}일) 밖 — 오늘 {day}일", "summary": "창 밖"})
    obs = observations or []
    words = REPLANT_WORDS
    seen = [o for o in obs if (o.get("observed_at") or "") >= (a + timedelta(days=w0)).isoformat() and any(k in (o.get("text") or "") for k in words)]
    if not seen:
        return Envelope("판단 불가(데이터)", "replant", sid, as_of,
                        missing=[{"axis": "observation", "who_can_fill": "농가 — 출현 상태 한 줄(채팅 관찰: 결주 · 듬성 · 안 났다)"}],
                        result={"why": "출현 관찰이 없다 — 최종 심급은 농가 관찰", "summary": "출현 관찰 대기"})
    dl = (a + timedelta(days=deadline)).isoformat()
    return Envelope("판단함", "replant", sid, as_of, inputs=_anchor_inputs(subject, anchor), grade=weakest(["관측", _grid_grade(unit)]),
                    revisit_at=(today + timedelta(days=1)).isoformat(),
                    result={"deadline": dl, "observations": [o.get("id") for o in seen],
                            "summary": f"결주 관찰 {len(seen)}건 — 마감 {dl} 까지 보식(칸 2 retry)"})


def _delegate_risk(subject, did: str, today: date, forecast, pest) -> Envelope:
    ctx, env = _base(subject, did, today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    r = risk_alert.judge(subject, forecast=forecast, today=today, pest=pest)
    if r.kind != "판단함":
        return Envelope(r.kind, did, sid, as_of, missing=list(r.missing), result=dict(r.result), notes=list(r.notes))
    tag = f"{stage['order']}. {stage['name']}"
    if tag not in (r.result.get("stages") or []):
        return Envelope("해당 없음", did, sid, as_of, result={"why": f"칸 '{tag}' 가 horizon 밖", "summary": "칸이 창 밖"})
    alerts = [a for a in r.result.get("alerts", []) if a.get("stage") == tag]
    body = " / ".join(f"{a['level']} {a['risk']}" for a in alerts) or "이 칸에 경보 없음"
    return Envelope("판단함", did, sid, as_of, inputs=list(r.inputs), grade=r.grade, revisit_at=r.revisit_at,
                    result={"stage": tag, "alerts": alerts, "signals": r.result.get("signals"), "summary": body}, notes=list(r.notes))


def judge_pest_alert(subject, today: date, forecast=None, pest=None) -> Envelope:
    return _delegate_risk(subject, "pest_alert", today, forecast, pest)


def judge_drainage_alert(subject, today: date, forecast=None, pest=None) -> Envelope:
    return _delegate_risk(subject, "drainage_alert", today, forecast, pest)


def judge_top_dressing(subject, did: str, today: date, evts: list[dict[str, Any]] | None = None,
                       prescriptions: list[dict[str, Any]] | None = None) -> Envelope:
    ctx, env = _base(subject, did, today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    d = registry.get(did)
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", did, sid, as_of, missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일"}], result={"why": "기준점이 없다"})
    a = date.fromisoformat(anchor)
    day = (today - a).days
    t = _task(stage, d.params["task_key"])
    if t is None:
        return Envelope("판단 불가(지식)", did, sid, as_of, result={"why": "격자에 그 작업 칸이 없다"})
    wd = int(t["work_day"])
    deadline = _deadline_day(t)
    if deadline is None:
        return _no_deadline(did, sid, as_of, str(t.get("name", d.params["task_key"])))
    cert = subject.get("cert")
    if not cert:
        return _need_cert(did, sid, as_of)                                   # [B2] 필요 축 부재는 데이터 미비 — 빈 자재로 판단하지 않는다
    mats = t.get("materials")
    m = mats.get(cert, []) if isinstance(mats, dict) else []
    work_date, dl = (a + timedelta(days=wd)).isoformat(), (a + timedelta(days=deadline)).isoformat()
    # [B5] 판별 순서(I-1 §3): 해당하는가 → 지식 → 데이터. 창 지남을 먼저 본다 — 전에는 지식 미비가 먼저라 시즌 내내 그 상태로 남았다
    if day > deadline:
        return Envelope("해당 없음", did, sid, as_of, result={"why": f"마감({dl})을 지났다", "summary": f"창 지남({dl})"})
    if did == "top_dressing_2":
        return Envelope("판단 불가(지식)", did, sid, as_of,
                        result={"why": "'필요 시' 의 필요 여부 판정 규칙이 격자에 미채움(생육 관찰 기준 없음)", "work_date": work_date, "deadline": dl,
                                "materials": m, "summary": f"필요 여부 규칙 없음 — 창 {work_date}~{dl} · 자재({cert}) {', '.join(m) or '없음'}"})
    # [B3] 이행 판정은 계획 대 실제와 **한 벌** — 같은 매처 · 같은 허용 폭(registry params). 전에는 wd-7 하드코딩 · 예정 경계가 달라
    # 같은 사건이 한쪽은 이행, 다른 쪽은 미이행이었다
    pva = registry.get(plan_vs_actual.DECISION_ID)
    row = {"task": t.get("name", d.params["task_key"]), "work_date": work_date, "deadline_date": dl}
    hit = plan_vs_actual._matched_event(row, list(evts or []), int(pva.params["tolerance_days"]), pva.params)
    done = [hit] if hit else []
    reason = plan_vs_actual.reason_for(list(evts or []), row["task"], work_date)   # 불이행 사유도 계획 대 실제와 같은 키 — 한 벌
    status = "이행" if done else ("사유 기록됨" if reason else ("예정" if day < wd else "미이행"))
    p = _prescription(prescriptions)
    inputs = _anchor_inputs(subject, anchor)
    if p is not None:
        amount = _amounts(p, "post") or "처방에 추비 값 없음"
        amount_note = f"추비 {amount} (kg/10a, {p['source']})" + (" — 유기 갈래는 목표 양분량(자재 환산 규칙 정본 없음)" if cert == "유기" else "")
        inputs = inputs + [_prescription_input(p)]
    else:
        amount_note = "판단 불가(지식) — 처방 정본 미도착(python -m ingest.fertilizer <주소>)"
    return Envelope("판단함", did, sid, as_of, inputs=inputs, grade=weakest(["관측", _grid_grade(unit)]),
                    revisit_at=(today + timedelta(days=1)).isoformat(),
                    result={"status": status, "work_date": work_date, "deadline": dl, "materials": m, "done_refs": [e.get("id") for e in done],
                            "amount": amount_note, "reason": (reason or {}).get("reason"), "reason_ref": (reason or {}).get("id"),
                            "summary": f"{status} — 작업일 {work_date} · 마감 {dl} · 자재({cert}) {', '.join(m) or '없음'} · {'양 ' + amount_note if p else '양은 정본 대기'}"
                                       + (f" · 사유: {reason['reason'][:120]}" if reason else "")},
                    notes=["양(kg/10a)은 지어내지 않는다 — 처방 정본이 없으면 비운다"])


def judge_ship_or_store(subject, today: date, targets: list[dict[str, Any]] | None = None, harvest: Envelope | None = None) -> Envelope:
    ctx, env = _base(subject, "ship_or_store", today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    use = str(subject.get("use") or "")
    if subject.get("mall_supply") is False or any(w in use for w in SELF_USE_WORDS):
        return Envelope("해당 없음", "ship_or_store", sid, as_of, result={"why": f"이번 작기 용도 '{use or '자가'}'(D-8) — 출하 결정 대상 아님", "summary": "자가 작기(D-8)"})
    tg = sorted((t for t in (targets or []) if t.get("target_date")), key=lambda t: t["target_date"])
    if not tg:
        return Envelope("판단 불가(데이터)", "ship_or_store", sid, as_of,
                        missing=[{"axis": "plan.target_date", "who_can_fill": "농가 — 납품 계획일(채팅: '10월 30일 납품 예정')"}],
                        result={"why": "납품 계획일이 없다", "summary": "납품 계획일 대기"})
    if harvest is None or harvest.kind != "판단함":
        return Envelope("판단 불가(데이터)", "ship_or_store", sid, as_of, missing=[{"axis": "anchor", "who_can_fill": "수확 시기 판정이 먼저"}],
                        result={"why": "수확 창이 없다"})
    target = date.fromisoformat(tg[0]["target_date"])
    h_end = date.fromisoformat(harvest.result["window_end"])
    store_days = (target - h_end).days
    t = _task(stage, "출하")
    deadline = _deadline_day(t)   # 마감을 읽는 법은 한 벌 — 네 결정이 같은 함수를 쓴다
    if deadline is None:
        # [B6 코드 쪽 2026-09-20] 전에는 63 을 기본값으로 메웠다(하드코딩 · 대리값 금지 위반) — 격자에 마감이 없으면 지식 미비다
        return Envelope("판단 불가(지식)", "ship_or_store", sid, as_of,
                        result={"why": "격자 칸 5 '출하 또는 단기 저장' 작업에 마감(retry.deadline_day)이 없다 — 값을 지어내지 않는다", "summary": "출하 마감 미채움"})
    a = date.fromisoformat(subject["anchor"])
    caps = []
    if target > a + timedelta(days=deadline):
        caps.append({"name": "단기 저장 한계", "basis": f"칸 5 '출하 또는 단기 저장' 마감 {deadline}일({(a + timedelta(days=deadline)).isoformat()})을 계획일이 넘는다"})
    notes = []
    h_to = int(stage["window"]["to_day"])
    if deadline < h_to:
        # 격자 자체 모순(코드 평가 B6): 출하 마감이 수확 창 끝보다 앞이면 창 끝에 수확한 것은 출하 마감을 이미 넘긴다. 지식 결함이라 여기서
        # 고치지 않고(검토지 ⓓ B6 발행자 답), 봉투에 그 사실을 남긴다 — 상한 제약이 그 모순에서 나온 것임을 읽는 쪽이 알게
        notes.append(f"격자 자체 모순(B6): 출하 마감 {deadline}일 < 수확 창 끝 {h_to}일 — 창 끝 수확분은 마감을 넘긴다. 검토지 ⓓ B6 답 대기")
    verdict = "출하(저장 없이)" if store_days <= 0 else f"단기 저장 {store_days}일 뒤 출하"
    return Envelope("판단함", "ship_or_store", sid, as_of, inputs=list(harvest.inputs), grade=weakest([str(harvest.grade), _grid_grade(unit)]), caps=caps,
                    result={"target_date": target.isoformat(), "harvest_window_end": h_end.isoformat(), "store_days": store_days, "ship_deadline_day": deadline,
                            "summary": f"{verdict} — 계획일 {target}"}, notes=notes)


def judge_all(subject: dict[str, Any], today: date, evts=None, forecast=None, pest=None, harvest: Envelope | None = None,
              prescriptions: list[dict[str, Any]] | None = None) -> list[Envelope]:
    evts = evts or []
    obs = [e for e in evts if e.get("kind") == "observation.note"]
    targets = [e for e in evts if e.get("kind") == "plan.target_date"]
    return [judge_sowing_window(subject, today), judge_base_fertilization(subject, today, prescriptions), judge_replant(subject, today, obs),
            judge_pest_alert(subject, today, forecast, pest), judge_top_dressing(subject, "top_dressing_1", today, evts, prescriptions),
            judge_top_dressing(subject, "top_dressing_2", today, evts, prescriptions), judge_drainage_alert(subject, today, forecast, pest),
            judge_ship_or_store(subject, today, targets, harvest)]
