# -*- coding: utf-8 -*-
# [M-15 ⑤ PSIS 등록약제] 파싱 · 오류 · 작용기작 라운드로빈 · 위험 이름 → 병해충 검색어 · 키 없음 · 캐시(격리 · 만료) ·
#        관행 갈래 '사실 인용'(주입) · 0건은 0건(범주명 금지) · 유기 갈래는 그대로.
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from ingest import media, parcels, psis
from judge import material_citation as MC
from schema import records as sch

_RAW = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
SUBJ = parcels.enrich_subject(_RAW, parcels.by_id("p001"))
T24 = date(2026, 9, 18)

OK_XML = """<service><totalCount>4</totalCount><list>
<item><cropName>쪽파</cropName><diseaseWeedName>고자리파리</diseaseWeedName><useName>살충</useName><pestiKorName>A입제</pestiKorName>
<pestiBrandName>에이</pestiBrandName><dilutUnit>3kg/10a</dilutUnit><useSuittime>파종전</useSuittime><useNum>1회</useNum><indictSymbl>4a</indictSymbl><pestiUse>토양혼화</pestiUse><pestiCode>1</pestiCode></item>
<item><cropName>쪽파</cropName><diseaseWeedName>고자리파리</diseaseWeedName><useName>살충</useName><pestiKorName>B입제</pestiKorName>
<pestiBrandName>비</pestiBrandName><dilutUnit>3kg/10a</dilutUnit><useSuittime>파종전</useSuittime><useNum>1회</useNum><indictSymbl>4a</indictSymbl><pestiUse>토양혼화</pestiUse></item>
<item><cropName>쪽파</cropName><diseaseWeedName>고자리파리</diseaseWeedName><useName>살충</useName><pestiKorName>C유제</pestiKorName>
<pestiBrandName>씨</pestiBrandName><dilutUnit>1000배</dilutUnit><useSuittime>수확14일전</useSuittime><useNum>2회</useNum><indictSymbl>1b</indictSymbl><pestiUse>경엽처리</pestiUse></item>
<item><cropName>쪽파</cropName><diseaseWeedName>고자리파리</diseaseWeedName><useName>기타</useName><pestiKorName>전착제X</pestiKorName>
<pestiBrandName>엑스</pestiBrandName><dilutUnit>-</dilutUnit><useSuittime></useSuittime><useNum></useNum><indictSymbl></indictSymbl><pestiUse></pestiUse></item>
</list></service>"""
ERR_XML = "<service><errorCode>ERR_103</errorCode><errorMsg>서비스코드 오류</errorMsg></service>"
EMPTY_XML = "<service><totalCount>0</totalCount><list></list></service>"


def test_parse_items_and_error():
    items, total = psis.parse_items(OK_XML)
    assert total == 4 and len(items) == 4 and items[0]["pestiKorName"] == "A입제" and "pestiCode" not in items[0]   # 화이트리스트
    assert psis.error_of(ERR_XML).startswith("ERR_103") and psis.error_of(OK_XML) is None and "파싱" in psis.error_of("<x")


def test_dedupe_prefers_different_modes_of_action_and_defers_others():
    items, _ = psis.parse_items(OK_XML)
    out = psis.dedupe(items)
    # VELA W-20 그대로: 기작이 새로운 것이 먼저(4a → 1b → 기작 없음'?') 그 뒤 같은 기작 잔여. '기타' 용도는 후순위지만 기작 축이 우선이다
    assert [i["pestiKorName"] for i in out] == ["A입제", "C유제", "전착제X", "B입제"]


@pytest.mark.parametrize("risk,terms", [
    ("고자리파리 유충", ["고자리파리"]), ("파총채벌레 · 파좀나방", ["파총채벌레", "파좀나방"]), ("노균병", ["노균병"]),
    ("첫 서리 · 한파로 잎 손상", []), ("과습 · 뿌리 부패(가을 장마)", []), ("수확 지연 — 잎 노화 · 도복", []),
])
def test_pest_terms_from_risk_names(risk, terms):
    assert psis.pest_terms(risk) == terms


