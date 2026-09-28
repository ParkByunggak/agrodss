# -*- coding: utf-8 -*-
# [D-21 장기 2026-09-28 · 발행자 ⓐ "장기는 수동 정본으로 — 자리를 세우자"] 기상청 1·3개월 전망은 오픈 API 가 없다(VELA 실측 2026-08-05 인용).
# 계약: 등재 항목 → 1층 레코드(출처 URL 필수 · 확률 합≈100 · 기간 형식) · 틀린 항목은 조용히 빠지지 않고 이유가 남는다 · 비면 "등재 없음" ·
# 지난 기간은 안 낸다 · 게이트를 지나 날씨 인용에 도착한다. 상태: 저장소의 실제 파일이 읽히고(0 못 읽음) 예시는 entries 밖이다.
from __future__ import annotations

import http.client
import json
from datetime import date
from pathlib import Path

import pytest

from frontend import words
from ingest import chat, dropped, media, outlook
from judge import boundary, run as judge_run, stage_decisions as SD
from schema import records as sch
from tests.test_brand_home import srv  # noqa: F401

TODAY = date(2026, 9, 28)
GOOD = {"period_type": "1개월", "issued_on": "2026-09-24", "target_from": "2026-10-05", "target_to": "2026-10-11", "region": "충북",
        "temp": {"above": 50, "normal": 30, "below": 20}, "precip": {"above": 30, "normal": 40, "below": 30},
        "source_title": "기상청 1개월 전망(2026.10.5.~11.1.) 발표", "source_url": "https://www.weather.go.kr/w/climate/prediction/month1.do"}
PAST = dict(GOOD, target_from="2026-09-14", target_to="2026-09-20", issued_on="2026-09-10")
LATER = dict(GOOD, target_from="2026-10-12", target_to="2026-10-18", precip=None, note="둘째 주")


def _write(tmp_path, entries):
    p = tmp_path / "climate_outlook.json"
    p.write_text(json.dumps({"_example": GOOD, "entries": entries}, ensure_ascii=False), encoding="utf-8")
    return p


def test_an_entry_becomes_a_record_that_passes_the_gate_verbatim():
    r = outlook.entry_to_record(GOOD, fetched_at="2026-09-28T05:00:00+09:00")
    assert r["kind"] == "reference.climate_outlook" and r["source"] == "publisher:kma_outlook" and r["observed_at"] == "2026-09-24"
    assert r["period_from"] == "2026-10-05" and r["period_to"] == "2026-10-11" and r["region"] == "충북" and r["resolution"] == "region:충북"
    assert r["values"] == {"temp": {"above": 50.0, "normal": 30.0, "below": 20.0}, "precip": {"above": 30.0, "normal": 40.0, "below": 30.0}}
    assert r["citation"] == {"title": GOOD["source_title"], "url": GOOD["source_url"]} and r["note"] is None
    boundary.gate_records([r], "outlook")
    assert "reference.climate_outlook" in sch.LAYER3_INPUT_KINDS and not sch.KINDS["reference.climate_outlook"].subject_bound
    with pytest.raises(sch.SchemaError):
        sch.validate(dict(r, source="external:kma_outlook"))                       # 원천을 부른 적 없다 — external: 은 거짓말


@pytest.mark.parametrize("patch, word", [
    ({"temp": {"above": 60, "normal": 30, "below": 20}}, "확률 합 110"),
    ({"temp": {"above": 50, "normal": 30}}, "셋이어야"),
    ({"temp": None, "precip": None}, "둘 다 없다"),
    ({"source_url": "기상청 발표"}, "source_url"),
    ({"source_url": ""}, "출처 없는"),
    ({"source_title": ""}, "source_title"),
    ({"target_from": "2026-10-12"}, "뒤다"),
    ({"issued_on": "2026-9-24"}, "YYYY-MM-DD"),
    ({"period_type": "6개월"}, "period_type"),
    ({"region": " "}, "region"),
    ({"forecast_text": "맑음"}, "모르는 키"),
])
def test_a_wrong_entry_is_refused_with_the_reason_not_silently_fixed(patch, word):
    with pytest.raises(ValueError) as e:
        outlook.entry_to_record(dict(GOOD, **patch))
    assert word in str(e.value)


