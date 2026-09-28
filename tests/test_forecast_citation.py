# -*- coding: utf-8 -*-
# [D-21 자리 2026-09-28] 발행자 "KMA api 가 있는데 날씨를 안내하지 않고, 예측도 하지 않는 이유는?" — 예보는 판단 넷의 입력이었지 산출이 아니었다.
# 발행자 "D-21 등재하자" → 사실 인용 종류로 등록. 계약(합성 예보)과 상태(실제 — 여기 격리 환경에는 좌표·키가 없어 데이터 미비)를 가른다.
# 거부·통과 둘 다: 예보가 없으면 못 받은 이유를 그대로 · 있으면 값을 원천 그대로(대리값 없음 · 없는 최저·최고는 표기에 남긴다) · 해석·권고 없음.
from __future__ import annotations

import http.client
from datetime import date

from frontend import words
from ingest import chat, media
from judge import registry, run as judge_run, stage_decisions as SD
from tests.test_brand_home import srv  # noqa: F401

TODAY = date(2026, 9, 28)


def _subject():
    return media.load_subjects()[0]


def _rec(day, tmin=None, tmax=None, pop=None, rain=None, tmin_tmp=None, tmax_tmp=None):
    v = {"tmin": tmin, "tmax": tmax, "pop_max": pop, "rain_mm": rain}
    if tmin_tmp is not None:
        v["tmin_from_tmp"] = tmin_tmp
    if tmax_tmp is not None:
        v["tmax_from_tmp"] = tmax_tmp
    return {"kind": "forecast.weather_daily", "axis": ["forecast"], "observed_at": "2026-09-28T05:00:00+09:00", "for_day": day,
            "fetched_at": "2026-09-28T05:10:00+09:00", "source": "external:kma:vilage", "resolution": "grid5km:69,107", "values": v}


FORECAST = [_rec("2026-09-27", 10, 20, 0, 0), _rec("2026-09-28", 12, 21, 30, 0), _rec("2026-09-29", 11, 22, 60, 5.0),
            _rec("2026-09-30", None, None, 20, 0, tmin_tmp=9.5, tmax_tmp=19.0), _rec("2026-10-01", 8, 18, 10, 0)]


def test_the_decision_is_registered_as_a_citation_and_judged_with_the_others():
    d = registry.get("forecast_citation")
    assert d and d.required_axes == ("forecast",) and "사실 인용" in d.rule and d.params["days"] == 3
    assert "forecast_citation" in SD.IDS and "forecast_citation" in SD.UNDECLARED
    envs = SD.judge_all(_subject(), TODAY)
    ids = [e.decision_id for e in envs]
    assert ids[-3:] == ["forecast_citation", "drought_alert", "symptom_triage"] and len(envs) == len(SD.IDS)


def test_without_a_forecast_it_carries_the_reason_it_was_not_fetched():
    e = SD.judge_forecast_citation(_subject(), TODAY, forecast=None, why="재배 단위에 좌표가 없다(I-6)")
    assert e.kind == "판단 불가(데이터)" and e.missing[0]["axis"] == "forecast" and "좌표가 없다" in e.missing[0]["who_can_fill"]
    assert "좌표가 없다" in e.result["summary"]
    e2 = SD.judge_forecast_citation(_subject(), TODAY, forecast=[_rec("2026-10-20", 1, 2, 0, 0)], why=None)   # 있어도 창 밖이면 없는 것
    assert e2.kind == "판단 불가(데이터)" and "3일" in e2.result["why"]


def test_with_a_forecast_it_cites_three_days_verbatim_and_marks_approximate_extremes():
    e = SD.judge_forecast_citation(_subject(), TODAY, forecast=FORECAST, why=None)
    assert e.kind == "사실 인용" and e.grade is None                                      # 판단이 아니다 — 등급 없음
    days = e.result["days"]
    assert [x["day"] for x in days] == ["2026-09-28", "2026-09-29", "2026-09-30"]          # 어제도 · 4일 뒤도 아니다
    assert days[1]["pop_max"] == 60 and days[1]["rain_mm"] == 5.0 and days[1]["approx"] is False
    assert days[2]["tmin"] == 9.5 and days[2]["tmax"] == 19.0 and days[2]["approx"] is True   # 최저·최고가 없는 날은 시간대 값 — 표기에 남는다
    s = e.result["summary"]
    assert "09-29 11~22℃ 비 60% 5.0mm" in s and "09-30 10~19℃(시간대 값) 비 20%" in s and "기상청 단기예보" in s and "발표 2026-09-28T05:00" in s
    assert e.result["citation"]["source"] == "external:kma:vilage" and e.inputs[0].axis == "forecast"
    for bad in ("권고", "해야", "주의", "위험"):
        assert bad not in s                                                                # 해석·권고를 붙이지 않는다


def test_the_chat_routes_weather_questions_here_and_keeps_risk_words_for_the_alert():
    for q in ("내일 날씨 어때", "이번 주 기온이 어떤가요", "비 올까요", "내일 비 오나", "예보 좀"):
        assert chat.topic_of(q) == "forecast_citation", q
    for q, did in (("비 오면 어떻게 하죠", "risk_alert"), ("서리 오면 어떻게 하죠", "risk_alert"), ("폭우 온다는데", "risk_alert"), ("가뭄이 심한데 물 줘야 하나", "drought_alert")):
        assert chat.topic_of(q) == did, q
    s = _subject()
    a = chat.answer(s, "내일 날씨 어때", TODAY)                                             # 격리 환경 — 좌표·키 없음 → 데이터 미비의 이유가 답에
    e = next(x for x in judge_run.judgments_for(s["id"], today=TODAY) if x.decision_id == "forecast_citation")
    assert a.startswith(f"[{words.said(e.kind)}]") and words.plain(e.result["summary"]) in a, a
    assert "판단이 아직 등록되지 않았습니다" not in a                                       # 붙여 주신 그 답은 더 안 나온다
    assert e.kind == "판단 불가(데이터)" and "좌표" in e.result["why"] and "좌표" in a, a     # 못 받은 이유(gather_forecast 의 문장)가 관문을 지나 답까지 온다(관문의 입력 — 주입 D 가 이것 없이 통과했다)


def test_the_chat_card_and_judge_page_render_a_citation_without_crashing(srv, monkeypatch):
    from judge import run as jr
    monkeypatch.setattr(jr, "gather_forecast", lambda s0: (FORECAST, ""))
    monkeypatch.setenv("AGRODSS_TODAY", TODAY.isoformat())
    s = _subject()
    e = next(x for x in jr.judgments_for(s["id"], today=TODAY) if x.decision_id == "forecast_citation")
    card = chat.summarize_envelope(e)
    assert card.startswith(f"[{words.said('사실 인용')}]") and "09-29" in card and "해석·권고 없음" in card
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", "/judge")
    resp = c.getresponse()
    body = resp.read().decode("utf-8", "replace")
    assert resp.status == 200 and "날씨 인용(단기예보)" in body and "비 올 확률(최대)" in body and "2026-09-29" in body and "(시간대 값)" in body
    assert "forecast_citation" not in body.replace('title="forecast_citation"', "")
