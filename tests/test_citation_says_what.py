# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-09] 오늘 상태로 농가 답 여섯을 읽었다. 「약 뭐 쳐요」 의 답이 이랬다.
#
#     [찾아본 것입니다] 4. 생육 중기 · 비대 · 공시 자재 계열 1건 인용 — 효능 보증 아님. 화면 /judge 에 목록
#
# 그 「1건」 은 **웃거름 2회의 유기질 비료**(공시 제품 113건)다 — 재배 달력의 칸 4 에 방제 자재는 없다. 그런데 답이 무엇을 인용했는지 말하지 않아
# **약을 물은 사람은 그것을 약 목록으로 읽는다**(약제 오용 축). 「화면 /judge」 는 주소이지 메뉴 이름이 아니다.
# 계열과 그 계열이 적힌 작업은 재배 달력에 이미 있었다 — 3층이 작업 이름을 싣지 않았고 답이 계열을 말하지 않았다(G1 셋째 형태).
# **무엇을 인용할지는 바꾸지 않는다** — 「약」 물음이 비료 칸을 인용하는 라우팅은 안전 판단이라 발행자 몫으로 올렸다.
#
# 고정하는 것 일곱:
#   ① 답이 **계열과 작업**을 말한다(오늘: 웃거름 2회 → 유기질 비료) — 「계열 N건」 만으로 끝나지 않는다
#   ② 건수는 **찾은 것만** — 짝을 못 지은 계열은 그렇다고 말한다(0건이라고 하면 「공시 제품이 없다」 는 다른 사실)
#   ③ 작업 이름은 3층이 **재배 달력에서** 싣는다 — 계열을 자르는 규칙은 하나(두 벌이면 한쪽만 바뀐다)
#   ④ 메뉴 이름은 정본에서 — 주소(/judge)가 농가 문장에 없다
#   ⑤ 보증이 아니라는 말은 남는다(인용이지 권고가 아니다 — 안전 축의 그 문장을 지우지 않는다)
#   ⑥ 작업마다 한 번 — 계열마다 작업 이름을 되풀이하지 않는다
#   ⑦ 판단 화면의 카드도 **같은 사실**(작업: 계열)을 말한다(두 지점)
from __future__ import annotations

import ast
import html as _html
import re
from datetime import date
from pathlib import Path

from frontend import words
from ingest import chat, media
from judge import material_citation as mc, run as judge_run
from schema import labels
from tests.test_screen_speaks_plainly import JARGON, _get, _visible, srv  # noqa: F401

ROOT = Path(chat.__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
TODAY = date(2026, 10, 9)          # 칸 4(생육 중기 · 비대) — 자재 칸이 웃거름의 비료 하나뿐인 날
STAGE3 = date(2026, 9, 15)         # 칸 3 — 예찰(방제)과 웃거름 두 작업에 자재가 있는 날


def _env(today: date):
    return next(x for x in judge_run.judgments_for(SID, today=today) if x.decision_id == "material_citation")


def test_the_answer_names_the_family_and_the_task():
    """[①] 오늘 「약 뭐 쳐요」 — 인용한 것이 웃거름용 유기질 비료라는 것을 답이 말한다."""
    e = _env(TODAY)
    assert e.kind == "사실 인용", e.kind
    said = chat.answer(media.load_subjects()[0], "약 뭐 쳐요", TODAY)
    for g in e.result["groups"]:
        assert g["family"] in said and g["task"] in said, (g["family"], g["task"], said)
    assert "계열 1건 인용" not in said, said


def test_counts_only_for_what_was_found():
    """[②] 찾은 것만 건수 — 짝을 못 지은 계열을 0건이라고 하지 않는다."""
    found = {"family": "유기질 비료", "task": "웃거름", "status": "success", "total": 7, "items": []}
    unmatched = {"family": "온탕 침지", "task": "종구 소독", "status": "no_alias", "items": []}
    said = words.citation_said("1. 종구 준비 · 파종", [found, unmatched])
    assert "유기질 비료(7건)" in said and "온탕 침지(공시 목록과 짝짓지 못함)" in said, said
    assert "0건" not in said, said
    assert words.citation_said("1. 종구 준비 · 파종", []) == ""                       # 인용한 것이 없으면 그 문장을 만들지 않는다


def test_the_task_comes_from_the_calendar_by_one_rule():
    """[③] 작업 이름은 재배 달력에서 — 계열을 자르는 규칙은 `_family_tasks` 하나(`_families` 는 그것을 부른다)."""
    from grid import schema as grid_schema
    unit, _miss = grid_schema.load_unit(media.load_subjects()[0])
    for st in unit["stages"]:
        assert mc._families(st) == list(mc._family_tasks(st)), st.get("order")
        for fam, task in mc._family_tasks(st).items():
            assert task in [t.get("name") for t in st.get("tasks") or []], (fam, task)
    fn = next(n for n in ast.walk(ast.parse((ROOT / "judge" / "material_citation.py").read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "_families")
    calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_family_tasks"]
    assert calls and not [c for c in ast.walk(fn) if isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "split"], "자르는 규칙이 두 벌이다"


def test_the_menu_name_is_the_canon_not_a_path():
    """[④] 주소가 아니라 메뉴 이름 — 「화면 /judge」 였다."""
    said = chat.answer(media.load_subjects()[0], "약 뭐 쳐요", TODAY)
    assert "/judge" not in said, said
    assert f"「{labels.label('/judge')}」" in said, said


def test_the_no_guarantee_line_stays():
    """[⑤] 인용이지 권고가 아니다 — 보증이 아니라는 말은 남는다(안전 축의 문장을 지우지 않는다)."""
    said = chat.answer(media.load_subjects()[0], "약 뭐 쳐요", TODAY)
    assert "효능 보증은 아닙니다" in said, said
    for bad in JARGON:
        assert bad not in said, (bad, said)


def test_each_task_is_named_once():
    """[⑥] 칸 3 — 예찰 하나에 계열 넷이 있어도 작업 이름은 한 번."""
    e = _env(STAGE3)
    tasks = {g["task"] for g in e.result["groups"] if g.get("task")}
    assert len(tasks) >= 2, tasks                                                   # 조건 — 작업 둘에 자재가 있는 날
    said = chat.answer(media.load_subjects()[0], "약 뭐 쳐요", STAGE3)
    for t in tasks:
        assert said.count(f"{t}:") == 1, (t, said)


def test_the_judge_card_says_the_same_fact(srv):
    """[⑦] 판단 화면의 카드 — 작업: 계열(채팅 답과 같은 사실 · 두 지점)."""
    st, body = _get(srv, "/judge")
    assert st == 200
    seen = _visible(_html.unescape(body))
    e = next(x for x in judge_run.judgments_for(SID, today=date(2026, 9, 19)) if x.decision_id == "material_citation")
    for g in e.result["groups"]:
        if g.get("status") == "success" and g.get("task"):
            assert f"{g['task']}: {g['family']}" in seen, (g["task"], g["family"])
