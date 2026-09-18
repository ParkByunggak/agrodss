# -*- coding: utf-8 -*-
# [D-9 · I-2 · I-6] 흙토람 토양검정 인용 클라이언트 — 네트워크 없이 순수 함수와 파싱을 본다.
# 거부: 관측 시각 없는 값은 1층에 못 들어간다 · 미검정은 no_data(대리값 없음).
# 통과: 정상 응답이 3요건(observed_at · source · resolution=parcel)을 갖춘 레코드가 된다.
from __future__ import annotations

import pytest

from ingest import config, soil_exam

SAMPLE_OK = """<?xml version="1.0" encoding="UTF-8"?>
<response><header><Result_Code>200</Result_Code><Result_Msg>OK</Result_Msg></header>
<body><items><item>
<Any_Year>2026</Any_Year><Exam_Day>20260410</Exam_Day><Pnu_Nm>충청북도 괴산군 연풍면 갈금리 50</Pnu_Nm>
<ACID>6.3</ACID><OM>28</OM><VLDPHA>412</VLDPHA><POSIFERT_K>0.85</POSIFERT_K>
<POSIFERT_CA>6.1</POSIFERT_CA><POSIFERT_MG>1.9</POSIFERT_MG><ELCD>0.7</ELCD>
</item></items></body></response>"""

SAMPLE_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<response><header><Result_Code>200</Result_Code><Result_Msg>OK</Result_Msg></header>
<body><items/></body></response>"""

SAMPLE_NO_DAY = SAMPLE_OK.replace("<Exam_Day>20260410</Exam_Day>", "")
SAMPLE_ERR = SAMPLE_OK.replace("<Result_Code>200</Result_Code>", "<Result_Code>30</Result_Code>")


# ── PNU 조합 (VELA 인용 순수 함수) ─────────────────────────────────────────────
@pytest.mark.parametrize("level5,expected", [
    ("50", (50, 0, False)), ("50-3", (50, 3, False)), ("산78임", (78, 0, True)), ("", (0, 0, False)),
])
def test_parse_level5(level5, expected):
    assert soil_exam.parse_level5(level5) == expected


def test_build_pnu_from_10_digit_code():
    assert soil_exam.build_pnu("4376038025", "50") == "4376038025" + "0" + "0050" + "0000"
    assert soil_exam.build_pnu("4376038025", "50-3") == "4376038025000500003"


def test_build_pnu_passthrough_19_and_reject_other():
    assert soil_exam.build_pnu("4376038025000500000", "무시") == "4376038025000500000"
    assert soil_exam.build_pnu("", "50") is None
    assert soil_exam.build_pnu("12345", "50") is None


# ── 파싱: 통과 ──────────────────────────────────────────────────────────────────
def test_parse_success_has_three_requirements():
    rec = soil_exam.parse_soil_exam_xml(SAMPLE_OK, "4376038025000500000", fetched_at="2026-09-18T00:00:00+00:00")
    assert rec.status == "success"
    assert rec.observed_at == "20260410"          # 관측 시각 = 검정일
    assert rec.source == "external:heuktoram_soilexam"
    assert rec.resolution == "parcel"
    assert rec.axis == "soil_chem"
    assert rec.values["ph"] == 6.3 and rec.values["organic_matter"] == 28.0
    assert rec.units["phosphorus"] == "mg/kg" and "ph" not in rec.units


# ── 파싱: 거부 ──────────────────────────────────────────────────────────────────
def test_parse_empty_is_no_data_not_fabricated():
    rec = soil_exam.parse_soil_exam_xml(SAMPLE_EMPTY, "x")
    assert rec.status == "no_data"
    assert rec.values == {}


def test_parse_without_exam_day_is_rejected():
    rec = soil_exam.parse_soil_exam_xml(SAMPLE_NO_DAY, "x")
    assert rec.status == "error"
    assert "검정일" in (rec.message or "")


def test_parse_source_error_code():
    rec = soil_exam.parse_soil_exam_xml(SAMPLE_ERR, "x")
    assert rec.status == "error" and "30" in rec.message


def test_parse_garbage_is_error():
    assert soil_exam.parse_soil_exam_xml("not xml", "x").status == "error"


# ── 지오코딩 응답 파싱 ─────────────────────────────────────────────────────────
def test_parse_geocode_builds_pnu():
    data = {"response": {"status": "OK", "result": {"point": {"x": "127.9", "y": "36.7"}},
                         "refined": {"structure": {"level4LC": "4376038025", "level5": "50"}}}}
    g = soil_exam.parse_geocode_json(data)
    assert g["pnu"] == "4376038025000500000" and g["lat"] == 36.7


def test_parse_geocode_not_ok_is_none():
    assert soil_exam.parse_geocode_json({"response": {"status": "NOT_FOUND"}}) is None


# ── 키 없음: 조용히 대리값을 만들지 않는다 ───────────────────────────────────────
def test_fetch_without_key_is_error(monkeypatch):
    for n in ("AGRODSS_SOIL_EXAM_API_KEY", "SOIL_API_KEY", "EXTERNAL_API__SOIL_API_KEY"):
        monkeypatch.delenv(n, raising=False)
    rec = soil_exam.fetch_soil_exam("4376038025000500000")
    assert rec.status == "error" and "키" in rec.message


def test_key_names_accept_vela_env(monkeypatch):
    monkeypatch.delenv("AGRODSS_SOIL_EXAM_API_KEY", raising=False)
    monkeypatch.setenv("SOIL_API_KEY", "x")
    assert config.soil_exam_key() == "x"