def test_load_keeps_good_entries_and_reports_bad_ones_by_index(tmp_path):
    dropped.clear()
    p = _write(tmp_path, [dict(GOOD, temp={"above": 90, "normal": 30, "below": 20}), GOOD, "문자열", LATER])
    recs, bad = outlook.load(p)
    assert [r["period_from"] for r in recs] == ["2026-10-05", "2026-10-12"] and len(bad) == 2
    assert bad[0].startswith("entries[0]: temp 확률 합 140") and bad[1].startswith("entries[2]: 항목이 객체가 아니다")
    assert [d["path"] for d in dropped.all_drops() if d["where"] == "장기 전망 정본"] == [f"{p.name}#0", f"{p.name}#2"]   # /changes 에도 남는다
    assert recs[1]["values"]["precip"] is None and recs[1]["note"] == "둘째 주"
    assert outlook.load(tmp_path / "없음.json") == ([], []) and outlook.load(_write(tmp_path, [])) == ([], [])
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    assert outlook.load(tmp_path / "bad.json")[1][0].startswith("JSON 아님")


def test_only_periods_covering_today_or_later_are_cited():
    recs = [outlook.entry_to_record(e) for e in (PAST, GOOD, LATER)]
    assert [r["period_from"] for r in outlook.covering(recs, TODAY)] == ["2026-10-05", "2026-10-12"]
    assert outlook.covering(recs, date(2026, 10, 12)) [0]["period_from"] == "2026-10-12"        # 진행 중인 기간은 덮는다
    assert outlook.covering(recs, date(2026, 10, 19)) == []


def test_gather_outlook_says_why_when_there_is_nothing_to_cite(tmp_path, monkeypatch):
    monkeypatch.setenv("AGRODSS_OUTLOOK_PATH", str(tmp_path / "없음.json"))
    recs, why = judge_run.gather_outlook(TODAY)
    assert recs is None and "등재된 장기 전망 없음" in why and "없음.json" in why and "발행자 몫" in why
    monkeypatch.setenv("AGRODSS_OUTLOOK_PATH", str(_write(tmp_path, [PAST])))
    recs, why = judge_run.gather_outlook(TODAY)
    assert recs is None and "모두 지난 기간(마지막 2026-09-20)" in why
    monkeypatch.setenv("AGRODSS_OUTLOOK_PATH", str(_write(tmp_path, [PAST, GOOD, dict(GOOD, source_url="x")])))
    recs, why = judge_run.gather_outlook(TODAY)
    assert recs and [r["period_from"] for r in recs] == ["2026-10-05"] and why.startswith("못 읽은 항목 1 — entries[2]")   # 산 항목 + 못 읽은 것 둘 다 말한다


def test_the_citation_carries_the_outlook_after_short_and_mid_and_its_reason_when_absent():
    s = media.load_subjects()[0]
    lrows = [outlook.entry_to_record(e) for e in (PAST, GOOD, LATER)]
    e = SD.judge_forecast_citation(s, TODAY, forecast=None, why="단기 없음", mid=None, mid_why="중기 없음", outlook=lrows, outlook_why=None)
    assert e.kind == "사실 인용" and e.result["days"] == [] and e.result["mid"]["days"] == []
    lg = e.result["long"]
    assert [p["from"] for p in lg["periods"]] == ["2026-10-05", "2026-10-12"] and lg["why"] is None
    assert lg["periods"][0]["temp"] == {"above": 50.0, "normal": 30.0, "below": 20.0} and lg["periods"][0]["url"] == GOOD["source_url"] and lg["periods"][1]["precip"] is None
    assert [i.source for i in e.inputs] == ["publisher:kma_outlook"] and e.inputs[0].resolution == "region:충북"
    sm = e.result["summary"]
    assert "장기(1개월 전망 · 등재 정본 · 발표 2026-09-24) 10-05~10-11 충북 기온 높음 50% · 비슷 30% · 낮음 20% / 강수 많음 30% · 비슷 40% · 적음 30% · 10-12~10-18 충북 기온 높음 50% · 비슷 30% · 낮음 20%" in sm
    assert "단기: 못 받음 — 단기 없음" in sm and "중기: 못 받음 — 중기 없음" in sm
    for bad in ("권고", "해야", "주의", "위험"):
        assert bad not in sm
    e2 = SD.judge_forecast_citation(s, TODAY, forecast=None, why="단기 없음", mid=None, mid_why="중기 없음", outlook=None, outlook_why="등재된 장기 전망 없음 — climate_outlook.json")
    assert e2.kind == "판단 불가(데이터)" and e2.result["long_why"].startswith("등재된 장기 전망 없음") and "장기: 등재된 장기 전망 없음" in e2.result["summary"]


