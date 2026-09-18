# -*- coding: utf-8 -*-
# [M-15 ③] NCPMS 예찰 인용 — 네트워크 없이 파서·코드 대리·키 없음. 필드명은 미확정(raw 보존)을 검사로 못 박는다.
from __future__ import annotations

from ingest import ncpms

XML = """<?xml version="1.0" encoding="UTF-8"?>
<service><totalCount>2</totalCount><list>
<item><kncrNm>파</kncrNm><dbyhsNm>고자리파리</dbyhsNm><sidoNm>충청북도</sidoNm><examinDay>20260915</examinDay><occrrncLevel>주의</occrrncLevel><examinCn>발생 증가</examinCn></item>
<item><kncrNm>파</kncrNm><dbyhsNm>파노균병</dbyhsNm><sidoNm>충청북도</sidoNm><examinDay>20260915</examinDay></item>
</list></service>"""


def test_crop_code_proxy_for_jjokpa():
    code, crop, why = ncpms.crop_code_for("쪽파")
    assert code == "VC041202" and crop == "파" and "미확정" in why
    assert ncpms.crop_code_for("파")[2] == ""
    assert ncpms.crop_code_for("들깨")[0] is None


def test_parse_xml_records_shape_and_proxy_resolution():
    recs = ncpms.parse_forecast(XML, "쪽파", fetched_at="x")
    assert len(recs) == 2
    r = recs[0]
    assert r["kind"] == "observation.pest_forecast" and r["axis"] == ["pest_regional"] and r["source"] == ncpms.SOURCE
    assert r["observed_at"] == "20260915" and r["resolution"] == "region:충청북도|proxy_crop:파"
    assert r["values"]["pest"] == "고자리파리" and r["values"]["level"] == "주의" and r["values"]["text"] == "발생 증가"
    assert r["schema_confirmed"] is False and r["raw"]["dbyhsNm"] == "고자리파리"   # 필드 미확정 — 원문 보존


def test_parse_missing_fields_are_none_not_guessed():
    r = ncpms.parse_forecast(XML, "쪽파")[1]
    assert r["values"]["level"] is None and r["values"]["text"] is None


def test_parse_json_variant_and_garbage():
    js = '{"service":{"list":{"item":[{"kncrNm":"파","dbyhsNm":"파총채벌레","examinYear":"2026"}]}}}'
    r = ncpms.parse_forecast(js, "파")[0]
    assert r["observed_at"] == "2026" and r["resolution"] == "region:전국" and r["proxy_reason"] is None
    assert ncpms.parse_forecast("garbage", "파") == [] and ncpms.parse_forecast("", "파") == []


def test_fetch_without_key_or_code(monkeypatch):
    monkeypatch.delenv("AGRODSS_NCPMS_API_KEY", raising=False)
    monkeypatch.delenv("NCPMS_API_KEY", raising=False)
    assert ncpms.fetch_forecast("쪽파")["status"] == "error"
    monkeypatch.setenv("NCPMS_API_KEY", "x")
    assert ncpms.fetch_forecast("들깨")["status"] == "no_code"
