# -*- coding: utf-8 -*-
# [M-15 ⑥ 시비량 처방 정본] 흙토람 FrtlzrUse(필지 처방) · FrtlzrStdUse(작물 표준) — 파싱 · 코드 네임스페이스 분리 · 저장소 격리 ·
#        수집 파이프라인(주입) · 결정 소비(밑거름 판단함 / 웃거름 양) · 처방 없으면 지식 미비 그대로 · 표준값은 처방으로 안 쓴다.
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from ingest import fertilizer as fz, media, parcels, soil_exam, soil_store
from judge import run as judge_run, stage_decisions as SD
from schema import records as sch

_RAW = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
SUBJ = parcels.enrich_subject(_RAW, parcels.by_id("p001"))
PNU = "4376038025100500000"

USE_XML = """<?xml version="1.0" encoding="UTF-8"?><response><header><result_Code>200</result_Code><result_Msg>OK</result_Msg></header>
<body><items><item><pnu_Code>4376038025100500000</pnu_Code><crop_Code>07027</crop_Code><crop_Nm>쪽파</crop_Nm>
<pre_Fert_N>8.4</pre_Fert_N><pre_Fert_P>4.1</pre_Fert_P><pre_Fert_K>6.2</pre_Fert_K>
<post_Fert_N>7.6</post_Fert_N><post_Fert_P>0</post_Fert_P><post_Fert_K>5.5</post_Fert_K>
<pre_Compost_Cattl>1800</pre_Compost_Cattl><pre_Compost_Pig>1200</pre_Compost_Pig><pre_Compost_Chick>900</pre_Compost_Chick><pre_Compost_Mix>1500</pre_Compost_Mix>
</item></items></body></response>"""
STD_XML = """<response><header><result_Code>200</result_Code></header><body><items><item><fstd_Crop_Code>07014</fstd_Crop_Code>
<fstd_Crop_Nm>쪽파(노지재배)</fstd_Crop_Nm><pre_Fert_N>12.0</pre_Fert_N><pre_Fert_P>7.0</pre_Fert_P><pre_Fert_K>8.0</pre_Fert_K>
<post_Fert_N>9.0</post_Fert_N><post_Fert_P>0</post_Fert_P><post_Fert_K>6.0</post_Fert_K></item></items></body></response>"""
NO_DATA_XML = """<response><header><result_Code>301</result_Code><result_Msg>NODATA</result_Msg></header></response>"""


@pytest.fixture(autouse=True)
def _soil_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AGRODSS_SOIL_DIR", str(tmp_path / "soil"))
    assert soil_store.soil_dir().resolve() != (soil_store.ROOT / "data" / "soil").resolve()


# ── 코드 · 파싱 ────────────────────────────────────────────────────────────────
def test_crop_codes_are_separate_namespaces():
    assert fz.crop_code("쪽파", "FrtlzrUse", "노지") == "07027" and fz.crop_code("쪽파", "FrtlzrStdUse", "노지") == "07014"
    assert fz.crop_code("쪽파", "FrtlzrUse", "시설") == "07035" and fz.crop_code("쪽파", "FrtlzrStdUse", "시설") == "07015"
    assert fz.crop_code("쪽파", "FrtlzrUse", "노지") != fz.crop_code("쪽파", "FrtlzrStdUse", "노지")   # 혼용 금지의 실체
    with pytest.raises(fz.CodeError, match="미등록"):
        fz.crop_code("배추", "FrtlzrUse", "노지")


