# -*- coding: utf-8 -*-
# [WO-ASK-01 §2 · §5-1 · 발행자 2026-10-03 "명령줄·환경변수를 말하는 요구 문장이 농가에게 가고 있습니다 … 래칫 하나로 지금 잡아두는 것이 맞습니다"]
#
# 요구 문장(판단 불가(데이터)의 `missing[].who_can_fill`)은 코드로 재니(2026-10-02) 17곳이 제각각이었고 3곳이 CLI/.env 를 농가에게
# 말했다. 처방은 정본 한 자리(`judge.need.need`) — 누가 · 무엇 · 어디서 · 왜 지금. 이 검사는 셋을 본다.
#   ① 호출형 — judge/ 안에서 요구 항목을 손으로 짓는 자리가 0 (형태 독립 · 인자 표현식은 안 박는다)
#   ② 관문 — 농가 문장에 개발자 토큰이 들어오면 need() 가 거부한다 · 자리(PLACES)가 없으면 거부 · 읽는 판정이 없는 필지 값(§5-1)이면 거부
#   ③ 배선 — 날짜를 가로질러 실제 봉투를 내고, 농가에게 가는 요구 문장과 요약에 개발자 토큰이 없고 요구 문장마다 자리가 있다
#      (함수만 검증하면 호출부가 안 쓰는 결함이 남는다 — "검증 대상은 함수가 아니라 배선")
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from ingest import media, parcels
from judge import need as N
from judge import run as judge_run

ROOT = Path(__file__).resolve().parent.parent
BUILDER = ("need.py", "envelope.py")          # 정본 자리와 자료형 선언 — 여기만 "who_can_fill" 리터럴을 둔다
DAYS = (date(2026, 8, 20), date(2026, 9, 1), date(2026, 9, 21), date(2026, 10, 3), date(2026, 10, 20), date(2026, 11, 20))


# ── ① 호출형 ──
def test_every_requirement_sentence_is_built_in_one_place():
    raw = {}
    for p in sorted((ROOT / "judge").glob("*.py")):
        if p.name in BUILDER:
            continue
        n = len(re.findall(r'"who_can_fill"\s*:', p.read_text(encoding="utf-8")))
        if n:
            raw[p.name] = n
    assert raw == {}, f"요구 문장을 손으로 짓는 자리: {raw} — judge.need.need() 로 만든다(누가 · 무엇 · 어디서 · 왜 지금)"


# ── ② 관문 ──
def test_the_builder_refuses_developer_tokens_in_the_farmer_sentence():
    for bad in ("python -m ingest.fertilizer <주소> 로 받는다", ".env PSIS_API_KEY 를 넣는다", "--probe 로 확인", "API 키 투입"):
        with pytest.raises(N.NeedError):
            N.need("soil_chem", "발행자", bad, "publisher", "이유")
    ok = N.need("soil_chem", "발행자", "토양 검정값", "publisher", "밑거름 양은 검정값으로 계산한다", detail="python -m ingest.fertilizer <주소>")
    assert "python" not in ok["who_can_fill"] and ok["detail"].startswith("python -m")       # 정확한 명령은 detail 로(정확함은 안 버린다)
    assert ok["where"] == N.PLACES["publisher"] and ok["why_now"] == "밑거름 양은 검정값으로 계산한다"


def test_the_builder_requires_a_place_a_known_asker_and_both_halves():
    with pytest.raises(N.NeedError):
        N.need("anchor", "농가", "심은 날", "nowhere", "이유")
    with pytest.raises(N.NeedError):
        N.need("anchor", "누군가", "심은 날", "chat", "이유")
    with pytest.raises(N.NeedError):
        N.need("anchor", "농가", "심은 날", "chat", "  ")
    with pytest.raises(N.NeedError):
        N.need("anchor", "농가", "", "chat", "이유")


def test_the_builder_refuses_a_parcel_value_no_judgment_reads():
    """§5-1 — 읽는 판정이 없는 필지 값(토성 · 경사 · 관수 시설 …)은 농가에게 요구하지 않는다(소비자 0 을 묻는 것은 헛걸음).
    배수는 결정 ①(2026-10-03)로 과습 근거가 읽으므로 **통과한다** — 막는 것을 검사하면 통과하는 것도 검사한다."""
    for f in parcels.FIELDS_STORED_ONLY:
        with pytest.raises(N.NeedError):
            N.need("soil_water", "농가", f"{parcels.FIELD_WORDS[f]} 한 줄", "parcel", "이유")
    assert "drainage" in parcels.FIELDS_READ_BY_JUDGMENT
    assert "배수" in N.need("soil_water", "농가", "배수(좋음 · 보통 · 나쁨)", "parcel", "과습 근거에 실린다")["who_can_fill"]
    assert set(parcels.FIELD_WORDS) >= set(parcels.input_fields())        # 농가 말이 없는 입력 필드가 없다 — 새 필드는 말부터


