# -*- coding: utf-8 -*-
# FILE: ingest/questions.py
# ROLE: [WO-ASK-01 §3 · §14 의 4 · 2026-10-03] **질문 생성** — 지금 판정이 못 서는 자리 가운데 하나를 골라 농가에게 한 줄로 묻는다.
#   질문은 지어내지 않는다: 재료는 판정이 이미 말한 두 가지뿐이다.
#     ① 위험 경보가 「없어서 근거에 못 실은 값」 (alert.needs_field — 회복 불가 위험 · 지금은 배수 하나)       ← 1순위(§3 "회복 불가 먼저")
#     ② 판단 불가(데이터)의 요구 항목(missing — 정본 judge.need 가 만든 문장)                                ← 농가 몫 먼저, 발행자 몫 뒤
#   문장은 judge.need.need() 로만(§2 · §5-1 관문을 같은 자리에서 지난다 — 읽는 판정이 없는 필지 값은 여기서도 못 묻는다).
#   한 번에 하나(§3)이고, 같은 축을 몇 번까지 묻는가(§8 반복 상한)는 **값**이라 여기 없다 — REPEAT_CAP 이 None 이면 상한 없이 세기만 하고,
#   발행자가 값을 주면 그 수를 넘은 축은 건너뛰며 묻기 원장에 '멈춤' 을 적는다(조용히 사라지지 않는다).
#   질문을 못 만든 것은 답을 막지 않되 보이게(dropped 「질문 생성」 — 검토 §3-ⓑ).
from __future__ import annotations

from datetime import date
from typing import Any

from ingest import asks, dropped, parcels
from judge.need import NeedError, need

DROP_WHERE = "질문 생성"
# [§8 반복 상한 — 값은 발행자 몫] None = 상한 없음(세기만 한다). 지시서 §8 의 수치가 오면 여기 하나만 바뀐다(출처를 옆에 적는다).
# [발행자 2026-10-03] *"제안드리면 — 반복 상한 3 … 전부 추론 표시로요. 그리고 상한에 닿은 항목이 '모르겠다'로 떨어지는 것과 같은 자리에 가도록요."*
# 유효기간(§8)도 같은 답: 필지 속성은 무기한(고칠 때까지 — 등록부 값이 그대로 있으니 이미 그렇다) · 검정값은 격자가 정하는 대로(격자에 그 키가 아직 없다 — 생기면 읽는다).
REPEAT_CAP: int | None = 3
REPEAT_CAP_SOURCE = "발행자 2026-10-03 — 추론(지시서 §8 의 '세 번' 도 근거 없는 추론이라고 발행자가 밝힘) · 표시 그대로 · 정본이 오면 바꾼다"
UNRECOVERABLE_FIRST = True        # §3 — 회복 불가 위험의 빈 값이 먼저


def _parcel_question(field: str, alert: dict[str, Any]) -> dict[str, Any]:
    """필지 값 하나를 묻는 문장 — 고를 말은 등록부 어휘(parcels.FIELD_CHOICES) 그대로(지어내지 않는다) · 자리는 밭 정보 화면."""
    word = parcels.FIELD_WORDS.get(field, field)
    opts = parcels.FIELD_CHOICES.get(field)
    what = f"{word}({' · '.join(opts)} 중 하나)" if opts else word
    why = f"{alert.get('risk', '위험')}(회복 불가 · {alert.get('stage', '지금 칸')})의 근거에 실린다"
    q = need("soil_water" if field == "drainage" else field, "농가", what, "parcel", why)
    q["decision"] = "risk_alert"
    q["field"] = field
    q["priority"] = 0 if alert.get("recoverable") is False else 1
    return q


def candidates(envs: list[Any]) -> list[dict[str, Any]]:
    """물을 수 있는 것 전부 — 우선순위 순(회복 불가 위험의 빈 값 → 농가 몫 요구 → 발행자 몫 요구). 같은 축은 한 번."""
    out: list[dict[str, Any]] = []
    for e in envs:
        if e.decision_id == "risk_alert" and e.kind == "판단함":
            for a in (e.result or {}).get("alerts") or []:
                f = a.get("needs_field")
                if not f:
                    continue
                try:
                    out.append(_parcel_question(str(f), a))
                except NeedError as err:                           # 읽는 판정이 없는 값 등 — 묻지 않고 그 사실을 남긴다(§5-1 은 여기서도 선다)
                    dropped.note(DROP_WHERE, f"risk_alert/{f}", str(err))
    for e in envs:
        if e.kind != "판단 불가(데이터)":
            continue
        for m in e.missing or []:
            if not m.get("axis"):
                continue
            q = dict(m)
            q["decision"] = e.decision_id
            q["priority"] = 2 if str(m.get("who_can_fill", "")).startswith("농가") else 3
            out.append(q)
    seen: set[str] = set()
    ordered = []
    for q in sorted(out, key=lambda q: q["priority"]):
        if q["axis"] in seen:
            continue
        seen.add(q["axis"])
        ordered.append(q)
    return ordered


def top(subject_id: str, envs: list[Any]) -> dict[str, Any] | None:
    """지금 물을 하나. 묻기 원장의 횟수가 REPEAT_CAP 을 넘은 축은 건너뛰고 원장에 멈춤을 적는다(값이 없으면 건너뛰지 않는다)."""
    cands = candidates(envs)
    if not cands:
        return None
    if REPEAT_CAP is None:
        return cands[0]
    counts = {r["axis"]: int(r.get("count", 0)) for r in asks.for_subject(subject_id)}
    for q in cands:
        if counts.get(q["axis"], 0) >= REPEAT_CAP:
            asks.mark_stopped(subject_id, q["axis"], f"반복 상한 {REPEAT_CAP}회 — 출처: {REPEAT_CAP_SOURCE}")
            continue
        return q
    return None


def line(q: dict[str, Any]) -> str:
    """답 끝에 붙는 한 줄 — 요구 문장 그대로(누가 · 무엇 · 어디서 · 왜 지금)."""
    return f"하나 물을 것 — {q['who_can_fill']}"
