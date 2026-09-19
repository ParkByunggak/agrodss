# -*- coding: utf-8 -*-
# FILE: ingest/events.py
# ROLE: [I-3 §2 사건 · §5 결정] 사건 원장 — 파종·정식·방제·시비·관수·제초·예찰·보식·배수·수확·납품·촬영 + 불이행 사유.
#       1층 기록. 모든 레코드에 source·recorded_at·observed_at·resolution·subject(공통 필드 5).
#       원장 격리: AGRODSS_EVENTS_DIR (테스트는 tmp — conftest).
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
EVENT_TYPES = ("파종", "정식", "방제", "시비", "관수", "제초", "예찰", "보식", "배수", "수확", "납품", "저장", "소독", "정리", "피해", "기타")
SOURCE = "farmer"
# [U-16] 피해 사건 — 경보(risk_alert)의 예측을 대조할 실제. risk 는 격자 위험 이름과 대조되는 말(서리 · 부패 · 해충 · 병 …)
SEVERITIES = ("경미", "보통", "심함")
DAMAGE_TYPE = "피해"


def events_dir() -> Path:
    return Path(os.environ.get("AGRODSS_EVENTS_DIR") or (ROOT / "data" / "events"))


def index_path() -> Path:
    return events_dir() / "index.jsonl"


class EventError(ValueError):
    pass


