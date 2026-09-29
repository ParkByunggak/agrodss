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

from ingest import config as _config  # [코드 평가 C11] .env 적재 + 타임아웃 정본 — 세 원천 모듈이 각자 15/20/30 으로 읽고 .env 는 안 읽었다

ROOT = Path(__file__).resolve().parent.parent
STATIONS_PATH = ROOT / "data" / "kma" / "stations.json"

HUB_BASE = os.environ.get("AGRODSS_KMA_HUB_BASE", "https://apihub.kma.go.kr/api/typ01/url")
FCST_BASE = os.environ.get("AGRODSS_KMA_FCST_BASE", "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0")
TIMEOUT = _config.TIMEOUT_SEC

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


def _float_or_none(s: Any) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


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


def _http_why(status: int, text: str = "") -> str:
    """못 받은 이유 문장. [D-21 실측 2026-09-28] 연결이 안 되면 `_get_text` 가 (0, 오류문) 을 돌려주는데 그것을 "HTTP 0" 이라고 적고 있었다 —
    HTTP 응답이 아니라 연결 실패다(키 문제 · 망 차단 · 원천 다운이 다 여기). 이유는 그대로 화면까지 가므로(사실 인용) 말이 맞아야 한다."""
    if status == 0:
        return f"연결 실패: {(text or '').strip()[:120] or '응답 없음'}"
    return f"HTTP {status}" + (f" {text[:120]}" if text else "")


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
        return {"status": "error", "message": _http_why(status, text), "records": []}
    recs = parse_daily_obs(text)
    return {"status": "success" if recs else "no_data", "records": recs}


# [D-20 · 발행자 2026-09-29 "이미 기상청 현시점 이전의 무강수일을 가지고 있다 — 이를 활용해서 관수를 권고해야"] 지난 날의 일자료는 바뀌지 않는다 —
# 같은 프로세스 안에서 같은 (지점, 날)을 다시 부르지 않는다(오늘은 담지 않는다 — 하루가 끝나야 확정). 예보 메모(§5 ⑦)와 다르다: 관측은 사실이지 대리값이 아니다.
_OBS_CACHE: dict[tuple[int, str], list[dict[str, Any]]] = {}


def fetch_recent_obs(stn: int, today: date, lookback: int, wet_mm: float = 0.1) -> dict[str, Any]:
    """어제부터 `lookback` 일 뒤로 하루씩(kma_sfcdd 는 tm 단일일 — VELA 정본 양식) — **비 온 날(일강수 ≥ wet_mm)을 만나면 멈춘다**(무강수 일수엔 마지막
    비 온 날만 필요하다) · 원천이 죽으면 첫 실패에서 멈춘다(30번 매달리지 않는다). 돌려주는 것: 받은 레코드(최근 날부터) · 몇 날을 봤는지 · 멈춘 이유."""
    key = hub_key()
    if not key:
        return {"status": "error", "message": "기상청 apihub 키 없음 (KMA_API_HUB_KEY)", "records": [], "days_seen": 0}
    out: list[dict[str, Any]] = []
    for back in range(1, lookback + 1):
        day = today - timedelta(days=back)
        ck = (stn, day.isoformat())
        if ck in _OBS_CACHE:
            recs = _OBS_CACHE[ck]
        else:
            r = fetch_daily_obs(stn, day)
            if r["status"] in ("error", "awaiting_approval"):
                return {"status": r["status"], "message": r.get("message", ""), "records": out, "days_seen": back - 1}
            recs = [x for x in r["records"] if x.get("station") == stn]
            _OBS_CACHE[ck] = recs
        out += recs
        if any((x["values"].get("rn_day_mm") or 0) >= wet_mm for x in recs):
            return {"status": "success", "records": out, "days_seen": back, "stopped": "wet"}
    return {"status": "success", "records": out, "days_seen": lookback, "stopped": "lookback"}


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
        return {"status": "error", "message": _http_why(status, text if status == 0 else ""), "records": []}
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


