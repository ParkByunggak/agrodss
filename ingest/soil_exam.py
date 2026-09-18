# -*- coding: utf-8 -*-
# FILE: ingest/soil_exam.py
# ROLE: [I-2 soil_chem · I-6] 흙토람 토양검정 조회 — 주소 → (VWorld) 좌표·PNU → (SoilExam) 검정값.
#       산출은 **1층 사실 레코드**: 관측 시각(검정일) · 출처 · 해상도(parcel)가 붙는다.
#
# [D-9 인용] 발행자 결정 2026-09-18 "토양검정 API 는 d:\vela 에서 인용". 이식 폐기의 유일한
#   예외. 원본: VELA backend_new/services/location_to_soil.py L2.1.0 (주소→PNU 파이프라인 ·
#   SoilExam 항목 매핑). 여기서는 aiohttp 대신 표준 라이브러리로 다시 썼고, 캐시·로그·VELA
#   설정 결합은 두지 않았다. 판단 로직은 없다 — 값을 해석하지 않는다(그것은 2층·3층).
#
# G3: 미검정 필지는 status=no_data 로 돌려준다. 대표값으로 메우지 않는다(그것은 별개 원천 ·
#   별개 해상도 district 이고 지금은 열지 않는다).
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ingest import config

SOURCE = "external:heuktoram_soilexam"
RESOLUTION = "parcel"
AXIS = "soil_chem"

# SoilExam 응답 태그 → (필드명, 단위). VELA 인용.
ITEM_MAP: dict[str, tuple[str, str]] = {
    "ACID": ("ph", ""),
    "OM": ("organic_matter", "g/kg"),
    "VLDPHA": ("phosphorus", "mg/kg"),
    "POSIFERT_K": ("potassium", "cmol+/kg"),
    "POSIFERT_CA": ("calcium", "cmol+/kg"),
    "POSIFERT_MG": ("magnesium", "cmol+/kg"),
    "VLDSIA": ("silica", "mg/kg"),
    "ELCD": ("conductivity", "dS/m"),
}


# ── PNU 조합 (순수 함수 — VELA 인용) ────────────────────────────────────────────
def parse_level5(level5: str) -> tuple[int, int, bool]:
    """'산78임' → (78, 0, True) · '50' → (50, 0, False) · '50-3' → (50, 3, False)"""
    if not level5:
        return 0, 0, False
    text = level5.strip()
    mountain = text.startswith("산")
    if mountain:
        text = text[1:]
    text = re.sub(r"[^0-9\-]", "", text)
    try:
        if "-" in text:
            a, b = text.split("-", 1)
            return (int(a) if a else 0), (int(b) if b else 0), mountain
        return (int(text) if text else 0), 0, mountain
    except ValueError:
        return 0, 0, mountain


def build_pnu(level4lc: str, level5: str) -> str | None:
    """법정동코드(10) + 산(1) + 본번(4) + 부번(4) = 19. level4LC 가 이미 19자리면 그대로."""
    if not level4lc:
        return None
    if len(level4lc) == 19:
        return level4lc
    if len(level4lc) == 10:
        bon, bu, mountain = parse_level5(level5)
        pnu = f"{level4lc}{'1' if mountain else '0'}{bon:04d}{bu:04d}"
        if len(pnu) == 19:
            return pnu
    return None


# ── 응답 파싱 (순수 함수 — 네트워크 없이 검사 가능) ───────────────────────────────
@dataclass
class SoilExamRecord:
    """1층 사실 레코드. 3요건(observed_at · source · resolution)이 항상 채워진다."""
    status: str                       # success | no_data | error
    pnu: str
    axis: str = AXIS
    source: str = SOURCE
    resolution: str = RESOLUTION
    observed_at: str | None = None    # 검정일(원천 Exam_Day) — 관측 시각
    fetched_at: str | None = None     # 조회 시각
    exam_year: str | None = None
    address_label: str | None = None  # 원천이 돌려주는 필지 표기 — PII, 화면에 싣지 않음
    values: dict[str, float | str] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def parse_soil_exam_xml(text: str, pnu: str, fetched_at: str | None = None) -> SoilExamRecord:
    fetched_at = fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return SoilExamRecord(status="error", pnu=pnu, fetched_at=fetched_at, message=f"XML 파싱 실패: {e}")
    header = root.find(".//header")
    if header is not None:
        code = header.findtext("Result_Code", "")
        if code and code != "200":
            return SoilExamRecord(status="error", pnu=pnu, fetched_at=fetched_at,
                                  message=f"원천 오류 {code}: {header.findtext('Result_Msg', '')}")
    item = root.find(".//item")
    if item is None:
        return SoilExamRecord(status="no_data", pnu=pnu, fetched_at=fetched_at,
                              message="토양검정 데이터 없음 — 미검정 필지 또는 미등록")
    rec = SoilExamRecord(
        status="success", pnu=pnu, fetched_at=fetched_at,
        observed_at=item.findtext("Exam_Day", "") or None,
        exam_year=item.findtext("Any_Year", "") or None,
        address_label=item.findtext("Pnu_Nm", "") or None,
    )
    for tag, (key, unit) in ITEM_MAP.items():
        raw = item.findtext(tag, "")
        if not raw:
            continue
        try:
            rec.values[key] = float(raw)
        except ValueError:
            rec.values[key] = raw
        if unit:
            rec.units[key] = unit
    if not rec.observed_at:
        # 검정일이 없으면 1층 3요건 미달 — 값이 있어도 사실로 진입시키지 않는다(F 1층 규칙)
        rec.status = "error"
        rec.message = "검정일(Exam_Day) 없음 — 관측 시각 없는 값은 1층에 진입하지 못한다"
    return rec