def _append(rec: dict[str, Any]) -> dict[str, Any]:
    rec = sch.stamp(rec)                      # [M-6] 원장에 쓰는 직전 한 번 — 스키마 밖 레코드는 여기서 죽는다
    index_path().parent.mkdir(parents=True, exist_ok=True)
    with index_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def list_records(subject: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    p = index_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if subject and r.get("subject") != subject:
            continue
        if kind and r.get("kind") != kind:
            continue
        out.append(r)
    return out


def _need_day(observed_at: str | None, what: str = "사건") -> str:
    observed_at = (observed_at or "").strip()
    if not observed_at:
        raise EventError(f"대상 시각(observed_at)이 없다 — {what}은 언제인지 없이는 1층에 들어가지 않는다")
    try:
        date.fromisoformat(observed_at[:10])
    except ValueError:
        raise EventError(f"날짜 형식이 아니다: {observed_at!r} (예 2026-09-19)")
    return observed_at


def add_event(subject: str, event_type: str, observed_at: str, note: str = "", advice_ref: str | None = None,
              materials: list[str] | None = None, quantity: str | None = None, now: datetime | None = None,
              chat_ref: str | None = None, risk: str | None = None, severity: str | None = None) -> dict[str, Any]:
    """사건 1건. observed_at(대상 시각) 필수 — 없으면 거부(지금 시각으로 메우지 않는다).
    피해(U-16)는 무엇의 피해인지(risk) 없이는 들어가지 않는다 — 경보와 대조할 수 없는 피해는 되먹임이 아니다."""
    if event_type not in EVENT_TYPES:
        raise EventError(f"사건 종류가 아니다: {event_type!r} ({', '.join(EVENT_TYPES)})")
    if not subject:
        raise EventError("재배 단위(subject) 필수")
    observed_at = _need_day(observed_at)
    risk = (risk or "").strip() or None
    if event_type == DAMAGE_TYPE and not risk:
        raise EventError("피해 사건은 무엇의 피해인지(risk — 서리 · 부패 · 해충 · 병 …)가 있어야 한다")
    if severity is not None and severity not in SEVERITIES:
        raise EventError(f"피해 정도는 {' · '.join(SEVERITIES)} 중 하나")
    now = now or datetime.now(timezone.utc)
    rec = {
        "id": f"evt_{uuid.uuid4().hex[:12]}", "kind": "event", "type": event_type, "subject": subject,
        "observed_at": observed_at, "recorded_at": now.isoformat(timespec="seconds"),
        "source": SOURCE, "resolution": "cultivation_unit",
        "advice_ref": advice_ref, "materials": materials or [], "quantity": quantity, "note": note.strip()[:500],
    }
    if chat_ref:
        rec["chat_ref"] = chat_ref
    if risk:
        rec["risk"] = risk[:100]
    if severity:
        rec["severity"] = severity
    return _append(rec)


def add_observation(subject: str, text: str, observed_at: str, tags: list[str] | None = None,
                    chat_ref: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """[I-3 §3] 직접 관찰값 — 농가가 본 것. 최종 심급. 판단은 여기 없다."""
    text = (text or "").strip()
    if not text:
        raise EventError("관찰 내용이 비어 있다")
    observed_at = _need_day(observed_at, "관찰")
    now = now or datetime.now(timezone.utc)
    rec: dict[str, Any] = {"id": f"obs_{uuid.uuid4().hex[:12]}", "kind": "observation.note", "subject": subject, "text": text[:1000],
                           "observed_at": observed_at, "recorded_at": now.isoformat(timespec="seconds"),
                           "source": SOURCE, "resolution": "cultivation_unit", "tags": tags or []}
    if chat_ref:
        rec["chat_ref"] = chat_ref
    return _append(rec)


def add_farmer_plan(subject: str, task: str, planned_day: str, note: str = "", chat_ref: str | None = None,
                    now: datetime | None = None) -> dict[str, Any]:
    """[I-3 §4] 농가 자신의 계획 — 영농일지의 '할 일'. 날짜 없는 계획은 계획이 아니다."""
    task = (task or "").strip()
    if not task:
        raise EventError("계획 작업이 비어 있다")
    planned_day = _need_day(planned_day, "계획")
    now = now or datetime.now(timezone.utc)
    rec: dict[str, Any] = {"id": f"pln_{uuid.uuid4().hex[:12]}", "kind": "plan.farmer", "subject": subject, "task": task[:200],
                           "planned_day": planned_day[:10], "observed_at": planned_day[:10],
                           "recorded_at": now.isoformat(timespec="seconds"), "source": SOURCE, "resolution": "cultivation_unit",
                           "note": note.strip()[:500]}
    if chat_ref:
        rec["chat_ref"] = chat_ref
    return _append(rec)


def add_target_date(subject: str, target_date: str, note: str = "", chat_ref: str | None = None,
                    now: datetime | None = None) -> dict[str, Any]:
    """[I-3 §4 · I-5] 납품 계획일 — 농가가 정한 것만(source=farmer 고정. 몰 수요는 여기로 못 들어온다)."""
    target_date = _need_day(target_date, "납품 계획일")
    now = now or datetime.now(timezone.utc)
    rec: dict[str, Any] = {"id": f"tgt_{uuid.uuid4().hex[:12]}", "kind": "plan.target_date", "subject": subject,
                           "target_date": target_date[:10], "observed_at": target_date[:10],
                           "recorded_at": now.isoformat(timespec="seconds"), "source": SOURCE, "resolution": "cultivation_unit",
                           "note": note.strip()[:500]}
    if chat_ref:
        rec["chat_ref"] = chat_ref
    return _append(rec)


def add_noncompliance(subject: str, planned_task: str, reason: str, planned_day: str, now: datetime | None = None) -> dict[str, Any]:
    """[I-3 §5 결정] 불이행 사유 — 조언(계획)을 안 따른 이유. '안 따른 이유가 조언보다 값지다'(J)."""
    reason = (reason or "").strip()
    if not reason:
        raise EventError("사유가 비어 있다")
    now = now or datetime.now(timezone.utc)
    return _append({
        "id": f"dec_{uuid.uuid4().hex[:12]}", "kind": "decision.noncompliance", "subject": subject,
        "planned_task": planned_task, "planned_day": planned_day, "reason": reason[:500],
        "observed_at": planned_day, "recorded_at": now.isoformat(timespec="seconds"),
        "source": SOURCE, "resolution": "cultivation_unit",
    })
