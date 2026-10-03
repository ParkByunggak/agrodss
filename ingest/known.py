# -*- coding: utf-8 -*-
# FILE: ingest/known.py
# ROLE: [발행자 진단 2026-10-04] **묻기 전에 원장을 먼저 읽는 규칙** — "이 값을 시스템이 이미 아는가" 를 확인하는 정본 하나. 질문 앞에 선다.
#
#   발행자: *"내부 정합성은 높다 — 관문이 파일끼리 맞는지를 본다. 그런데 밭과 맞는지는 아무도 안 본다. 10/3 관수를 적었는데 '마지막 관수 9/25' · 종구용이라고
#   말했는데 관찰로 적혔다 · 배수 좋음이 일지에 들어갔는데 과습 경보는 그대로이고 배수를 또 묻는다. 세 경우 다 정보가 시스템 안에 있는데 답에 안 쓰였고, 그러고
#   나서 시스템은 그 정보를 또 묻는다. 세 층(원장 · 속성 · 판정)이 따로 서서 어느 하나가 빠지면 '있는데 모른다' 가 된다. 처방은 하나 — 묻기 전에 원장을 먼저
#   읽는 규칙, 묻는 자리마다가 아니라 한 곳에서."*
#
#       지금    판정에 빈 축이 있다 → 묻는다
#       있어야  판정에 빈 축이 있다 → 원장·속성·사건·관찰에 그 값이 있는가 → 있으면 그것을 쓴다(초안으로 올리든 직접 읽든) → 없으면 묻는다
#
#   여기가 그 한 곳이다. 밭 정보 값(필지 속성)에 대해 세 층을 순서대로 본다 — ① 속성(등록부) ② 관찰 원장(일지의 본 것 — 최근 먼저) ③ 없음.
#   관찰에서 값을 **읽을 수 있으면** 초안(parcel.field · 「일지에서 읽음」)으로 올린다 — 등록부에 바로 쓰지 않는다(확인은 사람 · 원장 3칙). 값은 못 읽고 언급만
#   있으면 묻되 그 일지 줄을 들고 묻는다(같은 것을 처음 묻는 것처럼 되묻지 않는다). 사건(관수)은 판정이 이미 원장에서 읽는다 — 그 길은 검사가 거꾸로 센다.
#   어휘는 등록부(parcels)의 것이고 여기서는 **읽기만** 한다(쓰는 자리 0 · 지어내지 않는다 — 둘 이상 걸리면 값으로 읽지 않는다).
from __future__ import annotations

from typing import Any

from ingest import events as ev
from ingest import parcels, subjects

DROP_WHERE = "원장 읽기"
SUBJECT_AXES = ("cert",)          # 요구 문장의 축 이름이 곧 농사(재배 단위) 값인 것 — 질문 생성이 여기 든 축은 known_subject_field 를 먼저 본다
# 필지 값마다 일지에서 **언급**으로 보는 말(있으면 "일지에 그 말이 있다") 과 **값**으로 읽는 말(한 값만 걸릴 때만 값이다)
FIELD_MENTIONS: dict[str, tuple[str, ...]] = {
    "drainage": ("배수", "물 빠짐", "물빠짐", "고랑에 물", "물이 고", "물이 빠", "물이 안 빠", "물이 잘 빠", "고랑 물"),
    "use": tuple(w for ws in parcels.USE_WORDS.values() for w in ws),
}
FIELD_VALUE_WORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "drainage": {"좋음": ("잘 빠", "잘 되", "잘된", "잘돼", "안 고이", "안 고인", "고이지 않"),
                 "보통": ("보통",),
                 "나쁨": ("안 빠", "잘 안 빠", "물이 고", "고인다", "고여", "고임", "질퍽", "안 된다", "나쁘", "나빠")},
}


def value_in(field: str, text: str) -> str | None:
    """이 한 줄에서 그 필지 값을 **읽을 수 있는가** — 등록부 어휘 하나로만 떨어질 때 그 값, 아니면 None(둘 이상 · 없음)."""
    t = text or ""
    if field == "use":
        return parcels.use_declared(t)
    table = FIELD_VALUE_WORDS.get(field) or {}
    hits = [v for v, ws in table.items() if any(w in t for w in ws)]
    if field in parcels.FIELD_CHOICES:                       # 등록부 어휘 그 자체가 글에 있으면 그것도 값이다(「배수는 나쁨」)
        hits += [o for o in parcels.FIELD_CHOICES[field] if o in t and o not in hits]
    return hits[0] if len(hits) == 1 else None


def mentions(field: str, text: str) -> bool:
    t = text or ""
    if field == "use":
        return parcels.use_declared(t) is not None
    return any(w in t for w in FIELD_MENTIONS.get(field, ()))


