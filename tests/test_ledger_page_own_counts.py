# -*- coding: utf-8 -*-
# [앞날 걷기 F34~F38 · 2026-10-14] 대장 페이지의 **내 문장** 다섯이 손으로 적은 셈 · 날 지난 지시였다(세션 몫):
#   F34  세션 몫 「결정 화면 — 남은 N줄을 한 번에 저장(아직 안 지었다)」 — 10-07 에 지었고 그 줄이 「다음 회차에 지운다」 고 스스로 말했다
#   F35  「보고 확인 … 46줄 · 줄 수 하한이 46」 — 주장은 59, 검사 하한은 47(열둘이 말없이 빠질 수 있었다)
#   F36  머리 「항목 96」 인데 상태 알약 합 92 — 굵게 쓴 상태(「**완료(…)**」)와 상태 말이 아닌 「등재」 가 빠졌다
#   F37  ⓪ᵉ 「놓침 열두 가지」 — 용도에 「종구 생산」 이 들어가면 여덟(조건을 뗀 수)
#   F38  ⓪⁺ 「다섯 항목이 그 답에 매달린다」 — 결정 D-2 는 넷을 적고 「다섯」 이라 했다(사슬 다섯은 D-2 자신을 센 수)
# 처방은 하나의 꼴이다 — **정본에서 센다**(정본이 판정이면 판정을 다시 돌려 잰다). 이 검사가 각 셈을 그 정본과 대조한다.
# [재검토 F8 · R5 · R7 · 2026-10-14] 첫 판의 이 검사가 셋 다 좁았다 — F36 은 cwd 에 묶이고 소스 글자 한 줄을 찾아(주석 처리해도 초록 · 같은 뜻의 순서를 바꾸면 빨강),
# F38 은 「== 4」 를 박았고, F34 · F37 은 한 항목만 봤다(같은 꼴이 BEST 한 것 · 막힌 것과 세션 몫의 다른 두 줄에 남아 있었다). 페이지 전체를 보고 구조로 잰다
from __future__ import annotations

import ast
import importlib
import re
from datetime import timedelta
from pathlib import Path

from frontend import render
from ingest import decisions, media, parcels

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"


def _page(monkeypatch, today="2026-10-14"):
    monkeypatch.setenv("AGRODSS_TODAY", today)
    return importlib.reload(importlib.import_module("scripts.build_ledger_page"))


def _said(page) -> str:
    return " ".join(h + " " + b for h, b in page.NEXT_PUBLISHER + page.NEXT_SESSION)


def _all(page) -> str:
    """페이지가 말하는 것 전부 — 두 목록 + BEST(할 것 · 한 것 · 막힌 것)."""
    b = page.BEST
    return " ".join([_said(page), *map(str, b["do"].values()), *b["did"], b["blocked"]])


def test_f34_no_row_keeps_an_instruction_that_was_already_done(monkeypatch):
    page = _page(monkeypatch)
    said = _said(page)
    assert "아직 안 지었다" not in said and "다음 회차에 지운다" not in said, said[said.find("지었다") - 80:][:200]
    # [재검토 R7] 같은 꼴 둘 — 10-06 에 선 조사 정본을 세션 몫이 「정본으로」 라고 지시했고, 같은 페이지 ⓪ᴿ 가 즉시급을 세는데 「자율 큐는 비었다」 고 했다
    heads = [h for h, _ in page.NEXT_SESSION]
    assert not any("조사" in h and "정본으로" in h for h in heads), heads
    assert ("자율 큐는 비었다" in said) == (not page._WALK_OPEN), page._WALK_OPEN
    # [재재검토] 다음 일을 말하는 줄은 **하나**이고 그 줄이 남은 수를 센다 — 첫 판은 한 줄만 고쳐 다른 줄(「어미 계열 닫힘 … 다음은 ① 낡음 대조」)이 그대로 갈렸다
    plans = [b for _h, b in page.NEXT_SESSION if "자율 큐" in b or re.search(r"다음은\s*①", b)]
    assert len(plans) == 1, [p[:60] for p in plans]
    if page._WALK_OPEN:
        assert f"즉시급 **{len(page._WALK_OPEN)}개**" in plans[0]


def test_f35_the_claims_floor_is_read_from_the_tool(monkeypatch):
    from scripts import verify_claims
    page = _page(monkeypatch)
    said = _said(page)
    assert page._CLAIMS_MIN == verify_claims.CLAIMS_MIN and f"줄 수 하한 {verify_claims.CLAIMS_MIN}" in said
    assert not re.search(r"\b46\s?줄|하한이 46", said)


def test_f36_the_pills_count_every_row_even_bold_states():
    text = "\n".join(["| ID | 항목 | 출처 | 상태 | 등재 | 근거 |", "|---|---|---|---|---|---|",
                      "| D-90 | 가 | 나 | **완료(발행자 2026-10-03 — 반영)** | 10-02 | 다 |",
                      "| D-91 | 가 | 나 | 진행(값 대기) | 10-02 | 다 |",
                      "| D-92 | 가 | 나 | **등재(발행자)** | 10-02 | 다 |"])
    c = render.ledger_counts(text)
    assert c["완료"] == 1 and c["진행"] == 1 and sum(c.values()) == 2                  # 굵게 쓴 완료도 센다 · 「등재」 는 상태 말이 아니라 안 센다
    real = (ROOT / "docs" / "agrodss_backlog.md").read_text(encoding="utf-8")
    ids = re.findall(r"^\| ([DIMUR]-\d+) \|", real, re.M)
    assert sum(render.ledger_counts(real).values()) == len(ids)                         # 지금 대장 — 상태를 못 읽은 행 0
    # 갈리면 생성기가 멈춘다(배선) — 글자가 아니라 구조로: 모듈 맨 위 단언 하나가 sum(counts.values()) 와 len(ids) 를 (어느 순서로든) 같다고 비교한다(주석은 안 걸린다)
    tree = ast.parse((ROOT / "scripts" / "build_ledger_page.py").read_text(encoding="utf-8"))
    sides = {"sum(counts.values())", "len(ids)"}
    stops = [n for n in tree.body if isinstance(n, ast.Assert) and isinstance(n.test, ast.Compare)
             and isinstance(n.test.ops[0], ast.Eq) and {ast.unparse(n.test.left), ast.unparse(n.test.comparators[0])} == sides]
    assert len(stops) == 1, "생성기의 멈춤(상태 알약 합 == 항목 수)이 모듈 맨 위에 없다"


