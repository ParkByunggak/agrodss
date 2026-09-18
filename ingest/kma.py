# -*- coding: utf-8 -*-
# FILE: ingest/kma.py
# ROLE: [M-15 ② · I-4 temp/precip/forecast] 기상청 원천 셋 — 1층 사실 레코드로.
#   ① 지상 일자료(apihub kma_sfcdd)       → temp(일 최고/최저/평균) · precip(일 강수) · 일조   관측
#   ② 일별 평년값(apihub sfc_norm1)       → A1 '외부 기준'(평년과 다르다)                     기준
#   ③ 단기예보(data.go.kr VilageFcst 2.0) → forecast(일 최고/최저 · 강수확률 · 강수량)         예보
#
# [D-9 인용] 원본: VELA backend_new/services/kma_daily_temp.py(컬럼 상수·결측 가드) ·
#   kma_climate_normal.py(_COLS · 최근접 지점) · weather_service.py(_get_vilage_fcst_base_datetime) ·
#   weather_subsystems/weather_client.py(latlon_to_grid). 표준 라이브러리로 다시 썼다.
#
# 규칙: 결측 센티널(-90 이하 · 음수 강수)은 None — 0 이나 평균으로 메우지 않는다(G3).
#       예보는 관측이 아니다 — 축적(GDD)에는 관측만 쓴다(VELA 규율 인용). 레코드 kind 로 구분한다.
#       해상도: 관측·평년 = 관측소(station:<id> + 거리 km), 예보 = 5km 격자(grid5km:<nx>,<ny>).
from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATIONS_PATH = ROOT / "data" / "kma" / "stations.json"

HUB_BASE = os.environ.get("AGRODSS_KMA_HUB_BASE", "https://apihub.kma.go.kr/api/typ01/url")
FCST_BASE = os.environ.get("AGRODSS_KMA_FCST_BASE", "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0")
TIMEOUT = float(os.environ.get("AGRODSS_INGEST_TIMEOUT_SEC", "20"))

SRC_OBS = "external:kma_sfcdd"
SRC_NORM = "external:kma_sfc_norm1"
SRC_FCST = "external:kma_vilagefcst"


def hub_key() -> str | None:
    for n in ("AGRODSS_KMA_API_HUB_KEY", "KMA_API_HUB_KEY", "KMA__API_HUB_KEY", "EXTERNAL_API__KMA_API_HUB_KEY"):
        if os.environ.get(n):
            return os.environ[n]
    return None


def fcst_key() -> str | None:
    for n in ("AGRODSS_KMA_FORECAST_API_KEY", "KMA_FORECAST_API_KEY", "EXTERNAL_API__KMA_FORECAST_API_KEY", "DATA_GO_KR_API_KEY"):
        if os.environ.get(n):
            return os.environ[n]
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── ① 지상 일자료 kma_sfcdd (VELA 인용: 컬럼 0-idx TM=0 STN=1 TA_AVG=10 TA_MAX=11 TA_MIN=13 SS_DAY=32 RN_DAY=38) ──
_C_TM, _C_STN, _C_TA_AVG, _C_TA_MAX, _C_TA_MIN, _C_SS, _C_RN = 0, 1, 10, 11, 13, 32, 38
_MIN_COLS = 14


def _num(parts: list[str], idx: int) -> float | None:
    try:
        v = float(parts[idx])
    except (ValueError, IndexError):
        return None
    return None if v <= -90 else v


