# -*- coding: utf-8 -*-
# [M-15 ④] 공시자재 — 정본 검색(유효기간 재검증 · 유형 · 키워드 · no_data) · 재수집(급감 가드 · 키 없음) ·
# 첫 '사실 인용' 결정(유기만 · 관행은 해당 없음 · 인용에 출처·시각 동반).
from __future__ import annotations

import json
from datetime import date

import pytest

from ingest import media
from ingest import organic_materials as om
from judge import material_citation as MC

SUBJ = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
T24 = date(2026, 9, 18)


# ── 정본 검색 ─────────────────────────────────────────────────────────────────────
def test_canon_cited_and_types():
    canon = om.load()
    assert len(canon["rows"]) > 1000 and canon["fetched_at"] == "20260907"
    assert set(om.material_types()) == {om.TYPE_PEST, om.TYPE_SOIL}
    assert all(set(r) <= set(om.KEEP) for r in canon["rows"][:50])          # 열 10개로 줄여 인용(주소 등 없음)


def test_search_keyword_and_type_and_record_shape():
    res = om.search(om.TYPE_PEST, "비티", limit=3, today=T24)
    assert res["status"] == "success" and 1 <= len(res["items"]) <= 3 and res["total"] >= len(res["items"])
    it = res["items"][0]
    assert it["kind"] == "reference.organic_material_notice" and it["source"] == om.SOURCE
    assert it["observed_at"] == "2026-09-07" and it["resolution"] == "national"
    assert it["values"]["type"] == om.TYPE_PEST and "비티" in (it["values"]["material"] + it["values"]["product"])


def test_search_expired_rows_are_dropped_at_query_time():
    assert om.search(om.TYPE_PEST, "비티", today=date(2040, 1, 1))["status"] == "no_data"


def test_search_unknown_keyword_is_no_data_not_category():
    res = om.search(None, "존재하지않는자재명XYZ", today=T24)
    assert res["status"] == "no_data" and res["items"] == []


# ── 재수집 ──────────────────────────────────────────────────────────────────────────
def _page_factory(rows):
    def page(key, start, end):
        chunk = rows[start - 1:end]
        return {om.GRID_ID: {"result": {"code": "INFO-000"}, "totalCnt": len(rows), "row": chunk}}
    return page


def test_run_collection_without_key(monkeypatch):
    for n in ("AGRODSS_ORGANIC_MATERIAL_API_KEY", "ORGANIC_MATERIAL_API_KEY", "DATA_GO_KR_API_KEY"):
        monkeypatch.delenv(n, raising=False)
    assert om.run_collection(page=_page_factory([]))["status"] == "no_key"


def test_run_collection_replaces_and_guards_drop(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_GO_KR_API_KEY", "x")
    path = tmp_path / "om.json"
    monkeypatch.setattr(om, "DATA_PATH", path)
    mk = lambda i, end="20991231": {"PBLNTF_ID": f"ID{i}", "PBLNTF_NO": f"공시-{i}", "MTRIL_TYPE_NM": om.TYPE_PEST,
                                   "MTRIL_NM": "미생물", "PRODUCT_NM": f"제품{i}", "PBLNTF_END_DE": end, "CEO_NM": "개인정보보호"}
    rows = [mk(i) for i in range(10)] + [mk(99, end="20000101")]            # 1건 만료
    r = om.run_collection(page=_page_factory(rows), today=T24, path=path)
    assert r["status"] == "ok" and r["valid"] == 10 and r["added"] == 10
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved["rows"]) == 10 and "CEO_NM" not in saved["rows"][0]        # 유효분만 · 열 축소
    r2 = om.run_collection(page=_page_factory(rows[:3]), today=T24, path=path)  # 10→3 급감
    assert r2["status"] == "suspect_drop" and len(json.loads(path.read_text(encoding="utf-8"))["rows"]) == 10
    r3 = om.run_collection(page=_page_factory([mk(99, end="20000101")]), today=T24, path=path)
    assert r3["status"] == "error"                                                # 유효 0건 → 보류


def test_fetch_all_stops_on_source_error():
    def bad(key, s, e):
        return {om.GRID_ID: {"result": {"code": "ERROR-300", "message": "키 오류"}}}
    assert om.fetch_all("x", page=bad)["status"] == "error"


# ── 사실 인용 결정 ────────────────────────────────────────────────────────────────
def test_citation_for_organic_subject_at_stage3():
    env = MC.judge(SUBJ, today=T24)
    assert env.kind == "사실 인용" and env.result["stage"].startswith("3.")
    fams = [g["family"] for g in env.result["groups"]]
    assert any("BT" in f for f in fams) and any("님" in f for f in fams)
    ok = [g for g in env.result["groups"] if g["status"] == "success"]
    assert ok and all(g["items"][0]["notice_no"] for g in ok)                      # 실제 공시번호가 실린다
    c = env.result["citation"]
    assert c["observed_at"] == "2026-09-07" and "15080748" in c["source"] and "효능" in c["note"]
    assert [i.axis for i in env.inputs] == ["cert", "anchor"]


def test_citation_conventional_without_psis_key_is_data_gap(monkeypatch):
    # [M-15 ⑤] 관행 갈래는 이제 PSIS 인용 — 키가 없으면 데이터 미비(범주명으로 메우지 않는다). 인용 자체는 tests/test_psis.py
    for k in ("AGRODSS_PSIS_API_KEY", "PSIS_API_KEY", "EXTERNAL_API__PSIS_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    env = MC.judge({**SUBJ, "cert": "관행"}, today=T24)
    assert env.kind == "판단 불가(데이터)" and "PSIS" in env.result["why"] and env.missing[0]["axis"] == "cert"
    env = MC.judge({**SUBJ, "cert": "무농약"}, today=T24)
    assert env.kind == "해당 없음"


def test_citation_missing_cert_is_data_gap():
    s = {k: v for k, v in SUBJ.items() if k != "cert"}
    env = MC.judge(s, today=T24)
    assert env.kind == "판단 불가(데이터)" and env.missing[0]["axis"] == "cert"


def test_citation_outside_grid_window():
    assert MC.judge(SUBJ, today=date(2027, 3, 1)).kind == "해당 없음"


def test_families_extracted_from_grid_text():
    unit = MC._load_unit(SUBJ)
    st = [s for s in unit["stages"] if s["order"] == 3][0]
    fams = MC._families(st)
    assert "BT제" in fams and "님 추출물" in fams and any("유기질" in f for f in fams)
