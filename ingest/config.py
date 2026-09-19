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
# 흙토람 비료사용처방(FrtlzrUse — 필지 검정값 기반) · 비료표준사용량(FrtlzrStdUse — 작물 표준). [D-9] VELA
# backend_new/config_subsystems/infra_config.py FERTILIZER_BASE_URL / FERTILIZER_STD_BASE_URL 인용(2026-09-19).
FRTLZR_USE_URL: str = os.environ.get(
    "AGRODSS_FRTLZR_USE_URL", "https://apis.data.go.kr/1390802/SoilEnviron/FrtlzrUse/getSoilFrtlzrExamInfo"
)
FRTLZR_STD_URL: str = os.environ.get(
    "AGRODSS_FRTLZR_STD_URL", "https://apis.data.go.kr/1390802/SoilEnviron/FrtlzrStdUse/getSoilFrtlzrQyList"
)
# PSIS 농약등록정보 검색(SVC01) — 전용 인증키. [D-9] VELA infra_config PSIS_BASE_URL 인용(2026-09-19)
PSIS_URL: str = os.environ.get("AGRODSS_PSIS_URL", "https://psis.rda.go.kr/openApi/service.do")
PSIS_MAX_ITEMS: int = int(os.environ.get("AGRODSS_PSIS_MAX_ITEMS", "5"))
PSIS_CACHE_DAYS: int = int(os.environ.get("AGRODSS_PSIS_CACHE_DAYS", "7"))     # 등록정보는 저변동(VELA 6h 캐시 취지)
TIMEOUT_SEC: float = float(os.environ.get("AGRODSS_INGEST_TIMEOUT_SEC", "15"))


def _first(*names: str) -> str | None:
    for name in names:
        v = os.environ.get(name)
        if v:
            return v
    return None


def soil_exam_key() -> str | None:
    """키 이름은 agrodss 것이 먼저, VELA 이름은 인용 호환(로컬 .env 를 그대로 쓸 수 있게)."""
    return _first("AGRODSS_SOIL_EXAM_API_KEY", "SOIL_API_KEY", "EXTERNAL_API__SOIL_API_KEY")


def vworld_key() -> str | None:
    return _first("AGRODSS_VWORLD_API_KEY", "VWORLD_API_KEY", "EXTERNAL_API__VWORLD_API_KEY")


def fertilizer_key() -> str | None:
    """FrtlzrUse 키. VELA 이름 FERTILIZER_API_KEY, 없으면 data.go.kr 공통 키(같은 기관 1390802 활용신청이면 같은 키)."""
    return _first("AGRODSS_FERTILIZER_API_KEY", "FERTILIZER_API_KEY", "EXTERNAL_API__FERTILIZER_API_KEY", "DATA_GO_KR_API_KEY")


def fertilizer_std_key() -> str | None:
    return _first("AGRODSS_FERTILIZER_STD_API_KEY", "FERTILIZER_STD_API_KEY", "EXTERNAL_API__FERTILIZER_STD_API_KEY",
                  "FERTILIZER_API_KEY", "DATA_GO_KR_API_KEY")
