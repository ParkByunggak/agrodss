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
    # [U-15] BT 는 자재명이 '미생물'뿐 — 자재명 조건 위에 제품명 '비티'를 겹친다(제품명만으로는 안 뽑는다)
    res = om.search(om.TYPE_PEST, "미생물", limit=3, today=T24, product_keyword="비티")
    assert res["status"] == "success" and 1 <= len(res["items"]) <= 3 and res["total"] >= len(res["items"])
    it = res["items"][0]
    assert it["kind"] == "reference.organic_material_notice" and it["source"] == om.SOURCE
    assert it["observed_at"] == "2026-09-07" and it["resolution"] == "national"
    assert it["values"]["type"] == om.TYPE_PEST and "미생물" in it["values"]["material"] and "비티" in it["values"]["product"]
    assert it["values"]["match"] == "자재명+제품명"


def test_search_items_pass_schema_and_carry_no_price_and_citation_validates_at_exit():
    # [코드 평가 C1 · 2026-09-19] 검색 항목에 금지 필드 price 가 실려 인용 봉투(사실 인용 예외 경로)로 화면까지 닿았다.
    # 검색 산출은 스키마를 통과해야 하고, 인용 판정기는 출구에서 sch.validate 를 거친다(게이트 없는 유일한 값 경로의 관문).
    from schema import records as sch
    from pathlib import Path
    res = om.search(om.TYPE_PEST, "미생물", limit=3, today=T24, product_keyword="비티")
    for it in res["items"]:
        assert sch.validate(it) and "price" not in it["values"] and not (sch.FORBIDDEN_FIELDS & set(it["values"]))
    src = Path(MC.__file__).read_text(encoding="utf-8")
    blk = src[src.index("for fam in fams:"):]
    blk = blk[:blk.index("fetched = canon.get")]
    assert "sch.validate(i)" in blk and '"items": [' in blk                      # 출구에서 검증한 값만 싣는다


def test_search_expired_rows_are_dropped_at_query_time():
    assert om.search(om.TYPE_PEST, "미생물", today=date(2040, 1, 1), product_keyword="비티")["status"] == "no_data"


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
    monkeypatch.setenv("AGRODSS_ORGANIC_PATH", str(path))   # [R-4 전수] 경로가 호출 시점에 풀리므로 env 로 격리된다
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
    # [U-23 전수 2026-09-21] 전에는 `해당 없음` 을 박아 두었다 — 사유란이 *"무농약은 갈래 규칙 미정"* 이라고
    # 정직하게 적어 놓고 종류는 "아무리 채워도 안 바뀐다" 였다. 규칙이 서면 바뀌므로 지식 미비다(I-1 §2-6).
    env = MC.judge({**SUBJ, "cert": "무농약"}, today=T24)
    assert env.kind == "판단 불가(지식)" and "규칙" in env.result["why"]


def test_a_cert_we_do_not_know_is_a_different_grade_from_a_rule_we_have_not_written():
    """급을 가른다 — **선언된 갈래인데 규칙이 없는 것**(지식)과 **아는 갈래가 아닌 값**(해당 없음)은 다른 사실이다.
    섞으면 오타까지 '정본 대기' 가 되어 무엇을 기다리는지 알 수 없어진다."""
    assert MC.judge({**SUBJ, "cert": "무농약"}, today=T24).kind == "판단 불가(지식)"
    assert MC.judge({**SUBJ, "cert": "유기농"}, today=T24).kind == "해당 없음"     # 어휘 밖 — 값이 틀린 것


def test_conventional_proxy_query_is_labelled_not_asserted():
    # [코드 평가 C3 표기] 쪽파 0건 → '파' 대체 조회는 그 사실을 말한다 — 등록은 작물별(PLS). 대체 조회 자체의 존폐는 발행자 결정(법규)
    def fake(crop, pest, today=None):
        if "고자리" in pest:
            return {"status": "success", "total": 2, "items": [{"상표명": "A", "품목명": "B"}], "queried_as": "파"}
        return {"status": "success", "total": 1, "items": [{"상표명": "C"}]}                       # 직접 등록 — 대체 아님
    env = MC.judge({**SUBJ, "cert": "관행"}, today=T24, psis_search=fake)
    assert env.kind == "사실 인용"
    prox = [g for g in env.result["groups"] if g.get("proxy")]
    direct = [g for g in env.result["groups"] if g["status"] == "success" and not g.get("proxy")]
    assert prox and all("미등록" in g["proxy_label"] and "파 등록분" in g["proxy_label"] for g in prox)
    assert direct and all("proxy_label" not in g for g in direct)
    c = env.result["citation"]
    assert "대체 조회" in c["proxy_notice"] and "PLS" in c["proxy_notice"] and "발행자 확인" in c["proxy_notice"]
    assert env.result["cited_direct"] == len(direct) and env.result["cited_families"] == len(direct) + len(prox)
    # 화면(/judge)이 관행 그룹 모양을 안다 — family 가 없어도 KeyError 없이 표기가 붙는다
    from frontend import serve
    out: list[str] = []
    serve._render_env(out, env.to_dict(), "자재 인용")
    html = "".join(out)
    assert "대체 조회" in html and "파 등록분" in html and "상표명 A" in html


def test_citation_missing_cert_is_data_gap():
    s = {k: v for k, v in SUBJ.items() if k != "cert"}
    env = MC.judge(s, today=T24)
    assert env.kind == "판단 불가(데이터)" and env.missing[0]["axis"] == "cert"


def test_citation_outside_grid_window():
    assert MC.judge(SUBJ, today=date(2027, 3, 1)).kind == "해당 없음"


def test_families_extracted_from_grid_text():
    unit = MC.grid_schema.load_unit(SUBJ)[0]
    st = [s for s in unit["stages"] if s["order"] == 3][0]
    fams = MC._families(st)
    assert "BT제" in fams and "님 추출물" in fams and any("유기질" in f for f in fams)
