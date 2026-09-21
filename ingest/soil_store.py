# -*- coding: utf-8 -*-
# FILE: ingest/soil_store.py
# ROLE: [I-6 · M-15 ⑥] 필지별 토양 원천 저장소 — 토양검정 · 비료 처방 · 표준 시비량 레코드를 필지 id 로 묶어 둔다.
#       PII(PNU · 검정값)가 들어가므로 data/soil/ 은 git 에 올리지 않는다(.gitignore). 격리: AGRODSS_SOIL_DIR.
#       저장 직전 스키마 검증(stamp). 최신 1건만 쓴다 — 같은 (종류 · 필지 · 코드)는 덮어쓰되 이전 파일은 .prev 로 남긴다.
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ingest import dropped
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
KIND_FILE = {"observation.soil_exam": "soil_exam", "reference.fertilizer_prescription": "prescription",
             "reference.fertilizer_standard": "standard"}


def soil_dir() -> Path:
    return Path(os.environ.get("AGRODSS_SOIL_DIR") or (ROOT / "data" / "soil"))


def _name(kind: str, parcel: str | None, code: str | None) -> str:
    base = KIND_FILE[kind]
    parts = [p for p in (parcel, base, code) if p]
    return "_".join(parts) + ".json"


def save(rec: dict[str, Any], parcel: str | None, code: str | None = None) -> Path:
    rec = sch.stamp(rec)
    d = soil_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / _name(rec["kind"], parcel, code)
    if p.exists():
        p.replace(p.with_suffix(".prev.json"))
    p.write_text(json.dumps({"parcel": parcel, "code": code, "record": rec}, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def latest(kind: str, parcel: str | None, code: str | None = None) -> dict[str, Any] | None:
    p = soil_dir() / _name(kind, parcel, code)
    if not p.exists():
        return None
    try:
        rec = json.loads(p.read_text(encoding="utf-8")).get("record")
        return sch.validate(rec) if rec else None
    except (ValueError, sch.SchemaError) as e:
        # [조용한 실패 전수 2026-09-21] 전에는 그냥 None 이었다 — 처방 정본이 **있는데** 못 읽으면 판정이
        # "정본 미도착" 이라고 말한다. 원인이 뒤바뀌어 농가는 없는 것을 다시 받으러 간다. 버린 사실을 남긴다.
        dropped.note("토양 저장소", p.name, f"{type(e).__name__}: {e}")
        return None


def prescriptions_for(parcel: str) -> list[dict[str, Any]]:
    out = []
    for p in sorted(soil_dir().glob(f"{parcel}_prescription_*.json")):
        if p.name.endswith(".prev.json"):
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8")).get("record")
            if rec:
                out.append(sch.validate(rec))
        except (ValueError, sch.SchemaError) as e:
            dropped.note("토양 저장소(처방)", p.name, f"{type(e).__name__}: {e}")
            continue
    return out