def parse_daily_obs(text: str, fetched_at: str | None = None) -> list[dict[str, Any]]:
    """원문(줄당 하루·지점) → 1층 레코드. 파싱 붕괴 신호(tmax<tmin)는 행 폐기(정직 결측)."""
    fetched_at = fetched_at or _now_iso()
    out: list[dict[str, Any]] = []
    for ln in (text or "").splitlines():
        ln = ln.strip().rstrip("=").strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.replace(",", " ").split()
        if len(parts) < _MIN_COLS or not parts[_C_TM][:8].isdigit():
            continue
        tmax, tmin, ta_avg = _num(parts, _C_TA_MAX), _num(parts, _C_TA_MIN), _num(parts, _C_TA_AVG)
        if tmax is not None and tmin is not None and tmax < tmin:
            continue
        if ta_avg is not None and tmax is not None and tmin is not None and not (tmin - 0.5 <= ta_avg <= tmax + 0.5):
            ta_avg = None
        rn = _num(parts, _C_RN)
        if rn is not None and rn < 0:
            rn = None
        ss = _num(parts, _C_SS)
        if ss is not None and not (0.0 <= ss <= 24.0):
            ss = None
        try:
            stn = int(parts[_C_STN])
        except ValueError:
            continue
        d = parts[_C_TM][:8]
        out.append({
            "kind": "observation.weather_daily", "axis": ["temp", "precip"],
            "observed_at": f"{d[:4]}-{d[4:6]}-{d[6:]}", "fetched_at": fetched_at,
            "source": SRC_OBS, "resolution": f"station:{stn}", "station": stn,
            "values": {"tmax": tmax, "tmin": tmin, "ta_avg": ta_avg, "rn_day_mm": rn, "ss_day_hr": ss},
        })
    return out


def _get_text(url: str, params: dict[str, Any], encoding: str = "euc-kr") -> tuple[int, str]:
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "agrodss/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310
            return r.status, r.read().decode(encoding, errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError) as e:
        return 0, str(e)


def fetch_daily_obs(stn: int, day: date) -> dict[str, Any]:
    key = hub_key()
    if not key:
        return {"status": "error", "message": "기상청 apihub 키 없음 (KMA_API_HUB_KEY)", "records": []}
    status, text = _get_text(f"{HUB_BASE}/kma_sfcdd.php", {"tm": day.strftime("%Y%m%d"), "stn": stn, "help": 0, "authKey": key})
    if status == 403:
        return {"status": "awaiting_approval", "message": "kma_sfcdd 활용 미승인(403) — apihub 에서 지상관측 일자료 신청", "records": []}
    if status != 200:
        return {"status": "error", "message": f"HTTP {status} {text[:120]}", "records": []}
    recs = parse_daily_obs(text)
    return {"status": "success" if recs else "no_data", "records": recs}


# ── ② 일별 평년값 sfc_norm1 (VELA 인용: _COLS) ────────────────────────────────────────
_NORM_COLS = ["tmst", "stn", "mm", "dd", "ta", "ta_max", "ta_min", "rn", "ev", "ws", "hm", "pv", "ss", "ca_tot", "pa", "ps"]
_NORM_NUM = {"ta", "ta_max", "ta_min", "rn", "ev", "ws", "hm", "pv", "ss", "ca_tot", "pa", "ps"}
_NORM_NONNEG = {"rn", "ev", "ws", "hm", "ss", "ca_tot", "pv"}


def parse_normals(text: str, fetched_at: str | None = None) -> list[dict[str, Any]]:
    fetched_at = fetched_at or _now_iso()
    out: list[dict[str, Any]] = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = [p.strip() for p in ln.rstrip("=").strip().split(",")]
        if len(parts) < len(_NORM_COLS):
            continue
        rec: dict[str, Any] = {}
        for i, c in enumerate(_NORM_COLS):
            v = parts[i]
            if c in _NORM_NUM:
                try:
                    f = float(v)
                    rec[c] = None if (f <= -90 or (c in _NORM_NONNEG and f < 0)) else f
                except ValueError:
                    rec[c] = None
            else:
                rec[c] = v
        try:
            stn = int(rec["stn"]); mm = int(rec["mm"]); dd = int(rec["dd"]); tmst = int(rec["tmst"])
        except (ValueError, TypeError):
            continue
        out.append({
            "kind": "reference.climate_normal", "axis": ["temp", "precip"],
            "observed_at": f"normal:{tmst - 30}-{tmst - 1}", "for_day": f"{mm:02d}-{dd:02d}",
            "fetched_at": fetched_at, "source": SRC_NORM, "resolution": f"station:{stn}", "station": stn,
            "values": {"ta": rec["ta"], "ta_max": rec["ta_max"], "ta_min": rec["ta_min"], "rn_mm": rec["rn"], "ss_hr": rec["ss"]},
        })
    return out