def test_environment_is_asked_not_defaulted():
    # [코드 평가 C2] 재배환경 미상이면 노지(07027)로 메워 시설 필지에 노지 처방이 정본 저장소에 들어갔다 — 이제 되묻는다
    assert not hasattr(fz, "DEFAULT_ENV")
    with pytest.raises(fz.CodeError, match="재배환경 미상"):
        fz.crop_code("쪽파", "FrtlzrUse")
    with pytest.raises(fz.CodeError, match="어휘 밖"):
        fz.crop_code("쪽파", "FrtlzrUse", "하우스")
    # 수집 경로: 환경 없이 부르면 처방·표준은 no_code(되묻는 문장)이고 **저장되지 않는다**, 검정값은 그대로 저장된다
    soil = {"kind": "observation.soil_exam", "status": "success", "pnu": "4376038025100500000", "axis": "soil_chem", "source": "external:soil_exam",
            "resolution": "parcel", "observed_at": "2026-03-01", "fetched_at": "2026-09-19T00:00:00", "values": {"ph": 6.1}, "units": {}}
    res = fz.collect_for_parcel("p001", "x", "쪽파", None, geocode=lambda a: {"pnu": "4376038025100500000"}, fetch_soil=lambda pnu: soil,
                                fetch_use=lambda pnu, code: {"status": "success", "values": {"n": 1}}, fetch_std=lambda code: {"status": "success"})
    assert res["prescription"]["status"] == "no_code" and "재배환경 미상" in res["prescription"]["message"]
    assert res["standard"]["status"] == "no_code" and len(res["saved"]) == 1


def test_parse_prescription_and_standard_and_no_data():
    p = fz.parse_prescription_xml(USE_XML, PNU, "07027", fetched_at="2026-09-19T01:00:00+00:00")
    assert p["status"] == "success" and p["values"]["pre_n"] == 8.4 and p["values"]["compost_cattle"] == 1800 and p["units"]["pre_n"] == "kg/10a"
    assert p["resolution"] == "parcel" and p["source"].startswith("external:") and p["crop_name"] == "쪽파" and p["observed_at"] == "2026-09-19"
    sch.validate(p)
    s = fz.parse_standard_xml(STD_XML, "07014")
    assert s["status"] == "success" and s["resolution"] == "national" and s["values"]["pre_n"] == 12.0 and sch.validate(s)
    n = fz.parse_prescription_xml(NO_DATA_XML, PNU, "07027")
    assert n["status"] == "no_data" and n["values"] == {} and "301" in n["message"] and sch.validate(n)
    e = fz.parse_prescription_xml("<not xml", PNU, "07027")
    assert e["status"] == "error" and "파싱" in e["message"]


