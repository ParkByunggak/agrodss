# -*- coding: utf-8 -*-
# FILE: ingest/psis.py
# ROLE: [M-15 ⑤ · H 자재 분리(관행 갈래)] PSIS(농촌진흥청 농약안전정보시스템) 농약등록정보 — 작물·병해충별 현행 등록약제와
#       안전사용기준(PLS: 희석배수 · 안전사용시기 · 사용횟수 · 작용기작). 산출은 1층 레코드 — 효능을 판단하지 않는다.
#
# [D-9 인용] 원본: VELA backend_new/services/psis_client.py(실측 규격 2026-08-06 · 필드 화이트리스트 FIX-PSIS-FIELDS ·
#   작용기작 라운드로빈 W-20) · psis_api.py(한글 키). 표준 라이브러리로 다시 썼고 VELA 설정·별칭 정본·상담 캐시는 두지 않았다.
#   규격: GET {URL}?apiKey=..&serviceCode=SVC01&serviceType=AA003&cropName=..&diseaseWeedName=..&displayCount=N
#         응답 <service><totalCount><list><item> pestiKorName · pestiBrandName · useName · diseaseWeedName · pestiUse ·
#         dilutUnit · useSuittime · useNum · indictSymbl. 오류 <service><errorCode><errorMsg>.
#   ⚠️ PSIS 전용 인증키(활용신청) — NCPMS · data.go.kr 키와 별개. VELA 는 SSL 검증을 껐다(verify=False) — 여기서는 끄지 않는다.
#     인증서 오류가 나면 상태로 남긴다(원천 쪽 문제를 코드로 덮지 않는다).
#
# 정직 원칙: 키 없음 = unavailable, 0건 = no_data(범주명으로 메우지 않는다), 오류 = error. 캐시는 파일(data/psis, git 제외) · PSIS_CACHE_DAYS.
from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ingest import config
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "external:psis_svc01"
KIND = "reference.pesticide_registration"
AXIS = "cert"
FIELDS = ("cropName", "diseaseWeedName", "useName", "pestiKorName", "pestiBrandName", "dilutUnit", "useSuittime", "useNum",
          "indictSymbl", "pestiUse")
FIELD_KO = {"pestiKorName": "product", "pestiBrandName": "brand", "useName": "use", "diseaseWeedName": "pest", "cropName": "crop",
            "dilutUnit": "dilution", "useSuittime": "phi", "useNum": "times", "indictSymbl": "moa", "pestiUse": "method"}
MAIN_USES = ("살균", "살충", "살균살충")
# PSIS 작물 표기 후보 — 정본명이 0건이면 순서대로 한 번 더(VELA ALIAS-CANON 취지. 추론, 실측 대기)
CROP_QUERY: dict[str, tuple[str, ...]] = {"쪽파": ("쪽파", "파")}


class PsisError(ValueError):
    pass


def psis_dir() -> Path:
    return Path(os.environ.get("AGRODSS_PSIS_DIR") or (ROOT / "data" / "psis"))


def key() -> str | None:
    return config._first("AGRODSS_PSIS_API_KEY", "PSIS_API_KEY", "EXTERNAL_API__PSIS_API_KEY")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── 순수 함수 ────────────────────────────────────────────────────────────────────
def error_of(xml_text: str) -> str | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return "XML 파싱 실패(규격 변경 신호)"
    code = root.findtext(".//errorCode")
    if code:
        return f"{code}: {root.findtext('.//errorMsg') or ''}".strip()
    return None


def parse_items(xml_text: str) -> tuple[list[dict[str, str]], int]:
    root = ET.fromstring(xml_text)
    items = [{el.tag: (el.text or "").strip() for el in item if el.tag in FIELDS} for item in root.findall(".//item")]
    total = root.findtext(".//totalCount") or "0"
    return items, (int(total) if total.isdigit() else len(items))


def dedupe(items: list[dict[str, str]]) -> list[dict[str, str]]:
    """전착제 등 '기타' 용도 후순위 · 같은 품목명 제거 · 작용기작(indictSymbl) 라운드로빈(VELA W-20: 대표 5종이 전부 같은 기작이던 실사례)."""
    main = [i for i in items if i.get("useName") in MAIN_USES]
    rest = [i for i in items if i not in main]
    uniq, seen = [], set()
    for i in main + rest:
        k = i.get("pestiKorName")
        if k and k not in seen:
            seen.add(k)
            uniq.append(i)
    out, moa_seen, deferred = [], set(), []
    for i in uniq:
        moa = (i.get("indictSymbl") or "").strip() or "?"
        if moa not in moa_seen:
            moa_seen.add(moa)
            out.append(i)
        else:
            deferred.append(i)
    return out + deferred


