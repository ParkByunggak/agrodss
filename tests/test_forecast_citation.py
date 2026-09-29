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


def _mrec(day, tmin, tmax, pop_am=None, pop_pm=None, sky_am=None, sky_pm=None, allday=None):
    r = {"kind": "forecast.weather_mid", "axis": ["forecast"], "observed_at": "2026-09-27T18:00:00+09:00", "for_day": day,
         "fetched_at": "2026-09-28T05:10:00+09:00", "source": "external:kma_midfcst", "resolution": "region:11C10000/11C10401", "region": "괴산",
         "values": {"tmin": tmin, "tmax": tmax, "pop_max": max(p for p in (pop_am, pop_pm, (allday or {}).get("pop")) if p is not None)}}
    if allday:
        r["allday"] = allday
    else:
        r["am"], r["pm"] = {"pop": pop_am, "sky": sky_am}, {"pop": pop_pm, "sky": sky_pm}
    return r


# 어제 18시 발표 → D+3 = 09-30 (단기 창 안 · 단기가 이긴다) … D+10 = 10-07
MID = [_mrec("2026-09-30", 9, 19, 20, 30, "구름많음", "흐림"), _mrec("2026-10-01", 7, 17, 60, 70, "흐리고 비", "흐리고 비"),
       _mrec("2026-10-02", 6, 18, 20, 20, "맑음", "맑음"), _mrec("2026-10-05", 5, 16, allday={"pop": 40, "sky": "구름많음"})]


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
    # [중기] 이유가 둘 — 단기·중기 각각의 문장이 그대로(한쪽 이유로 다른 쪽을 덮지 않는다)
    e3 = SD.judge_forecast_citation(_subject(), TODAY, forecast=None, why="단기예보 키 없음", mid=None, mid_why="중기예보 원천 no_region: 권역을 못 찾았다")
    assert e3.kind == "판단 불가(데이터)" and e3.result["short_why"] == "단기예보 키 없음" and "권역을 못 찾았다" in e3.result["mid_why"]
    assert "\n단기 — 단기예보 키 없음" in e3.result["summary"] and "\n중기 — 중기예보 원천 no_region" in e3.result["summary"]   # [2026-09-29 가독성] 이유도 줄마다


def test_with_a_forecast_it_cites_three_days_verbatim_and_marks_approximate_extremes():
    e = SD.judge_forecast_citation(_subject(), TODAY, forecast=FORECAST, why=None)
    assert e.kind == "사실 인용" and e.grade is None                                      # 판단이 아니다 — 등급 없음
    days = e.result["days"]
    assert [x["day"] for x in days] == ["2026-09-28", "2026-09-29", "2026-09-30"]          # 어제도 · 4일 뒤도 아니다
    assert days[1]["pop_max"] == 60 and days[1]["rain_mm"] == 5.0 and days[1]["approx"] is False
    assert days[2]["tmin"] == 9.5 and days[2]["tmax"] == 19.0 and days[2]["approx"] is True   # 최저·최고가 없는 날은 시간대 값 — 표기에 남는다
    s = e.result["summary"]
    assert "09-29 11~22℃ 비 60% 5.0mm" in s and "09-30 10~19℃(시간대 값) 비 20%" in s and "기상청 단기예보" in s and "발표 09-28 05시" in s
    assert "T05" not in s and "+09:00" not in s                                            # ISO 시각을 농가 줄에 그대로 내지 않는다
    assert e.result["citation"]["source"] == "external:kma:vilage" and e.inputs[0].axis == "forecast"
    for bad in ("권고", "해야", "주의", "위험"):
        assert bad not in s                                                                # 해석·권고를 붙이지 않는다
    assert e.result["mid"]["days"] == [] and "3일" not in e.result["mid"]["why"] and "2026-09-30 뒤" in e.result["mid"]["why"]   # 중기 없음 — 이유가 자리에
    assert "\n중기 — 못 받음: " in s and "중기예보는 못 받았다" in " ".join(e.notes)


