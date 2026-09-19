# -*- coding: utf-8 -*-
# FILE: judge/evolve.py
# ROLE: [M-6 · J 되먹임 · D-14] 자기개선 · 자율진화 루프 — 측정 → 제안 → (사람) 채택 → 적용 → 검증.
#
#   측정   예측 원장 ↔ 사건 원장을 대조해 적중 / 빗나감 / 대조 불가를 적는다. 사건이 없으면 값을 메우지 않는다.
#   제안   빗나감 · 놓침+사유 · 사용자 개선 요구에서 개선 항목을 만든다. 같은 출처로 두 번 만들지 않는다.
#   자율   **보수 방향만 자동 적용**(등급 상한 하향) — 되돌릴 수 있고 범위가 좁다. 확장(임계·규칙·칸 변경)은 제안까지.
#   적용   apply_caps — 3층 봉투가 나온 뒤, 돌려주기 전, 한 번(경계 게이트와 같은 자리 규율).
#   검증   라이브 독립 3회 3/3 — ingest.feedback.record_verification.
#
#   3층 판정기는 이 파일을 모른다. 이 파일은 판정기의 규칙을 바꾸지 않는다 — 산출의 등급만 낮춘다.
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ingest import events as ev
from ingest import feedback as fb
from judge.envelope import Envelope, weakest

CAP_GRADE = "추정"
HARVEST_TOLERANCE_DAYS_KEY = "error_days"


# ── 예측 원장에 실을 주장(대조 가능한 것만) ──────────────────────────────────────────
def payload_of(env: Envelope) -> dict[str, Any] | None:
    if env.kind != "판단함":
        return None
    r = env.result
    if env.decision_id == "harvest_timing":
        return {"window_start": r.get("window_start"), "window_end": r.get("window_end"), "error_days": r.get("error_days")}
    if env.decision_id == "risk_alert":
        return {"alerts": sorted(f"{a.get('level')}:{a.get('risk') or a.get('name')}" for a in r.get("alerts", []))}
    if env.decision_id == "plan_vs_actual":
        return {"missed": sorted(row["task"] for row in r.get("rows", []) if row.get("status") == "놓침")}
    return None            # 사실 인용은 주장이 아니다 — 대조할 것이 없다


def record_predictions(subject: str, envs: list[Envelope], code_head: str | None = None) -> int:
    n = 0
    for e in envs:
        p = payload_of(e)
        if p is None:
            continue
        if fb.record_prediction(subject, e.decision_id, e.kind, p, e.as_of, grade=e.grade, code_head=code_head):
            n += 1
    return n


