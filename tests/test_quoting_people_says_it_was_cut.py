# -*- coding: utf-8 -*-
# [2026-10-05 전수] 앞 칸에서 *사람이 쓴 말이 **바뀌어** 돌아오던 것*을 고쳤다. 같은 축을 하나 더 세니 — **뒤가 사라지는** 쪽이 있었다.
# 사람이 쓴 글을 잘라서 다른 문장에 싣는 자리가 **여섯**인데 잘렸다고 말하는 곳은 **한 곳**뿐이었다(채팅 인용 꼬리만 「…」).
# 그중 가장 나쁜 것은 물음 문장의 일지 인용이다 — 한도가 **30자**라 거의 매번 걸리고, 시스템이 그 토막을 **그 사람의 말로** 되묻는다:
#     「고랑 물 빠짐이 잘 되고 있고, 잎 끝 황화 현상은」 를 봤습니다, 어느 쪽인지
# 쓰지 않은 짧은 문장을 쓴 것처럼 되돌려 주는 꼴이다. 꼴을 정본 하나로 모으고(`schema.records.quote`) 여섯 자리를 전부 그것으로 옮겼다.
#
# 이 검사가 고정하는 것 넷:
#   ① 자른 자리에는 꼬리가 붙고, **안 자른 글에는 안 붙는다**(양방향 — 안 자른 글에 붙이면 그것도 거짓이다)
#   ② 한도 경계(limit · limit+1)에서 갈린다
#   ③ 인용 자리 전수 — 그 모듈들에서 사람 글을 직접 토막 내는 꼴이 **0**(새 자리가 생기면 정본을 쓰게 된다)
#   ④ 실제 경로에서 보인다: 물음 문장 · 할 일 이름 · 불이행 사유 요약 · 채팅 인용
from __future__ import annotations

import ast
import pathlib
import re
from datetime import date

import pytest

from ingest import chat, questions
from schema import records as sch

ROOT = pathlib.Path(sch.__file__).resolve().parent.parent
LONG = "고랑 물 빠짐이 잘 되고 있고, 잎 끝 황화 현상은 더 진행이 되지 않는다. 다만 아래쪽 두 줄은 아직 물이 고인다"      # 발행자 일지 투 · 30자보다 길다

# 사람이 쓴 글을 인용하는 자리 — (파일, 그 안에서 quote 를 부르는 함수)
SITES = {
    ("ingest/questions.py", "_parcel_question"): "물음 문장의 일지 인용(30자) — 가장 자주 걸린다",
    ("ingest/chat.py", "request_improvement"): "고쳐 달라는 말의 답변 인용(200자)",
    ("ingest/chat.py", "_classify"): "작업 어휘를 못 읽은 할 일의 이름(60자)",
    ("ingest/chat.py", "choose_kind"): "종류를 고친 할 일·불이행의 이름(60자)",
    ("judge/stage_decisions.py", "judge_top_dressing"): "불이행 사유를 요약에 싣는 줄(120자)",
    ("frontend/chat_pages.py", "_answer_actions"): "채팅 인용 꼬리(80자) — 여섯 중 유일하게 옳았던 자리",
}
# 사람이 쓴 글의 이름 — 이 모듈들에서 이 이름을 직접 토막 내면 터진다(정본을 쓰라는 뜻)
PEOPLE_NAMES = {"text", "note", "reason", "raw", "t", "said", "body", "proposal", "detail", "response"}
# **안 하기로 한 것**(빠뜨린 것과 가른다 — CLAUDE.md 검사 규율): 인용이 아니라 **저장**이라 꼬리를 붙이지 않는다.
# 자르면 되돌릴 수 없어 더 나쁘지만, 오늘 원장의 가장 긴 사람 글은 176자라 2000자에 **안 닿는다**(측정 2026-10-05) —
# 급을 가른 것이다(즉시 아님 · 칸 2 등재 후보 · 발행자 판단 — 다리 B). 새 저장 자르기가 생기면 이 검사가 그것도 묻는다.
STORAGE_CUTS = {("ingest/chat.py", "send", "text"): "농가 글을 원장에 남기는 자리(2000자) — 저장이라 꼬리가 아니라 '자른 것을 말하기'가 처방이다(등재 후보)"}


def test_the_tail_marks_the_cut_and_only_the_cut():
    assert sch.quote(LONG, 30) == LONG[:30] + sch.QUOTE_TAIL
    assert sch.quote("짧은 글", 30) == "짧은 글"                                  # 안 자른 글에는 안 붙는다
    assert sch.quote("", 30) == "" and sch.quote(None, 30) == ""
    assert sch.QUOTE_TAIL not in sch.quote("가" * 30, 30)                         # 경계 — 딱 맞으면 그대로
    assert sch.quote("가" * 31, 30) == "가" * 30 + sch.QUOTE_TAIL                 # 한 글자 넘으면 꼬리
    with pytest.raises(ValueError):
        sch.quote(LONG, 0)


