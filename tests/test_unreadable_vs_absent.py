# -*- coding: utf-8 -*-
# [U-21 2026-09-21] 앞 회차에 '버린 사실'은 `/changes` 에 남겼지만 **판정은 여전히 못 들었다** — 카드는 그대로
# "처방 정본 미도착" 이라고 했다. 그러면 발행자는 **이미 받은 것을 다시 받으러** 간다.
#
#   없다            아직 조회한 적 없다            → 판단 불가(**지식**) · 정본이 안 왔다
#   있는데 못 읽었다  저장된 파일이 깨졌다           → 판단 불가(**데이터**) · 고치면 바뀐다
#
# 가르는 기준은 I-1 §2-6 이다: **채우면 바뀌는가.** 깨진 파일은 다시 받으면 바뀌므로 데이터 미비이고, 그래서
# `missing` 을 채울 수 있다(봉투가 그것을 강제한다 — missing 은 판단 불가(데이터)에서만).
#
# 그리고 이 회차의 자기 정정: 앞 회차 보고에서 이것을 *"발행자가 밭에서 돌아온 뒤"* 로 미뤘는데, 재 보니 실사용 입력에
# 매인 것이 아니라 **합성 파일로 검증되는 코드 계약**이었다. 발행자가 지적한 *"배선 결함을 지식 결함으로 읽으면 사람
# 몫으로 넘어가 영영 안 닫힌다"* 를 내가 그대로 했다.
from __future__ import annotations

import json
from datetime import date

import pytest

from ingest import dropped, media, parcels, soil_store
from judge import run as judge_run, stage_decisions as SD

SID = "p001-jjokpa-2026f"
TODAY = date(2026, 8, 30)        # 밑거름 창(칸 1: 기준점 8/25 ~ +14일) **안** — 창 밖이면 '해당 없음'이라 처방 갈래에 닿지 않는다
TD_TODAY = date(2026, 9, 21)     # 웃거름 1회 창(칸 3) 안


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    monkeypatch.setenv("AGRODSS_SOIL_DIR", str(tmp_path))
    dropped.clear()
    yield
    dropped.clear()


def _subject(soil_chem: bool = True) -> dict:
    """밑거름은 `soil_chem` 이 **앞 분기**다(없으면 거기서 판단 불가(데이터)로 끝나 처방 갈래에 닿지 않는다).
    그 순서 자체가 옳으므로(검정값 없이 처방을 논하지 않는다) 검사는 그 앞 분기를 지나게 해 두고 **다음 갈래**를 본다."""
    raw = next(s for s in media.load_subjects() if s["id"] == SID)
    s = parcels.enrich_subject(raw, parcels.by_id("p001"))
    if soil_chem:
        s["soil_chem"] = {"ph": 6.2}          # 값은 여기서 쓰이지 않는다 — 축이 **있다**는 것만 필요하다
        s["soil_exam_at"] = "2026-08-20"
    return s


def _broken(name: str = "p001_prescription_07027.json") -> str:
    p = soil_store.soil_dir()
    p.mkdir(parents=True, exist_ok=True)
    (p / name).write_text(json.dumps({"record": {"kind": "reference.fertilizer_prescription", "id": "자리 없는 필드만"}}),
                          encoding="utf-8")
    return name


def test_the_store_reports_what_it_could_not_read_alongside_what_it_could():
    name = _broken()
    ok, bad = soil_store._scan_prescriptions("p001")
    assert ok == [] and bad == [name]
    assert soil_store.prescriptions_for("p001") == [] and soil_store.unreadable_for("p001") == [name]


def test_base_fertilization_says_data_missing_not_knowledge_missing_when_the_file_is_broken():
    """원 결함: 둘 다 '판단 불가(지식) — 정본 미도착'. 그러면 이미 받은 것을 다시 받으러 간다."""
    name = _broken()
    e = SD.judge_base_fertilization(_subject(), TODAY, prescriptions=[], unreadable=[name])
    assert e.kind == "판단 불가(데이터)"                                  # 고치면 바뀐다(I-1 §2-6)
    assert "있는데 읽지 못했다" in e.result["why"] and "없는 것이 아니다" in e.result["why"]
    assert e.result["unreadable"] == [name]
    assert e.missing and name in e.missing[0]["who_can_fill"]            # 누가 어떻게 메우는지도 말한다


def test_nothing_stored_at_all_still_says_knowledge_missing():
    """[게이트는 양방향] 넓히면서 원래 답까지 바꾸면 안 된다 — 정말 없을 때는 여전히 지식 미비다."""
    e = SD.judge_base_fertilization(_subject(), TODAY, prescriptions=[], unreadable=[])
    assert e.kind == "판단 불가(지식)" and "아직 이 필지에 없다" in e.result["why"]
    assert not e.missing


def test_top_dressing_keeps_judging_the_window_but_names_the_broken_file_for_the_amount():
    """웃거름은 창·자재를 계속 '판단함' 으로 낸다(양만 못 낸다) — 그래서 등급이 아니라 **문면**으로 가른다."""
    name = _broken()
    e = SD.judge_top_dressing(_subject(), "top_dressing_1", TD_TODAY, evts=[], prescriptions=[], unreadable=[name])
    assert e.kind == "판단함"
    assert "판단 불가(데이터)" in e.result["amount"] and name in e.result["amount"] and "없는 것이 아니다" in e.result["amount"]
    assert "저장된 처방이 깨져" in e.result["summary"]                     # 카드에서 읽히는 줄에서도 갈린다(표현 층)
    bare = SD.judge_top_dressing(_subject(), "top_dressing_1", TD_TODAY, evts=[], prescriptions=[], unreadable=[])
    assert "판단 불가(지식)" in bare.result["amount"] and "미도착" in bare.result["amount"]      # 반대편도 그대로
    assert "양은 정본 대기" in bare.result["summary"]


def test_the_screen_path_carries_the_unreadable_signal_all_the_way():
    """[§7.5 관문의 입력] 판정이 받을 자리를 만들어도 **호출부가 안 넘기면** 아무 일도 안 일어난다.

    화면 경로로 본다. 밑거름은 검정값이 앞 분기라(격리 저장소엔 검정값이 없다) 웃거름 카드로 잰다 —
    그쪽은 기준점·인증만 필요해서 **처방 갈래까지 실제로 내려간다**.
    """
    name = _broken()
    envs = judge_run.judgments_for(SID, today=TD_TODAY)
    top = next(e for e in envs if e.decision_id == "top_dressing_1")
    assert name in top.result["amount"] and "있는데 읽지 못했다" in top.result["amount"]
    assert "저장된 처방이 깨져" in top.result["summary"]
    assert any(d["path"] == name for d in dropped.all_drops())           # 같은 읽기가 /changes 에도 남는다