def test_fetch_without_key_is_unavailable_not_fabricated(monkeypatch):
    for k in ("AGRODSS_FERTILIZER_API_KEY", "FERTILIZER_API_KEY", "EXTERNAL_API__FERTILIZER_API_KEY", "DATA_GO_KR_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    r = fz.fetch_prescription(PNU, "07027")
    assert r["status"] == "unavailable" and r["values"] == {}


# ── 저장소 ────────────────────────────────────────────────────────────────────
def test_store_saves_only_validated_and_keeps_previous():
    p = fz.parse_prescription_xml(USE_XML, PNU, "07027")
    path = soil_store.save(p, "p001", "07027")
    assert path.name == "p001_prescription_07027.json" and soil_store.latest("reference.fertilizer_prescription", "p001", "07027")["values"]["pre_n"] == 8.4
    soil_store.save(p, "p001", "07027")
    assert (path.parent / "p001_prescription_07027.prev.json").exists()
    assert [x["crop_code"] for x in soil_store.prescriptions_for("p001")] == ["07027"]
    with pytest.raises(sch.SchemaError):
        soil_store.save({**p, "stock": 1}, "p001", "07027")


def test_collect_pipeline_with_injected_fetchers():
    soil = soil_exam.SoilExamRecord(status="success", pnu=PNU, observed_at="2026-04-10", fetched_at="x", values={"ph": 6.1, "organic_matter": 21.0})
    res = fz.collect_for_parcel("p001", "<지번 주소>", "쪽파", "노지",
                                geocode=lambda a: {"lat": 36.8, "lon": 128.0, "pnu": PNU},
                                fetch_soil=lambda pnu: soil,
                                fetch_use=lambda pnu, code: fz.parse_prescription_xml(USE_XML, pnu, code),
                                fetch_std=lambda code: fz.parse_standard_xml(STD_XML, code))
    assert res["pnu"] == PNU and len(res["saved"]) == 3
    assert soil_store.latest("observation.soil_exam", "p001")["values"]["ph"] == 6.1
    assert soil_store.latest("reference.fertilizer_standard", None, "07014")["values"]["pre_n"] == 12.0
    res2 = fz.collect_for_parcel("p001", "x", "쪽파", geocode=lambda a: None)
    assert res2["pnu"] is None and "PNU" in res2["message"] and res2["saved"] == []
    res3 = fz.collect_for_parcel("p001", "x", "쪽파", "노지", geocode=lambda a: {"pnu": PNU}, fetch_soil=lambda pnu: soil,
                                 fetch_use=lambda pnu, code: fz.parse_prescription_xml(NO_DATA_XML, pnu, code),
                                 fetch_std=lambda code: fz.parse_standard_xml(NO_DATA_XML, code))
    assert res3["prescription"]["status"] == "no_data" and len(res3["saved"]) == 1            # 실패는 정본으로 안 남긴다


# ── 결정 소비 ───────────────────────────────────────────────────────────────────
def _pres():
    return [fz.parse_prescription_xml(USE_XML, PNU, "07027", fetched_at="2026-09-01T00:00:00+00:00")]


def test_base_fertilization_becomes_judged_with_prescription():
    t = date(2026, 8, 30)
    s = {**SUBJ, "soil_chem": {"ph": 6.1}}
    e = SD.judge_base_fertilization(s, t, prescriptions=None)
    assert e.kind == "판단 불가(지식)"
    e = SD.judge_base_fertilization(s, t, prescriptions=_pres())
    assert e.kind == "판단함" and e.grade == "추정" and "N 8.4kg/10a" in e.result["pre"] and e.result["compost_kg_10a"]["compost_cattle"] == 1800
    assert any(i.axis == "soil_chem" and i.source == fz.SOURCE_USE for i in e.inputs) and any("목표 양분량" in n for n in e.notes)
    std = fz.parse_standard_xml(STD_XML, "07014")
    assert SD.judge_base_fertilization(s, t, prescriptions=[std]).kind == "판단 불가(지식)"          # 표준값은 필지 처방이 아니다
    e = SD.judge_base_fertilization(SUBJ, t, prescriptions=_pres())
    assert e.kind == "판단 불가(데이터)"                                                            # 검정값 없이는 처방이 있어도 안 낸다


def test_top_dressing_amount_from_prescription():
    e = SD.judge_top_dressing(SUBJ, "top_dressing_1", date(2026, 9, 19), evts=[], prescriptions=_pres())
    assert "N 7.6kg/10a" in e.result["amount"] and "K₂O 5.5" in e.result["amount"] and "지식" not in e.result["amount"]
    e = SD.judge_top_dressing(SUBJ, "top_dressing_1", date(2026, 9, 19), evts=[], prescriptions=None)
    assert "지식" in e.result["amount"]


def test_run_wires_store_into_subject_and_decisions():
    soil = soil_exam.SoilExamRecord(status="success", pnu=PNU, observed_at="2026-04-10", fetched_at="x", values={"ph": 6.1}).to_dict()
    soil_store.save(soil, "p001")
    soil_store.save(_pres()[0], "p001", "07027")
    envs = {e.decision_id: e for e in judge_run.judgments_for("p001-jjokpa-2026f", today=date(2026, 8, 30))}
    assert envs["base_fertilization"].kind == "판단함"
    assert envs["top_dressing_1"].kind == "해당 없음" or "N 7.6" in envs["top_dressing_1"].result.get("amount", "")
    for e in envs.values():
        assert "6.1" not in str(e.to_dict().get("inputs"))                                        # 값은 봉투에 안 실린다(이름만)
