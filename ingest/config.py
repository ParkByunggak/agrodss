# -*- coding: utf-8 -*-
# FILE: ingest/config.py
# ROLE: 외부 원천 주소·키 이름 — 값은 환경변수(.env)에만. 문서·커밋에 값 기재 금지.
from __future__ import annotations

import os

# 흙토람 토양검정(SoilExam) — data.go.kr 1390802. [D-9] VELA 에서 인용한 원천.
SOIL_EXAM_URL: str = os.environ.get(
    "AGRODSS_SOIL_EXAM_URL",
    "https://apis.data.go.kr/1390802/SoilEnviron/SoilExam/V2/getSoilExam",
)
# VWorld 지오코딩(주소 → 좌표·법정동코드·지번)
VWORLD_ADDRESS_URL: str = os.environ.get(
    "AGRODSS_VWORLD_ADDRESS_URL", "https://api.vworld.kr/req/address"
)
TIMEOUT_SEC: float = float(os.environ.get("AGRODSS_INGEST_TIMEOUT_SEC", "15"))


def soil_exam_key() -> str | None:
    """키 이름은 agrodss 것이 먼저, VELA 이름은 인용 호환(로컬 .env 를 그대로 쓸 수 있게)."""
    for name in ("AGRODSS_SOIL_EXAM_API_KEY", "SOIL_API_KEY", "EXTERNAL_API__SOIL_API_KEY"):
        v = os.environ.get(name)
        if v:
            return v
    return None


def vworld_key() -> str | None:
    for name in ("AGRODSS_VWORLD_API_KEY", "VWORLD_API_KEY", "EXTERNAL_API__VWORLD_API_KEY"):
        v = os.environ.get(name)
        if v:
            return v
    return None