def test_mid_term_days_follow_the_short_window_verbatim_and_the_short_window_wins_on_overlap():
    e = SD.judge_forecast_citation(_subject(), TODAY, forecast=FORECAST, why=None, mid=MID, mid_why=None)
    assert e.kind == "사실 인용" and e.grade is None
    assert [x["day"] for x in e.result["days"]] == ["2026-09-28", "2026-09-29", "2026-09-30"]
    m = e.result["mid"]
    assert [x["day"] for x in m["days"]] == ["2026-10-01", "2026-10-02", "2026-10-05"]        # 09-30 은 단기 창 안 — 중기 줄은 버린다(격자가 권역을 이긴다)
    assert m["days"][0] == {"day": "2026-10-01", "tmin": 7, "tmax": 17, "pop_max": 70, "sky": "흐리고 비", "region": "괴산", "ta_region": None}   # 오전·오후 중 큰 값 · 같은 날씨는 한 번
    assert m["days"][1]["sky"] == "맑음" and m["days"][2]["pop_max"] == 40 and m["days"][2]["sky"] == "구름많음"                # 8일 뒤는 하루 하나
    assert m["citation"]["source"] == "external:kma_midfcst" and m["citation"]["region"] == "괴산" and m["why"] is None
    assert [i.source for i in e.inputs] == ["external:kma:vilage", "external:kma_midfcst"]                                     # 원천 둘이 입력에 따로
    s = e.result["summary"]
    # [발행자 2026-09-29 "가독성이 떨어진다 — 시간과 날짜 단위로 줄바꿈"] 지평 머리 한 줄 + 날마다 한 줄. ' · ' 로 잇던 한 줄은 휴대폰에서 못 읽었다
    assert s.split("\n") == ["단기 — 기상청 단기예보 · 필지 자리 5km 예보 구역 · 3시간 단위 · 발표 09-28 05시",       # [발행자 2026-09-29 "어느 지점을 말하는가"] 자리를 머리에
                             "09-28 12~21℃ 비 30%", "09-29 11~22℃ 비 60% 5.0mm", "09-30 10~19℃(시간대 값) 비 20%",
                             "중기 — 괴산 권역 · 기상청 중기예보 · 발표 09-27 18시",
                             "10-01 7~17℃ 비 70%", "10-02 6~18℃ 비 20%", "10-05 5~16℃ 비 40%",
                             "장기 — 없음: 오늘 뒤를 덮는 장기 전망 등재 없음"], s
    assert "격자" not in s                                                                  # '격자' 는 낱말 표가 재배 달력으로 바꾼다
    e3 = SD.judge_forecast_citation(_subject(), TODAY, forecast=FORECAST, why=None, mid=[dict(r, ta_region="충주") for r in MID], mid_why=None)
    assert "\n중기 — 괴산 권역 · 기온은 충주 기준 · 기상청 중기예보" in e3.result["summary"] and e3.result["mid"]["citation"]["ta_region"] == "충주"   # 빌린 기온 코드를 숨기지 않는다
    for bad in ("권고", "해야", "주의", "위험"):
        assert bad not in s
    # 반대편 — 단기가 없고 중기만 있어도 사실 인용이다(못 받은 쪽의 이유가 자리에 남는다)
    e2 = SD.judge_forecast_citation(_subject(), TODAY, forecast=None, why="예보 원천 error: HTTP 500", mid=MID, mid_why=None)
    assert e2.kind == "사실 인용" and e2.result["days"] == [] and e2.result["short_why"] == "예보 원천 error: HTTP 500"
    assert [x["day"] for x in e2.result["mid"]["days"]] == ["2026-10-01", "2026-10-02", "2026-10-05"] and e2.result["summary"].startswith("단기 — 못 받음: 예보 원천 error: HTTP 500\n중기 — ")
    assert e2.result["citation"]["source"] is None and [i.source for i in e2.inputs] == ["external:kma_midfcst"]


def test_the_chat_routes_weather_questions_here_and_keeps_risk_words_for_the_alert():
    for q in ("내일 날씨 어때", "이번 주 기온이 어떤가요", "비 올까요", "내일 비 오나", "예보 좀"):
        assert chat.topic_of(q) == "forecast_citation", q
    for q, did in (("비 오면 어떻게 하죠", "risk_alert"), ("서리 오면 어떻게 하죠", "risk_alert"), ("폭우 온다는데", "risk_alert"), ("가뭄이 심한데 물 줘야 하나", "drought_alert")):
        assert chat.topic_of(q) == did, q
    # [중기·장기 처방 직후 전수] 기간·요소가 붙은 전망 물음은 날씨 인용으로 — '전망' 홀로는 안 된다(수확 · 출하 전망은 그쪽 판단이 맞다)
    for q in ("장기 전망 알려줘", "한 달 전망 어때", "10월 강수량 전망", "이번 달 강수 전망", "가을 전망이 어떤가요", "중기 전망 좀", "다음 주 강수 확률"):
        assert chat.topic_of(q) == "forecast_citation", q
    for q, did in (("수확 전망은 어때", "harvest_timing"), ("출하 전망", "ship_or_store"), ("중기 계획", "plan_vs_actual")):
        assert chat.topic_of(q) == did, q
    assert chat.topic_of("장기적으로 어떻게 해야 하나") != "forecast_citation"                         # '장기' 홀로도 안 된다
    s = _subject()
    a = chat.answer(s, "내일 날씨 어때", TODAY)                                             # 격리 환경 — 좌표·키 없음 → 데이터 미비의 이유가 답에
    e = next(x for x in judge_run.judgments_for(s["id"], today=TODAY) if x.decision_id == "forecast_citation")
    assert a.startswith(f"[{words.said(e.kind)}]") and words.plain(e.result["summary"]) in a, a
    assert "판단이 아직 등록되지 않았습니다" not in a                                       # 붙여 주신 그 답은 더 안 나온다
    assert e.kind == "판단 불가(데이터)" and "좌표" in e.result["why"] and "좌표" in a, a     # 못 받은 이유(gather_forecast 의 문장)가 관문을 지나 답까지 온다(관문의 입력 — 주입 D 가 이것 없이 통과했다)
    assert e.result["short_why"] and e.result["mid_why"] and "좌표" in e.result["mid_why"]   # [중기] gather_mid 의 이유도 같은 관문을 지나 도착한다