# ── 네트워크 ─────────────────────────────────────────────────────────────────────
def _get(url: str, params: dict[str, str]) -> str:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full, timeout=config.TIMEOUT_SEC) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def fetch_soil_exam(pnu: str, key: str | None = None) -> SoilExamRecord:
    key = key or config.soil_exam_key()
    if not key:
        return SoilExamRecord(status="error", pnu=pnu, message="토양검정 API 키 없음 (AGRODSS_SOIL_EXAM_API_KEY)")
    try:
        text = _get(config.SOIL_EXAM_URL, {"serviceKey": key, "PNU_CD": pnu})
    except (urllib.error.URLError, OSError) as e:
        return SoilExamRecord(status="error", pnu=pnu, message=f"원천 접속 실패: {e}")
    return parse_soil_exam_xml(text, pnu)


def geocode(address: str, key: str | None = None) -> dict[str, Any] | None:
    """주소 → {lat, lon, level4lc, level5, pnu}. 실패 시 None."""
    key = key or config.vworld_key()
    if not key:
        return None
    params = {
        "service": "address", "request": "getcoord", "address": address,
        "crs": "epsg:4326", "key": key, "format": "json", "type": "parcel",
    }
    try:
        data = json.loads(_get(config.VWORLD_ADDRESS_URL, params))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return parse_geocode_json(data)


def parse_geocode_json(data: dict[str, Any]) -> dict[str, Any] | None:
    response = data.get("response", {})
    if response.get("status") != "OK":
        return None
    point = response.get("result", {}).get("point", {})
    lon, lat = point.get("x"), point.get("y")
    if not (lon and lat):
        return None
    structure = response.get("refined", {}).get("structure", {})
    level4lc = structure.get("level4LC", "")
    level5 = structure.get("level5", "")
    return {
        "lat": float(lat), "lon": float(lon),
        "level4lc": level4lc, "level5": level5, "pnu": build_pnu(level4lc, level5),
    }


def address_to_soil_exam(address: str) -> dict[str, Any]:
    """주소 → 좌표·PNU → 검정 레코드. 반환 {location, soil}. 실패 단계가 message 에 남는다."""
    geo = geocode(address)
    if not geo:
        return {"location": {"address": address}, "soil": SoilExamRecord(
            status="error", pnu="", message="주소 → 좌표 변환 실패(키 없음 또는 원천 실패)").to_dict()}
    loc = {"address": address, "lat": geo["lat"], "lon": geo["lon"], "pnu": geo.get("pnu")}
    if not geo.get("pnu"):
        return {"location": loc, "soil": SoilExamRecord(status="error", pnu="", message="PNU 조합 실패").to_dict()}
    return {"location": loc, "soil": fetch_soil_exam(geo["pnu"]).to_dict()}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("사용: python -m ingest.soil_exam <지번 주소>   (또는 --pnu <19자리>)")
        sys.exit(2)
    if sys.argv[1] == "--pnu" and len(sys.argv) >= 3:
        out: Any = fetch_soil_exam(sys.argv[2]).to_dict()
    else:
        out = address_to_soil_exam(" ".join(sys.argv[1:]))
    # 출력은 화면에만 — 파일로 저장하지 않는다(PII). 저장은 스키마(M-6)가 선 뒤 레코드로.
    print(json.dumps(out, ensure_ascii=False, indent=2))
