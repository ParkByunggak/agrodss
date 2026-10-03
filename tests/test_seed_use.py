# -*- coding: utf-8 -*-
# [발행자 전달 2026-10-03 "용도 = 종구 생산. 수확 칸 덮어쓰기 필요"] 이장 결정: 종구(씨알) 생산. 지금 재배 달력은 잎 수확 기준이라 10/14 부터 「수확 지연 — 잎 노화·도복
# — 회복 불가」 가 매일 나갈 형태였다 — 종구에서는 그 상태가 목표다.
#
#   자리   칸의 `by_use: {"종구": {source, …덮어쓸 키…}}` — load_unit 하나가 용도에 맞게 합친다(소비자 전부가 그 한 자리를 지난다)
#   값     종구의 창 · 위험 · 할 일은 지식 — 발행자 몫(apply_grid_value --stage 5 6 --key by_use)
#   문     값이 오기 전까지 용도가 종구이고 수확 칸 이후에 덮어쓰기가 없으면 — 수확 시기는 판단 불가(지식), 위험 경보는 그 칸을 내지 않고 메모로 말하고,
#          계획표는 그 칸의 할 일을 두지 않고 메모로 말한다 · 출하는 해당 없음(씨알을 남긴다). 틀린 경보보다 빈 자리가 낫다 — 그리고 빈 자리는 이유를 말한다.
#   관문   by_use 는 용도 이름 · source · 덮어쓸 수 있는 키만, 그리고 **합친 격자가 같은 검증을 지난다**(덮어쓴 창·위험·할 일도 같은 관문)
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from grid import schema as GS
from ingest import media, parcels
from judge import harvest_timing as HT
from judge import plan, plan_vs_actual as PVA
from judge import risk_alert as RA
from judge import stage_decisions as SD

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
D56, D36, D75 = date(2026, 10, 20), date(2026, 9, 30), date(2026, 11, 8)      # 칸 5 · 칸 4 · 칸 5 창 지남


def _subject(use: str | None):
    s = dict(next(x for x in media.load_subjects() if x["id"] == SID))
    if use is not None:
        s["use"] = use
    return s


def _unit_json():
    return json.loads((ROOT / "data" / "grid" / "jjokpa_autumn.json").read_text(encoding="utf-8"))


# ── 용도 이름 ──
def test_use_key_reads_the_word_not_the_exact_label():
    for t in ("종구 생산", "종구용", "씨알 종구로 남긴다"):
        assert GS.use_key(t) == "종구", t
    for t in ("시험 재배(자가)", "판매", "몰 납품", None, ""):
        assert GS.use_key(t) is None, t
    assert "종구" in dict(parcels.FIELD_LABELS)["use"] and "종구" in SD.SELF_USE_WORDS


# ── 문 — 값이 오기 전 ──
def test_a_seed_bulb_unit_gets_no_leaf_harvest_window_but_everything_before_the_harvest_cell_is_unchanged():
    base, seed = _subject(None), _subject("종구 생산")
    u_base, _ = GS.load_unit(base)
    u_seed, _ = GS.load_unit(seed)
    assert u_base["_use"] is None and u_seed["_use"] == "종구" and u_seed["_use_overridden"] == []
    ho = GS.harvest_order(u_seed)
    assert ho == 5 and [s["order"] for s in u_seed["stages"] if GS.use_gap(u_seed, s)] == [5, 6]
    e = HT.judge(seed, today=D56)
    assert e.kind == "판단 불가(지식)" and "종구 재배의 수확 때는 재배 달력에 아직 없습니다" in e.result["summary"] and "by_use" in e.result["why"]
    assert HT.judge(base, today=D56).kind == "판단함"                                # 잎 수확(자가)은 그대로


def test_no_harvest_delay_or_leaf_risk_alert_goes_to_a_seed_bulb_unit_and_the_note_says_why():
    seed = _subject("종구 생산")
    e = RA.judge(seed, today=D75)                                                      # 창(50~70)을 넘긴 날 — 잎 기준이면 「수확 지연」 경보
    assert e.kind == "판단함" and not any(a["risk"] == "수확 지연" for a in e.result["alerts"])
    assert e.result["use_gap_stages"] == ["6. 수확 후 · 후작"]                           # 75일째 — 열린 칸은 6, 수확 지연은 칸 5 의 것(둘 다 안 낸다)
    e5 = RA.judge(seed, today=D56)                                                     # 56일째 — 칸 5 가 열려 있고 그 위험(서리 · 지연)을 안 낸다
    assert e5.result["use_gap_stages"] == ["5. 수확"] and not any(a["stage"].startswith("5.") for a in e5.result["alerts"])
    assert any(a["stage"].startswith("5.") for a in RA.judge(_subject(None), today=D56).result["alerts"])   # 잎 수확은 칸 5 위험(서리 주의)을 낸다
    assert any("종구" in n and "by_use" in n for n in e.notes)
    base = RA.judge(_subject(None), today=D75)
    assert any(a["risk"] == "수확 지연" for a in base.result["alerts"])                 # 반대편 — 잎 수확은 그대로 경보
    e4 = RA.judge(seed, today=D36)                                                     # 칸 4(수확 전)는 용도와 무관 — 과습 경보 그대로
    assert any("과습" in a["risk"] for a in e4.result["alerts"])


