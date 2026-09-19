# -*- coding: utf-8 -*-
# [M-10 ②] 달력형 위험 경보 — 비대칭(회복 불가는 달력만으로 '주의', 회복 가능은 신호 있을 때만) · 창 · 순서.
from __future__ import annotations

import json
from datetime import date

from ingest import media
from judge import registry as R
from judge import risk_alert as A

SUBJ = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
T24 = date(2026, 9, 18)


def _fc(day: str, tmin=None, rain=0.0, pop=0):
    return {"for_day": day, "observed_at": "2026-09-18T05:00:00+09:00", "source": "external:kma_vilagefcst",
            "resolution": "grid5km:69,107", "values": {"tmin": tmin, "rain_mm": rain, "pop_max": pop}}


def _levels(env):
    return {a["risk"]: a["level"] for a in env.result["alerts"]}


def test_registered_and_consistent_with_every_grid_stage():
    d = R.get("risk_alert")
    assert d and d.revisit_days == 1
    unit = A._load_unit(SUBJ)
    for s in unit["stages"]:
        assert R.check_against_grid(d, s) == [], s["name"]


def test_unrecoverable_gets_calendar_caution_without_data():
    env = A.judge(SUBJ, today=T24)
    assert env.kind == "판단함" and env.grade == "추정"
    lv = _levels(env)
    assert lv["고자리파리 유충"] == "주의"                    # 회복 불가 · 창 안 · 신호 없음 → 달력 주의
    assert "파총채벌레 · 파좀나방" not in lv                   # 회복 가능 · 신호 없음 → 침묵
    assert env.result["watched_recoverable"] >= 2
    assert any("예보 없음" in n for n in env.notes)


def test_next_stage_within_horizon_is_forecast_not_caution():
    env = A.judge(SUBJ, today=T24)                             # 4단계(30일)는 6일 뒤 → 예고
    lv = _levels(env)
    assert lv["과습 · 뿌리 부패(가을 장마)"] == "예고"


def test_heavy_rain_signal_raises_unrecoverable_to_alert():
    fc = [_fc("2026-09-19", rain=30.0), _fc("2026-09-21", rain=25.0)]
    env = A.judge(SUBJ, forecast=fc, today=T24)
    assert _levels(env)["과습 · 뿌리 부패(가을 장마)"] == "경보"
    assert [i.axis for i in env.inputs] == ["anchor", "forecast"]


def test_wet_run_signal_fires_recoverable_only_when_strong():
    weak = [_fc("2026-09-19", pop=80), _fc("2026-09-20", pop=80)]              # 2일 — 임계 3일 미만
    assert "노균병" not in _levels(A.judge(SUBJ, forecast=weak, today=T24))
    strong = weak + [_fc("2026-09-21", pop=90)]
    assert _levels(A.judge(SUBJ, forecast=strong, today=T24))["노균병"] == "경보"


def test_signal_outside_horizon_is_ignored():
    far = [_fc("2026-10-20", tmin=-2.0, rain=80.0)]
    lv = _levels(A.judge(SUBJ, forecast=far, today=T24))
    assert lv.get("과습 · 뿌리 부패(가을 장마)") == "예고"     # 강우 80mm 는 horizon 밖 → 신호 아님


def test_frost_in_harvest_stage():
    today = date(2026, 10, 20)
    assert _levels(A.judge(SUBJ, today=today))["첫 서리 · 한파로 잎 손상"] == "주의"
    fc = [_fc("2026-10-23", tmin=-1.0)]
    assert _levels(A.judge(SUBJ, forecast=fc, today=today))["첫 서리 · 한파로 잎 손상"] == "경보"


def test_harvest_overrun_alert_after_window():
    env = A.judge(SUBJ, today=date(2026, 11, 10))
    assert _levels(env)["수확 지연"] == "경보"


def test_alerts_sorted_alert_first():
    fc = [_fc("2026-09-19", rain=60.0)]
    levels = [a["level"] for a in A.judge(SUBJ, forecast=fc, today=T24).result["alerts"]]
    assert levels == sorted(levels, key={"경보": 0, "주의": 1, "예고": 2}.get)


