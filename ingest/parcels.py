# -*- coding: utf-8 -*-
# FILE: ingest/parcels.py
# ROLE: [M-6 · I-3 §1 · I-6] 필지 등록부 — 필지 고정 정보의 자리. 주소·PNU·좌표는 여기 있고 화면·봉투·몰에는 안 나간다(I-5 §1-2).
#       값이 없으면 키가 없다(대리값 금지). 3층에는 PARCEL_FIELDS_TO_LAYER3 만 붙여 준다.
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
PARCELS_PATH = ROOT / "data" / "parcels.json"


def parcels_path() -> Path:
    """[R-4 · 코드 평가 C4] 경로는 호출 시점에 env 로 푼다 — 기본 인자에 묶으면 conftest 격리가 안 닿는다(오늘 전수 처방에서 빠진 한 곳)."""
    return Path(os.environ.get("AGRODSS_PARCELS_PATH") or PARCELS_PATH)


def load(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or parcels_path()
    if not p.exists():
        return []
    rows = json.loads(p.read_text(encoding="utf-8")).get("parcels", [])
    return [sch.validate(r, kind="parcel") for r in rows]


def by_id(pid: str, path: Path | None = None) -> dict[str, Any] | None:
    for r in load(path):
        if r.get("id") == pid:
            return r
    return None


def public_view(rec: dict[str, Any]) -> dict[str, Any]:
    """화면용 — PII 를 뺀다. 있음/없음만 남긴다."""
    out = {k: v for k, v in rec.items() if k not in sch.PII_FIELDS}
    out["location"] = "있음" if any(rec.get(k) is not None for k in ("address", "pnu", "lat", "lon")) else "없음"
    return out


def enrich_subject(subject: dict[str, Any], parcel: dict[str, Any] | None) -> dict[str, Any]:
    """재배 단위에 필지의 3층 허용 필드만 붙인다. 주소·PNU 는 붙지 않는다. 없는 값은 안 붙는다."""
    s = dict(subject)
    if not parcel:
        return s
    for k in sch.PARCEL_FIELDS_TO_LAYER3:
        if k in parcel and k not in s:
            s[k] = parcel[k]
    return s


def missing_inputs(parcel: dict[str, Any] | None) -> list[str]:
    """I-6 입력 대기 — 필지 레코드에 아직 없는 키(화면에 '입력 대기'로)."""
    want = ("lat", "lon", "area_m2", "use", "environment", "soil_texture", "slope", "drainage", "irrigation",
            "microclimate", "night_light", "cert_legal", "seed_source", "soil_exam_ref")
    have = set(parcel or {})
    return [k for k in want if k not in have]
