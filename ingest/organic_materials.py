# -*- coding: utf-8 -*-
# FILE: ingest/organic_materials.py
# ROLE: [M-15 ④ · H 자재 분리(유기 갈래)] 농관원 유기농업자재 공시현황 — 정본 파일 + 재수집기 + 검색.
#
# [D-9 인용] 원본: VELA backend_new/core/organic_materials_job.py(수집 — data.go.kr 15080748 → data.mafra Grid,
#   1,000건 페이징, 유효기간 재검증, 전량 교체, 급감 가드) · organic_materials.py(검색 — 유형/키워드, 조회 시점 재검증).
#   표준 라이브러리로 다시 썼고 초기 정본은 VELA 사본(fetched_at 20260907)을 열 10개로 줄여 인용했다.
#
# 정직 원칙(VELA 인용): 공시 = '유기재배에 쓸 수 있음'이지 효능 보증이 아니다. 만료분은 조회 시점에 걸러 낸다.
#   0건이면 no_data — 범주명으로 메우지 않는다. 증분 병합 금지 — 취소분이 영원히 남는다.
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = Path(os.environ.get("AGRODSS_ORGANIC_PATH") or (ROOT / "data" / "organic" / "organic_materials_public.json"))
GRID_ID = "Grid_20200929000000000606_1"
BASE = os.environ.get("AGRODSS_ORGANIC_BASE", "http://211.237.50.150:7080/openapi")
SOURCE = "external:naqs_organic_materials"
TYPE_PEST = "병해충관리"
TYPE_SOIL = "토양개량 및 작물생육"
KEEP = ("PBLNTF_ID", "PBLNTF_NO", "MTRIL_TYPE_NM", "MTRIL_NM", "PRODUCT_NM", "PBLNTF_BEGIN_DE", "PBLNTF_END_DE",
        "PRODUCT_PC", "CMPNY_NM", "MANAGE_INSTT_NM")
DROP_GUARD = 0.5     # 유효 건수가 직전의 절반 미만이면 교체 보류(원본 장애로 정본이 비는 사고 차단)


def api_key() -> str | None:
    for n in ("AGRODSS_ORGANIC_MATERIAL_API_KEY", "ORGANIC_MATERIAL_API_KEY", "DATA_GO_KR_API_KEY"):
        if os.environ.get(n):
            return os.environ[n]
    return None


# ── 정본 읽기 · 검색 ─────────────────────────────────────────────────────────────
def load() -> dict[str, Any]:
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"rows": [], "fetched_at": None, "source": SOURCE}


def _valid(rows: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    t = today.strftime("%Y%m%d")
    return [r for r in rows if (r.get("PBLNTF_END_DE") or "") >= t]


def search(material_type: str | None = None, keyword: str | None = None, limit: int = 5,
           today: date | None = None) -> dict[str, Any]:
    """공시 자재 검색 → 1층 참조 레코드 목록. 조회 시점 유효분만. 0건이면 no_data."""
    today = today or date.today()
    canon = load()
    rows = _valid(canon.get("rows", []), today)
    if material_type:
        rows = [r for r in rows if r.get("MTRIL_TYPE_NM") == material_type]
    if keyword:
        k = keyword.strip()
        rows = [r for r in rows if k in (r.get("MTRIL_NM") or "") or k in (r.get("PRODUCT_NM") or "")]
    total = len(rows)
    rows.sort(key=lambda r: r.get("PBLNTF_END_DE") or "", reverse=True)
    fetched = canon.get("fetched_at")
    items = [{
        "kind": "reference.organic_material_notice", "axis": ["cert"],
        "observed_at": f"{fetched[:4]}-{fetched[4:6]}-{fetched[6:]}" if fetched and len(fetched) == 8 else fetched,
        "source": SOURCE, "resolution": "national",
        "values": {"notice_no": r.get("PBLNTF_NO"), "type": r.get("MTRIL_TYPE_NM"), "material": r.get("MTRIL_NM"),
                   "product": r.get("PRODUCT_NM"), "price": r.get("PRODUCT_PC"), "company": r.get("CMPNY_NM"),
                   "valid_until": r.get("PBLNTF_END_DE")},
    } for r in rows[:limit]]
    return {"status": "success" if items else "no_data", "items": items, "total": total,
            "fetched_at": fetched, "note": "공시 = 유기재배에 쓸 수 있음(인정)이지 효능 보증이 아니다"}


def material_types() -> list[str]:
    return sorted({r.get("MTRIL_TYPE_NM") for r in load().get("rows", []) if r.get("MTRIL_TYPE_NM")})


# ── 재수집 (전량 교체) ─────────────────────────────────────────────────────────────
def _http_page(key: str, start: int, end: int) -> dict[str, Any]:
    req = urllib.request.Request(f"{BASE}/{key}/json/{GRID_ID}/{start}/{end}", headers={"User-Agent": "agrodss/0.1"})
    with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8", errors="replace"))


def fetch_all(key: str, page: Callable[[str, int, int], dict[str, Any]] = _http_page, step: int = 1000) -> dict[str, Any]:
    rows, start = [], 1
    while True:
        body = page(key, start, start + step - 1).get(GRID_ID, {})
        code = (body.get("result") or {}).get("code")
        if code and code != "INFO-000":
            return {"status": "error", "message": f"{code}: {(body.get('result') or {}).get('message')}", "rows": []}
        got = body.get("row") or []
        rows += got
        if not got or len(rows) >= int(body.get("totalCnt", 0) or 0):
            break
        start += step
    return {"status": "success", "rows": rows}


def run_collection(page: Callable[[str, int, int], dict[str, Any]] = _http_page, today: date | None = None,
                   path: Path | None = None) -> dict[str, Any]:
    """전량 재수집 → 유효분 교체. 급감이면 보류. 반환 {status, total_all, valid, added, dropped}."""
    today = today or date.today()
    path = path or DATA_PATH
    key = api_key()
    if not key:
        return {"status": "no_key", "message": "data.go.kr 인증키 없음 (ORGANIC_MATERIAL_API_KEY 또는 DATA_GO_KR_API_KEY)"}
    try:
        got = fetch_all(key, page)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"status": "error", "message": f"요청 실패: {e}"}
    if got["status"] != "success":
        return got
    rows = [{k: r.get(k) for k in KEEP} for r in got["rows"]]
    valid = _valid(rows, today)
    if not valid:
        return {"status": "error", "message": "유효 공시 0건 — 원본 이상으로 판단해 교체 보류"}
    prev = _valid(load().get("rows", []), today) if path.exists() else []
    if prev and len(valid) < len(prev) * DROP_GUARD:
        return {"status": "suspect_drop", "message": f"유효 {len(prev)}→{len(valid)} 급감 — 교체 보류", "valid": len(valid)}
    prev_ids = {r.get("PBLNTF_ID") for r in prev}
    new_ids = {r.get("PBLNTF_ID") for r in valid}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "source": f"농관원 유기농업자재 공시현황(data.go.kr 15080748 → data.mafra {GRID_ID})",
        "fetched_at": today.strftime("%Y%m%d"), "total_all": len(rows), "rows": valid,
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "total_all": len(rows), "valid": len(valid),
            "added": len(new_ids - prev_ids), "dropped": len(prev_ids - new_ids)}