# 기상청 단기예보 코드값(공공데이터포털 「기상청_단기예보 조회서비스」 문서의 코드표 — 원천의 사실이지 지식이 아니다) → 사람 말
SKY_SAID = {"1": "맑음", "3": "구름많음", "4": "흐림"}
PTY_SAID = {"0": "", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기", "5": "빗방울", "6": "빗방울/눈날림", "7": "눈날림"}


def parse_vilage(payload: dict[str, Any], nx: int, ny: int, fetched_at: str | None = None) -> list[dict[str, Any]]:
    """응답 JSON → 날짜별 요약 레코드(TMX·TMN·POP 최대·PCP 합·TMP 시간대) + **3시간 줄**(`hours`). 판단 없음.

    [발행자 2026-09-29 17시 *"단기예보는 격자형예보로 3시간 단위로 예보를 사용자에게 알려 줘야 한다"*] 원천이 3시간 단위인데 하루로 접어 냈다 —
    시각마다 기온 · 하늘 · 강수형태 · 비 확률 · 강수량 · 바람을 그대로 싣는다(코드는 원천 코드표로 말만 바꾼다 · 값은 그대로)."""
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
        rec = days.setdefault(d, {"tmax": None, "tmin": None, "pop_max": None, "rain_mm": 0.0, "tmp": {}, "sky": {}, "pty": {}, "pop": {}, "pcp": {}, "wsd": {}})
        cat, val, t = it.get("category"), str(it.get("fcstValue", "")), it.get("fcstTime", "")
        # [코드 평가 C10] 값이 숫자가 아니면(빈 문자열 · '-') 그 항목만 결측(None) — float() 이 그날 예보 전부를 죽이지 않게
        fv = _float_or_none(val)
        if cat == "TMX":
            rec["tmax"] = fv
        elif cat == "TMN":
            rec["tmin"] = fv
        elif cat == "POP":
            if fv is not None:
                rec["pop_max"] = max(rec["pop_max"] or 0, int(fv))
                rec["pop"][t] = int(fv)
        elif cat == "PCP":
            mm = _pcp_mm(val)
            if mm is not None and rec["rain_mm"] is not None:
                rec["rain_mm"] += mm
            if mm is not None:
                rec["pcp"][t] = mm
        elif cat == "TMP":
            if fv is not None:
                rec["tmp"][t] = fv
        elif cat == "SKY":
            rec["sky"][t] = val
        elif cat == "PTY":
            rec["pty"][t] = val
        elif cat == "WSD":
            if fv is not None:
                rec["wsd"][t] = fv
    out = []
    for d in sorted(days):
        r = days[d]
        if r["tmax"] is None and r["tmp"]:
            r["tmax_from_tmp"] = max(r["tmp"].values())     # TMX 가 없는 날(발표 시각 뒤)은 시간대 최고로 — 표기 구분
        if r["tmin"] is None and r["tmp"]:
            r["tmin_from_tmp"] = min(r["tmp"].values())
        times = sorted(set(r["tmp"]) | set(r["sky"]) | set(r["pty"]) | set(r["pop"]) | set(r["pcp"]) | set(r["wsd"]))
        hours = [{"t": t, "tmp": r["tmp"].get(t), "sky": SKY_SAID.get(r["sky"].get(t, ""), r["sky"].get(t) or None),
                  "pty": PTY_SAID.get(r["pty"].get(t, ""), r["pty"].get(t) or None) or None,
                  "pop": r["pop"].get(t), "pcp": r["pcp"].get(t), "wsd": r["wsd"].get(t)} for t in times]
        out.append({
            "kind": "forecast.weather_daily", "axis": ["forecast"],
            "observed_at": f"{base_date[:4]}-{base_date[4:6]}-{base_date[6:]}T{base_time[:2]}:{base_time[2:]}:00+09:00" if base_date else None,
            "for_day": f"{d[:4]}-{d[4:6]}-{d[6:]}", "fetched_at": fetched_at,
            "source": SRC_FCST, "resolution": f"grid5km:{nx},{ny}",
            "values": {k: v for k, v in r.items() if k not in ("tmp", "sky", "pty", "pop", "pcp", "wsd")},
            "hourly_tmp": r["tmp"], "sky": r["sky"], "pty": r["pty"], "hours": hours,      # hours: 3시간 줄(원천 시각 그대로 · 코드는 말로)
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
        return {"status": "error", "message": _http_why(status, text if status == 0 else ""), "records": []}
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


# ── ④ 중기예보 MidFcstInfoService (D-21 중기 · VELA 인용: weather_service._get_mid_fcst_tmfc · weather_analyzer.normalize_mid_term ·
#      resolve_reg_id · nwp_graphic_service._resolve_reg_id 좌표→최근접 지점명→권역) ─────────────────────────────────────────
# 중기예보는 격자가 아니라 **권역(regId)** 단위다 — 육상(getMidLandFcst · 광역)과 기온(getMidTa · 시군)이 코드가 다르다.
# 좌표만 있는 재배 단위는 최근접 관측 지점 이름으로 권역표를 찾는다(VELA 의 스냅 처리). 표에 없으면 '권역 미해소' — 수도권 등으로 대체하지 않는다.
MID_BASE = os.environ.get("AGRODSS_KMA_MID_BASE", "https://apis.data.go.kr/1360000/MidFcstInfoService")
MID_REGIONS_PATH = ROOT / "data" / "kma" / "mid_regions.json"
SRC_MID = "external:kma_midfcst"
MID_DAYS = tuple(range(3, 11))          # D+3 ~ D+10 (발표일 기준)
_MID_SNAP_STATIONS = 40                 # 권역 이름을 찾기 위해 보는 최근접 지점 수(이름이 권역표에 있는 것을 만날 때까지)
_ADMIN_SUFFIX = ("특별시", "광역시", "특별자치시", "특별자치도", "도", "시", "군", "구")


def mid_tmfc(now: datetime) -> str:
    """중기예보 발표 시각(06 · 18시) 중 now−30분 이전의 최신 — YYYYMMDDHHMM. 없으면 전날 18시."""
    cand = now - timedelta(minutes=30)
    avail = [h for h in (6, 18) if h <= cand.hour]
    if avail:
        return cand.strftime("%Y%m%d") + f"{max(avail):02d}00"
    cand -= timedelta(days=1)
    return cand.strftime("%Y%m%d") + "1800"


@lru_cache(maxsize=1)
def mid_regions() -> dict[str, dict[str, str]]:
    if not MID_REGIONS_PATH.exists():
        return {}
    return json.loads(MID_REGIONS_PATH.read_text(encoding="utf-8")).get("regions", {})


def region_by_name(name: str) -> tuple[str, dict[str, str]] | None:
    """지점·행정 이름 → (권역 이름, 코드). 괄호 꼬리를 떼고 · 그대로 · 행정 접미사를 뗀 것 · 접미사 앞 토큰 순(VELA resolve_reg_id 인용)."""
    table = mid_regions()
    if not name or not table:
        return None
    clean = name.split("(")[0].strip()
    if clean in table:
        return clean, table[clean]
    for suf in _ADMIN_SUFFIX:
        if clean.endswith(suf) and clean[:-len(suf)] in table:
            return clean[:-len(suf)], table[clean[:-len(suf)]]
    for tok in clean.split():
        for suf in _ADMIN_SUFFIX:
            if tok.endswith(suf) and tok[:-len(suf)] in table:
                return tok[:-len(suf)], table[tok[:-len(suf)]]
    return None


def resolve_mid_region(lat: float, lon: float) -> dict[str, Any] | None:
    """좌표 → 최근접 지점들의 이름으로 권역을 찾는다. {name, land, ta, stn_id, via, dist_km} — 못 찾으면 None(대체 없음)."""
    near = sorted(stations(), key=lambda s: haversine_km(lat, lon, s["lat"], s["lon"]))[:_MID_SNAP_STATIONS]
    for s in near:
        hit = region_by_name(s.get("name") or "")
        if hit:
            name, codes = hit
            return {"name": name, "land": codes["land"], "ta": codes["ta"], "stn_id": codes.get("stn_id"),
                    "ta_from": codes.get("ta_from"),                     # [발행자 2026-09-29 "이 날씨는 어느 지점을 말하는가"] 기온 코드를 빌린 곳(괴산 → 충주) — 표기에 싣는다
                    "via": s["name"], "dist_km": round(haversine_km(lat, lon, s["lat"], s["lon"]), 1)}
    return None


def _mid_item(payload: dict[str, Any] | None) -> dict[str, Any]:
    try:
        items = payload["response"]["body"]["items"]["item"]
    except (KeyError, TypeError):
        return {}
    if isinstance(items, list):
        return items[0] if items else {}
    return items or {}


def _int_or_none(s: Any) -> int | None:
    f = _float_or_none(s)
    return None if f is None else int(f)


def parse_mid(land: dict[str, Any] | None, ta: dict[str, Any] | None, tmfc: str, region: dict[str, Any],
              fetched_at: str | None = None) -> list[dict[str, Any]]:
    """육상(rnSt·wf) + 기온(taMin·taMax) 원문 → 날짜별 레코드. D+3~D+7 은 오전·오후, D+8~ 는 하루 하나. 판단 없음 · 값은 그대로."""
    fetched_at = fetched_at or _now_iso()
    if not tmfc or len(tmfc) < 12 or not tmfc[:12].isdigit():
        return []
    base = date(int(tmfc[:4]), int(tmfc[4:6]), int(tmfc[6:8]))
    issued = f"{tmfc[:4]}-{tmfc[4:6]}-{tmfc[6:8]}T{tmfc[8:10]}:{tmfc[10:12]}:00+09:00"
    land, ta = land or {}, ta or {}
    out: list[dict[str, Any]] = []
    for d in MID_DAYS:
        rec: dict[str, Any] = {
            "kind": "forecast.weather_mid", "axis": ["forecast"], "observed_at": issued, "fetched_at": fetched_at,
            "for_day": (base + timedelta(days=d)).isoformat(), "source": SRC_MID,
            "resolution": f"region:{region.get('land')}/{region.get('ta')}", "region": region.get("name"),
            "values": {"tmin": _float_or_none(ta.get(f"taMin{d}")), "tmax": _float_or_none(ta.get(f"taMax{d}")), "pop_max": None},
        }
        if region.get("ta_from"):
            rec["ta_region"] = region["ta_from"]                      # 기온은 이 권역 코드로 받았다 — 사실 인용이 "기온은 충주 기준" 이라 말한다
        pops: list[int] = []
        if d <= 7:
            for half in ("Am", "Pm"):
                p, w = _int_or_none(land.get(f"rnSt{d}{half}")), (land.get(f"wf{d}{half}") or None)
                rec[half.lower()] = {"pop": p, "sky": w}
                if p is not None:
                    pops.append(p)
        else:
            p, w = _int_or_none(land.get(f"rnSt{d}")), (land.get(f"wf{d}") or None)
            rec["allday"] = {"pop": p, "sky": w}
            if p is not None:
                pops.append(p)
        rec["values"]["pop_max"] = max(pops) if pops else None
        if rec["values"]["tmin"] is None and rec["values"]["tmax"] is None and not pops:
            continue                                                    # 그날 값이 하나도 없으면 줄을 만들지 않는다(빈 줄은 '예보 있음'으로 읽힌다)
        out.append(rec)
    return out


def fetch_mid(lat: float, lon: float, now: datetime | None = None) -> dict[str, Any]:
    key = fcst_key()
    if not key:
        return {"status": "error", "message": "중기예보 키 없음 (KMA_FORECAST_API_KEY 또는 DATA_GO_KR_API_KEY — 단기와 같은 키)", "records": []}
    region = resolve_mid_region(lat, lon)
    if not region:
        return {"status": "no_region", "message": f"좌표의 권역을 못 찾았다 — data/kma/mid_regions.json 에 최근접 {_MID_SNAP_STATIONS}개 지점 이름이 없다", "records": []}
    tmfc = mid_tmfc(now or datetime.now())
    common = {"serviceKey": key, "pageNo": 1, "numOfRows": 10, "dataType": "JSON", "tmFc": tmfc}
    st_l, txt_l = _get_text(f"{MID_BASE}/getMidLandFcst", {**common, "regId": region["land"]}, encoding="utf-8")
    st_t, txt_t = _get_text(f"{MID_BASE}/getMidTa", {**common, "regId": region["ta"]}, encoding="utf-8")
    if st_l != 200 and st_t != 200:
        return {"status": "error", "message": f"육상 {_http_why(st_l, txt_l if st_l == 0 else '')} · 기온 {_http_why(st_t, txt_t if st_t == 0 else '')}", "records": []}
    try:
        land = _mid_item(json.loads(txt_l)) if st_l == 200 else {}
        ta = _mid_item(json.loads(txt_t)) if st_t == 200 else {}
    except ValueError:
        return {"status": "error", "message": "JSON 아님", "records": []}
    recs = parse_mid(land, ta, tmfc, region)
    return {"status": "success" if recs else "no_data", "region": region, "tmfc": tmfc, "records": recs,
            "partial": " · ".join(f"{side} {_http_why(st, txt if st == 0 else '')}" for side, st, txt in (("육상", st_l, txt_l), ("기온", st_t, txt_t)) if st != 200) or None}
