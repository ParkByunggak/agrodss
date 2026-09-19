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
EVENT_TYPES = ("파종", "정식", "방제", "시비", "관수", "제초", "예찰", "보식", "배수", "수확", "납품", "저장", "소독", "정리", "기타")
SOURCE = "farmer"


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


def add_event(subject: str, event_type: str, observed_at: str, note: str = "", advice_ref: str | None = None,
              materials: list[str] | None = None, quantity: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """사건 1건. observed_at(대상 시각) 필수 — 없으면 거부(지금 시각으로 메우지 않는다)."""
    if event_type not in EVENT_TYPES:
        raise EventError(f"사건 종류가 아니다: {event_type!r} ({', '.join(EVENT_TYPES)})")
    if not subject:
        raise EventError("재배 단위(subject) 필수")
    observed_at = (observed_at or "").strip()
    if not observed_at:
        raise EventError("대상 시각(observed_at)이 없다 — 사건은 언제 일어났는지 없이는 1층에 들어가지 않는다")
    try:
        date.fromisoformat(observed_at[:10])
    except ValueError:
        raise EventError(f"날짜 형식이 아니다: {observed_at!r} (예 2026-09-19)")
    now = now or datetime.now(timezone.utc)
    return _append({
        "id": f"evt_{uuid.uuid4().hex[:12]}", "kind": "event", "type": event_type, "subject": subject,
        "observed_at": observed_at, "recorded_at": now.isoformat(timespec="seconds"),
        "source": SOURCE, "resolution": "cultivation_unit",
        "advice_ref": advice_ref, "materials": materials or [], "quantity": quantity, "note": note.strip()[:500],
    })


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
