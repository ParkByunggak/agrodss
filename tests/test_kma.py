# -*- coding: utf-8 -*-
# [M-15 ②] 기상청 인용 클라이언트 — 네트워크 없이 파서·변환·지점 매칭. 결측은 None(대리값 없음).
from __future__ import annotations

from datetime import datetime

import pytest

from ingest import kma


def _sfcdd_line(tm="20260918", stn="131", ta_avg="22.1", ta_max="27.3", ta_min="17.4", ss="6.2", rn="0.0"):
    cols = ["-9.0"] * 45
    cols[0], cols[1], cols[10], cols[11], cols[13], cols[32], cols[38] = tm, stn, ta_avg, ta_max, ta_min, ss, rn
    return " ".join(cols)


# ── ① 일자료 ────────────────────────────────────────────────────────────────────
def test_parse_daily_obs_record_shape():
    recs = kma.parse_daily_obs("# header\n" + _sfcdd_line() + " =\n", fetched_at="x")
    assert len(recs) == 1
    r = recs[0]
    assert r["observed_at"] == "2026-09-18" and r["resolution"] == "station:131" and r["source"] == kma.SRC_OBS
    assert r["values"] == {"tmax": 27.3, "tmin": 17.4, "ta_avg": 22.1, "rn_day_mm": 0.0, "ss_day_hr": 6.2}


def test_parse_daily_obs_sentinels_become_none_not_zero():
    recs = kma.parse_daily_obs(_sfcdd_line(ta_max="-99.0", rn="-9.0", ss="-9.0"))
    v = recs[0]["values"]
    assert v["tmax"] is None and v["rn_day_mm"] is None and v["ss_day_hr"] is None


def test_parse_daily_obs_drops_row_when_tmax_below_tmin():
    assert kma.parse_daily_obs(_sfcdd_line(ta_max="10.0", ta_min="20.0")) == []


def test_parse_daily_obs_discards_inconsistent_average_only():
    recs = kma.parse_daily_obs(_sfcdd_line(ta_avg="40.0"))
    assert recs[0]["values"]["ta_avg"] is None and recs[0]["values"]["tmax"] == 27.3


def test_fetch_daily_obs_without_key(monkeypatch):
    for n in ("AGRODSS_KMA_API_HUB_KEY", "KMA_API_HUB_KEY", "KMA__API_HUB_KEY", "EXTERNAL_API__KMA_API_HUB_KEY"):
        monkeypatch.delenv(n, raising=False)
    r = kma.fetch_daily_obs(131, datetime(2026, 9, 18).date())
    assert r["status"] == "error" and r["records"] == []


# ── ② 평년 ──────────────────────────────────────────────────────────────────────
def test_parse_normals():
    line = "2021,131,09,18,20.4,26.1,15.6,3.2,-9.0,1.8,70,-9,6.5,4.1,1010.2,1005.0"
    recs = kma.parse_normals("#h\n" + line, fetched_at="x")
    r = recs[0]
    assert r["for_day"] == "09-18" and r["observed_at"] == "normal:1991-2020" and r["resolution"] == "station:131"
    assert r["values"]["ta"] == 20.4 and r["values"]["rn_mm"] == 3.2 and r["values"]["ss_hr"] == 6.5
    assert r["source"] == kma.SRC_NORM


def test_parse_normals_negative_nonneg_fields_are_none():
    line = "2021,131,09,18,20.4,26.1,15.6,-9.0,-9.0,1.8,70,-9,-9.0,4.1,1010.2,1005.0"
    v = kma.parse_normals(line)[0]["values"]
    assert v["rn_mm"] is None and v["ss_hr"] is None and v["ta"] == 20.4


# ── ③ 예보 ──────────────────────────────────────────────────────────────────────
def test_latlon_to_grid_known_point():
    assert kma.latlon_to_grid(37.5665, 126.9780) == (60, 127)   # 서울 시청 — 공개 예제값


def test_vilage_base_datetime_rule():
    assert kma.vilage_base_datetime(datetime(2026, 9, 18, 6, 0)) == ("20260918", "0500")
    assert kma.vilage_base_datetime(datetime(2026, 9, 18, 5, 10)) == ("20260918", "0200")   # 40분 유예
    assert kma.vilage_base_datetime(datetime(2026, 9, 18, 1, 0)) == ("20260917", "2300")


def test_parse_vilage_daily_summary():
    items = [
        {"baseDate": "20260918", "baseTime": "0500", "fcstDate": "20260919", "fcstTime": "0600", "category": "TMN", "fcstValue": "12.0"},
        {"baseDate": "20260918", "baseTime": "0500", "fcstDate": "20260919", "fcstTime": "1500", "category": "TMX", "fcstValue": "24.0"},
        {"baseDate": "20260918", "baseTime": "0500", "fcstDate": "20260919", "fcstTime": "0900", "category": "POP", "fcstValue": "30"},
        {"baseDate": "20260918", "baseTime": "0500", "fcstDate": "20260919", "fcstTime": "1200", "category": "POP", "fcstValue": "60"},
        {"baseDate": "20260918", "baseTime": "0500", "fcstDate": "20260919", "fcstTime": "1200", "category": "PCP", "fcstValue": "1.0mm"},
        {"baseDate": "20260918", "baseTime": "0500", "fcstDate": "20260919", "fcstTime": "1500", "category": "PCP", "fcstValue": "강수없음"},
        {"baseDate": "20260918", "baseTime": "0500", "fcstDate": "20260919", "fcstTime": "1200", "category": "TMP", "fcstValue": "22"},
        {"baseDate": "20260918", "baseTime": "0500", "fcstDate": "20260920", "fcstTime": "0600", "category": "TMP", "fcstValue": "11"},
    ]
    recs = kma.parse_vilage({"response": {"body": {"items": {"item": items}}}}, 69, 107, fetched_at="x")
    assert [r["for_day"] for r in recs] == ["2026-09-19", "2026-09-20"]
    d1 = recs[0]
    assert d1["values"]["tmax"] == 24.0 and d1["values"]["tmin"] == 12.0 and d1["values"]["pop_max"] == 60 and d1["values"]["rain_mm"] == 1.0
    assert d1["resolution"] == "grid5km:69,107" and d1["source"] == kma.SRC_FCST
    assert d1["observed_at"] == "2026-09-18T05:00:00+09:00"     # 발표 시각 — 예보의 관측 시각
    d2 = recs[1]
    assert d2["values"]["tmax"] is None and d2["values"]["tmin_from_tmp"] == 11.0   # TMX/TMN 없으면 시간대값으로, 표기 구분


def test_parse_vilage_garbage_is_empty():
    assert kma.parse_vilage({"nope": 1}, 1, 1) == []


# ── 지점 ────────────────────────────────────────────────────────────────────────
def test_stations_cited_and_nearest_for_goesan():
    assert len(kma.stations()) > 1000
    s = kma.nearest_station(36.80, 127.88)        # 괴산 연풍 부근(근사 — I-6 좌표 도착 전)
    assert s and s["dist_km"] < 60


def test_nearest_station_respects_allowed_ids():
    s = kma.nearest_station(36.80, 127.88, allowed_ids=frozenset({131}))   # 청주만 허용
    assert s and s["id"] == 131
    assert kma.nearest_station(36.80, 127.88, allowed_ids=frozenset()) is None