def _quote_sites() -> set[tuple[str, str]]:
    """전수 — (파일, 함수) 가 정본을 부르는가. 줄 번호·인자 꼴은 고정하지 않는다(구조로 자른다)."""
    found = set()
    for rel in sorted({f for f, _ in SITES}):
        p = ROOT / rel
        tree = ast.parse(p.read_text(encoding="utf-8"))
        fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "quote":
                inner = max((x for x in fns if x.lineno <= n.lineno <= (x.end_lineno or x.lineno)), key=lambda x: x.lineno, default=None)
                found.add((rel, inner.name if inner else "<모듈>"))
    return found


def test_every_quoting_place_uses_the_canon():
    assert set(SITES) <= _quote_sites(), (set(SITES) - _quote_sites(), SITES)


def test_no_module_cuts_people_text_by_hand():
    """사람 글 이름을 직접 토막 내는 꼴이 남아 있으면 그 자리는 말없이 자른다 — 전수로 막는다(한도 숫자는 고정하지 않는다)."""
    left = []       # 집합이 아니라 목록 — 같은 함수·같은 이름의 **두 번째** 자르기도 보여야 한다([주입 G 2026-10-05] 집합이 그것을 삼켰다)
    for rel in sorted({f for f, _ in SITES}):
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice)):
                continue
            up, lo = n.slice.upper, n.slice.lower
            if lo is not None or not (isinstance(up, ast.Constant) and isinstance(up.value, int) and up.value >= 20):
                continue                                            # 날짜 자르기([:10]) 등은 사람 글이 아니다
            # 자르는 **대상 안에 나오는 이름 전부**를 본다 — 모양으로 좁히면 괄호 하나에 눈을 감는다
            # ([주입 G 2026-10-05 실측] 처음엔 `이름[:N]` 과 `r["이름"][:N]` 두 꼴만 봐서 `(text or "")[:300]` 을 못 봤다 — 탐지 축 오선택 계열)
            said = {x.id for x in ast.walk(n.value) if isinstance(x, ast.Name)}
            said |= {x.value for x in ast.walk(n.value) if isinstance(x, ast.Constant) and isinstance(x.value, str)}
            hit = sorted(said & PEOPLE_NAMES)
            if hit:
                inner = max((x for x in fns if x.lineno <= n.lineno <= (x.end_lineno or x.lineno)), key=lambda x: x.lineno, default=None)
                left.append((rel, inner.name if inner else "<모듈>", hit[0]))
    assert sorted(left) == sorted(STORAGE_CUTS), (sorted(left), sorted(STORAGE_CUTS))      # 남은 것은 **안 하기로 한 것**뿐 — 그 이유가 위에 적혀 있다


def test_the_question_shows_the_cut(tmp_path, monkeypatch):
    """실제 경로 — 일지 줄만 있고 값이 없을 때 그 줄을 들고 묻는다(ingest.questions). 그 인용에 꼬리가 보인다."""
    from ingest import known

    monkeypatch.setattr(known, "known_field", lambda subject, field: {"from": "observation", "value": None, "observed_at": "2026-10-03", "text": LONG})
    q = questions._parcel_question("drainage", {"risk": "과습", "stage": "비대", "recoverable": False}, subject={"id": "s1"})
    said = q and q["who_can_fill"]                                            # 요구 문장의 '누가 채울 수 있는가' 줄이 그 인용을 싣는다
    assert said and sch.QUOTE_TAIL in said, q
    assert LONG[:30] in said and LONG[:40] not in said                        # 자른 자리까지만 · 꼬리가 그것을 말한다


def test_the_task_name_shows_the_cut():
    """작업 어휘가 없는 긴 계획 문장 — 할 일 **이름**이 토막인데 토막이라고 말하지 않으면 사람이 안 쓴 이름이 된다(원문은 note 에 그대로)."""
    said = "내일은 고랑 쪽 물길을 다시 보고 아래쪽 두 줄을 손봐서 물이 안 고이게 해 둘 것이다 그리고 멀칭도 걷어 볼 생각이다"
    drafts = chat.classify(said, date(2026, 10, 5), subject={"id": "s1", "crop": "쪽파", "anchor": "2026-09-01"})
    plan = next((d for d in drafts if d["kind"] == "plan.farmer"), None)
    assert plan, drafts
    assert plan["task"].endswith(sch.QUOTE_TAIL) and len(plan["task"]) == 61, plan["task"]
    assert plan["note"] == said                                              # 쓴 글은 그대로 남는다 — 자르는 것은 이름뿐
