# -*- coding: utf-8 -*-
# [대리값 전수 · 2026-09-20] B6 은 출하 결정의 기본값 63 을 없앴다. 그런데 같은 지식(격자 작업의 retry.deadline_day)을
# 읽는 자리가 **넷**이었고 처방은 한 곳에만 닿았다(§7.5 지점 축). 나머지 셋(밑거름 · 보식 · 웃거름)은 마감이 없으면
# `stage["window"]["to_day"]` 로 메웠다 — 리터럴이 아니라 **식**이라 직전 회차의 숫자 축 전수가 못 봤다.
# 그리고 격자 관문의 문면은 `retry {possible, deadline_day} 필수` 인데 검사는 possible 만 봤다(잠든 관문).
#
# 마감이 지어지면 '창 지남 — 해당 없음'이 틀린 날에 나온다. 판독을 오염시키므로 즉시 급.
from __future__ import annotations

import copy
import re
from datetime import date
from pathlib import Path

import pytest

from grid import schema
from ingest import media, parcels
from judge import envelope, stage_decisions as SD

ROOT = Path(__file__).resolve().parent.parent
_RAW = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
SUBJ = parcels.enrich_subject(_RAW, parcels.by_id("p001"))


def _unit_without_deadline(task_key: str) -> dict:
    """그 작업의 retry.deadline_day 만 null 로 — 나머지는 그대로(부분 주입이 아니라 이 한 축만 비운다)."""
    unit = copy.deepcopy(SD._load_unit(SUBJ))
    hit = 0
    for s in unit["stages"]:
        for t in (s.get("tasks") or []) if isinstance(s.get("tasks"), list) else []:
            if task_key in t.get("name", ""):
                t.setdefault("retry", {})["deadline_day"] = None
                hit += 1
    assert hit, f"격자에 '{task_key}' 작업이 없다 — 주입이 성립하지 않는다"
    return unit


# ── 결정 넷이 같은 지식 부재를 같게 말한다 ────────────────────────────────────────
@pytest.mark.parametrize("task_key, call", [
    ("밑거름", lambda subj, today: SD.judge_base_fertilization(subj, today)),
    ("보식", lambda subj, today: SD.judge_replant(subj, today, observations=[])),
    ("웃거름 1회", lambda subj, today: SD.judge_top_dressing(subj, "top_dressing_1", today)),
])
def test_missing_deadline_is_a_knowledge_gap_not_the_window_end(task_key, call, monkeypatch):
    unit = _unit_without_deadline(task_key)          # 먼저 만든다 — 치환 뒤에 부르면 자기를 부른다
    monkeypatch.setattr(SD, "_load_unit", lambda subject: unit)
    e = call(SUBJ, date(2026, 9, 19))
    assert e.kind == "판단 불가(지식)", f"{task_key}: 마감이 없는데 {e.kind} 가 나왔다"
    assert "retry.deadline_day" in e.result["why"] and "지어내지 않는다" in e.result["why"]


def test_grid_deadline_is_used_when_the_grid_has_one():
    # 반대편 — 막는 것을 검사하면 통과하는 것도 검사한다(게이트 검사 규율). 격자에 마감이 있으면 그 값으로 판단이 선다.
    e = SD.judge_top_dressing(SUBJ, "top_dressing_1", date(2026, 9, 19))
    assert e.kind in ("판단함", "판단 불가(데이터)", "해당 없음")
    assert e.kind != "판단 불가(지식)" or "retry.deadline_day" not in e.result.get("why", "")


# ── 격자 관문: 문면이 요구한 것을 실제로 본다 ─────────────────────────────────────
def test_schema_rejects_a_task_whose_retry_has_no_deadline_key():
    unit = copy.deepcopy(schema.load(schema.GRID_DIR / "jjokpa_autumn.json"))
    for s in unit["stages"]:
        for t in (s.get("tasks") or []) if isinstance(s.get("tasks"), list) else []:
            t["retry"].pop("deadline_day", None)
    rep = schema.validate(unit)
    assert not rep.ok and any("deadline_day" in e for e in rep.errors)


