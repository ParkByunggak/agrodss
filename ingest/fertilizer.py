# -*- coding: utf-8 -*-
# FILE: ingest/fertilizer.py
# ROLE: [M-15 ⑥ 시비량 처방 정본 · I-2 soil_chem] 흙토람 비료사용처방(FrtlzrUse — 필지 검정값 기반 N·P·K·퇴비) 과
#       비료표준사용량(FrtlzrStdUse — 작물 표준) 조회. 산출은 1층 레코드 — 값을 해석하지 않는다(그것은 3층).
#
# [D-9 인용] 원본: VELA backend_new/services/fertilizer_service.py v1.3.0(FrtlzrUse · FERT_ITEM_MAP · 작물코드) ·
#   fertilizer_std_service.py v1.3.0(FrtlzrStdUse · STD_ITEM_MAP) · data/crop_code_crosswalk.json(쪽파 확정 코드).
#   표준 라이브러리로 다시 썼고, 캐시·로그·FertilizerAdvisor 폴백·VELA 설정 결합은 두지 않았다.
#   ★ 작물코드 네임스페이스 원칙(VELA): FrtlzrUse crop_Code 와 FrtlzrStdUse fstd_Crop_Code 는 **다른 체계** — 혼용 금지
#     (실측: 쪽파 노지 FrtlzrUse=07027 vs FrtlzrStdUse=07014). CLAUDE.md 절대 제약과 같은 줄.
#
# 대리값 금지: 키가 없거나 원천이 no_data 면 status 로 돌려주고 표준값으로 메우지 않는다(표준은 별개 레코드 · 별개 해상도).
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from ingest import config, soil_exam, soil_store

SOURCE_USE = "external:heuktoram_frtlzruse"
SOURCE_STD = "external:heuktoram_frtlzrstduse"
AXIS = "soil_chem"
# 응답 태그 → (필드, 단위). VELA FERT_ITEM_MAP / STD_ITEM_MAP 인용.
ITEM_MAP: dict[str, tuple[str, str]] = {
    "pre_Fert_N": ("pre_n", "kg/10a"), "pre_Fert_P": ("pre_p2o5", "kg/10a"), "pre_Fert_K": ("pre_k2o", "kg/10a"),
    "post_Fert_N": ("post_n", "kg/10a"), "post_Fert_P": ("post_p2o5", "kg/10a"), "post_Fert_K": ("post_k2o", "kg/10a"),
    "pre_Compost_Cattl": ("compost_cattle", "kg/10a"), "pre_Compost_Pig": ("compost_pig", "kg/10a"),
    "pre_Compost_Chick": ("compost_chicken", "kg/10a"), "pre_Compost_Mix": ("compost_mixed", "kg/10a"),
}
# 작물코드 — VELA crop_code_crosswalk.json 확정값(2026-09-19 인용). 두 API 는 코드 체계가 다르다.
CROP_CODES: dict[str, dict[str, dict[str, str]]] = {
    "쪽파": {"FrtlzrUse": {"노지": "07027", "시설": "07035"}, "FrtlzrStdUse": {"노지": "07014", "시설": "07015"}},
}
DEFAULT_ENV = "노지"
# VELA 명세서 기본값(가축분 혼합비율) — 응답의 퇴비량 산정에 쓰이는 파라미터. 출처: fertilizer_service._ANIMIX_DEFAULTS
ANIMIX_DEFAULTS = {"animix_Ratio_Cattl": "28", "animix_Ratio_Pig": "22", "animix_Ratio_Chick": "19"}


class CodeError(ValueError):
    pass


