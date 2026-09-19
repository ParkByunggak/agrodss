# -*- coding: utf-8 -*-
# [U-15 자재 계열↔공시 검색어 정밀도] 자재명 **성분** 부분일치(제품명은 안 본다) · BT 는 자재명 조건 위에 제품명 겹침 ·
#        실측 오탐(황금바다골드 · 루트님유박 · 나비티)이 사라진다 · 복합명사(석회유황합제 · 가축분퇴비)는 남는다 · 인용 결정 배선.
from __future__ import annotations

from datetime import date

import pytest

from ingest import media, organic_materials as om, parcels
from judge import material_citation as MC

T24 = date(2026, 9, 18)
_RAW = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
SUBJ = parcels.enrich_subject(_RAW, parcels.by_id("p001"))


def test_material_components_and_match():
    assert om.material_components("규산나트륨+황") == ["규산나트륨", "황"] and om.material_components(None) == []
    assert om.material_matches("규산나트륨+황", "황") and om.material_matches("석회유황합제", "황") and om.material_matches("가축분퇴비", "퇴비")
    assert not om.material_matches("미생물", "비티") and not om.material_matches("혼합유기질", "") and not om.material_matches(None, "황")


@pytest.mark.parametrize("kw,mtype,bad_product", [("황", om.TYPE_PEST, "황금바다골드"), ("님", om.TYPE_PEST, "루트님유박"), ("유기질", om.TYPE_SOIL, "땅살리기 유기질")])
def test_real_canon_no_product_only_false_positives(kw, mtype, bad_product):
    res = om.search(mtype, kw, limit=500, today=T24)
    assert res["status"] == "success"
    assert all(om.material_matches(i["values"]["material"], kw) for i in res["items"])
    assert all(i["values"]["product"] != bad_product for i in res["items"])
    assert res["match"] == "자재명"


def test_bt_needs_material_condition_not_product_alone(monkeypatch):
    rows = [
        {"PBLNTF_NO": "1", "MTRIL_TYPE_NM": om.TYPE_PEST, "MTRIL_NM": "미생물", "PRODUCT_NM": "순천비티제", "PBLNTF_END_DE": "20301231"},
        {"PBLNTF_NO": "2", "MTRIL_TYPE_NM": om.TYPE_PEST, "MTRIL_NM": "식물추출물", "PRODUCT_NM": "나비티", "PBLNTF_END_DE": "20301231"},   # 실측 오탐(2026-09-18)
        {"PBLNTF_NO": "3", "MTRIL_TYPE_NM": om.TYPE_PEST, "MTRIL_NM": "미생물", "PRODUCT_NM": "그린가드", "PBLNTF_END_DE": "20301231"},
    ]
    monkeypatch.setattr(om, "load", lambda: {"rows": rows, "fetched_at": "20260907"})
    res = om.search(om.TYPE_PEST, "미생물", today=T24, product_keyword="비티")
    assert [i["values"]["notice_no"] for i in res["items"]] == ["1"] and res["match"] == "자재명+제품명"
    assert om.search(om.TYPE_PEST, "비티", today=T24)["status"] == "no_data"                # 제품명만으로는 안 뽑는다
    assert om.search(om.TYPE_PEST, None, today=T24, product_keyword="비티")["total"] == 2   # 자재명 조건이 없으면 제품명 부분일치는 나비티도 문다 — 결정은 항상 자재명을 준다


def test_citation_groups_use_material_condition_and_bt_product_overlay():
    env = MC.judge(SUBJ, today=T24)
    assert env.kind == "사실 인용"
    by = {g["family"]: g for g in env.result["groups"]}
    bt = next(g for f, g in by.items() if "BT" in f)
    assert bt["keyword"] == "미생물+비티" and bt["match"] == "자재명+제품명" and bt["status"] == "success"
    assert all("미생물" in i["material"] and "비티" in i["product"] for i in bt["items"])
    for g in env.result["groups"]:
        if g["status"] == "success" and g["match"] == "자재명":
            assert all(om.material_matches(i["material"], g["keyword"]) for i in g["items"])
