# -*- coding: utf-8 -*-
# FILE: ingest/profile.py
# ROLE: [M-13 사용자 정보 탭 — 발행자 2026-09-19] 사용자 등록부 하나(data/profile.json). 이름·역할·필지 목록·설정 상태.
#       연락처·주소 같은 PII 는 여기 두지 않는다 — 필지 상세는 필지 등록부(ingest.parcels)가 벗겨서 낸다.
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingest import media
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "profile.json"
ROLES = ("farmer", "publisher")


class ProfileError(ValueError):
    pass


def path() -> Path:
    import os
    return Path(os.environ.get("AGRODSS_PROFILE_PATH") or PATH)


def load() -> dict[str, Any]:
    p = path()
    if not p.exists():
        return {"id": "u001", "name": "", "role": "farmer", "parcels": [], "source": "publisher",
                "recorded_at": "", "note": "아직 이름이 없다 — 사용자 정보 탭에서 적는다"}
    rec = json.loads(p.read_text(encoding="utf-8"))
    return sch.validate(rec, kind="user")


def save(name: str, role: str, note: str = "", now: datetime | None = None) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ProfileError("이름(표시명)이 비어 있다")
    if role not in ROLES:
        raise ProfileError(f"역할은 {' · '.join(ROLES)} 중 하나")
    for bad in ("@", "010-", "010 "):
        if bad in name or bad in note:
            raise ProfileError("이름·메모에 연락처를 넣지 않는다(PII)")
    cur = load()
    rec = {"id": cur.get("id", "u001"), "kind": "user", "name": name[:60], "role": role,
           "parcels": sorted({s.get("parcel") for s in media.load_subjects() if s.get("parcel")}),
           "source": "publisher", "recorded_at": (now or datetime.now(timezone.utc).astimezone()).isoformat(timespec="seconds")}
    if note.strip():
        rec["note"] = note.strip()[:300]
    sch.validate(rec, kind="user")
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rec