def test_search_without_key_is_unavailable_and_not_cached(monkeypatch):
    for k in ("AGRODSS_PSIS_API_KEY", "PSIS_API_KEY", "EXTERNAL_API__PSIS_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    r = psis.search("쪽파", "고자리파리", today=T24)
    assert r["status"] == "unavailable" and r["items"] == [] and not list(psis.psis_dir().glob("*.json"))


def test_search_success_caches_and_expires():
    calls = []

    def get(params):
        calls.append(dict(params))
        return OK_XML

    r = psis.search("쪽파", "고자리파리", today=T24, get=get, api_key="k")
    assert r["status"] == "success" and r["items"][0]["product"] == "A입제" and r["items"][0]["phi"] == "파종전" and sch.validate(r)
    assert calls[0]["serviceCode"] == "SVC01" and calls[0]["serviceType"] == "AA003" and calls[0]["diseaseWeedName"] == "고자리파리"
    r2 = psis.search("쪽파", "고자리파리", today=T24, get=get, api_key="k")
    assert len(calls) == 1 and r2["items"] == r["items"]                                  # 캐시 적중
    psis.search("쪽파", "고자리파리", today=T24 + timedelta(days=psis.config.PSIS_CACHE_DAYS + 1), get=get, api_key="k")
    assert len(calls) == 2                                                                # 만료 → 재조회


def test_search_zero_then_alias_and_error_not_masked():
    seen = []

    def get(params):
        seen.append(params["cropName"])
        return EMPTY_XML if params["cropName"] == "쪽파" else OK_XML

    r = psis.search("쪽파", "고자리파리", today=T24, get=get, api_key="k")
    assert seen == ["쪽파", "파"] and r["status"] == "success" and r["queried_as"] == "파"
    r = psis.search("쪽파", "노균병", today=T24, get=lambda p: ERR_XML, api_key="k")
    assert r["status"] == "error" and "ERR_103" in r["message"]
    r = psis.search("쪽파", "총채벌레", today=T24, get=lambda p: EMPTY_XML, api_key="k")
    assert r["status"] == "no_data" and r["items"] == [] and r["total"] == 0


# ── 관행 갈래 인용 ─────────────────────────────────────────────────────────────
def _fake_search(crop, pest, today=None):
    if pest == "고자리파리":
        return psis.to_record(crop, pest, "success", psis.dedupe(psis.parse_items(OK_XML)[0])[:3], 4, "2026-09-18T00:00:00+00:00")
    return psis.to_record(crop, pest, "no_data", [], 0, "2026-09-18T00:00:00+00:00")


def test_conventional_citation_cites_registered_pesticides_per_risk():
    env = MC.judge({**SUBJ, "cert": "관행"}, today=T24, psis_search=_fake_search)
    assert env.kind == "사실 인용" and env.result["stage"].startswith("3.")
    by = {g["pest"]: g for g in env.result["groups"]}
    assert set(by) == {"고자리파리", "파총채벌레", "파좀나방", "노균병"}
    assert by["고자리파리"]["status"] == "success" and by["고자리파리"]["items"][0]["product"] == "A입제"
    assert by["노균병"]["status"] == "no_data" and by["노균병"]["items"] == []                # 0건은 0건
    assert env.result["cited_families"] == 1 and "PSIS" in env.result["citation"]["source"] and "유기" in env.result["citation"]["note"]
    assert [i.axis for i in env.inputs] == ["cert", "anchor"]


def test_organic_branch_unchanged_and_no_pest_stage_is_not_applicable():
    env = MC.judge(SUBJ, today=T24, psis_search=_fake_search)
    assert env.kind == "사실 인용" and "15080748" in env.result["citation"]["source"]
    env = MC.judge({**SUBJ, "cert": "관행"}, today=date(2026, 8, 30), psis_search=_fake_search)   # 칸 2 — 결주 위험만(병해충 아님)
    assert env.kind == "해당 없음" and "병해충" in env.result["why"]
