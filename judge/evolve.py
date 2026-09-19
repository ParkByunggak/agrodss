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
DAMAGE_TYPE = "피해"
ALERT_LEVELS_COUNT = ("경보", "주의")          # 예고는 아직 창이 안 열린 것 — 대조에 안 센다
# [U-16] 피해 사건의 risk 와 격자 위험 이름을 잇는 갈래 — 양쪽을 갈래로 바꿔 비교하고, 갈래가 없으면 부분 일치
RISK_FAMILIES: dict[str, tuple[str, ...]] = {
    "서리": ("서리", "동해", "냉해", "얼었", "얼어", "결빙"),
    "부패": ("부패", "썩", "무름", "습해", "물러", "장마"),
    "해충": ("해충", "벌레", "파리", "유충", "구더기", "나방", "진딧물", "굼벵이", "응애", "총채"),
    "병": ("병", "반점", "곰팡이", "잎마름", "노균", "탄저"),
    "수확 지연": ("수확 지연", "지연", "추대", "웃자"),
}


def risk_family(text: str | None) -> str | None:
    t = (text or "").replace(" ", "")
    for fam, words in RISK_FAMILIES.items():
        if any(w.replace(" ", "") in t for w in words):
            return fam
    return None


def match_risk(event_risk: str | None, alert_risk: str | None) -> bool:
    a, b = risk_family(event_risk), risk_family(alert_risk)
    if a and b:
        return a == b
    x, y = (event_risk or "").replace(" ", ""), (alert_risk or "").replace(" ", "")
    return bool(x and y) and (x in y or y in x)


# ── 예측 원장에 실을 주장(대조 가능한 것만) ──────────────────────────────────────────
def payload_of(env: Envelope) -> dict[str, Any] | None:
    if env.kind != "판단함":
        return None
    r = env.result
    if env.decision_id == "harvest_timing":
        return {"window_start": r.get("window_start"), "window_end": r.get("window_end"), "error_days": r.get("error_days")}
    if env.decision_id == "risk_alert":
        alerts = sorted(({"level": a.get("level"), "risk": a.get("risk") or a.get("name"), "recoverable": bool(a.get("recoverable"))}
                         for a in r.get("alerts", [])), key=lambda a: (str(a["risk"]), str(a["level"])))
        return {"alerts": alerts, "horizon_days": int(r.get("horizon_days") or 0)}
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
            out += _measure_risk(subject, today, events)
            o = None
        else:
            o = None
        if o:
            out.append(o)
    return out


def _pred_window(pred: dict[str, Any]) -> tuple[date, date]:
    as_of = date.fromisoformat(pred["observed_at"][:10])
    return as_of, as_of + timedelta(days=int(pred["payload"].get("horizon_days") or 0))


def _measure_risk(subject: str, today: date, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """[U-16] 경보 ↔ 피해 사건.
    (a) 피해가 있으면: 그 날을 창(as_of ~ as_of+horizon)에 품는 예측 중 같은 갈래를 경보·주의한 것이 있나 → 적중 / 없으면 빗나감(놓친 경보)
    (b) 창이 지난 경보에 피해가 없으면: 회복 불가 위험은 과경보 허용(H 비대칭) → 대조 불가 · 회복 가능 위험은 빗나감(과경보)
    사건이 아예 없으면 값을 메우지 않는다 — (b)는 예측 창이 지난 뒤에만."""
    preds = [r for r in fb.list_records("feedback.prediction", subject) if r.get("decision_id") == "risk_alert"]
    if not preds:
        return []
    out: list[dict[str, Any]] = []
    damages = sorted((e for e in events if e.get("type") == DAMAGE_TYPE and e.get("observed_at")), key=lambda e: e["observed_at"])
    for dmg in damages:
        d = date.fromisoformat(dmg["observed_at"][:10])
        covering = [p for p in preds if _pred_window(p)[0] <= d <= _pred_window(p)[1]]
        hit = next((p for p in covering if any(a.get("level") in ALERT_LEVELS_COUNT and match_risk(dmg.get("risk"), a.get("risk"))
                                               for a in p["payload"].get("alerts", []))), None)
        if hit:
            o = fb.add_outcome(hit, "적중", f"피해 {dmg.get('risk')} {d} — 창 안에 같은 갈래 경보가 있었다", actual_ref=dmg.get("id"), observed_at=d.isoformat())
        else:
            base = (covering or [p for p in preds if _pred_window(p)[0] <= d] or preds)[-1]
            o = fb.add_outcome(base, "빗나감", f"피해 {dmg.get('risk')} {d} — 앞선 경보 없음(놓친 경보)", actual_ref=dmg.get("id"), observed_at=d.isoformat())
        if o:
            out.append(o)
    latest = preds[-1]
    start, end = _pred_window(latest)
    if today > end:
        for a in latest["payload"].get("alerts", []):
            if a.get("level") not in ALERT_LEVELS_COUNT:
                continue
            if any(start <= date.fromisoformat(e["observed_at"][:10]) <= end and match_risk(e.get("risk"), a.get("risk")) for e in damages):
                continue
            if a.get("recoverable"):
                o = fb.add_outcome(latest, "빗나감", f"{a.get('level')} {a.get('risk')} — 창({start}~{end}) 안 피해 없음(과경보 · 회복 가능 위험은 신호 있을 때만)",
                                   actual_ref=f"alert:{a.get('risk')}", observed_at=today.isoformat())
            else:
                o = fb.add_outcome(latest, "대조 불가", f"{a.get('level')} {a.get('risk')} — 창 안 피해 없음. 회복 불가 위험은 과경보 허용(H) — 빗나감으로 세지 않는다",
                                   actual_ref=f"alert:{a.get('risk')}", observed_at=today.isoformat())
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
            what = "격자 창(window) 재검토" if o["decision_id"] == "harvest_timing" else "신호 임계 · 경보 규칙(달력 창 · 회복 가능 여부) 재검토"
            it = fb.propose("feedback.outcome", o["id"] + ":grid", "grid", f"{o['decision_id']}: {o['detail']} — {what}. 사람이 채택한다",
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