def to_record(crop: str, pest: str | None, status: str, items: list[dict[str, str]], total: int, fetched_at: str,
              queried_as: str | None = None, message: str | None = None) -> dict[str, Any]:
    rec: dict[str, Any] = {"kind": KIND, "axis": [AXIS], "status": status, "crop": crop, "pest": pest or "",
                           "observed_at": fetched_at[:10], "fetched_at": fetched_at, "source": SOURCE, "resolution": "national",
                           "total": total, "items": [{FIELD_KO.get(k, k): v for k, v in i.items()} for i in items]}
    if queried_as and queried_as != crop:
        rec["queried_as"] = queried_as
    if message:
        rec["message"] = message
    return rec


# ── 호출 ────────────────────────────────────────────────────────────────────────
def _get(params: dict[str, str]) -> str:
    req = urllib.request.Request(f"{config.PSIS_URL}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "agrodss/0.1"})
    with urllib.request.urlopen(req, timeout=config.TIMEOUT_SEC) as r:
        return r.read().decode("utf-8", errors="replace")


def query_once(crop_name: str, pest: str | None, limit: int, api_key: str, get=None) -> dict[str, Any]:
    params = {"apiKey": api_key, "serviceCode": "SVC01", "serviceType": "AA003", "cropName": crop_name, "displayCount": str(max(limit * 4, 20))}
    if pest:
        params["diseaseWeedName"] = pest
    try:
        text = (get or _get)(params)
    except ssl.SSLError as e:
        return {"status": "error", "note": f"SSL 인증서 오류(원천 쪽): {e} — 검증을 끄지 않는다. AGRODSS_PSIS_URL 로 원천 주소만 바꿀 수 있다"}
    except (urllib.error.URLError, OSError) as e:
        return {"status": "error", "note": f"요청 실패: {e}"}
    err = error_of(text)
    if err:
        return {"status": "error", "note": err}
    try:
        items, total = parse_items(text)
    except ET.ParseError:
        return {"status": "error", "note": "XML 파싱 실패(규격 변경 신호)"}
    items = dedupe(items)[:limit]
    return {"status": "success" if items else "no_data", "items": items, "total": total}


def _cache_path(crop: str, pest: str | None) -> Path:
    safe = re.sub(r"[^0-9A-Za-z가-힣]+", "_", f"{crop}_{pest or 'all'}")
    return psis_dir() / f"{safe}.json"


def search(crop: str, pest: str | None = None, limit: int | None = None, today: date | None = None, get=None,
           api_key: str | None = None) -> dict[str, Any]:
    """작물(+병해충) 등록약제 레코드. 캐시가 PSIS_CACHE_DAYS 안이면 그것을 쓴다. 키 없으면 unavailable. 0건이면 표기 후보로 한 번 더."""
    today = today or _now().date()
    limit = limit or config.PSIS_MAX_ITEMS
    p = _cache_path(crop, pest)
    if p.exists():
        try:
            cached = sch.validate(json.loads(p.read_text(encoding="utf-8")))
            age = (today - date.fromisoformat(cached["observed_at"])).days
            if 0 <= age <= config.PSIS_CACHE_DAYS and cached.get("status") in ("success", "no_data"):
                return cached
        except (ValueError, sch.SchemaError, KeyError):
            pass
    api_key = api_key or key()
    fetched = _now().isoformat(timespec="seconds")
    if not api_key:
        rec = to_record(crop, pest, "unavailable", [], 0, fetched, message="PSIS 키 없음(.env PSIS_API_KEY — psis.rda.go.kr 전용 활용신청)")
        rec["observed_at"] = today.isoformat()
        return rec
    result: dict[str, Any] = {"status": "no_data", "items": [], "total": 0}
    used = crop
    for name in CROP_QUERY.get(crop, (crop,)):
        result = query_once(name, pest, limit, api_key, get=get)
        used = name
        if result["status"] == "success":
            break
        if result["status"] == "error":
            return to_record(crop, pest, "error", [], 0, fetched, message=result.get("note"))
    rec = to_record(crop, pest, result["status"], result.get("items", []), result.get("total", 0), fetched, queried_as=used)
    rec["observed_at"] = today.isoformat()        # 관측일 = 조회한 날(캐시 나이의 기준). fetched_at 은 실제 시각
    rec = sch.stamp(rec)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return rec


def pest_terms(risk_name: str) -> list[str]:
    """격자 위험 이름 → PSIS 적용병해충 검색어. '고자리파리 유충' → ['고자리파리'], '파총채벌레 · 파좀나방' → 둘, '노균병' → ['노균병'].
    괄호·'유충'·'—' 뒤는 뗀다. 병해충이 아닌 위험(서리 · 지연 · 부패)은 []."""
    base = re.sub(r"\(.*?\)", "", risk_name).split("—")[0]
    out = []
    for part in re.split(r"[·,/]", base):
        t = re.sub(r"\s*(유충|성충|피해|발생)\s*$", "", part.strip())
        if t and any(k in t for k in ("파리", "벌레", "나방", "진딧물", "병", "응애", "총채", "굼벵이", "선충", "달팽이")):
            out.append(t)
    return out
