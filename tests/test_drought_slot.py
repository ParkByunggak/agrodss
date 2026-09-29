# -*- coding: utf-8 -*-
# [D-20 자리 2026-09-28] 발행자 실사용 "가을 가뭄이 심하다. 아침에 포장을 보니 특별한 징후는 없다" → 규칙은 본 것으로 적었고(맞다) 가뭄을 읽는 판단이
# 없었다(격자 water 소비자 0 · 경보는 과습만). 발행자 "D-20 등재하자" → D-18 과 같은 형태로 결정을 지식 없이 세운다. 계약(합성 격자)과 상태(실제 격자)를
# 가른다: 실제 격자는 임계가 없어 판단 불가(지식)가 **어느 칸의 어느 키가 비었는지와 지금 칸의 수분 값**을 말해야 하고, 합성 격자에 임계가 있으면
# 마지막 비·관수 뒤 날수로 낸다(비·관수 기록이 없으면 데이터 미비). 거부·통과 둘 다.
from __future__ import annotations

import copy
import http.client
import json
from datetime import date, timedelta

import pytest

from frontend import words
from grid import schema as grid_schema
from ingest import chat, media
from judge import registry, run as judge_run, stage_decisions as SD
from tests.test_brand_home import srv  # noqa: F401

TODAY = date(2026, 9, 28)
RULES = {"dry_days": 7, "source": "합성 — 검사용"}


def _subject():
    return media.load_subjects()[0]


def _stage_today(subject):
    from grid import capture
    unit, _ = grid_schema.load_unit(subject)
    return capture.stage_for_day(unit, (TODAY - date.fromisoformat(subject["anchor"])).days)