def test_not_applicable_and_data_gap():
    assert A.judge({"id": "x"}, today=T24).kind == "해당 없음"
    env = A.judge({**SUBJ, "anchor": None}, today=T24)
    assert env.kind == "판단 불가(데이터)" and env.missing[0]["axis"] == "anchor"


def test_before_any_stage_is_not_applicable():
    assert A.judge(SUBJ, today=date(2026, 8, 1)).kind == "해당 없음"    # 기준점 24일 전 — 칸 -7일도 horizon 밖


def _pest(pest, level=None, text=None, proxy=True):
    return {"observed_at": "20260915", "source": "external:ncpms_svc51", "resolution": "region:충청북도|proxy_crop:파",
            "region": "충청북도", "crop_code_crop": "파", "proxy_reason": "쪽파 코드 미확정" if proxy else None,
            "values": {"pest": pest, "level": level, "text": text}}


def test_pest_forecast_raises_unrecoverable_to_alert_with_proxy_note():
    env = A.judge(SUBJ, today=T24, pest=[_pest("고자리파리", level="주의")])
    lv = _levels(env)
    assert lv["고자리파리 유충"] == "경보" and "대리 작물" in [a for a in env.result["alerts"] if a["risk"] == "고자리파리 유충"][0]["basis"]
    assert [i.axis for i in env.inputs] == ["anchor", "pest_regional"]
    assert any("대리 작물" in n for n in env.notes)


def test_pest_forecast_fires_recoverable_only_with_signal_word():
    quiet = [_pest("파총채벌레")]                                       # 수준·본문 없음 → 신호 아님
    assert "파총채벌레 · 파좀나방" not in _levels(A.judge(SUBJ, today=T24, pest=quiet))
    loud = [_pest("파총채벌레", text="발생 증가")]
    assert _levels(A.judge(SUBJ, today=T24, pest=loud))["파총채벌레 · 파좀나방"] == "경보"


def test_pest_forecast_other_pest_does_not_match():
    assert _levels(A.judge(SUBJ, today=T24, pest=[_pest("배추좀나방", level="경보")]))["고자리파리 유충"] == "주의"


def test_envelope_has_no_raw_forecast_values():
    fc = [_fc("2026-09-19", tmin=3.0, rain=60.0, pop=90)]
    dumped = json.dumps(A.judge(SUBJ, forecast=fc, today=T24).to_dict(), ensure_ascii=False)
    assert '"pop_max"' not in dumped and '"tmin"' not in dumped


def test_harvest_delay_alert_stops_after_harvest_event_or_end():
    # [코드 평가 B1 · 2026-09-19] 창을 넘기면 수확 사건이 있어도 시즌 끝까지 매일 '수확 지연' 경보가 나갔다 — 판정기가 사건을 못 봤다
    from datetime import timedelta
    from judge import run as judge_run
    late = date.fromisoformat(SUBJ["anchor"]) + timedelta(days=100)
    assert _levels(A.judge(SUBJ, today=late)).get("수확 지연") == "경보"                       # 사건 없음 → 지연이 맞다
    harvest = {"kind": "event", "type": "수확", "subject": SUBJ["id"], "observed_at": (late - timedelta(days=30)).isoformat(),
               "recorded_at": "2026-11-01T00:00:00", "source": "farmer", "resolution": "cultivation_unit"}
    assert "수확 지연" not in _levels(A.judge(SUBJ, today=late, evts=[harvest]))                 # 수확했다 → 지연 아님
    assert "수확 지연" not in _levels(A.judge({**SUBJ, "status": "종료"}, today=late))          # 단위 종료 → 지연 아님
    future = {**harvest, "observed_at": (late + timedelta(days=5)).isoformat()}
    assert _levels(A.judge(SUBJ, today=late, evts=[future])).get("수확 지연") == "경보"          # 미래 날짜 사건은 아직 아니다
    # 배선: run.all_judgments 가 게이트 통과 사건을 판정기에 넘긴다
    src = open(judge_run.__file__, encoding="utf-8").read()
    blk = src[src.index("def all_judgments"):]
    call = blk[blk.index("risk_alert.judge("):]
    call = call[:call.index(")")]
    assert "evts=" in call, call                                              # 호출형만 고정 — 인자 표현식은 고정하지 않는다
