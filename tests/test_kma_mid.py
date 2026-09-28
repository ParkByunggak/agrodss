# -*- coding: utf-8 -*-
# [D-21 중기 2026-09-28] 기상청 중기예보 원천 — VELA 인용(D-9). 계약: 발표 시각 규칙(06·18시 −30분) · 좌표→권역(최근접 지점 이름 → 표 · 대체 없음) ·
# 원문(rnSt·wf·taMin·taMax) → 레코드 그대로(오전·오후 최대 · 빈 날은 줄 없음) · 스키마 kind 가 3층 입력이라 게이트를 지난다.
from __future__ import annotations

from datetime import datetime

import pytest

from ingest import kma
from judge import boundary
from schema import records as sch

REGION = {"name": "괴산", "land": "11C10000", "ta": "11C10401", "stn_id": "131"}


def test_mid_issue_time_is_06_or_18_minus_thirty_minutes():
    assert kma.mid_tmfc(datetime(2026, 9, 28, 6, 29)) == "202609271800"     # 06:29 — 아직 06시 발표를 못 쓴다(−30분)
    assert kma.mid_tmfc(datetime(2026, 9, 28, 6, 30)) == "202609280600"
    assert kma.mid_tmfc(datetime(2026, 9, 28, 18, 29)) == "202609280600"
    assert kma.mid_tmfc(datetime(2026, 9, 28, 18, 31)) == "202609281800"
    assert kma.mid_tmfc(datetime(2026, 9, 28, 0, 10)) == "202609271800"     # 자정 넘어 — 전날 18시


def test_region_table_is_cited_from_vela_and_resolves_names_without_a_default():
    t = kma.mid_regions()
    assert t["괴산"] == {"land": "11C10000", "ta": "11C10401", "stn_id": "131", "ta_from": "충주"} and t["대전"]["ta"] == "11C20401" and len(t) >= 14
    assert kma.resolve_mid_region(36.75, 127.98)["ta_from"] == "충주"                                   # [2026-09-29 "어느 지점"] 빌린 기온 코드의 이름
    recs = kma.parse_mid({"rnSt3Am": "10"}, None, "202609280600", dict(REGION, ta_from="충주"))
    assert recs[0]["ta_region"] == "충주" and "ta_region" not in kma.parse_mid({"rnSt3Am": "10"}, None, "202609280600", REGION)[0]
    from judge import boundary
    boundary.gate_records(recs, "mid")                                                                   # 스키마가 그 필드를 안다
    assert kma.region_by_name("괴산") == ("괴산", t["괴산"]) and kma.region_by_name("괴산군") == ("괴산", t["괴산"])
    assert kma.region_by_name("충주(관)")[0] == "충주" and kma.region_by_name("대구광역시")[0] == "대구"   # 괄호 꼬리 · '구'로 끝나는 이름(VELA 06-13 버그)
    assert kma.region_by_name("연풍") is None and kma.region_by_name("") is None                          # 없으면 없다 — 수도권으로 대체하지 않는다
    r = kma.resolve_mid_region(36.75, 127.98)                                                              # 괴산군 부근 좌표(공개 지점 좌표 기준 · 필지 아님)
    assert r and r["land"] == "11C10000" and r["ta"] == "11C10401" and r["name"] in t and r["dist_km"] < 40
    assert kma.resolve_mid_region(37.4, 130.9) is None                                                     # 울릉 — 표에 없는 권역은 None


def _land():
    d = {}
    for i in range(3, 8):
        d[f"rnSt{i}Am"], d[f"rnSt{i}Pm"], d[f"wf{i}Am"], d[f"wf{i}Pm"] = 20, 30 + i, "구름많음", "흐리고 비" if i == 4 else "맑음"
    for i in range(8, 11):
        d[f"rnSt{i}"], d[f"wf{i}"] = 10 * (i - 7), "맑음"
    return d


def _ta():
    d = {}
    for i in range(3, 11):
        d[f"taMin{i}"], d[f"taMax{i}"] = str(5 + i), str(15 + i)
    return d


def test_parse_mid_keeps_the_source_values_and_passes_the_boundary_gate():
    recs = kma.parse_mid(_land(), _ta(), "202609271800", REGION, fetched_at="2026-09-28T05:10:00+09:00")
    assert [r["for_day"] for r in recs] == [f"2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07"]
    r3 = recs[0]
    assert r3["kind"] == "forecast.weather_mid" and r3["observed_at"] == "2026-09-27T18:00:00+09:00" and r3["region"] == "괴산"
    assert r3["resolution"] == "region:11C10000/11C10401" and r3["source"] == kma.SRC_MID and r3["axis"] == ["forecast"]
    assert r3["values"] == {"tmin": 8.0, "tmax": 18.0, "pop_max": 33} and r3["am"] == {"pop": 20, "sky": "구름많음"} and r3["pm"] == {"pop": 33, "sky": "맑음"}
    assert recs[1]["pm"]["sky"] == "흐리고 비" and recs[5]["allday"] == {"pop": 10, "sky": "맑음"} and "am" not in recs[5]     # 8일 뒤는 하루 하나
    assert recs[7]["values"] == {"tmin": 15.0, "tmax": 25.0, "pop_max": 30}
    boundary.gate_records(recs, "mid")                                                                      # 3층 입력 — 스키마 정본을 지난다
    assert "forecast.weather_mid" in sch.LAYER3_INPUT_KINDS and not sch.KINDS["forecast.weather_mid"].subject_bound