def test_the_mid_term_reason_and_rows_reach_the_decision_through_the_gate(monkeypatch):
    """[관문의 입력 래칫 · 중기] gather_mid 가 준 이유와 줄이 게이트를 지나 forecast_citation 까지 온다 — 한쪽만 배선하면 관문은 서 있고 아무것도 안 거른다."""
    from judge import run as jr
    monkeypatch.setattr(jr, "gather_forecast", lambda s0: (None, "단기 없음(검사)"))
    monkeypatch.setattr(jr, "gather_mid", lambda s0: (None, "중기 없음(검사 — 이 문장이 도착해야 한다)"))
    s = _subject()
    e = next(x for x in jr.judgments_for(s["id"], today=TODAY) if x.decision_id == "forecast_citation")
    assert e.kind == "판단 불가(데이터)" and e.result["mid_why"] == "중기 없음(검사 — 이 문장이 도착해야 한다)" and e.result["short_why"] == "단기 없음(검사)"
    monkeypatch.setattr(jr, "gather_mid", lambda s0: (MID, ""))
    e = next(x for x in jr.judgments_for(s["id"], today=TODAY) if x.decision_id == "forecast_citation")
    assert e.kind == "사실 인용" and [x["day"] for x in e.result["mid"]["days"]] == ["2026-10-01", "2026-10-02", "2026-10-05"]
    info = next(i for ss, _, i in jr.all_judgments(today=TODAY, only=s["id"]))
    assert info["mid"] == "중기예보 사용" and info["forecast"] == "단기 없음(검사)"


def test_the_short_forecast_is_told_in_three_hour_lines_under_each_day():
    """[발행자 2026-09-29 17시] *"단기예보는 격자형예보로 3시간 단위로 예보를 사용자에게 알려 줘야 한다"* — 원천이 3시간 단위인데 하루로 접어 냈다.
    날 한 줄 아래 시각마다 한 줄 · 값은 원천 그대로 · 없는 값은 비운다 · 3시간 줄이 없는 레코드(옛 형태)는 날 한 줄만."""
    hours = [{"t": "0600", "tmp": 12.0, "sky": "맑음", "pty": None, "pop": 0, "pcp": None, "wsd": 1.2},
             {"t": "0900", "tmp": 16.0, "sky": "흐림", "pty": "비", "pop": 60, "pcp": 1.0, "wsd": None},
             {"t": "1200", "tmp": None, "sky": None, "pty": None, "pop": None, "pcp": 0.0, "wsd": None}]
    fc = [dict(FORECAST[1], hours=hours)] + FORECAST[2:]
    e = SD.judge_forecast_citation(_subject(), TODAY, forecast=fc, why=None)
    assert e.result["days"][0]["hours"] == hours and e.result["days"][1]["hours"] == []
    lines = e.result["summary"].split("\n")
    assert lines[0] == "단기 — 기상청 단기예보 · 필지 자리 5km 예보 구역 · 3시간 단위 · 발표 09-28 05시"
    assert lines[1:5] == ["09-28 12~21℃ 비 30%", "· 06시 12℃ 맑음 비 0% 바람 1.2m/s", "· 09시 16℃ 흐림 비 비 60% 1.0mm", "· 12시"]
    assert lines[5].startswith("09-29 ") and lines[6].startswith("09-30 ")                                 # 3시간 줄 없는 날은 날 한 줄만
    for bad in ("None", "nan"):
        assert bad not in e.result["summary"]


