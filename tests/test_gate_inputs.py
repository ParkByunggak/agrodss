# -*- coding: utf-8 -*-
# [관문의 입력 전수 래칫 2026-09-28] §7.5 "관문을 세울 때 입력 도착 전수 래칫을 짝으로" — 이번 회차에 같은 형태의 입력 쌍이 셋(단기 · 중기 · 장기)이
# 되면서 쌍마다 검사를 따로 썼다(주입 A·B 가 매번 잡았다). 형태 규칙은 하나다: `all_judgments` 가 `x, xwhy = gather_*()` 로 모은 것은
# ① 레코드가 게이트를 **거쳐서만** 판정기에 닿고(원 변수를 판정기에 직접 넘기지 않는다) ② 이유가 판정기 또는 상태 꼬리에 도착한다.
# 다음 입력 쌍이 생길 때 검사를 잊어도 이 래칫이 말한다.
from __future__ import annotations

import re
from pathlib import Path

from judge import stage_decisions as SD

ROOT = Path(__file__).resolve().parent.parent


def _all_judgments_body() -> str:
    src = (ROOT / "judge" / "run.py").read_text(encoding="utf-8")
    body = src[src.index("def all_judgments("):]
    return body


def _gathered() -> list[tuple[str, str, str]]:
    body = _all_judgments_body()
    return re.findall(r"^\s+(\w+), (\w+) = gather_(\w+)\(", body, re.M)


def _call(body: str, head: str) -> str:
    i = body.index(head)
    depth, j = 0, i
    while True:
        c = body[j]
        depth += (c == "(") - (c == ")")
        j += 1
        if depth == 0 and c == ")":
            return body[i:j]


def test_every_gathered_input_is_gated_and_its_reason_arrives():
    body = _all_judgments_body()
    pairs = _gathered()
    assert len(pairs) >= 4 and {p[2] for p in pairs} >= {"forecast", "mid", "outlook", "pest"}
    gate = _call(body, "boundary.gate(")
    judge_all = _call(body, "stage_decisions.judge_all(")
    status = body[body.index("out.append((s, envs, {"):]
    status = status[:status.index("}))")]
    for recs, why, name in pairs:
        assert re.search(rf"=\s*{recs}\b", gate), f"{name}: 레코드 {recs} 가 게이트에 안 들어간다"
        after_gate = body[body.index("boundary.gate("):]
        direct = re.findall(rf"=\s*{recs}\b", after_gate.replace(gate, ""))
        assert not direct, f"{name}: 게이트를 안 거친 {recs} 를 판정기에 직접 넘긴다"
        assert re.search(rf"\b{why}\b", judge_all) or re.search(rf"\b{why}\b", status), f"{name}: 이유 {why} 가 판정기에도 상태 꼬리에도 안 닿는다"


def test_reasons_that_judge_all_accepts_are_actually_passed():
    """판정기 서명이 받는 *_why 는 전부 호출부가 넘긴다 — 서명에만 있고 호출이 안 넘기면 관문은 서 있고 아무것도 안 거른다."""
    import inspect
    params = [p for p in inspect.signature(SD.judge_all).parameters if p.endswith("_why")]
    assert params and set(params) >= {"forecast_why", "mid_why", "outlook_why"}
    judge_all = _call(_all_judgments_body(), "stage_decisions.judge_all(")
    for p in params:
        m = re.search(rf"\b{p}\s*=\s*(\w+)", judge_all)
        assert m and m.group(1) != "None", f"{p} 를 안 넘긴다(또는 None 을 넘긴다)"