def _missed_after_season(use: str | None) -> int:
    """농가가 받는 수 — **판정 경로 전체**(judge.run)에서 잰다. plan_vs_actual 하나만 부르면 용도 문(use_gap)이 말미에 걸리기 전이라 늘 12 다
    (첫 판의 이 검사가 그렇게 재서 틀렸다 · 측정 경로가 화면 경로와 달랐다 — 지표를 쓰기 전에 경로를 본다)."""
    from grid import schema as grid_schema
    from judge import run as judge_run
    if use:
        parcels.set_fields("p001", use=use, overwrite=True)                              # 격리 사본의 덮개(conftest)
    sub = next(s for s in media.load_subjects() if s["id"] == SID)
    unit, _ = grid_schema.load_unit(sub)
    last = int(grid_schema.last_day(unit))
    day = __import__("datetime").date.fromisoformat(sub["anchor"]) + timedelta(days=last + 1)
    env = next(e for _s, envs, _i in judge_run.all_judgments(day, only=SID) for e in envs if e.decision_id == "plan_vs_actual")
    return int(env.result["counts"]["놓침"])


def test_f37_the_missed_counts_are_the_judgment_s_with_their_condition(monkeypatch):
    page = _page(monkeypatch)
    leaf = _missed_after_season(None)
    seed = _missed_after_season("종구 생산")
    assert (leaf, seed) == (page._MISSED_END["잎"], page._MISSED_END["종구"]), (leaf, seed, page._MISSED_END)
    assert leaf != seed                                                                   # 조건이 수를 바꾼다 — 그래서 조건과 함께 적는다
    zr = next(b for h, b in page.NEXT_PUBLISHER if h.startswith("⓪ᵉ"))
    assert f"놓침 {leaf} — 사유를 묻는다" in zr and f"「종구 생산」 을 넣으면 수확 칸 이후 할 일이 빠져 {seed}" in zr
    assert "열두 가지" not in _all(page)                                                  # [재검토 R5] BEST 한 것에도 같은 손 셈이 남아 있었다 — 페이지 전체를 본다
    assert f"「놓침 {leaf} — 사유를 묻는다」(용도를 안 넣은 밭)" in " ".join(page.BEST["did"])


def test_f38_the_dependents_are_counted_from_what_is_listed(monkeypatch):
    page = _page(monkeypatch)
    d2 = next(i for i in decisions.ITEMS if i["id"] == "D-2")["unblocks"]
    listed = re.findall(r"\b[DMU]-\d+\b", d2)
    assert page._D2_HANG == len(listed) > 0
    # [재검토 F8] 결정 문면이 그 목록 옆에 수 말(「넷」 · 「다섯」)을 손으로 적지 않는다 — 적으면 목록이 바뀌는 날 갈린다(F38 의 원 결함)
    assert not re.search(r"(하나|둘|셋|넷|다섯|여섯|일곱|여덟|아홉|열)[이가]? 이 답에", d2), d2
    zp = next(b for h, b in page.NEXT_PUBLISHER if h.startswith("⓪⁺"))
    assert f"항목 {len(listed)}개가 그 답에 매달린다" in zp and "다섯 항목" not in zp


def test_r5_the_readers_and_the_inference_table_are_counted_everywhere(monkeypatch):
    """[재검토 R5] 같은 셈이 BEST 한 것(「용도는 다섯 · 배수는 둘」) · ⓪ʷ · 막힌 것(「§10 표 24행 · 농가 9 · 기준 자료 15」)에 손으로 남아 있었다."""
    from grid import schema as grid_schema
    page = _page(monkeypatch)
    said = _all(page)
    use, drain = parcels.FIELD_CONSUMERS["use"], parcels.FIELD_CONSUMERS["drainage"]
    assert f"용도는 **{len(use)}개**" in said and f"배수는 {len(drain)}개" in said and "**다섯**" not in said
    unit = grid_schema.load_unit(next(s for s in media.load_subjects() if s["id"] == SID))[0]
    infer = [v for v in grid_schema.sourced_values(unit) if v["inference"]]
    doc = (ROOT / "docs" / "grid_jjokpa_autumn.md").read_text(encoding="utf-8")
    sec = doc[doc.index("## 추론값 — 누가 고칠 수 있는가"):doc.index("## 단계별 칸")]
    rows = re.findall(r"^\| \d+ [^|]*\|[^|]*\|[^|]*\| \*\*(\S+)\*\* \|", sec, re.M)
    assert len(rows) == len(infer) and f"· {len(infer)}건 ·" in sec                       # 문서 표와 정본 목록이 같은 수
    farmer, canon = rows.count("농가"), rows.count("정본")
    assert f"{len(infer)}행</b>: 세션이 농가 {farmer} · 기준 자료 {canon}" in said and f"§10 표 {len(infer)}행" in page.BEST["blocked"]