def _synthetic_grid(tmp_path, monkeypatch, rules=RULES):
    unit = copy.deepcopy(grid_schema.load(grid_schema.GRID_DIR / "jjokpa_autumn.json"))
    order = _stage_today(_subject())["order"]
    for s in unit["stages"]:
        s.pop(SD.DROUGHT_RULES_KEY, None)
        if s["order"] == order and rules is not None:
            s[SD.DROUGHT_RULES_KEY] = rules
    (tmp_path / "jjokpa_autumn.json").write_text(json.dumps(unit, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(grid_schema, "GRID_DIR", tmp_path)


def test_the_decision_is_registered_undeclared_and_judged_before_symptoms():
    d = registry.get("drought_alert")
    assert d and d.required_axes == ("anchor",) and "precip" in d.optional_axes and d.params["rules_key"] == grid_schema.DROUGHT_RULES_KEY
    assert "drought_alert" in SD.IDS and "drought_alert" in SD.UNDECLARED
    envs = SD.judge_all(_subject(), TODAY)
    ids = [e.decision_id for e in envs]
    assert ids[-2:] == ["drought_alert", "symptom_triage"] and len(envs) == len(SD.IDS)   # 증상 결정이 마지막(그 검사가 그렇게 박혀 있다)
    src = (grid_schema.ROOT / "judge" / "stage_decisions.py").read_text(encoding="utf-8")
    assert "DROUGHT_RULES_KEY = grid_schema.DROUGHT_RULES_KEY" in src and '"drought_rules"' not in src   # 키 정본 하나


def test_with_the_real_grid_it_says_which_cell_is_empty_and_what_the_water_values_are():
    """**상태 검사 — 실제 격자의 가뭄 임계를 보는 유일한 검사.** 지금은 임계가 없다 — 어디가 비었는지 + 지금 칸의 수분 값(정본이 이미 아는 것)을 함께."""
    s = _subject()
    e = SD.judge_drought_alert(s, TODAY, evts=[], observations=[{"id": "o", "text": "가을 가뭄이 심하다", "observed_at": TODAY.isoformat()}])
    st = _stage_today(s)
    assert e.kind == "판단 불가(지식)"
    assert f"칸 {st['order']}" in e.result["why"] and SD.DROUGHT_RULES_KEY in e.result["why"] and "D-20" in e.result["why"] and ".json" in e.result["why"]
    assert st["water"]["demand"] in e.result["summary"] and st["water"]["deficit_sensitivity"] in e.result["summary"] and "기준" in e.result["summary"]


def test_with_a_threshold_but_no_rain_or_irrigation_record_it_asks_for_the_last_wet_day(tmp_path, monkeypatch):
    _synthetic_grid(tmp_path, monkeypatch)
    e = SD.judge_drought_alert(_subject(), TODAY, evts=[], observations=[{"id": "o", "text": "가을 가뭄이 심하다", "observed_at": TODAY.isoformat()}])
    assert e.kind == "판단 불가(데이터)" and e.missing[0]["axis"] == "precip" and "비 온 날" in e.missing[0]["who_can_fill"]


def test_with_a_threshold_the_days_since_the_last_rain_or_irrigation_decide(tmp_path, monkeypatch):
    _synthetic_grid(tmp_path, monkeypatch)
    s = _subject()
    rain = [{"id": "o1", "text": "어제 비가 왔다", "observed_at": "2026-09-18"}]
    e = SD.judge_drought_alert(s, TODAY, evts=[], observations=rain)                        # 10일 ≥ 7 → 관수 검토
    assert e.kind == "판단함" and e.grade == "추정" and e.result["dry_days"] == 10 and e.result["due"] is True and "관수 검토" in e.result["summary"]
    irr = [{"kind": "event", "type": "관수", "observed_at": "2026-09-25"}]
    e2 = SD.judge_drought_alert(s, TODAY, evts=irr, observations=rain)                      # 관수 3일 전이 더 최근 → 3 < 7
    assert e2.kind == "판단함" and e2.result["dry_days"] == 3 and e2.result["due"] is False and "아직" in e2.result["summary"]
    old = [{"id": "o2", "text": "비가 왔다", "observed_at": "2026-08-01"}]                    # 30일 밖 — 기록으로 안 센다
    assert SD.judge_drought_alert(s, TODAY, evts=[], observations=old).kind == "판단 불가(데이터)"
    assert not SD.judge_drought_alert(s, TODAY, evts=[], observations=[{"id": "o3", "text": "비료 줬다", "observed_at": TODAY.isoformat()}]).kind == "판단함"   # '비료' 는 비가 아니다


def _obs(day: str, rn, stn: int = 131):
    return {"kind": "observation.weather_daily", "axis": ["temp", "precip"], "observed_at": day, "fetched_at": "2026-09-28T06:00:00+09:00",
            "source": "external:kma_sfcdd", "resolution": f"station:{stn}", "station": stn, "values": {"tmax": 20.0, "tmin": 10.0, "ta_avg": 15.0, "rn_day_mm": rn, "ss_day_hr": 5.0}}


def test_the_last_rain_day_also_comes_from_kma_observed_daily_precipitation(tmp_path, monkeypatch):
    """[발행자 2026-09-29 "이미 기상청 현시점 이전의 무강수일을 가지고 있다 — 이를 활용해서 관수를 권고해야"] 마지막 비 온 날의 원천 셋 — 농가 관찰 · 관수 사건 ·
    기상청 관측. 가장 최근 날이 이긴다 · 비 온 날 = 일강수 ≥ 0.1mm(기상청 강수일 정의 · 격자 wet_mm 이 있으면 그것) · 0.0 은 비가 아니다."""
    _synthetic_grid(tmp_path, monkeypatch)
    s = _subject()
    obs = [_obs("2026-09-27", 0.0), _obs("2026-09-26", 0.0), _obs("2026-09-25", 3.5), _obs("2026-09-24", 0.1)]
    e = SD.judge_drought_alert(s, TODAY, evts=[], observations=[], obs_rain=obs)                # 농가 기록 없이 관측만으로 — 25일 비 → 3일
    assert e.kind == "판단함" and e.result["last_wet"] == "2026-09-25" and e.result["dry_days"] == 3 and e.result["due"] is False
    assert "기상청 관측 지점 131" in e.result["summary"] and e.result["wet_source"] == "기상청 관측 지점 131"
    assert any(i.axis == "precip" and i.source == "external:kma_sfcdd" for i in e.inputs) and any("4일 읽음" in n for n in e.notes)
    rain = [{"id": "o1", "text": "어제 비가 왔다", "observed_at": "2026-09-27"}]                 # 농가 관찰이 더 최근이면 그쪽
    e2 = SD.judge_drought_alert(s, TODAY, evts=[], observations=rain, obs_rain=obs)
    assert e2.result["last_wet"] == "2026-09-27" and e2.result["wet_source"] == "농가 관찰" and e2.result["dry_days"] == 1
    trace = [_obs("2026-09-27", 0.05)]                                                          # 0.05mm 는 강수일이 아니다(0.1 미만) → 비 온 날 없음
    e3 = SD.judge_drought_alert(s, TODAY, evts=[], observations=[], obs_rain=trace, obs_rain_why=None)
    assert e3.kind == "판단 불가(데이터)" and "비 온 날이 없다(1일만 받음)" in e3.result["why"]


def test_thirty_dry_observed_days_is_a_judgement_not_a_question(tmp_path, monkeypatch):
    _synthetic_grid(tmp_path, monkeypatch)
    dry30 = [_obs((TODAY - timedelta(days=k)).isoformat(), 0.0) for k in range(1, 31)]
    e = SD.judge_drought_alert(_subject(), TODAY, evts=[], observations=[], obs_rain=dry30)
    assert e.kind == "판단함" and e.result["dry_days"] == 30 and e.result["due"] is True and e.result["last_wet"] is None
    assert e.result["summary"].startswith("최근 30일 동안 비도 관수 기록도 없습니다(기상청 관측 지점 131)") and "관수 검토" in e.result["summary"]


def test_the_observation_window_follows_the_threshold_not_the_thirty_day_lookback(tmp_path, monkeypatch):
    """[구조적 위험 2026-09-29] 첫 답이 관측을 최대 30번 부르던 것 — 임계 N 이 있으면 N 일만 보면 판단이 선다(그 안에 비가 없으면 무강수는 이미 임계 이상).
    판정기: 관측이 덮은 날수 ≥ 임계 이고 비가 없으면 판단함 · 그보다 적게 받았으면 아직 묻는다. 수집기: 부르는 날수 = min(30, 임계) · 임계가 없으면 30."""
    _synthetic_grid(tmp_path, monkeypatch)                                                       # 임계 7
    s = _subject()
    dry7 = [_obs((TODAY - timedelta(days=k)).isoformat(), 0.0) for k in range(1, 8)]
    e = SD.judge_drought_alert(s, TODAY, evts=[], observations=[], obs_rain=dry7)
    assert e.kind == "판단함" and e.result["dry_days"] == 7 and e.result["due"] is True and "무강수 7일 이상" in e.result["summary"]
    e6 = SD.judge_drought_alert(s, TODAY, evts=[], observations=[], obs_rain=dry7[:6])
    assert e6.kind == "판단 불가(데이터)" and "6일만 받음" in e6.result["why"]                     # 임계에 못 미치는 날수만 봤으면 아직 모른다
    from judge import run as judge_run
    from ingest import kma
    monkeypatch.setenv("KMA_API_HUB_KEY", "x")
    monkeypatch.setattr(kma, "nearest_station", lambda lat, lon, allowed_ids=None: {"id": 131, "name": "충주"})
    seen = []
    monkeypatch.setattr(kma, "fetch_recent_obs", lambda stn, today, lookback, wet_mm=0.1: seen.append(lookback) or {"status": "success", "records": [], "days_seen": 0})
    judge_run.gather_obs_rain(dict(s, lat=36.75, lon=127.98), TODAY)
    assert seen == [7]                                                                            # 임계 7 → 7일만 부른다
    _synthetic_grid(tmp_path, monkeypatch, rules=None)                                           # 임계 없음 → 30
    judge_run.gather_obs_rain(dict(s, lat=36.75, lon=127.98), TODAY)
    assert seen == [7, 30]
    assert judge_run.drought_days_needed(dict(s, anchor=None), TODAY, 30) == 30                   # 심은 날이 없으면 칸을 못 정한다 → 30


def test_without_observed_rain_the_reason_travels_and_the_grid_can_override_wet_mm(tmp_path, monkeypatch):
    _synthetic_grid(tmp_path, monkeypatch, rules=dict(RULES, wet_mm=1.0))
    s = _subject()
    e = SD.judge_drought_alert(s, TODAY, evts=[], observations=[], obs_rain=None, obs_rain_why="기상청 관측 키 없음(검사)")
    assert e.kind == "판단 불가(데이터)" and "기상청 관측도 없다 — 기상청 관측 키 없음(검사)" in e.result["why"] and any("키 없음(검사)" in n for n in e.notes)
    e2 = SD.judge_drought_alert(s, TODAY, evts=[], observations=[], obs_rain=[_obs("2026-09-27", 0.5), _obs("2026-09-20", 2.0)])
    assert e2.result["last_wet"] == "2026-09-20" and e2.result["dry_days"] == 8                  # 격자 wet_mm 1.0 — 0.5mm 는 비가 아니다
    from judge import run as judge_run
    for n in ("AGRODSS_KMA_API_HUB_KEY", "KMA_API_HUB_KEY", "KMA__API_HUB_KEY", "EXTERNAL_API__KMA_API_HUB_KEY"):
        monkeypatch.delenv(n, raising=False)
    recs, why = judge_run.gather_obs_rain(dict(s, lat=36.75, lon=127.98), TODAY)
    assert recs is None and "키 없음" in why
    assert judge_run.gather_obs_rain(dict(s, lat=None, lon=None), TODAY)[1].startswith("재배 단위에 좌표가 없다")


def test_rain_words_are_one_canon_in_layer_one():
    assert chat.rain_in("어제 비가 왔다") and chat.rain_in("소나기 지나감") and not chat.rain_in("비료 줬다") and not chat.rain_in("비닐 덮었다")
    src = (grid_schema.ROOT / "judge" / "stage_decisions.py").read_text(encoding="utf-8")
    body = src[src.index("def judge_drought_alert"):]
    body = body[:body.index("\ndef ", 10)]
    assert "from ingest.chat import rain_in" in body and "RAIN_WORDS" not in body            # 3층은 목록을 두 벌째 두지 않는다


def test_the_chat_routes_a_drought_question_to_the_decision_and_judge_shows_the_card(srv):
    s = _subject()
    assert chat.topic_of("가뭄이 심한데 물 줘야 하나") == "drought_alert" and chat.topic_of("지금 뭘 해야 하죠") == "plan_vs_actual"
    a = chat.answer(s, "가뭄이 심한데 물 줘야 하나", TODAY)
    e = next(x for x in judge_run.judgments_for(s["id"], today=TODAY) if x.decision_id == "drought_alert")
    assert a.startswith(f"[{words.said(e.kind)}]") and words.plain(e.result["summary"]) in a and "다음 예정" not in a, a
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", "/judge")
    body = c.getresponse().read().decode("utf-8", "replace")
    assert "가뭄 · 관수 판단" in body and "drought_alert" not in body.replace('title="drought_alert"', "")


@pytest.mark.parametrize("bad, word", [({"dry_days": "7"}, "정수"), ({"dry_days": 0}, "정수"), ({"dry_days": True}, "정수"), ([7], "dict"), ({"dry_days": 7, "source": 3}, "source"),
                                       ({"dry_days": 7, "wet_mm": "0.1"}, "wet_mm"), ({"dry_days": 7, "wet_mm": -1}, "wet_mm")])   # [2026-09-29] 선택 키 wet_mm 도 형태를 본다
def test_validator_rejects_malformed_thresholds(bad, word):
    unit = copy.deepcopy(grid_schema.load(grid_schema.GRID_DIR / "jjokpa_autumn.json"))
    unit["stages"][2][SD.DROUGHT_RULES_KEY] = bad
    rep = grid_schema.validate(unit)
    assert not rep.ok and any(word in e and "drought_rules" in e for e in rep.errors), rep.errors


def test_validator_passes_a_threshold_and_the_doc_renders_it():
    import sys
    sys.path.insert(0, str(grid_schema.ROOT / "scripts"))
    import build_grid_doc as bg
    unit = copy.deepcopy(grid_schema.load(grid_schema.GRID_DIR / "jjokpa_autumn.json"))
    unit["stages"][2][SD.DROUGHT_RULES_KEY] = RULES
    assert grid_schema.validate(unit).ok
    assert "가뭄 임계: 무강수 7일 · 합성 — 검사용" in bg.build(unit)