def fetch_normals(stn: int, mm1: int, dd1: int, mm2: int, dd2: int, tmst: int = 2021) -> dict[str, Any]:
    key = hub_key()
    if not key:
        return {"status": "error", "message": "기상청 apihub 키 없음 (KMA_API_HUB_KEY)", "records": []}
    status, text = _get_text(f"{HUB_BASE}/sfc_norm1.php", {
        "norm": "D", "tmst": tmst, "stn": stn, "MM1": mm1, "DD1": dd1, "MM2": mm2, "DD2": dd2, "help": 0, "authKey": key})
    if status != 200:
        return {"status": "error", "message": f"HTTP {status}", "records": []}
    recs = parse_normals(text)
    return {"status": "success" if recs else "no_data", "records": recs}


# ── ③ 단기예보 VilageFcst 2.0 (VELA 인용: 격자 변환 · 발표 시각 규칙) ──────────────────────
_RE, _GRID, _SLAT1, _SLAT2, _OLON, _OLAT, _XO, _YO = 6371.00877, 5.0, 30.0, 60.0, 126.0, 38.0, 43, 136


def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    deg = math.pi / 180.0
    re_ = _RE / _GRID
    slat1, slat2, olon, olat = _SLAT1 * deg, _SLAT2 * deg, _OLON * deg, _OLAT * deg
    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (sf ** sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re_ * sf / (ro ** sn)
    ra = math.tan(math.pi * 0.25 + lat * deg * 0.5)
    ra = re_ * sf / (ra ** sn)
    theta = lon * deg - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    return int(math.floor(ra * math.sin(theta) + _XO + 0.5)), int(math.floor(ro - ra * math.cos(theta) + _YO + 0.5))


def vilage_base_datetime(now: datetime) -> tuple[str, str]:
    """발표 시각(02·05·08·11·14·17·20·23시) 중 now−40분 이전의 최신. 없으면 전날 23시."""
    cand = now - timedelta(minutes=40)
    avail = [h for h in (2, 5, 8, 11, 14, 17, 20, 23) if h <= cand.hour]
    if avail:
        return cand.strftime("%Y%m%d"), f"{max(avail):02d}00"
    cand -= timedelta(days=1)
    return cand.strftime("%Y%m%d"), "2300"


def _pcp_mm(s: str) -> float | None:
    s = (s or "").strip()
    if not s or s in ("강수없음", "-", "0"):
        return 0.0
    for tok in ("mm 미만", "mm", "이상"):
        s = s.replace(tok, "")
    s = s.replace("~", " ").split()[-1] if s else s
    try:
        return float(s)
    except ValueError:
        return None


def parse_vilage(payload: dict[str, Any], nx: int, ny: int, fetched_at: str | None = None) -> list[dict[str, Any]]:
    """응답 JSON → 날짜별 요약 레코드(TMX·TMN·POP 최대·PCP 합·TMP 시간대). 판단 없음."""
    fetched_at = fetched_at or _now_iso()
    try:
        body = payload["response"]["body"]["items"]["item"]
    except (KeyError, TypeError):
        return []
    if isinstance(body, dict):
        body = [body]
    base_date = base_time = ""
    days: dict[str, dict[str, Any]] = {}
    for it in body:
        d = it.get("fcstDate", "")
        if not d:
            continue
        base_date, base_time = it.get("baseDate", base_date), it.get("baseTime", base_time)
        rec = days.setdefault(d, {"tmax": None, "tmin": None, "pop_max": None, "rain_mm": 0.0, "tmp": {}, "sky": {}, "pty": {}})
        cat, val, t = it.get("category"), str(it.get("fcstValue", "")), it.get("fcstTime", "")
        if cat == "TMX":
            rec["tmax"] = float(val)
        elif cat == "TMN":
            rec["tmin"] = float(val)
        elif cat == "POP":
            rec["pop_max"] = max(rec["pop_max"] or 0, int(float(val)))
        elif cat == "PCP":
            mm = _pcp_mm(val)
            if mm is not None and rec["rain_mm"] is not None:
                rec["rain_mm"] += mm
        elif cat == "TMP":
            rec["tmp"][t] = float(val)
        elif cat == "SKY":
            rec["sky"][t] = val
        elif cat == "PTY":
            rec["pty"][t] = val
    out = []
    for d in sorted(days):
        r = days[d]
        if r["tmax"] is None and r["tmp"]:
            r["tmax_from_tmp"] = max(r["tmp"].values())     # TMX 가 없는 날(발표 시각 뒤)은 시간대 최고로 — 표기 구분
        if r["tmin"] is None and r["tmp"]:
            r["tmin_from_tmp"] = min(r["tmp"].values())
        out.append({
            "kind": "forecast.weather_daily", "axis": ["forecast"],
            "observed_at": f"{base_date[:4]}-{base_date[4:6]}-{base_date[6:]}T{base_time[:2]}:{base_time[2:]}:00+09:00" if base_date else None,
            "for_day": f"{d[:4]}-{d[4:6]}-{d[6:]}", "fetched_at": fetched_at,
            "source": SRC_FCST, "resolution": f"grid5km:{nx},{ny}",
            "values": {k: v for k, v in r.items() if k not in ("tmp", "sky", "pty")},
            "hourly_tmp": r["tmp"], "sky": r["sky"], "pty": r["pty"],
        })
    return out


def fetch_vilage(lat: float, lon: float, now: datetime | None = None) -> dict[str, Any]:
    key = fcst_key()
    if not key:
        return {"status": "error", "message": "단기예보 키 없음 (KMA_FORECAST_API_KEY 또는 DATA_GO_KR_API_KEY)", "records": []}
    nx, ny = latlon_to_grid(lat, lon)
    base_date, base_time = vilage_base_datetime(now or datetime.now())
    status, text = _get_text(f"{FCST_BASE}/getVilageFcst", {
        "serviceKey": key, "pageNo": 1, "numOfRows": 1000, "dataType": "JSON",
        "base_date": base_date, "base_time": base_time, "nx": nx, "ny": ny}, encoding="utf-8")
    if status != 200:
        return {"status": "error", "message": f"HTTP {status}", "records": []}
    try:
        payload = json.loads(text)
    except ValueError:
        return {"status": "error", "message": "JSON 아님", "records": []}
    recs = parse_vilage(payload, nx, ny)
    return {"status": "success" if recs else "no_data", "grid": [nx, ny], "base": [base_date, base_time], "records": recs}


# ── 관측 지점 (VELA stations.json 인용, 한반도 범위) ──────────────────────────────────
@lru_cache(maxsize=1)
def stations() -> list[dict[str, Any]]:
    if not STATIONS_PATH.exists():
        return []
    return json.loads(STATIONS_PATH.read_text(encoding="utf-8")).get("stations", [])


def haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    dlat, dlon = math.radians(b_lat - a_lat), math.radians(b_lon - a_lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(min(1.0, math.sqrt(h)))


def nearest_station(lat: float, lon: float, allowed_ids: frozenset[int] | None = None) -> dict[str, Any] | None:
    """최근접 지점 {id, name, dist_km}. allowed_ids 는 각 API 가 실제로 보유한 지점 집합(원천에서 유도) —
    평년(sfc_norm1)과 일자료(kma_sfcdd)의 보유 지점이 다르므로 집합을 API 별로 넘긴다(VELA 규율 인용)."""
    cands = [s for s in stations() if allowed_ids is None or s["id"] in allowed_ids]
    if not cands:
        return None
    best = min(cands, key=lambda s: haversine_km(lat, lon, s["lat"], s["lon"]))
    return {"id": best["id"], "name": best["name"], "lat": best["lat"], "lon": best["lon"],
            "dist_km": round(haversine_km(lat, lon, best["lat"], best["lon"]), 1)}