def test_the_outlook_and_its_reason_reach_the_decision_through_the_gate(tmp_path, monkeypatch):
    """[관문의 입력 래칫 · 장기] gather_outlook 의 줄과 이유가 게이트를 지나 forecast_citation 까지 온다 — 좌표·키 없는 격리 환경에서도(수동 정본이라)."""
    s = media.load_subjects()[0]
    e = next(x for x in judge_run.judgments_for(s["id"], today=TODAY) if x.decision_id == "forecast_citation")
    assert e.kind == "판단 불가(데이터)" and "등재된 장기 전망 없음" in e.result["long_why"]
    monkeypatch.setenv("AGRODSS_OUTLOOK_PATH", str(_write(tmp_path, [GOOD])))
    e = next(x for x in judge_run.judgments_for(s["id"], today=TODAY) if x.decision_id == "forecast_citation")
    assert e.kind == "사실 인용" and [p["from"] for p in e.result["long"]["periods"]] == ["2026-10-05"]
    info = next(i for _, _, i in judge_run.all_judgments(today=TODAY, only=s["id"]))
    assert info["outlook"] == "장기 전망(등재분) 사용" and "좌표" in info["forecast"]
    a = chat.answer(s, "다음 달 날씨 어때", TODAY)
    assert a.startswith(f"[{words.said('사실 인용')}]") and "10-05~10-11" in a and "높음 50%" in a, a


def test_the_judge_page_renders_the_outlook_table_with_its_source_link(srv, tmp_path, monkeypatch):
    monkeypatch.setenv("AGRODSS_TODAY", TODAY.isoformat())
    monkeypatch.setenv("AGRODSS_OUTLOOK_PATH", str(_write(tmp_path, [GOOD, LATER])))
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", "/judge")
    resp = c.getresponse()
    body = resp.read().decode("utf-8", "replace")
    # 화면은 사람 말로 옮긴다(words.plain: 정본 → 기준) — 시스템 문면이 아니라 화면에 실제로 보이는 글자를 본다
    assert resp.status == 200 and "<b>장기</b>(등재 기준)" in body and "기온(높음/비슷/낮음)" in body and "2026-10-05 ~ 2026-10-11" in body
    assert f'<a href="{GOOD["source_url"]}">' in body and "높음 50% / 비슷 30% / 낮음 20%" in body and "장기: 장기 전망(등재분) 사용" in body
    monkeypatch.setenv("AGRODSS_OUTLOOK_PATH", str(tmp_path / "없음.json"))
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", "/judge")
    body = c.getresponse().read().decode("utf-8", "replace")
    # 격리 환경은 단기·중기도 없어 셋 다 없음 → 판단 불가(데이터) 갈래 — 그 사유 줄에 장기 이유가 그대로 실린다(표는 없다)
    assert "장기: 등재된 장기 전망 없음" in body and "기온(높음/비슷/낮음)" not in body


def test_state_the_repository_file_is_readable_and_its_example_is_not_an_entry():
    p = outlook.DEFAULT_PATH
    doc = json.loads(p.read_text(encoding="utf-8"))
    recs, bad = outlook.load(p)
    assert bad == [], f"발행자 등재분에 못 읽는 항목이 있다 — {bad}"
    assert isinstance(doc.get("entries"), list) and "_example" in doc and "_how_to" in doc and doc["_example"] not in doc["entries"]
    outlook.entry_to_record(doc["_example"])                                           # 예시 자체가 형식을 지킨다(따라 적으면 읽힌다)
    for r in recs:
        assert r["citation"]["url"].startswith("http")