def test_schema_accepts_null_deadline_but_not_a_string():
    base = schema.load(schema.GRID_DIR / "jjokpa_autumn.json")
    ok = copy.deepcopy(base)
    ok["stages"][0]["tasks"][0]["retry"]["deadline_day"] = None      # 모른다고 적을 자리 — 통과해야 한다
    assert schema.validate(ok).ok, schema.validate(ok).errors
    bad = copy.deepcopy(base)
    bad["stages"][0]["tasks"][0]["retry"]["deadline_day"] = "14일"
    assert not schema.validate(bad).ok


@pytest.mark.parametrize("mutate, why", [
    (lambda t: t.pop("name"), "작업명"),
    (lambda t: t["lead_days"].update(own=None), "lead_days 값"),
    (lambda t: t["retry"].update(possible="false"), "retry.possible 값"),
])
def test_gate_looks_at_the_value_not_just_the_key(mutate, why):
    # 처방 직후 전수 — 문면은 키를 요구하는데 값을 안 보던 자리가 셋 더 있었다. 소비자가 그 값을 믿고 쓴다(계획표 작업명 · 준비일 · 재시도 가능).
    unit = copy.deepcopy(schema.load(schema.GRID_DIR / "jjokpa_autumn.json"))
    mutate(unit["stages"][0]["tasks"][0])
    assert not schema.validate(unit).ok, f"{why}: 관문이 통과시킨다"


# ── 등급도 지어내지 않는다 ────────────────────────────────────────────────────────
def test_weakest_refuses_an_empty_axis_list():
    assert envelope.weakest(["계산", "추정"]) == "추정"      # 통과편 — 가장 약한 축
    with pytest.raises(ValueError):
        envelope.weakest([])


# ── 래칫: 마감을 읽는 법은 한 벌 ──────────────────────────────────────────────────
def _body(src: str, name: str) -> str:
    start = src.index(f"def {name}(")
    nxt = src.index("\ndef ", start + 10)
    return src[start:nxt]


def test_only_the_canon_reads_deadline_day():
    src = (ROOT / "judge" / "stage_decisions.py").read_text(encoding="utf-8")
    for fn in ("judge_base_fertilization", "judge_replant", "judge_top_dressing", "judge_ship_or_store"):
        body = _body(src, fn)
        code = "\n".join(ln.split("#", 1)[0] for ln in body.splitlines())
        assert "_deadline_day(" in code, f"{fn}: 마감 정본을 안 쓴다"
        # 변별 표지 — 읽는 **꼴**만 본다(§7.1 4번: 처방이 만든 안내 문면에도 'deadline_day' 가 들어 있다)
        assert not re.search(r'(get\(\s*["\']deadline_day|\[\s*["\']deadline_day)', code), f"{fn}: 마감을 직접 읽는다 — 정본 하나로"
    canon = _body(src, "_deadline_day")
    canon = re.sub(r'\"{3}.*?\"{3}', "", canon, flags=re.S)   # 독스트링을 걷는다 — 그 안에 옛 꼴을 설명해 두었다
    assert 'get("deadline_day")' in canon and "to_day" not in canon, "정본이 창 끝으로 메운다"


def test_no_window_end_stands_in_for_a_deadline_anywhere_in_judge():
    # 형태 독립 — 어느 파일이든 마감 자리에 창 끝을 기본값으로 넘기는 꼴을 금한다
    for f in sorted((ROOT / "judge").glob("*.py")):
        code = "\n".join(ln.split("#", 1)[0] for ln in f.read_text(encoding="utf-8").splitlines())
        assert not re.search(r'deadline_day"\s*,\s*[^)]*to_day', code), f"{f.name}: 마감을 창 끝으로 메운다"
