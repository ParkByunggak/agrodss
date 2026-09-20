# -*- coding: utf-8 -*-
# FILE: ingest/subjects.py
# ROLE: [M-13 · 몰-B] 재배 단위 등록부 쓰기 — 채팅 목록의 단위. 작목을 추가하거나 계획이 생길 때 하나 만든다.
#       작목 이름은 사전(names.resolve)을 거친다 — 모호하면 되묻고, 모르면 추측하지 않는다(I-8).
#       파종 전이면 anchor 없음 · status="계획". 격자 단위는 있으면 붙이고 없으면 붙이지 않는다(판단 불가(지식)가 된다).
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from grid import schema as grid_schema
from ingest import media
from names import resolve as names
from schema import records as sch

def default_parcel() -> str | None:
    """필지 등록부에 필지가 **하나뿐이면** 그것, 아니면 None(사람이 고른다). [발행자 2026-09-20 "쪽파는 사례"] 전에는 상수 "p001" 이라
    둘째 필지가 생겨도 새 재배 단위가 조용히 첫 농가 필지에 붙었다(fallback 대표값 금지)."""
    from ingest import parcels   # 호출 시점에 — 등록부 경로는 env 로 격리된다(R-4)
    ps = parcels.load()
    return ps[0]["id"] if len(ps) == 1 else None


def path() -> Path:
    """호출 시점에 푼다 — 기본 인자·모듈 상수에 묶으면 격리가 안 닿는다(R-4 실측: 운영 등록부에 33줄 오염)."""
    return media.subjects_path()


class SubjectError(ValueError):
    pass


def load() -> list[dict[str, Any]]:
    return media.load_subjects()


def by_id(sid: str) -> dict[str, Any] | None:
    for s in load():
        if s["id"] == sid:
            return s
    return None


def resolve_crop(name: str) -> str:
    r = names.resolve(name)
    if r.status in ("canonical", "alias"):
        return r.canonical or r.query
    if r.status == "ambiguous":
        raise SubjectError(f"'{name}' 은 여러 작목을 가리킨다 — {' / '.join(r.candidates)} 중 어느 것인가")
    # [U-14] 모르는 이름은 추측하지 않고 후보로 적어 둔다 — 보이게까지 자동, 등재는 발행자(/improve 이름 후보)
    from names import candidates
    cand = candidates.add(name, context="new_chat")
    tail = f" 후보로 적어 두었다({cand['id']}) — /improve 에서 정본명에 잇는다" if cand else " 이미 후보에 있다 — /improve 에서 정본명에 잇는다"
    raise SubjectError(f"'{name}' 은 사전에 없는 이름이다 — 정본명으로 적거나 발행자가 사전(data/crop_names.csv)에 올린다(U-14).{tail}")


def grid_unit_for(crop: str, season: str) -> str | None:
    for p in sorted(grid_schema.GRID_DIR.glob("*.json")):
        try:
            u = json.loads(p.read_text(encoding="utf-8")).get("unit", {})
        except json.JSONDecodeError:
            continue
        if u.get("crop") == crop and u.get("season") and u["season"] in season:
            return u.get("id")
    return None


def _slug(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", s)


def add(crop: str, season: str, status: str = "계획", parcel: str | None = None, anchor: str | None = None,
        anchor_kind: str | None = None, cert: str | None = None, source: str = "farmer", note: str = "",
        now: datetime | None = None) -> dict[str, Any]:
    p = path()
    parcel = (parcel or "").strip() or default_parcel()
    if not parcel:
        raise SubjectError("필지를 지정한다 — 등록된 필지가 하나가 아니라 기본값을 두지 않는다(fallback 대표값 금지)")
    crop_c = resolve_crop(crop)
    season = (season or "").strip()
    if not season:
        raise SubjectError("작기(예: 2026 가을)가 없다 — 재배 단위는 작목 × 작기다")
    if status not in sch.SUBJECT_STATUS:
        raise SubjectError(f"상태는 {' · '.join(sch.SUBJECT_STATUS)} 중 하나")
    if status == "재배 중" and not anchor:
        raise SubjectError("재배 중이면 기준점(파종·정식일)이 있어야 한다 — 없으면 '계획'으로 만든다")
    subjects = load()
    for s in subjects:
        if s["crop"] == crop_c and s["season"] == season and s.get("parcel") == parcel:
            raise SubjectError(f"이미 있는 재배 단위: {s['label']} ({s['id']})")
    sid = f"{parcel}-{_slug(crop_c)}-{_slug(season)}"
    rec: dict[str, Any] = {"id": sid, "parcel": parcel, "label": f"{crop_c} · {season}", "crop": crop_c, "season": season,
                           "source": source, "status": status,
                           "recorded_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")}
    if anchor:
        rec["anchor"] = anchor
        rec["anchor_kind"] = anchor_kind or "파종"
    if cert:
        rec["cert"] = cert
    gu = grid_unit_for(crop_c, season)
    if gu:
        rec["grid_unit"] = gu
    if note:
        rec["note"] = note[:300]
    sch.validate(rec, kind="subject")
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"subjects": []}
    data.setdefault("subjects", []).append(rec)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rec


def set_anchor(sid: str, anchor: str, anchor_kind: str = "파종") -> dict[str, Any]:
    """계획이던 목록이 파종되면 기준점을 넣고 '재배 중'으로 — 파종 사건 확인 시 채팅이 부른다."""
    p = path()
    data = json.loads(p.read_text(encoding="utf-8"))
    for s in data.get("subjects", []):
        if s["id"] == sid:
            s["anchor"], s["anchor_kind"], s["status"] = anchor[:10], anchor_kind, "재배 중"
            sch.validate(s, kind="subject")
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return s
    raise SubjectError(f"없는 재배 단위: {sid}")