# ── 측정 ─────────────────────────────────────────────────────────────────────────────
def measure(subject: str, today: date, events: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """최신 예측마다 대조. 돌려주는 것은 새로 적힌 outcome 들."""
    events = events if events is not None else ev.list_records(subject, "event")
    out: list[dict[str, Any]] = []
    for did, pred in fb.latest_predictions(subject).items():
        p = pred["payload"]
        if did == "harvest_timing":
            harvests = sorted((e for e in events if e.get("type") == "수확" and e.get("observed_at")), key=lambda e: e["observed_at"])
            if harvests:
                h = harvests[0]
                d = date.fromisoformat(h["observed_at"][:10])
                tol = int(p.get(HARVEST_TOLERANCE_DAYS_KEY) or 0)
                ws, we = date.fromisoformat(p["window_start"]), date.fromisoformat(p["window_end"])
                hit = ws - timedelta(days=tol) <= d <= we + timedelta(days=tol)
                o = fb.add_outcome(pred, "적중" if hit else "빗나감",
                                   f"첫 수확 {d} vs 창 {ws}~{we} (±{tol}일)", actual_ref=h.get("id"), observed_at=d.isoformat())
            elif today > date.fromisoformat(p["window_end"]) + timedelta(days=int(p.get(HARVEST_TOLERANCE_DAYS_KEY) or 0)):
                o = fb.add_outcome(pred, "대조 불가", "창이 지났는데 수확 사건이 없다 — 수확했으면 기록을, 안 했으면 사유를", observed_at=today.isoformat())
            else:
                o = None
        elif did == "risk_alert":
            o = fb.add_outcome(pred, "대조 불가", "피해·발생 사건의 입력형이 아직 없다(U-16) — 경보는 대조 못 한다", observed_at=today.isoformat()) if p.get("alerts") else None
        else:
            o = None
        if o:
            out.append(o)
    return out


# ── 제안 ─────────────────────────────────────────────────────────────────────────────
def propose(subject: str, today: date, reasons: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """빗나감 → 보수 자동(등급 상한) + 확장 제안(창 재검토). 대조 불가(수확 사건 없음) → 입력 제안.
    불이행 사유 → 격자 작업 칸 재검토 제안. 사용자 개선 요구(접수) → 개선 항목 제안 + 요구는 검토로."""
    made: list[dict[str, Any]] = []
    reasons = reasons if reasons is not None else ev.list_records(subject, "decision.noncompliance")
    for o in fb.list_records("feedback.outcome", subject):
        if o["verdict"] == "빗나감":
            it = fb.propose("feedback.outcome", o["id"], "decision", f"{o['decision_id']}: 빗나감 — 등급 상한을 '{CAP_GRADE}'으로(보수, 자동)",
                            "보수", subject=subject, target_ref=o["decision_id"], auto_apply=True, applied_ref="grade_cap")
            if it:
                made.append(it)
            it = fb.propose("feedback.outcome", o["id"] + ":grid", "grid", f"{o['decision_id']}: {o['detail']} — 격자 창(window) 재검토. 사람이 채택한다",
                            "확장", subject=subject, target_ref=o["decision_id"])
            if it:
                made.append(it)
        elif o["verdict"] == "대조 불가" and o["decision_id"] == "harvest_timing":
            it = fb.propose("feedback.outcome", o["id"], "input", "수확 사건이 없어 대조 못 함 — 채팅/사건 화면에서 수확일을 묻는다", "보수",
                            subject=subject, target_ref="event:수확")
            if it:
                made.append(it)
    for r in reasons:
        it = fb.propose("decision.noncompliance", r["id"], "grid",
                        f"'{r.get('planned_task')}' 불이행 사유: {r.get('reason')} — 격자 작업 칸(lead_days · retry) 재검토. 사람이 채택한다",
                        "확장", subject=subject, target_ref=r.get("planned_task"))
        if it:
            made.append(it)
    for req in fb.latest_by_id("feedback.request").values():
        if req["status"] != "접수" or (req.get("subject") and req.get("subject") != subject):
            continue
        it = fb.propose("feedback.request", req["id"], req["target"], f"사용자 요구: {req['text']}", "확장",
                        source=req["source"], subject=req.get("subject"), target_ref=req.get("target_ref"))
        if it:
            made.append(it)
            fb.set_request_status(req["id"], "검토", item_ref=it["id"])
    return made


# ── 적용(보수만) ──────────────────────────────────────────────────────────────────────
def apply_caps(subject: str, envs: list[Envelope], caps: list[dict[str, Any]] | None = None) -> list[Envelope]:
    """자동 적용된 보수 항목(등급 상한)을 봉투에 건다 — 판정기 뒤, 돌려주기 전, 한 번. 규칙은 안 바꾼다."""
    caps = caps if caps is not None else fb.active_caps(subject)
    by_dec = {c.get("target_ref") for c in caps if c.get("applied_ref") == "grade_cap"}
    for e in envs:
        if e.kind == "판단함" and e.decision_id in by_dec and e.grade:
            new = weakest([e.grade, CAP_GRADE])
            if new != e.grade:
                e.notes.append(f"[자율진화 보수] 등급 {e.grade}→{new}: 이 결정의 예측이 빗나간 적이 있다(개선 항목 반영 중)")
                e.grade = new
    return envs


# ── 한 바퀴 ──────────────────────────────────────────────────────────────────────────
def cycle(today: date | None = None, code_head: str | None = None) -> dict[str, Any]:
    """측정 → 제안. 채택은 사람 몫이라 여기 없다. 여러 번 돌려도 같은 것을 두 번 적지 않는다."""
    from judge import run as judge_run     # 순환 import 회피 — run 은 apply_caps 를 쓴다
    today = today or date.today()
    summary = {"predictions": 0, "outcomes": [], "proposals": []}
    for s, envs, _ in judge_run.all_judgments(today=today):
        summary["predictions"] += record_predictions(s["id"], envs, code_head)
        summary["outcomes"] += measure(s["id"], today)
        summary["proposals"] += propose(s["id"], today)
    return summary
