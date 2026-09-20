# -*- coding: utf-8 -*-
# [M-10 ① · M-8 · I-1] 수확 시기 — 봉투 8종 · 등록부 거부 · 판별 순서 · 4층 격리.
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from ingest import media
from judge import envelope as E
from judge import harvest_timing as H
from judge import registry as R

SUBJ = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
TODAY = date(2026, 9, 18)


# ── 봉투 ────────────────────────────────────────────────────────────────────────
def test_envelope_rejects_unknown_kind_and_missing_grade():
    with pytest.raises(ValueError):
        E.Envelope("대충", "x", "s", "t")
    with pytest.raises(ValueError):
        E.Envelope("판단함", "x", "s", "t")                      # 등급 없음
    with pytest.raises(ValueError):
        E.Envelope("판단함", "x", "s", "t", grade="관측", missing=[{"axis": "a"}])   # missing 은 데이터 미비에만


def test_weakest_grade():
    assert E.weakest(["계산", "관측", "추정"]) == "추정" and E.weakest(["계산"]) == "계산"


# ── 등록부 ──────────────────────────────────────────────────────────────────────
def test_registry_refuses_without_rule_or_required():
    with pytest.raises(R.RegistrationError, match="판정 규칙"):
        R.register(R.Decision("x", "x", ("anchor",), (), (), "  ", None))
    with pytest.raises(R.RegistrationError, match="필요 축"):
        R.register(R.Decision("y", "y", (), (), (), "규칙", None))
    with pytest.raises(R.RegistrationError, match="I-4 밖"):
        R.register(R.Decision("z", "z", ("moon",), (), (), "규칙", None))
    assert R.get("x") is None and R.get("y") is None


def test_harvest_timing_registered_and_consistent_with_grid():
    d = R.get("harvest_timing")
    assert d and d.required_axes == ("anchor",) and "humidity_air" in d.forbidden_axes
    unit = H._load_unit(SUBJ)
    assert R.check_against_grid(d, H._harvest_stage(unit)) == []


# ── 판단함 ──────────────────────────────────────────────────────────────────────
def test_judges_window_from_anchor_and_grid():
    env = H.judge(SUBJ, today=TODAY)
    assert env.kind == "판단함" and env.grade == "추정"          # 격자가 추론 초안 → 추정을 넘지 못한다
    r = env.result
    # [발행자 몫 ③ 미리 걷기 2026-09-20] 전에는 ("2026-10-14", "2026-11-03") 을 박아 두었다 — 수확 창은 **검토지 W 의 답이
    # 바꿀 지식**이라, 답이 오는 날 이 검사도 손봐야 했다(대장이 "격자 한 수정으로 끝난다"고 적은 것과 어긋난다).
    # 검사가 지킬 계약은 값이 아니라 **"창은 기준점 + 격자 창에서 나온다"** 다 — 기대값을 격자에서 계산한다.
    w = H._harvest_stage(H._load_unit(SUBJ))["window"]
    a = date.fromisoformat(SUBJ["anchor"])
    assert (r["window_start"], r["window_end"]) == ((a + timedelta(days=w["from_day"])).isoformat(),
                                                    (a + timedelta(days=w["to_day"])).isoformat())
    assert r["error_days"] == (w["to_day"] - w["from_day"]) / 2
    assert r["days_since_anchor"] == (TODAY - a).days and r["position"] == "창 이전"
    assert env.revisit_at == "2026-09-25" and env.consumer_visible is False
    assert [i.axis for i in env.inputs] == ["anchor"] and env.caps == []
    assert any("품종 미확인" in n for n in env.notes)


def test_forecast_frost_becomes_cap_only_inside_window():
    fc = [
        {"for_day": "2026-10-20", "observed_at": "2026-09-18T05:00:00+09:00", "source": "external:kma_vilagefcst",
         "resolution": "grid5km:69,107", "values": {"tmin": -1.0}},
        {"for_day": "2026-09-20", "observed_at": "2026-09-18T05:00:00+09:00", "source": "external:kma_vilagefcst",
         "resolution": "grid5km:69,107", "values": {"tmin": -3.0}},     # 창 밖 — 상한 제약 아님
    ]
    env = H.judge(SUBJ, forecast=fc, today=TODAY)
    assert len(env.caps) == 1 and "2026-10-20" in env.caps[0]["basis"]
    assert [i.axis for i in env.inputs] == ["anchor", "forecast"]


def test_position_after_window():
    assert H.judge(SUBJ, today=date(2026, 11, 10)).result["position"] == "창 지남"


# ── 판별 순서 ──────────────────────────────────────────────────────────────────
def test_not_applicable_without_grid_unit():
    env = H.judge({"id": "s", "anchor": "2026-08-25"}, today=TODAY)
    assert env.kind == "해당 없음"


def test_knowledge_gap_precedes_data_gap(tmp_path, monkeypatch):
    # 격자 창도 없고 기준점도 없을 때 → 판단 불가(지식) 가 먼저다
    unit = H._load_unit(SUBJ)
    for s in unit["stages"]:
        if "harvest_timing" in s["decisions"]:
            s.pop("window")
    p = tmp_path / "jjokpa_autumn.json"
    p.write_text(json.dumps(unit, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(H.grid_schema, "GRID_DIR", tmp_path)
    env = H.judge({**SUBJ, "anchor": None}, today=TODAY)
    assert env.kind == "판단 불가(지식)"


def test_data_gap_when_anchor_missing():
    env = H.judge({**SUBJ, "anchor": None}, today=TODAY)
    assert env.kind == "판단 불가(데이터)" and env.missing[0]["axis"] == "anchor" and "농가" in env.missing[0]["who_can_fill"]


# ── 4층 격리: 봉투에 1층 값이 실리지 않는다 ──────────────────────────────────────
def test_envelope_carries_no_raw_layer1_values():
    fc = [{"for_day": "2026-10-20", "observed_at": "x", "source": "s", "resolution": "g",
           "values": {"tmin": -1.0, "tmax": 9.0, "pop_max": 40}, "hourly_tmp": {"0600": 1.0}}]
    env = H.judge(SUBJ, forecast=fc, today=TODAY)
    dumped = json.dumps(env.to_dict(), ensure_ascii=False)
    assert "hourly_tmp" not in dumped and "pop_max" not in dumped and '"tmax"' not in dumped