def crop_code(crop: str, api: str, environment: str | None = None) -> str:
    env = environment or DEFAULT_ENV
    try:
        return CROP_CODES[crop][api][env]
    except KeyError:
        raise CodeError(f"{api} 작물코드 미등록: {crop!r}/{env!r} — VELA crop_code_crosswalk.json 에서 인용해 CROP_CODES 에 추가(실측 확인 뒤)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _values(item: ET.Element) -> tuple[dict[str, float | str], dict[str, str], dict[str, str]]:
    values: dict[str, float | str] = {}
    units: dict[str, str] = {}
    raw: dict[str, str] = {}
    for child in item:
        text = (child.text or "").strip()
        raw[child.tag] = text
        if child.tag in ITEM_MAP:
            name, unit = ITEM_MAP[child.tag]
            try:
                values[name] = float(text)
            except ValueError:
                values[name] = text
            units[name] = unit
    return values, units, raw


def _header_status(root: ET.Element) -> tuple[str | None, str]:
    h = root.find(".//header")
    if h is None:
        return None, ""
    code = h.findtext("result_Code") or h.findtext("Result_Code") or ""     # FrtlzrUse 는 소문자 r(VELA 실측)
    msg = h.findtext("result_Msg") or h.findtext("Result_Msg") or ""
    if code and code != "200":
        return ("no_data" if code == "301" else "error"), f"{code} {msg}".strip()
    return None, ""


def parse_prescription_xml(text: str, pnu: str, code: str, fetched_at: str | None = None) -> dict[str, Any]:
    fetched_at = fetched_at or _now()
    rec: dict[str, Any] = {"kind": "reference.fertilizer_prescription", "axis": AXIS, "status": "error", "pnu": pnu, "crop_code": code,
                           "observed_at": fetched_at[:10], "fetched_at": fetched_at, "source": SOURCE_USE, "resolution": "parcel",
                           "values": {}, "units": {}}
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        rec["message"] = f"XML 파싱 실패: {e}"
        return rec
    st, msg = _header_status(root)
    if st:
        rec["status"], rec["message"] = st, msg
        return rec
    item = root.find(".//item")
    if item is None:
        rec["status"], rec["message"] = "no_data", "응답에 item 이 없다"
        return rec
    values, units, raw = _values(item)
    rec.update({"status": "success" if values else "no_data", "values": values, "units": units,
                "crop_name": raw.get("crop_Nm"), "raw": raw})
    return rec


def parse_standard_xml(text: str, fstd_code: str, fetched_at: str | None = None) -> dict[str, Any]:
    fetched_at = fetched_at or _now()
    rec: dict[str, Any] = {"kind": "reference.fertilizer_standard", "axis": AXIS, "status": "error", "crop_code": fstd_code,
                           "observed_at": fetched_at[:10], "fetched_at": fetched_at, "source": SOURCE_STD, "resolution": "national",
                           "values": {}, "units": {}}
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        rec["message"] = f"XML 파싱 실패: {e}"
        return rec
    st, msg = _header_status(root)
    if st:
        rec["status"], rec["message"] = st, msg
        return rec
    item = root.find(".//item")
    if item is None:
        rec["status"], rec["message"] = "no_data", "응답에 item 이 없다"
        return rec
    values, units, raw = _values(item)
    rec.update({"status": "success" if values else "no_data", "values": values, "units": units,
                "crop_name": raw.get("fstd_Crop_Nm"), "raw": raw})
    return rec


def _get(url: str, params: dict[str, str]) -> str:
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "agrodss/0.1"})
    with urllib.request.urlopen(req, timeout=config.TIMEOUT_SEC) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_prescription(pnu: str, code: str, key: str | None = None) -> dict[str, Any]:
    key = key or config.fertilizer_key()
    if not key:
        return {"kind": "reference.fertilizer_prescription", "axis": AXIS, "status": "unavailable", "pnu": pnu, "crop_code": code,
                "observed_at": _now()[:10], "fetched_at": _now(), "source": SOURCE_USE, "resolution": "parcel", "values": {}, "units": {},
                "message": "키 없음(.env FERTILIZER_API_KEY 또는 DATA_GO_KR_API_KEY)"}
    try:
        text = _get(config.FRTLZR_USE_URL, {"serviceKey": key, "PNU_Code": pnu, "crop_Code": code, **ANIMIX_DEFAULTS})
    except (urllib.error.URLError, OSError) as e:
        rec = parse_prescription_xml("", pnu, code)
        rec["message"] = f"원천 연결 실패: {e}"
        return rec
    return parse_prescription_xml(text, pnu, code)


