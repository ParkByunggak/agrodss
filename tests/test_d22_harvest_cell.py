# -*- coding: utf-8 -*-
# [D-22 발행자 맞다 2026-10-03 "추론 표시 그대로 올라갔으니 맞다 한 번입니다"] 수확 칸에는 가뭄 판단을 두지 않는다 — 격자 수확 칸 drought_rules.dry_days = "N/A".
#
#   비운 것 ≠ 두지 않기로 한 것(U-21 · 없다와 못 읽었다를 가른다). 전에는 10-15 부터 가뭄 답이 「기준이 없습니다」(판단 불가(지식))로 돌아갔다.
#   결정도 지식이라 N/A 에도 출처가 필수다(출처 없는 N/A 는 검증을 못 지난다). 답(해당 없음)의 why 에 그 출처가 실린다 · 문서는 「없음」 으로 적는다.
#   화면: 결정 화면의 D-22 카드는 답한 카드로 남고(decisions.DECIDED) 측정(열린 행)에서는 빠진다 · 반복 상한에 닿은 물음은 모르겠다와 같은 자리(발행자 2026-10-03).
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from frontend import chat_pages, words
from grid import schema as GS
from ingest import asks, chat, decisions as dc, media, questions
from judge import stage_decisions as SD

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)


def _subject():
    return media.load_subjects()[0]


def test_the_real_grid_puts_na_with_a_source_on_the_harvest_cell_and_nowhere_else():
    unit = json.loads((ROOT / "data" / "grid" / "jjokpa_autumn.json").read_text(encoding="utf-8"))
    by = {s["order"]: s for s in unit["stages"]}
    dr = by[5].get(GS.DROUGHT_RULES_KEY)
    assert dr and dr["dry_days"] == GS.NA and "D-22" in dr["source"] and "맞다" in dr["source"] and "추론" in dr["source"]
    assert by[3][GS.DROUGHT_RULES_KEY]["dry_days"] == 7 and by[4][GS.DROUGHT_RULES_KEY]["dry_days"] == 7      # 칸 3·4 는 그대로
    assert GS.DROUGHT_RULES_KEY not in by[6]                                                                   # 칸 6 은 water 자체가 N/A — 임계 키 없음
    assert GS.validate(unit).errors == []


def test_na_without_a_source_does_not_pass_and_an_empty_cell_is_still_different():
    unit = json.loads((ROOT / "data" / "grid" / "jjokpa_autumn.json").read_text(encoding="utf-8"))
    s5 = next(s for s in unit["stages"] if s["order"] == 5)
    s5[GS.DROUGHT_RULES_KEY] = {"dry_days": GS.NA}
    errs = GS.validate(unit).errors
    assert any("source" in e for e in errs), errs
    s5[GS.DROUGHT_RULES_KEY] = {"dry_days": "없음", "source": "x"}                  # N/A 가 아닌 문자열은 비운 것도 결정도 아니다
    assert any("dry_days" in e for e in GS.validate(unit).errors)


def test_on_a_harvest_day_the_drought_answer_is_not_applicable_and_names_the_decision():
    s = _subject()
    e = SD.judge_drought_alert(s, date(2026, 10, 20), evts=[], observations=[], obs_rain=None, obs_rain_why="")     # 기준점 후 56일 — 칸 5
    assert e.kind == "해당 없음" and "가뭄 · 관수 판단을 두지 않습니다" in e.result["summary"] and "D-22" in e.result["why"]
    assert "기준이 없습니다" not in e.result["summary"]                             # 전의 답(판단 불가(지식))이 아니다
    e4 = SD.judge_drought_alert(s, date(2026, 9, 28), evts=[], observations=[], obs_rain=None, obs_rain_why="")    # 칸 4 는 그대로 판단 불가(데이터)
    assert e4.kind == "판단 불가(데이터)"


def test_no_observation_is_fetched_for_the_harvest_cell():
    from judge import run as judge_run
    assert judge_run.drought_days_needed(_subject(), date(2026, 10, 20)) == 0 and judge_run.drought_days_needed(_subject(), date(2026, 9, 28)) == 7


def test_the_grid_doc_says_none_not_a_number_for_the_harvest_cell():
    doc = (ROOT / "docs" / "grid_jjokpa_autumn.md").read_text(encoding="utf-8")
    assert "가뭄 임계: 없음(이 칸에는 가뭄 판단을 두지 않는다 · N/A)" in doc and doc.count("가뭄 임계: 무강수 7일") == 2


# ── 결정 화면 ──
def test_the_decided_card_stays_on_the_screen_without_a_form_and_is_out_of_the_measurement():
    html = chat_pages.decisions_main()
    i = html.index("<b>D-22 · ")
    card = html[i:html.index('<div class="card dec">', i + 1) if '<div class="card dec">' in html[i + 1:] else len(html)]
    assert "결정됨: 맞다 — 발행자 2026-10-03" in card and 'name="verdict"' not in card and "이 답 지우기" not in card
    assert "D-22" in dc.DECIDED and "D-23" in dc.IDS and dc.item("D-23")["basis"] == dc.BASIS_INFERRED and "전자" in dc.item("D-23")["basis_from"]


def test_stopped_asks_show_next_to_unknowns_as_the_same_signal(monkeypatch):
    monkeypatch.setattr(questions, "REPEAT_CAP", 1)
    chat.send(SID, "풀 뽑았다", today=date(2026, 9, 28), now=NOW)           # 배수를 한 번 묻는다(상한 1)
    chat.send(SID, "풀 뽑았다", today=date(2026, 9, 28), now=NOW)           # 상한에 닿아 건너뛴다 → 멈춤 기록
    sm = dc.summary({})
    assert [r["axis"] for r in sm["stopped_asks"]] == ["soil_water"] and sm["stopped_asks_why"] is None
    html = chat_pages.decisions_main()
    visible = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html))
    assert "더 묻지 않는 것 1건" in visible and words.axis("soil_water") in visible and "모르겠다와 같은 신호" in visible
    asks.path().write_text("{bad", encoding="utf-8")
    sm2 = dc.summary({})
    assert sm2["stopped_asks"] == [] and sm2["stopped_asks_why"]                 # 못 읽으면 0 이 아니라 이유
    assert "물은 것 기록을 못 읽었다" in chat_pages.decisions_main()
