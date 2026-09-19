# -*- coding: utf-8 -*-
# FILE: ingest/ncpms.py
# ROLE: [M-15 ③ · I-4 pest_regional] 국가농작물병해충관리시스템(NCPMS) 병해충 예찰 검색(SVC51) → 1층 사실 레코드.
#
# [D-9 인용] 원본: VELA backend_new/services/ncpms_api.py(BASE_URL · serviceCode SVC51 · serviceType AA003 ·
#   searchKncrCode/searchExaminYear · XML→dict) · data/crop_code_crosswalk.json(_api_registry.NCPMS: '파'=VC041202).
#   표준 라이브러리로 다시 썼다.
#
# 정직성:
#   · SVC51 응답 필드명은 **실응답으로 확정 전**이다(VELA 규율 needs_schema_confirm). 파서는 알려진 별칭 후보에서
#     찾고, 못 찾은 필드는 None 으로 둔다. 원문 item 은 raw 에 보존한다 — 스키마 확정 시 대조용.
#   · 쪽파의 NCPMS 작물 코드는 미확정 — '파'(VC041202)를 **대리 작물**로 쓰되 레코드 해상도에 proxy 를 남긴다.
#     대리값이 아니라 '해상도 낮은 사실'(I-2 district 와 같은 논리) — 산출은 그 조건을 함께 싣는다.
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from ingest import config as _config  # [코드 평가 C11] .env 적재 + 타임아웃 정본

BASE_URL = os.environ.get("AGRODSS_NCPMS_BASE_URL", "http://ncpms.rda.go.kr/npmsAPI/service")
TIMEOUT = _config.TIMEOUT_SEC
SOURCE = "external:ncpms_svc51"
SERVICE_FORECAST = "SVC51"
SERVICE_TYPE = "AA003"

# NCPMS 작물 코드(영숫자 체계 — FrtlzrUse 숫자 코드와 혼용 금지). VELA crosswalk _confirmed_codes 인용.
CROP_CODES: dict[str, str] = {"파": "VC041202", "감귤": "FT060614", "감자": "FC050501", "고추": "VC011205",
                              "논벼": "FC010101", "마늘": "VC041209", "배": "FT010602", "사과": "FT010601", "포도": "FT040603"}
# 정본명 → NCPMS 작물 (대리 포함). 대리는 (코드 작물, 이유).
PROXY: dict[str, tuple[str, str]] = {
    "쪽파": ("파", "쪽파 코드 미확정 — 파속 예찰(고자리파리·총채벌레·좀나방·노균병)이 겹친다"),
    "대파": ("파", ""),
    "벼": ("논벼", ""),
}

# 응답 필드 별칭 후보 — 실응답으로 확정 전(needs_schema_confirm)
_F = {
    "crop": ("kncrNm", "cropName", "kncrName", "crop"),
    "pest": ("dbyhsNm", "dbyhsKorName", "sicknsKorName", "insectKorName", "pestName", "dbyhsName"),
    "region": ("sidoNm", "sidoName", "areaNm", "examinArea", "region"),
    "date": ("examinDay", "examinDate", "examinDe", "inqireDe", "date"),
    "year": ("examinYear", "year"),
    "level": ("occrrncLevel", "occrrncGrad", "dbyhsOccrrncLevel", "level", "grade"),
    "text": ("examinCn", "occrrncCn", "cn", "content", "text"),
}


def api_key() -> str | None:
    for n in ("AGRODSS_NCPMS_API_KEY", "NCPMS_API_KEY"):
        if os.environ.get(n):
            return os.environ[n]
    return None


def crop_code_for(canonical_crop: str) -> tuple[str | None, str | None, str]:
    """정본명 → (코드, 코드 작물명, 대리 사유). 코드 없으면 (None, None, 사유)."""
    name, why = PROXY.get(canonical_crop, (canonical_crop, ""))
    code = CROP_CODES.get(name)
    if not code:
        return None, None, f"NCPMS 작물 코드 없음: {canonical_crop!r}"
    return code, name, why


def _xml_items(text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(text)
    items = []
    for it in root.iter("item"):
        d = {}
        for ch in it:
            d[ch.tag] = (ch.text or "").strip() if len(ch) == 0 else "".join(ch.itertext()).strip()
        items.append(d)
    return items


def _pick(d: dict[str, Any], key: str) -> str | None:
    for k in _F[key]:
        v = d.get(k)
        if v not in (None, ""):
            return str(v)
    return None


def parse_forecast(text: str, canonical_crop: str, fetched_at: str | None = None) -> list[dict[str, Any]]:
    """응답(XML 또는 JSON) → 예찰 레코드. 필드 미확정 — 별칭 후보로 읽고 raw 보존."""
    fetched_at = fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    text = (text or "").strip()
    if not text:
        return []
    try:
        if text.startswith("<"):
            items = _xml_items(text)
        else:
            payload = json.loads(text)
            body = payload.get("service", payload)
            lst = body.get("list", body.get("items", []))
            items = lst.get("item", []) if isinstance(lst, dict) else lst
            if isinstance(items, dict):
                items = [items]
    except (ET.ParseError, ValueError, AttributeError):
        return []
    _, code_crop, why = crop_code_for(canonical_crop)
    res = f"region:{{sido}}" + (f"|proxy_crop:{code_crop}" if why else "")
    out = []
    for it in items:
        date_ = _pick(it, "date")
        year = _pick(it, "year")
        observed = date_ or (f"{year}" if year else None)
        if not observed:
            # [코드 평가 C12] 관측일이 없는 예찰 항목은 1층에 못 들어간다(3요건) — soil_exam 과 같은 규율. None 으로 레코드화하지 않는다
            continue
        region = _pick(it, "region") or "전국"
        out.append({
            "kind": "observation.pest_forecast", "axis": ["pest_regional"],
            "observed_at": observed, "fetched_at": fetched_at, "source": SOURCE,
            "resolution": res.replace("{sido}", region), "region": region,
            "crop_requested": canonical_crop, "crop_code_crop": code_crop, "proxy_reason": why or None,
            "values": {"crop": _pick(it, "crop"), "pest": _pick(it, "pest"), "level": _pick(it, "level"), "text": _pick(it, "text")},
            "raw": it,
            "schema_confirmed": False,
        })
    return out


def fetch_forecast(canonical_crop: str, year: int | None = None, display_count: int = 50) -> dict[str, Any]:
    key = api_key()
    if not key:
        return {"status": "error", "message": "NCPMS 키 없음 (NCPMS_API_KEY)", "records": []}
    code, code_crop, why = crop_code_for(canonical_crop)
    if not code:
        return {"status": "no_code", "message": why, "records": []}
    params = {"apiKey": key, "serviceCode": SERVICE_FORECAST, "serviceType": SERVICE_TYPE,
              "displayCount": display_count, "startPoint": 1, "searchKncrCode": code}
    if year:
        params["searchExaminYear"] = str(year)
    req = urllib.request.Request(f"{BASE_URL}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "agrodss/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310
            text = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return {"status": "error", "message": f"HTTP {e.code}", "records": []}
    except (urllib.error.URLError, OSError) as e:
        return {"status": "error", "message": f"원천 접속 실패: {e}", "records": []}
    recs = parse_forecast(text, canonical_crop)
    return {"status": "success" if recs else "no_data", "crop_code": code, "proxy": why or None, "records": recs}