def fetch_standard(fstd_code: str, key: str | None = None) -> dict[str, Any]:
    key = key or config.fertilizer_std_key()
    if not key:
        return {"kind": "reference.fertilizer_standard", "axis": AXIS, "status": "unavailable", "crop_code": fstd_code,
                "observed_at": _now()[:10], "fetched_at": _now(), "source": SOURCE_STD, "resolution": "national", "values": {}, "units": {},
                "message": "키 없음(.env FERTILIZER_STD_API_KEY 또는 DATA_GO_KR_API_KEY)"}
    try:
        text = _get(config.FRTLZR_STD_URL, {"serviceKey": key, "fstd_Crop_Code": fstd_code, "numOfRows": "10", "pageNo": "1"})
    except (urllib.error.URLError, OSError) as e:
        rec = parse_standard_xml("", fstd_code)
        rec["message"] = f"원천 연결 실패: {e}"
        return rec
    return parse_standard_xml(text, fstd_code)


def collect_for_parcel(parcel_id: str, address: str, crop: str, environment: str | None = None,
                       fetch_soil=None, fetch_use=None, fetch_std=None, geocode=None) -> dict[str, Any]:
    """[I-6 한 번에] 주소 → PNU → 토양검정 + 비료 처방 + 표준 시비량 → soil_store 에 필지 id 로 저장. 실패 단계는 status 로 남는다.
    fetch_* 는 검사용 주입점(네트워크 없이). 저장은 status=success 인 것만 — 실패를 정본으로 남기지 않는다."""
    geocode = geocode or soil_exam.geocode
    geo = geocode(address)
    out: dict[str, Any] = {"parcel": parcel_id, "crop": crop, "pnu": None, "soil": None, "prescription": None, "standard": None, "saved": []}
    if not geo or not geo.get("pnu"):
        out["message"] = "주소 → PNU 실패(VWorld 키 또는 주소)"
        return out
    pnu = geo["pnu"]
    out["pnu"] = pnu
    soil = (fetch_soil or soil_exam.fetch_soil_exam)(pnu)
    soil_rec = soil.to_dict() if hasattr(soil, "to_dict") else soil
    out["soil"] = soil_rec
    if soil_rec.get("status") == "success":
        out["saved"].append(str(soil_store.save(soil_rec, parcel_id)))
    try:
        use_code = crop_code(crop, "FrtlzrUse", environment)
        pres = (fetch_use or fetch_prescription)(pnu, use_code)
        out["prescription"] = pres
        if pres.get("status") == "success":
            out["saved"].append(str(soil_store.save(pres, parcel_id, use_code)))
    except CodeError as e:
        out["prescription"] = {"status": "no_code", "message": str(e)}
    try:
        std_code = crop_code(crop, "FrtlzrStdUse", environment)
        std = (fetch_std or fetch_standard)(std_code)
        out["standard"] = std
        if std.get("status") == "success":
            out["saved"].append(str(soil_store.save(std, None, std_code)))
    except CodeError as e:
        out["standard"] = {"status": "no_code", "message": str(e)}
    return out


def summary(res: dict[str, Any]) -> dict[str, Any]:
    """수집 결과의 상태 요약 — PNU · 검정값 · 처방값은 뺀다(PII). 채팅에 붙이는 용도."""
    def st(x: Any) -> str:
        return (x or {}).get("status", "없음") if isinstance(x, dict) else "없음"
    return {"parcel": res.get("parcel"), "crop": res.get("crop"), "pnu": "있음" if res.get("pnu") else "없음",
            "soil": st(res.get("soil")), "prescription": st(res.get("prescription")), "standard": st(res.get("standard")),
            "saved": len(res.get("saved") or []), "message": res.get("message"),
            "notes": [f"{k}: {(res.get(k) or {}).get('message')}" for k in ("soil", "prescription", "standard")
                      if isinstance(res.get(k), dict) and res[k].get("message")]}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    if not args:
        print("사용: python -m ingest.fertilizer <지번 주소> [--parcel=p001] [--crop=쪽파] [--env=노지|시설]")
        sys.exit(2)
    res = collect_for_parcel(opts.get("--parcel", "p001"), " ".join(args), opts.get("--crop", "쪽파"), opts.get("--env"))
    if "--summary" in sys.argv:
        # 상태만(PII 없음) — 채팅에 붙여도 되는 형태. 값은 data/soil/ 에만
        print(json.dumps(summary(res), ensure_ascii=False, indent=2))
    else:
        # 화면 출력은 PNU·검정값을 담는다(PII) — 저장은 data/soil/ (git 제외) 에만
        print(json.dumps(res, ensure_ascii=False, indent=2))
