# -*- coding: utf-8 -*-
# FILE: judge/plan_vs_actual.py
# ROLE: [M-10 ③ · F 계획 대 실제 대조 · J 되먹임] 계획(격자)과 사건 원장을 대조한다 — "놓친 것을 아는 것도 판단".
#
#   이행      계획 작업일 ± tolerance 안에 같은 종류의 사건이 있다 (파종은 기준점 자체가 사건 · 촬영은 영상 원장)
#   예정      작업일이 아직 안 왔다
#   미이행    작업일이 지났고 사건이 없지만 재시도 마감 전 — 남은 날수를 낸다
#   놓침      마감도 지났다 — 불이행 사유를 묻는다(I-3 §5: 창이 지났을 때 묻는다). 사유가 있으면 '기록됨'
#
# 선제 발화(F): 예정 중 준비 착수일(임대 기준)이 오늘 안이면 표시한다.
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from ingest import events as ev
from ingest import media
from judge import plan, registry
from judge.envelope import AxisUse, Envelope, weakest
from judge.harvest_timing import GRID_GRADE, _load_unit

DECISION_ID = "plan_vs_actual"

registry.register(registry.Decision(
    id=DECISION_ID,
    name="계획 대 실제 대조",
    required_axes=("anchor",),
    optional_axes=(),
    forbidden_axes=(),
    rule=("격자 작업 칸을 기준점으로 날짜화한 계획과 사건 원장을 대조한다. 작업일 ±tolerance 안 같은 종류의 사건이면 이행, "
          "작업일 전이면 예정, 지났고 마감 전이면 미이행(남은 날수), 마감도 지났으면 놓침 — 이때 불이행 사유를 묻는다. "
          "파종은 기준점이 곧 사건, 촬영은 영상 원장이 증거. 사건 원장은 축이 아니라 기록이다."),
    revisit_days=1,
    params={
        "tolerance_days": 3,
        "task_event_types": {"파종": ("파종",), "정식": ("정식",), "소독": ("소독", "방제"), "관수": ("관수",), "보식": ("보식", "파종"),
                             "예찰": ("예찰", "방제"), "웃거름": ("시비",), "밑거름": ("시비", "파종"), "제초": ("제초",),
                             "배수": ("배수",), "수확": ("수확",), "출하": ("납품", "저장"), "저장": ("저장", "납품"),
                             "잔사": ("정리",), "정리": ("정리",)},
        "source": "작업명 키워드 ↔ 사건 종류 대응 — 추론(격자 작업명 문면), 발행자 검토 대기",
    },
))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _types_for(task_name: str, params: dict[str, Any]) -> tuple[str, ...]:
    for k, v in params["task_event_types"].items():
        if k in task_name:
            return v
    return ()


def _matched_event(p: dict[str, Any], evts: list[dict[str, Any]], tol: int, params: dict[str, Any]) -> dict[str, Any] | None:
    types = _types_for(p["task"], params)
    if not types:
        return None
    wd = date.fromisoformat(p["work_date"])
    lo, hi = wd - timedelta(days=tol), (date.fromisoformat(p["deadline_date"]) if p.get("deadline_date") else wd + timedelta(days=tol))
    for e in evts:
        if e.get("type") in types and lo <= date.fromisoformat(e["observed_at"][:10]) <= hi:
            return e
    return None


def judge(subject: dict[str, Any], today: date | None = None, evts: list[dict[str, Any]] | None = None,
          videos: list[dict[str, Any]] | None = None, reasons: list[dict[str, Any]] | None = None) -> Envelope:
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
                        missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일(사건 입력)"}], result={"why": "기준점이 없다"})
    anchor_d = date.fromisoformat(anchor)
    evts = evts if evts is not None else ev.list_records(sid, "event")
    videos = videos if videos is not None else media.list_records(sid)
    reasons = reasons if reasons is not None else ev.list_records(sid, "decision.noncompliance")
    # 기준점은 그 자체가 사건이다(농가 행위 기준점)
    evts = list(evts) + [{"type": "파종", "observed_at": anchor, "id": "anchor", "source": subject.get("source", "farmer")}]
    tol = int(d.params["tolerance_days"])
    rows = []
    counts = {"이행": 0, "예정": 0, "미이행": 0, "놓침": 0, "사유 기록됨": 0}
    ask = []
    prep = []
    for p in plan.from_unit(unit, anchor_d, subject.get("cert")):
        wd = date.fromisoformat(p["work_date"])
        dl = date.fromisoformat(p["deadline_date"]) if p.get("deadline_date") else wd + timedelta(days=tol)
        status, evidence = None, None
        if p["kind"] == "plan.capture":
            hit = [v for v in videos if p["work_date"] <= (v.get("observed_at") or "")[:10] <= p["deadline_date"]]
            if hit:
                status, evidence = "이행", f"영상 {hit[0].get('id')} ({hit[0].get('observed_at', '')[:10]})"
        else:
            m = _matched_event(p, evts, tol, d.params)
            if m:
                status, evidence = "이행", f"사건 {m.get('type')} {m.get('observed_at', '')[:10]}"
        if status is None:
            if today < wd:
                status = "예정"
                pr = p.get("prep_date_rental")
                if pr and date.fromisoformat(pr) <= today:
                    prep.append({"task": p["task"], "work_date": p["work_date"], "prep_date": pr})
            elif today <= dl:
                status, evidence = "미이행", f"마감까지 {(dl - today).days}일 (재시도 {'가능' if p['retry_possible'] else '불가'})"
            else:
                rec = next((r for r in reasons if r.get("planned_task") == p["task"] and r.get("planned_day") == p["work_date"]), None)
                if rec:
                    status, evidence = "사유 기록됨", rec["reason"]
                else:
                    status, evidence = "놓침", f"마감 {p['deadline_date'] or p['work_date']} 지남 — 불이행 사유를 묻는다"
                    ask.append({"task": p["task"], "work_date": p["work_date"], "stage": p["stage"]})
        counts[status] += 1
        rows.append({"stage": p["stage"], "task": p["task"], "work_date": p["work_date"], "deadline_date": p.get("deadline_date"),
                     "status": status, "evidence": evidence, "materials": p.get("materials"), "kind": p["kind"]})
    inputs = [AxisUse("anchor", anchor, subject.get("source", "farmer"), "cultivation_unit", "관측")]
    grades = ["관측", GRID_GRADE.get(unit["unit"].get("confidence", "하"), "추정")]
    return Envelope(
        "판단함", DECISION_ID, sid, as_of, inputs=inputs, grade=weakest(grades),
        revisit_at=(today + timedelta(days=d.revisit_days)).isoformat(),
        result={"days_since_anchor": (today - anchor_d).days, "counts": counts, "rows": rows,
                "ask_reason": ask, "prep_now": prep,
                "events_used": len(evts) - 1, "videos_used": len(videos), "reasons_used": len(reasons)},
        notes=[f"격자 출처: {unit['unit'].get('source', '?')}", f"작업↔사건 대응: {d.params['source']}",
               "사건 원장·영상 원장은 축이 아니라 기록 — inputs 에 축으로 싣지 않는다"],
    )