def test_the_plan_leaves_the_seed_bulb_harvest_cells_empty_and_says_so():
    u_seed, _ = GS.load_unit(_subject("종구 생산"))
    rows = plan.from_unit(u_seed, date(2026, 8, 25), "유기")
    assert rows and all(not r["stage"].startswith(("5.", "6.")) for r in rows)
    u_base, _ = GS.load_unit(_subject(None))
    assert any(r["stage"].startswith("5.") for r in plan.from_unit(u_base, date(2026, 8, 25), "유기"))
    e = PVA.judge(_subject("종구 생산"), today=D56, evts=[], videos=[], reasons=[], notes=[])
    assert e.kind == "판단함" and any("칸 5(수확)의 할 일은" in n and "by_use 대기" in n for n in e.notes)


def test_ship_or_store_is_not_applicable_for_seed_bulbs():
    s = dict(_subject("종구 생산"), mall_supply=True)
    assert SD.judge_ship_or_store(s, D56).kind == "해당 없음"


# ── 값이 오면 — 자리와 관문 ──
def _with_override(unit: dict, use: str = "종구", ov: dict | None = None) -> dict:
    s5 = next(s for s in unit["stages"] if s["order"] == 5)
    s5[GS.BY_USE_KEY] = {use: ov if ov is not None else {
        "source": "검사용 합성 — 값은 발행자 몫", "name": "종구 비대 · 수확",
        "window": {"from_day": 60, "to_day": 95, "basis": "anchor"},
        "risks": [{"name": "인경 부패(과습)", "trigger": "검사", "recoverable": False, "alert": "oversignal_ok", "axes": ["precip", "soil_water"], "source": "검사용 합성"}]}}
    return unit


def test_an_override_with_a_source_merges_into_the_unit_and_only_for_that_use(tmp_path, monkeypatch):
    unit = _with_override(_unit_json())
    assert GS.validate(unit).errors == []
    merged = GS.apply_use(unit, "종구")
    s5 = next(s for s in merged["stages"] if s["order"] == 5)
    assert s5["window"]["to_day"] == 95 and s5["name"] == "종구 비대 · 수확" and [r["name"] for r in s5["risks"]] == ["인경 부패(과습)"]
    assert GS.BY_USE_KEY not in s5 and s5["_use_source"].startswith("검사용") and merged["_use_overridden"] == [5]
    assert not GS.use_gap(merged, s5) and GS.use_gap(merged, next(s for s in merged["stages"] if s["order"] == 6))   # 칸 6 은 아직
    plain = GS.apply_use(unit, None)
    assert next(s for s in plain["stages"] if s["order"] == 5)["window"]["to_day"] == 70                        # 용도 없으면 잎 기준 그대로
    bad = _with_override(_unit_json(), ov={"source": "x", "order": 9, "window": {"from_day": 60, "to_day": 95, "basis": "anchor"}})
    s5b = next(s for s in GS.apply_use(bad, "종구")["stages"] if s["order"] == 5)                                # 덮어쓸 수 없는 키(order)는 합치지 않는다 — 검증기와 별개의 관문
    assert s5b["order"] == 5 and s5b["window"]["to_day"] == 95


def test_an_override_without_a_source_or_with_an_unknown_use_or_key_does_not_pass():
    unit = _with_override(_unit_json(), ov={"window": {"from_day": 60, "to_day": 95, "basis": "anchor"}})
    assert any("source" in e for e in GS.validate(unit).errors)
    unit = _with_override(_unit_json(), use="가공")
    assert any("모르는 용도" in e for e in GS.validate(unit).errors)
    unit = _with_override(_unit_json(), ov={"source": "x", "order": 9})
    assert any("덮어쓸 수 없는 키" in e for e in GS.validate(unit).errors)
    unit = _with_override(_unit_json(), ov={"source": "x", "window": {"from_day": 95, "to_day": 60, "basis": "anchor"}})
    assert any(e.startswith("[by_use 종구]") and "window" in e for e in GS.validate(unit).errors)          # 합친 격자도 같은 관문


def test_with_the_override_in_place_the_seed_bulb_unit_gets_its_own_window(monkeypatch, tmp_path):
    unit = _with_override(_unit_json())
    p = tmp_path / "jjokpa_autumn.json"
    p.write_text(GS.dump_text(unit), encoding="utf-8")
    monkeypatch.setattr(GS, "unit_path", lambda uid: p)
    e = HT.judge(_subject("종구 생산"), today=D56)
    assert e.kind == "판단함" and e.result["window_end"] == "2026-11-28"                # 8-25 + 95
    r = RA.judge(_subject("종구 생산"), today=D75)
    assert r.result["use_gap_stages"] == ["6. 수확 후 · 후작"] and not any(a["risk"] == "수확 지연" for a in r.result["alerts"])


def test_the_real_grid_has_no_override_yet_and_the_doc_renders_one_when_present():
    unit = _unit_json()
    assert all(GS.BY_USE_KEY not in s for s in unit["stages"])                          # 값은 발행자 몫 — 세션이 지어 넣지 않았다
    from scripts import build_grid_doc as BD
    doc = BD.build(_with_override(unit))
    assert "용도 '종구' 덮어쓰기: name · risks · window · 검사용 합성 — 값은 발행자 몫" in doc