def test_parse_mid_is_honest_about_missing_halves_and_makes_no_row_from_nothing():
    land = {"rnSt3Am": "40", "wf3Am": "흐림"}                                                                # 오후 없음 · 기온 없음
    recs = kma.parse_mid(land, None, "202609280600", REGION)
    assert len(recs) == 1 and recs[0]["for_day"] == "2026-10-01"
    assert recs[0]["values"] == {"tmin": None, "tmax": None, "pop_max": 40} and recs[0]["pm"] == {"pop": None, "sky": None}
    assert kma.parse_mid({}, {}, "202609280600", REGION) == [] and kma.parse_mid(_land(), _ta(), "", REGION) == []
    bad = {"rnSt3Am": "-", "wf3Am": ""}                                                                      # 숫자 아님 · 빈 문자열 → 그 항목만 결측, 줄은 없다
    assert kma.parse_mid(bad, None, "202609280600", REGION) == []


def test_fetch_mid_reports_why_without_key_or_region(monkeypatch):
    for n in ("AGRODSS_KMA_FORECAST_API_KEY", "KMA_FORECAST_API_KEY", "EXTERNAL_API__KMA_FORECAST_API_KEY", "DATA_GO_KR_API_KEY"):
        monkeypatch.delenv(n, raising=False)
    r = kma.fetch_mid(36.75, 127.98)
    assert r["status"] == "error" and "키 없음" in r["message"] and r["records"] == []
    monkeypatch.setenv("DATA_GO_KR_API_KEY", "x")
    calls = []
    monkeypatch.setattr(kma, "_get_text", lambda url, params, encoding="euc-kr": calls.append(url) or (0, "차단(검사)"))
    r = kma.fetch_mid(37.4, 130.9)
    assert r["status"] == "no_region" and "mid_regions.json" in r["message"] and calls == []                # 권역이 없으면 원천을 부르지도 않는다
    r = kma.fetch_mid(36.75, 127.98, now=datetime(2026, 9, 28, 7, 0))
    assert r["status"] == "error" and len(calls) == 2 and calls[0].endswith("/getMidLandFcst") and calls[1].endswith("/getMidTa")
    assert r["message"] == "육상 연결 실패: 차단(검사) · 기온 연결 실패: 차단(검사)" and "HTTP 0" not in r["message"]   # 연결 실패는 HTTP 응답이 아니다


def test_a_dead_network_is_reported_as_a_connection_failure_not_http_zero(monkeypatch):
    """[D-21 실측 2026-09-28] 망이 죽으면 `_get_text` 가 (0, 오류문) 을 주는데 단기·중기·관측·평년 넷이 "HTTP 0" 이라 적었다 — 이유가 그대로
    화면까지 가는 사실 인용에서 틀린 말. 넷 다 같은 정본(`_http_why`)으로."""
    monkeypatch.setenv("DATA_GO_KR_API_KEY", "x")
    monkeypatch.setenv("KMA_API_HUB_KEY", "x")
    monkeypatch.setattr(kma, "_get_text", lambda url, params, encoding="euc-kr": (0, "<urlopen error [Errno -3] Temporary failure in name resolution>"))
    from datetime import date
    for r in (kma.fetch_vilage(36.75, 127.98, now=datetime(2026, 9, 28, 7, 0)), kma.fetch_mid(36.75, 127.98, now=datetime(2026, 9, 28, 7, 0)),
              kma.fetch_daily_obs(131, date(2026, 9, 27)), kma.fetch_normals(131, 9, 27, 9, 27)):
        assert r["status"] == "error" and "연결 실패: <urlopen error" in r["message"] and "HTTP 0" not in r["message"], r
    monkeypatch.setattr(kma, "_get_text", lambda url, params, encoding="euc-kr": (503, "<html>busy</html>"))
    r = kma.fetch_vilage(36.75, 127.98, now=datetime(2026, 9, 28, 7, 0))
    assert r["message"] == "HTTP 503"                                                                      # 진짜 HTTP 응답은 그대로 HTTP 다


@pytest.mark.parametrize("st_land, st_ta", [(200, 500), (500, 200)])
def test_fetch_mid_with_one_endpoint_down_is_partial_not_silent(monkeypatch, st_land, st_ta):
    monkeypatch.setenv("DATA_GO_KR_API_KEY", "x")
    import json

    def fake(url, params, encoding="euc-kr"):
        if url.endswith("getMidLandFcst"):
            return st_land, json.dumps({"response": {"body": {"items": {"item": [_land()]}}}})
        return st_ta, json.dumps({"response": {"body": {"items": {"item": [_ta()]}}}})

    monkeypatch.setattr(kma, "_get_text", fake)
    r = kma.fetch_mid(36.75, 127.98, now=datetime(2026, 9, 28, 7, 0))
    dead = "기온" if st_ta != 200 else "육상"
    assert r["status"] == "success" and r["tmfc"] == "202609280600" and r["partial"] == f"{dead} HTTP 500" and len(r["records"]) == 8   # 죽은 쪽만 이름을 부른다
    v = r["records"][0]["values"]
    assert (v["tmin"] is None) == (st_ta != 200) and (v["pop_max"] is None) == (st_land != 200)             # 죽은 쪽만 결측 — 산 쪽은 그대로
