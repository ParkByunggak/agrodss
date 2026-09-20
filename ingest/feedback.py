# -*- coding: utf-8 -*-
# FILE: ingest/feedback.py
# ROLE: [M-6 · J 되먹임] 되먹임 원장 — 사용자 개선 요구 · 예측 원장 · 대조 결과 · 개선 항목.
#       원장 격리: AGRODSS_FEEDBACK_DIR (테스트는 tmp — conftest). 쓰기 직전 스키마 검증(schema.records.stamp).
#
#   규율(D-14 자율진화):
#     · 보이게까지 자동 — 제안은 시스템이 만든다. **확장 방향(임계·규칙·칸 변경)의 채택은 사람만**.
#     · 보수 방향(등급 하향·판단 불가 전환·범위 축소)은 자동 적용될 수 있다 — 되돌릴 수 있고 범위가 좁다.
#     · 반영 → 검증은 라이브 독립 3회 3/3(N-152 전례). 2/3 이면 잔여.
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
VERIFY_REQUIRED = 3
AUTO_DIRECTIONS: frozenset[str] = frozenset({"보수"})
RESOLUTION = "cultivation_unit"


class FeedbackError(ValueError):
    pass


def feedback_dir() -> Path:
    return Path(os.environ.get("AGRODSS_FEEDBACK_DIR") or (ROOT / "data" / "feedback"))


def index_path() -> Path:
    return feedback_dir() / "index.jsonl"


