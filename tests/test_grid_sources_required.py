# -*- coding: utf-8 -*-
# [2026-10-01 · 출처 규율의 뿌리] "출처가 추론이면 그 표시가 답까지 간다"(D-20 · 격자 출처 전수)는 **출처가 적혀 있을 때**만 성립한다. 실측(2026-10-01):
# 검증기가 unit.source 만 요구하고 unit.confidence · drought_rules.source · symptom_rules[].source 는 안 봤다 — 출처 없는 값이 들어오면 답이 '확신 ?' ·
# '적히지 않음' 으로 나가고, 그 뒤엔 아무도 그것이 추론인지 모른다. 계약: 출처 없는 규칙은 검증을 못 지난다 · 지금 격자는 지난다(전부 적혀 있다).
from __future__ import annotations

import copy
from datetime import date, timedelta

import pytest

from grid import schema
from ingest import media
from judge import stage_decisions as SD

JJ = schema.GRID_DIR / "jjokpa_autumn.json"


def _unit():
    return copy.deepcopy(schema.load(JJ))


def _stage(unit, order):
    return next(s for s in unit["stages"] if s["order"] == order)


def test_the_real_grid_carries_a_source_everywhere_and_validates():
    u = _unit()
    assert schema.validate(u).ok
    assert u["unit"]["confidence"] in schema.CONF
    for s in u["stages"]:
        for r in s.get("symptom_rules") or []:
            assert r["source"].strip()
        if s.get("drought_rules"):
            assert s["drought_rules"]["source"].strip() and "추론" in s["drought_rules"]["source"]   # 발행자 측 추론 — 그 표시가 격자에 있다


@pytest.mark.parametrize("mutate, word", [
    (lambda u: _stage(u, 3)["drought_rules"].pop("source"), "drought_rules.source 가 없다"),
    (lambda u: _stage(u, 4)["drought_rules"].__setitem__("source", "  "), "drought_rules.source 가 없다"),
    (lambda u: _stage(u, 3)["symptom_rules"][0].pop("source"), "source 가 없다 — 출처 없는 감별 규칙"),
    (lambda u: u["unit"].pop("confidence"), "unit.confidence 는 상/중/하"),
    (lambda u: u["unit"].__setitem__("confidence", "높음"), "unit.confidence 는 상/중/하"),
])
def test_a_rule_without_a_source_is_refused_with_the_reason(mutate, word):
    u = _unit()
    mutate(u)
    rep = schema.validate(u)
    assert not rep.ok and any(word in e for e in rep.errors), rep.errors


def test_the_symptom_answer_carries_the_rules_own_source():
    s = media.load_subjects()[0]
    day = date.fromisoformat(s["anchor"]) + timedelta(days=24)
    e = SD.judge_symptom_triage(s, day, [{"id": "o", "text": "잎 끝이 노랗다", "observed_at": day.isoformat()}])
    assert e.kind == "판단함"
    src = _stage(_unit(), 3)["symptom_rules"][0]["source"]
    assert f"감별 출처: {src}" in e.notes and "D-18" in src and "발행자" in src