def known_field(subject: dict[str, Any], field: str) -> dict[str, Any] | None:
    """세 층을 순서대로 — ① 속성 ② 관찰 원장(최근 먼저 · 그 값을 **언급**한 첫 줄) ③ None. 관찰 항목은 값이 없을 수 있다(언급만)."""
    pid = subject.get("parcel") or ""
    p = parcels.by_id(pid) if pid else None
    attr = (p or {}).get(field)
    if attr not in (None, ""):
        return {"from": "attribute", "field": field, "value": attr}
    obs = sorted(ev.list_records(subject.get("id"), "observation.note"), key=lambda o: (str(o.get("observed_at") or ""), str(o.get("recorded_at") or "")), reverse=True)
    for o in obs:
        text = str(o.get("text") or "")
        if mentions(field, text):
            return {"from": "observation", "field": field, "value": value_in(field, text), "id": o.get("id"),
                    "observed_at": str(o.get("observed_at") or "")[:10], "text": text}
    return None


def known_use_differs(subject: dict[str, Any]) -> dict[str, Any] | None:
    """용도는 속성이 비어 있지 않아도 일지의 선언이 다른 용도를 말하면 그것이 더 새 사실이다(발행자 10-04 「종구생산을 위한 목적이다」 — 속성은 「시험 재배(자가)」 였다)."""
    from grid import schema as grid_schema
    pid = subject.get("parcel") or ""
    p = parcels.by_id(pid) if pid else None
    cur = str((p or {}).get("use") or "")
    obs = sorted(ev.list_records(subject.get("id"), "observation.note"), key=lambda o: (str(o.get("observed_at") or ""), str(o.get("recorded_at") or "")), reverse=True)
    for o in obs:
        text = str(o.get("text") or "")
        v = parcels.use_declared(text)
        if not v:
            continue
        if v == cur or (grid_schema.use_key(v) and grid_schema.use_key(v) == grid_schema.use_key(cur)):
            return None                                       # 이미 그 용도다
        return {"from": "observation", "field": "use", "value": v, "id": o.get("id"), "observed_at": str(o.get("observed_at") or "")[:10], "text": text}
    return None


def known_subject_field(subject: dict[str, Any], field: str) -> dict[str, Any] | None:
    """농사(재배 단위) 값 — 지금은 인증(cert). 속성 → 관찰 원장의 선언(최근 먼저) → 없음. 심은 날은 파종 사건 확인이 바로 넣는다(chat.confirm) — 여기서 다시 읽지 않는다."""
    if field != "cert":
        return None
    cur = subject.get("cert")
    if cur:
        return {"from": "attribute", "field": field, "value": cur}
    obs = sorted(ev.list_records(subject.get("id"), "observation.note"), key=lambda o: (str(o.get("observed_at") or ""), str(o.get("recorded_at") or "")), reverse=True)
    for o in obs:
        text = str(o.get("text") or "")
        v = subjects.cert_declared(text)
        if v:
            return {"from": "observation", "field": field, "value": v, "id": o.get("id"), "observed_at": str(o.get("observed_at") or "")[:10], "text": text}
    return None


def proposals(subject: dict[str, Any], fields: tuple[str, ...] | list[str], already: set[tuple[str, str]] = frozenset(),
              subject_fields: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """일지에서 **값을 읽을 수 있는** 필지 값마다 밭 정보 초안 하나(parcel.field · why_key from_diary) · 농사 값(subject_fields — 인증)도 같은 길(subject.field).
    속성이 이미 있으면 안 올린다(용도는 다른 선언이면 올린다) · 같은 (필드, 값) 초안이 이미 서 있으면 다시 안 올린다 · 등록부에는 쓰지 않는다."""
    out: list[dict[str, Any]] = []
    for f in subject_fields:
        k = known_subject_field(subject, f)
        if k and k["from"] == "observation" and k.get("value") and (f, k["value"]) not in already:
            out.append({"kind": "subject.field", "subject": subject.get("id"), "field": f, "value": k["value"], "text": k["text"],
                        "why": f"일지 {k['observed_at']} 관찰({k['id']})에서 읽은 {subjects.SUBJECT_FIELD_WORDS.get(f, f)} '{k['value']}' — 묻지 않고 초안으로(확인 뒤 subjects.set_cert)",
                        "why_key": "from_diary", "source_ref": k["id"], "observed_at": k["observed_at"], "needs": []})
    pid = subject.get("parcel")
    if not pid:
        return out
    for f in fields:
        k = known_use_differs(subject) if f == "use" else known_field(subject, f)
        if not k or k["from"] != "observation" or not k.get("value"):
            continue
        if (f, k["value"]) in already:
            continue
        out.append({"kind": "parcel.field", "parcel": pid, "field": f, "value": k["value"], "text": k["text"],
                    "why": f"일지 {k['observed_at']} 관찰({k['id']})에서 읽은 {parcels.FIELD_WORDS.get(f, f)} '{k['value']}' — 묻지 않고 초안으로(확인 뒤 parcels.set_fields)",
                    "why_key": "from_diary", "source_ref": k["id"], "observed_at": k["observed_at"], "needs": []})
    return out
