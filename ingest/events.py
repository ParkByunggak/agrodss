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

# [사건 소비자 측정 2026-10-06] **어느 판정이 어느 사건을 읽는가** — 선언이 아니라 측정이다(밭 정보 값의 FIELD_CONSUMERS 와 같은 축).
# 왜 필요한가: 아직 일지에 **안 넣은** 사건 초안이 있으면 판정은 그것을 못 읽는다. 그 사실을 답이 말해야 하는데, 그 줄이 **관수(가뭄 답) 한 곳**에만 있었다 —
# 실측: 「10월 18일에 수확했다」 를 넣지 않은 채 「오늘 뭐 해야 하나」 를 물으면 「놓침 8 … 수확(뽑기) 다음 예정」 이 나가고 **그 초안을 말하지 않는다**(한 일이 놓침으로 읽힌다).
# 재는 법: 사건 하나를 **그 날의 하루 전**으로 넣고 봉투 전부를 대조한다. 날 셋(09-20 · 10-07 · 10-20)을 합친 것이 아래 표다.
#   측정이 두 번 틀렸다(둘 다 조건 축): ① 사건 날짜를 10-18 로 고정해 9월 측정에서는 **미래 사건**이 됐다 ② 10-20 은 수확 칸이라 가뭄 판정 자체가 없다(D-22 N/A).
#   그래서 관수→가뭄이 두 번 안 보였다. **조건을 바꿔 세 날을 합쳐야** 관수 2 · 시비 2 가 나온다.
#   그리고 처방 직후 전수를 재니(§7.5) 처음 쓴 표가 **일곱 줄**이었다 — 쟀던 일곱만 적은 것이다. 열여섯을 다 재니 **아홉 줄이 더** 나왔다(전부 계획 대 실제).
#   빠진 줄은 "소비자 0" 으로 읽히고, 소비자 0 이면 답이 그 초안을 말하지 않는다 — 안 쟀던 것이 안 말하기로 한 것처럼 보이는 자리다. 그래서 **전수와 같은지**를 아래에서 못 박는다.
#   측정 경계: 봉투(판정 결과·메모)만 대조한다. 화면·되먹임 쪽 소비(피해 → 경보 대조 U-16)는 이 측정이 못 본다 — 못 잰 것이고 소비자 0 이 아니다.
EVENT_CONSUMERS: dict[str, tuple[str, ...]] = {
    "관수": ("drought_alert", "plan_vs_actual"),
    "시비": ("top_dressing_1", "plan_vs_actual"),
    "파종": ("plan_vs_actual",), "정식": ("plan_vs_actual",), "방제": ("plan_vs_actual",), "제초": ("plan_vs_actual",),
    "예찰": ("plan_vs_actual",), "보식": ("plan_vs_actual",), "배수": ("plan_vs_actual",), "수확": ("plan_vs_actual",),
    "납품": ("plan_vs_actual",), "저장": ("plan_vs_actual",), "소독": ("plan_vs_actual",), "정리": ("plan_vs_actual",),
    "피해": ("plan_vs_actual",), "기타": ("plan_vs_actual",),
}
assert set(EVENT_CONSUMERS) == set(EVENT_TYPES), sorted(set(EVENT_TYPES) ^ set(EVENT_CONSUMERS))   # 종류를 늘리면 재서 여기 적는다 — 안 적으면 그 사건은 말 없이 사라진다


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
    return _append(observation_record(subject, text, observed_at, tags=tags, chat_ref=chat_ref, now=now))


SAID_ID = "물으신 말"     # 원장에 없는 관찰 — 방금 물으신 말 그 자체. 봉투가 인용하면 이 이름으로 보인다


def observation_record(subject: str, text: str, observed_at: str, tags: list[str] | None = None, chat_ref: str | None = None,
                       now: datetime | None = None, rec_id: str | None = None) -> dict[str, Any]:
    """관찰 레코드 **한 건을 만들기만** 한다(원장에 안 쓴다). 저장은 `add_observation`, 한 번 쓰고 버리는 것은 `said_observation`.

    [D-18 직렬 게이트 2026-09-27] 증상 물음의 답이 저장된 관찰만 읽었다 — 규칙(게이트 1)이 서도 물으신 말은 아직 초안이라
    관찰(게이트 2)이 닫혀 "관찰이 없다" 가 나갈 형태. 물으신 말을 같은 스키마의 레코드로 만들어 경계 게이트를 지나게 한다.
    """
    text = (text or "").strip()
    if not text:
        raise EventError("관찰 내용이 비어 있다")
    observed_at = _need_day(observed_at, "관찰")
    now = now or datetime.now(timezone.utc)
    rec: dict[str, Any] = {"id": rec_id or f"obs_{uuid.uuid4().hex[:12]}", "kind": "observation.note", "subject": subject, "text": text[:1000],
                           "observed_at": observed_at, "recorded_at": now.isoformat(timespec="seconds"),
                           "source": SOURCE, "resolution": "cultivation_unit", "tags": tags or []}
    if chat_ref:
        rec["chat_ref"] = chat_ref
    return rec


def said_observation(subject: str, text: str, today: str) -> dict[str, Any]:
    """방금 물으신 말을 **저장하지 않는** 관찰 레코드로 — 판정 한 번에만 쓰고 버린다(일지에는 '넣기' 를 누르셔야 들어간다)."""
    return observation_record(subject, text, today, rec_id=SAID_ID)


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
    planned_day = _need_day(planned_day, "계획일")[:10]   # [코드 평가 C13] 다른 add_* 넷과 같은 규율 — 날짜가 아닌 문자열이 observed_at 으로 들어갔다
    now = now or datetime.now(timezone.utc)
    return _append({
        "id": f"dec_{uuid.uuid4().hex[:12]}", "kind": "decision.noncompliance", "subject": subject,
        "planned_task": planned_task, "planned_day": planned_day, "reason": reason[:500],
        "observed_at": planned_day, "recorded_at": now.isoformat(timespec="seconds"),
        "source": SOURCE, "resolution": "cultivation_unit",
    })