def test_a_day_between_the_horizons_is_filled_from_the_short_source_or_named_as_missing():
    """[발행자 실사용 2026-09-29 14시] 단기 09-29~10-01 · 중기 10-03~ — 10-02 가 어느 줄에도 없었다(06시 발표 중기의 D+3 이 원천에 비어 줄이 안 섰고 단기는 창 3일에서
    잘렸다). 빈 날은 단기 원천에 더 있는 날로 메우고, 그래도 없으면 없다고 말한다 — 조용히 건너뛰지 않는다."""
    mid_late = [dict(r, for_day="2026-10-03") for r in MID if r["for_day"] == "2026-10-05"]                    # 중기가 10-03 부터
    short4 = FORECAST                                                                                            # 단기 원천에 4일째 10-01 이 이미 있다(창 3일이 자르던 것)
    e = SD.judge_forecast_citation(_subject(), TODAY, forecast=short4, why=None, mid=mid_late, mid_why=None)
    assert [x["day"] for x in e.result["days"]] == ["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01"] and e.result["gap_days"] == ["2026-10-02"]
    lines = e.result["summary"].split("\n")
    assert lines[4].startswith("10-01 ") and lines[5] == "10-02 값 없음 — 단기 창 뒤 · 중기 시작 전(두 원천 어느 쪽에도 없음)" and lines[6].startswith("중기 — ")
    assert any("2026-10-02" in n and "어느 쪽에도" in n for n in e.notes)
    e2 = SD.judge_forecast_citation(_subject(), TODAY, forecast=FORECAST, why=None, mid=MID, mid_why=None)     # 중기가 바로 이어지면 빈 날 없음
    assert e2.result["gap_days"] == [] and "값 없음" not in e2.result["summary"]
    e3 = SD.judge_forecast_citation(_subject(), TODAY, forecast=short4, why=None, mid=None, mid_why="x")       # 중기가 없으면 단기 창(3일)은 그대로 — 창 계약
    assert [x["day"] for x in e3.result["days"]] == ["2026-09-28", "2026-09-29", "2026-09-30"] and e3.result["gap_days"] == []


def test_the_chat_card_and_judge_page_render_a_citation_without_crashing(srv, monkeypatch):
    from judge import run as jr
    monkeypatch.setattr(jr, "gather_forecast", lambda s0: (FORECAST, ""))
    monkeypatch.setattr(jr, "gather_mid", lambda s0: (MID, ""))
    monkeypatch.setenv("AGRODSS_TODAY", TODAY.isoformat())
    s = _subject()
    e = next(x for x in jr.judgments_for(s["id"], today=TODAY) if x.decision_id == "forecast_citation")
    card = chat.summarize_envelope(e)
    assert card.startswith(f"[{words.said('사실 인용')}]\n단기 — ") and "\n09-29 " in card and "\n중기 — 괴산 권역 · " in card and card.endswith("\n해석·권고 없음")   # 머리·꼬리도 제 줄
    a = chat.answer(s, "내일 날씨 어때", TODAY)
    assert "\n중기 — 괴산 권역 · " in a and "\n10-01 7~17℃" in a and "\n장기 — 없음: " in a, a       # 답변까지 줄이 산다
    for q in ("오늘 날씨 어떄", "오늘 날씨는", "오늘 날씨"):                                       # [2026-09-29] 오타 · 조사로 끝나는 물음도 같은 답
        assert "\n중기 — 괴산 권역 · " in chat.answer(s, q, TODAY), q
    from frontend import chat_pages
    css = chat_pages.__dict__.get("CSS") or open(chat_pages.__file__, encoding="utf-8").read()
    assert ".msg.sys .bub" in css and "white-space:pre-wrap" in css[css.index(".msg.sys .bub"):css.index("}", css.index(".msg.sys .bub"))]   # 말풍선이 줄을 보인다
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", "/judge")
    resp = c.getresponse()
    body = resp.read().decode("utf-8", "replace")
    assert resp.status == 200 and "날씨 인용(단기·중기 예보)" in body and "비 올 확률(최대)" in body and "2026-09-29" in body and "(시간대 값)" in body
    assert "비 올 확률(오전·오후 최대)" in body and "2026-10-05" in body and "흐리고 비" in body and "<b>중기</b>(괴산 권역)" in body   # 중기 표 — 단기와 다른 열
    assert "<b>단기</b>(필지 자리 5km 예보 구역 69,107)" in body and "5km 재배 달력" not in body                                      # 어느 자리인지 — 격자 번호까지
    from frontend import render
    assert f"발표 {render.local_time('2026-09-28T05:00:00+09:00')}" in body and f"발표 {render.local_time('2026-09-27T18:00:00+09:00')}" in body   # 시각 표기 정본(C16) — 손으로 자르지 않는다
    assert "2026-09-28T05:00" not in body
    assert "forecast_citation" not in body.replace('title="forecast_citation"', "")
    # 반대편 — 중기를 못 받으면 그 이유가 화면에(빈 표가 아니라)
    monkeypatch.setattr(jr, "gather_mid", lambda s0: (None, "중기예보 원천 no_region: 권역을 못 찾았다"))
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", "/judge")
    body = c.getresponse().read().decode("utf-8", "replace")
    assert "<b>중기</b> · 못 받음 — 중기예보 원천 no_region" in body and "비 올 확률(오전·오후 최대)" not in body