def _now(now: datetime | None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def _append(rec: dict[str, Any]) -> dict[str, Any]:
    rec = sch.stamp(rec)                      # [M-6] 원장에 쓰는 직전 한 번 — 스키마 밖 레코드는 여기서 죽는다
    index_path().parent.mkdir(parents=True, exist_ok=True)
    with index_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def list_records(kind: str | None = None, subject: str | None = None) -> list[dict[str, Any]]:
    p = index_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if kind and r.get("kind") != kind:
            continue
        if subject and r.get("subject") != subject:
            continue
        out.append(r)
    return out


def latest_by_id(kind: str) -> dict[str, dict[str, Any]]:
    """같은 id 의 마지막 줄이 현재 상태(append-only 원장 — 상태 변경도 한 줄)."""
    out: dict[str, dict[str, Any]] = {}
    for r in list_records(kind):
        out[r["id"]] = r
    return out


# ── 사용자 개선 요구 ─────────────────────────────────────────────────────────────────
def add_request(text: str, target: str = "other", target_ref: str | None = None, subject: str | None = None,
                source: str = "farmer", observed_at: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise FeedbackError("요구 내용이 비어 있다")
    if source not in sch.HUMAN_SOURCES:
        raise FeedbackError("개선 요구는 사람(farmer · publisher)이 낸다")
    ts = _now(now)
    rec: dict[str, Any] = {"id": f"req_{uuid.uuid4().hex[:12]}", "kind": "feedback.request", "text": text[:1000],
                           "target": target, "status": "접수", "observed_at": observed_at or ts[:10], "recorded_at": ts,
                           "source": source, "resolution": RESOLUTION}
    if subject:
        rec["subject"] = subject
    if target_ref:
        rec["target_ref"] = target_ref
    return _append(rec)


def set_request_status(req_id: str, status: str, response: str = "", item_ref: str | None = None,
                       now: datetime | None = None) -> dict[str, Any]:
    cur = latest_by_id("feedback.request").get(req_id)
    if not cur:
        raise FeedbackError(f"없는 요구: {req_id}")
    rec = dict(cur)
    rec["status"] = status
    rec["recorded_at"] = _now(now)
    if response:
        rec["response"] = response[:1000]
    if item_ref:
        rec["item_ref"] = item_ref
    rec.pop("schema_version", None)
    return _append(rec)


# ── 예측 원장 ─────────────────────────────────────────────────────────────────────────
def record_prediction(subject: str, decision_id: str, envelope_kind: str, payload: dict[str, Any], as_of: str,
                      grade: str | None = None, code_head: str | None = None, now: datetime | None = None) -> dict[str, Any] | None:
    """판단함의 대조 가능한 주장을 한 줄로. 같은 (subject, decision) 의 직전 줄과 payload 가 같으면 안 쓴다(바뀔 때만).
    [C17] 직전 줄을 읽어 견주고 쓰는 꼴이라 겹치면 같은 주장이 두 줄 — 한 덩이로."""
    with sch.ledger_lock:
        return _record_prediction_locked(subject, decision_id, envelope_kind, payload, as_of, grade, code_head, now)


def _record_prediction_locked(subject: str, decision_id: str, envelope_kind: str, payload: dict[str, Any], as_of: str,
                              grade: str | None, code_head: str | None, now: datetime | None) -> dict[str, Any] | None:
    h = sch.payload_hash(payload)
    prev = [r for r in list_records("feedback.prediction", subject) if r.get("decision_id") == decision_id]
    if prev and prev[-1].get("payload_hash") == h:
        # [코드 평가 A2] 주장은 그대로여도 "마지막으로 확인된 날"은 나아간다 — 같은 id 로 last_seen_at 만 갱신해 덧붙인다(원장 append-only ·
        # 같은 id 는 latest 우선). 이것이 없으면 대조 창이 첫 발행일+horizon 에서 끝나, 살아 있던 경보 뒤의 피해가 "앞선 경보 없음"이 된다.
        last = prev[-1]
        if as_of > (last.get("last_seen_at") or last.get("observed_at") or ""):
            upd = {k: v for k, v in last.items() if k != "schema_version"}
            upd["last_seen_at"], upd["recorded_at"] = as_of, _now(now)
            _append(upd)
        return None
    rec: dict[str, Any] = {"id": f"prd_{uuid.uuid4().hex[:12]}", "kind": "feedback.prediction", "subject": subject,
                           "decision_id": decision_id, "envelope_kind": envelope_kind, "payload": payload, "payload_hash": h,
                           "observed_at": as_of, "recorded_at": _now(now), "source": "computed:judge", "resolution": RESOLUTION}
    if grade:
        rec["grade"] = grade
    if code_head:
        rec["code_head"] = code_head
    return _append(rec)


def latest_predictions(subject: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in list_records("feedback.prediction", subject):
        out[r["decision_id"]] = r
    return out


# ── 대조 결과 ─────────────────────────────────────────────────────────────────────────
def add_outcome(prediction: dict[str, Any], verdict: str, detail: str, actual_ref: str | None = None,
                observed_at: str | None = None, now: datetime | None = None) -> dict[str, Any] | None:
    """한 예측에 같은 판정·같은 실제를 두 번 적지 않는다. [C17] 검사와 쓰기를 한 덩이로 — 겹치면 둘 다 '없다'를 본다."""
    with sch.ledger_lock:
        for o in list_records("feedback.outcome", prediction["subject"]):
            if o["prediction_id"] == prediction["id"] and o["verdict"] == verdict and o.get("actual_ref") == actual_ref:
                return None
        return _add_outcome_locked(prediction, verdict, detail, actual_ref, observed_at, now)


def _add_outcome_locked(prediction: dict[str, Any], verdict: str, detail: str, actual_ref: str | None,
                        observed_at: str | None, now: datetime | None) -> dict[str, Any] | None:
    ts = _now(now)
    rec: dict[str, Any] = {"id": f"out_{uuid.uuid4().hex[:12]}", "kind": "feedback.outcome", "subject": prediction["subject"],
                           "decision_id": prediction["decision_id"], "prediction_id": prediction["id"], "verdict": verdict,
                           "detail": detail[:500], "observed_at": observed_at or ts[:10], "recorded_at": ts,
                           "source": "computed:evolve", "resolution": RESOLUTION}
    if actual_ref:
        rec["actual_ref"] = actual_ref
    return _append(rec)


# ── 개선 항목(자기개선 업무의 단위) ────────────────────────────────────────────────────
def propose(origin_kind: str, origin_ref: str, target: str, proposal: str, direction: str, source: str = "computed:evolve",
            subject: str | None = None, target_ref: str | None = None, auto_apply: bool = False,
            applied_ref: str | None = None, now: datetime | None = None) -> dict[str, Any] | None:
    """개선 항목 1건. 같은 출처(origin)로 이미 살아 있는 항목이 있으면 안 만든다(중복 제안 금지).
    auto_apply 는 보수 방향에서만 — 확장은 '제안'으로 남고 사람이 채택한다(D-14). [C17] 검사와 쓰기를 한 덩이로."""
    with sch.ledger_lock:
        return _propose_locked(origin_kind, origin_ref, target, proposal, direction, source, subject, target_ref,
                               auto_apply, applied_ref, now)


def _propose_locked(origin_kind: str, origin_ref: str, target: str, proposal: str, direction: str, source: str,
                    subject: str | None, target_ref: str | None, auto_apply: bool,
                    applied_ref: str | None, now: datetime | None) -> dict[str, Any] | None:
    for it in latest_by_id("improvement.item").values():
        if it["origin"].get("kind") == origin_kind and it["origin"].get("ref") == origin_ref and it["status"] not in ("거부",):
            return None
    if auto_apply and direction not in AUTO_DIRECTIONS:
        raise FeedbackError("확장 방향은 자동 적용될 수 없다 — 사람이 채택한다(D-14)")
    ts = _now(now)
    status = "반영" if auto_apply else "제안"
    rec: dict[str, Any] = {"id": f"imp_{uuid.uuid4().hex[:12]}", "kind": "improvement.item",
                           "origin": {"kind": origin_kind, "ref": origin_ref}, "target": target, "proposal": proposal[:1000],
                           "direction": direction, "status": status, "auto_applied": bool(auto_apply),
                           "observed_at": ts[:10], "recorded_at": ts, "source": source, "resolution": RESOLUTION,
                           "history": [{"at": ts, "status": status, "by": source}]}
    if subject:
        rec["subject"] = subject
    if target_ref:
        rec["target_ref"] = target_ref
    if applied_ref:
        rec["applied_ref"] = applied_ref
    if auto_apply:
        rec["verify"] = {"required": VERIFY_REQUIRED, "ok": 0, "fail": 0}
    return _append(rec)


def set_item_status(item_id: str, status: str, by: str, note: str = "", applied_ref: str | None = None,
                    now: datetime | None = None) -> dict[str, Any]:
    """상태 전이. 확장 방향의 채택·반영은 사람(farmer · publisher)만 할 수 있다 — computed 가 하면 거부."""
    cur = latest_by_id("improvement.item").get(item_id)
    if not cur:
        raise FeedbackError(f"없는 개선 항목: {item_id}")
    if status not in sch.ITEM_STATUS:
        raise FeedbackError(f"상태가 어휘 밖: {status!r}")
    if status in ("채택", "반영") and cur["direction"] == "확장" and by not in sch.HUMAN_SOURCES:
        raise FeedbackError("확장 방향의 채택·반영은 사람만 — 자율진화는 제안까지(D-14)")
    if status == "검증":
        v = cur.get("verify") or {"required": VERIFY_REQUIRED, "ok": 0, "fail": 0}
        if v.get("ok", 0) < v.get("required", VERIFY_REQUIRED) or v.get("fail", 0):
            raise FeedbackError(f"검증은 라이브 독립 {VERIFY_REQUIRED}회 {VERIFY_REQUIRED}/{VERIFY_REQUIRED} 이어야 한다 — 지금 {v.get('ok', 0)} ok · {v.get('fail', 0)} fail")
    ts = _now(now)
    rec = dict(cur)
    rec["status"] = status
    rec["recorded_at"] = ts
    rec["history"] = list(cur.get("history", [])) + [{"at": ts, "status": status, "by": by, "note": note[:300]}]
    if note:
        rec["note"] = note[:500]
    if applied_ref:
        rec["applied_ref"] = applied_ref
    if status == "반영" and "verify" not in rec:
        rec["verify"] = {"required": VERIFY_REQUIRED, "ok": 0, "fail": 0}
    rec.pop("schema_version", None)
    return _append(rec)


def record_verification(item_id: str, ok: bool, session_ref: str, now: datetime | None = None) -> dict[str, Any]:
    """반영된 항목의 라이브 확인 1회. 같은 session_ref 는 두 번 세지 않는다(캐시 재판정 = 1회, 독립 세션 규율)."""
    cur = latest_by_id("improvement.item").get(item_id)
    if not cur:
        raise FeedbackError(f"없는 개선 항목: {item_id}")
    if cur["status"] not in ("반영", "검증"):
        raise FeedbackError("검증 기록은 반영된 항목에만")
    seen = {h.get("session_ref") for h in cur.get("history", [])}
    if session_ref in seen:
        raise FeedbackError("같은 세션의 재판정은 1회로 센다 — 독립 세션이어야 한다")
    v = dict(cur.get("verify") or {"required": VERIFY_REQUIRED, "ok": 0, "fail": 0})
    v["ok" if ok else "fail"] = v.get("ok" if ok else "fail", 0) + 1
    ts = _now(now)
    rec = dict(cur)
    rec["verify"] = v
    rec["recorded_at"] = ts
    rec["history"] = list(cur.get("history", [])) + [{"at": ts, "status": cur["status"], "by": "publisher",
                                                      "session_ref": session_ref, "ok": ok}]
    rec.pop("schema_version", None)
    return _append(rec)


def active_caps(subject: str) -> list[dict[str, Any]]:
    """자동 적용된 보수 항목 중 살아 있는 것(반영·검증) — 3층 산출에 상한으로 걸린다(judge.evolve.apply_caps)."""
    return [it for it in latest_by_id("improvement.item").values()
            if it.get("subject") == subject and it["auto_applied"] and it["status"] in ("반영", "검증")]