def test_every_source_reason_keeps_setup_names_in_the_tail(monkeypatch):
    """원천을 못 받은 이유(judge.run.gather_*)는 농가 요약까지 간다 — 열쇠·모듈 이름은 `[설정: …]` 꼬리에만. 주입 H(열쇠 이름을 꼬리 밖에)가
    배선 검사를 통과했다: 이 환경은 좌표가 없어 열쇠 갈래를 안 탄다(§7.1 2번 — 검사가 그 배선을 안 봤다). 그래서 갈래를 **직접** 탄다 —
    env 삭제가 아니라 열쇠 함수를 비워서(발행자 PC 에 열쇠가 있어도 원천을 부르지 않는다)."""
    from ingest import kma, ncpms
    monkeypatch.setattr(kma, "fcst_key", lambda: "")
    monkeypatch.setattr(kma, "hub_key", lambda: "")
    monkeypatch.setattr(ncpms, "api_key", lambda: "")
    s0 = dict(media.load_subjects()[0], lat=36.75, lon=127.98)
    today = date(2026, 9, 21)
    reasons = [judge_run.gather_forecast(s0)[1], judge_run.gather_mid(s0)[1], judge_run.gather_pest(s0, today)[1],
               judge_run.gather_obs_rain(s0, today)[1], judge_run.gather_outlook(today)[1],
               judge_run.gather_forecast(dict(s0, lat=None, lon=None))[1], judge_run.gather_obs_rain(dict(s0, lat=None, lon=None), today)[1]]
    for r in reasons:
        assert r, reasons
        plain = N.plain_reason(r)
        hit = [t for t in N.DEV_TOKENS if t in plain]
        assert not hit, f"농가 줄에 {hit} — {r!r}"
    assert sum("[설정:" in r for r in reasons) >= 4                      # 정확한 이름은 버리지 않았다 — 꼬리에 있다


def test_plain_reason_strips_only_the_setup_tail():
    assert N.plain_reason("예보 조회 열쇠가 발행자 PC 설정에 없다 [설정: .env KMA_FORECAST_API_KEY]") == "예보 조회 열쇠가 발행자 PC 설정에 없다"
    assert N.plain_reason("권역을 못 찾았다") == "권역을 못 찾았다" and N.plain_reason(None) is None


# ── ③ 배선 ──
def _farmer_lines(e) -> list[str]:
    out = [m["who_can_fill"] for m in (e.missing or [])]
    if e.kind != "판단함" and (e.result or {}).get("summary"):
        out.append(e.result["summary"])
    return out


@pytest.mark.parametrize("today", DAYS)
def test_what_reaches_the_farmer_names_a_place_and_no_setup(today):
    for _, envs, _ in judge_run.all_judgments(today=today):
        for e in envs:
            for m in (e.missing or []):
                assert "어디서:" in m["who_can_fill"] and any(p in m["who_can_fill"] for p in N.PLACES.values()), (e.decision_id, m)
                assert "왜 지금:" in m["who_can_fill"], (e.decision_id, m)
            for line in _farmer_lines(e):
                hit = [t for t in N.DEV_TOKENS if t in line]
                assert not hit, f"{e.decision_id} {today}: 농가 줄에 {hit} — {line!r}"


def test_without_a_sowing_date_every_judgment_asks_for_it_with_one_sentence(monkeypatch):
    """심은 날은 아홉 판정이 요구한다 — 문장은 하나(need_anchor)이고 '왜 지금' 만 판정마다 다르다."""
    raw = [dict(s) for s in media.load_subjects()]
    for s in raw:
        s.pop("anchor", None)
    monkeypatch.setattr(media, "load_subjects", lambda: raw)
    asked = {}
    for _, envs, _ in judge_run.all_judgments(today=date(2026, 9, 21)):
        for e in envs:
            for m in (e.missing or []):
                if m["axis"] == "anchor":
                    asked[e.decision_id] = m["who_can_fill"]
    assert len(asked) >= 8, sorted(asked)
    assert len({v.split(" · 왜 지금:")[0] for v in asked.values()}) == 1, asked          # 누가 · 무엇 · 어디서 는 한 문장
    assert len({v.split(" · 왜 지금:")[1] for v in asked.values()}) >= 5, asked          # 열리는 판단은 제각각 말한다
