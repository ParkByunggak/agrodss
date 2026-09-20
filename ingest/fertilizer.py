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

from ingest import config, parcels, soil_exam, soil_store
from schema import records as sch

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
# [코드 평가 C2 · 2026-09-19] 재배환경 기본값(DEFAULT_ENV="노지")을 없앴다 — 미상이면 노지 코드(07027)로 처방을 받아 시설 필지에
# 노지 처방이 **정본 저장소**에 들어가던 대리값(헌법 "fallback 대표값 강제 금지 — 수령 불명 시 되묻기"). 이제 미상은 CodeError 로 되묻는다.
ENVIRONMENTS = parcels.FIELD_CHOICES["environment"]   # 어휘 정본은 등록부(ingest.parcels) — 화면 폼이 보는 목록과 같은 것 하나(두 벌 금지)
# VELA 명세서 기본값(가축분 혼합비율) — 응답의 퇴비량 산정에 쓰이는 파라미터. 출처: fertilizer_service._ANIMIX_DEFAULTS
ANIMIX_DEFAULTS = {"animix_Ratio_Cattl": "28", "animix_Ratio_Pig": "22", "animix_Ratio_Chick": "19"}


class CodeError(ValueError):
    pass


def crop_code(crop: str, api: str, environment: str | None = None) -> str:
    """작물코드. 재배환경이 없으면 **묻는다**(기본값으로 메우지 않는다) — 노지/시설은 코드가 다르고 처방이 정본으로 저장된다."""
    if not environment:
        raise CodeError(f"재배환경 미상: {crop!r} — 필지 등록부 environment(노지|시설)를 채우거나 --env 로 준다. 기본값으로 메우지 않는다")
    if environment not in ENVIRONMENTS:
        raise CodeError(f"재배환경 어휘 밖: {environment!r} — {' | '.join(ENVIRONMENTS)}")
    try:
        return CROP_CODES[crop][api][environment]
    except KeyError:
        raise CodeError(f"{api} 작물코드 미등록: {crop!r}/{environment!r} — VELA crop_code_crosswalk.json 에서 인용해 CROP_CODES 에 추가(실측 확인 뒤)")


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
    # [발행자 라이브 2026-09-19 21:34] 지오코딩이 좌표·PNU 를 얻었는데 필지 등록부에 쓰지 않아 예보가 "좌표 없음"으로 남았다 —
    # 검정값처럼 좌표도 등록부에 남긴다(있는 값은 덮지 않는다). 등록부에 없는 필지면 그냥 지나간다(수집은 계속).
    try:
        geo_fields = {k: geo.get(k) for k in ("lat", "lon", "pnu") if geo.get(k) is not None}
        parcels.set_fields(parcel_id, **geo_fields)
        out["registry"] = "좌표·PNU 등록부 반영"
    except (parcels.ParcelError, sch.SchemaError) as e:
        out["registry"] = f"등록부 미반영 — {e}"
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


def resolve_subject(subject_id: str) -> dict[str, str | None]:
    """[코드 평가 D1·D11] 재배 단위 id(ASCII) 하나로 작목 · 필지 · 주소 · 재배환경을 **등록부에서** 푼다.
    배치 파일에 한글 주소·작목을 리터럴로 두지 않기 위한 경로(cmd 는 배치를 cp949 로 읽어 UTF-8 한글이 깨진다 · 주소는 PII)."""
    from ingest import parcels, subjects
    s = subjects.by_id(subject_id)
    if not s:
        raise CodeError(f"없는 재배 단위: {subject_id}")
    p = parcels.by_id(s.get("parcel", "")) or {}
    return {"parcel": s.get("parcel"), "crop": s.get("crop"), "address": p.get("address"), "environment": p.get("environment")}


def set_environment(subject_id: str, environment: str) -> dict[str, Any]:
    """되물은 재배환경(노지|시설)을 재배 단위의 필지 등록부에 남긴다 — 어휘 밖은 거부, 있는 값은 덮는다(발행자가 답한 값이 정본)."""
    if environment not in ENVIRONMENTS:
        raise CodeError(f"재배환경 어휘 밖: {environment!r} — {' | '.join(ENVIRONMENTS)}")
    r = resolve_subject(subject_id)
    return parcels.set_fields(r["parcel"] or "", environment=environment, overwrite=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    if opts.get("--subject"):
        r = resolve_subject(opts["--subject"])
        if not r["address"]:
            print(json.dumps({"status": "error", "message": f"필지 {r['parcel']} 에 주소가 없다 — 등록부(parcels)에 넣는다"}, ensure_ascii=False))
            sys.exit(2)
        if opts.get("--env"):
            # 되물은 답(노지|시설)은 등록부에 남긴다 — 다음 수집부터는 묻지 않는다
            set_environment(opts["--subject"], opts["--env"])
        res = collect_for_parcel(r["parcel"] or "", r["address"], r["crop"] or "", opts.get("--env") or r["environment"])
    elif not args or not opts.get("--parcel") or not opts.get("--crop"):
        # [발행자 2026-09-20 "쪽파는 사례"] 주소 모드는 필지 · 작목을 **명시**한다 — 전에는 p001 · 쪽파가 기본값이라 다른 필지의 검정값이
        # 첫 농가 필지에 저장될 수 있었다(fallback 대표값 금지). 등록된 재배 단위면 --subject 가 정본이다
        print("사용: python -m ingest.fertilizer <지번 주소> --parcel=<필지 id> --crop=<작목> [--env=노지|시설]  |  --subject=<재배 단위 id>")
        sys.exit(2)
    else:
        res = collect_for_parcel(opts["--parcel"], " ".join(args), opts["--crop"], opts.get("--env"))
    if "--summary" in sys.argv:
        # 상태만(PII 없음) — 채팅에 붙여도 되는 형태. 값은 data/soil/ 에만
        print(json.dumps(summary(res), ensure_ascii=False, indent=2))
    else:
        # 화면 출력은 PNU·검정값을 담는다(PII) — 저장은 data/soil/ (git 제외) 에만
        print(json.dumps(res, ensure_ascii=False, indent=2))
