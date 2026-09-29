# -*- coding: utf-8 -*-
# FILE: ingest/misclassified.py
# ROLE: [WO-LLM-01 측정 정본 · 읽기 전용] 채팅 원장에서 **규칙이 틀리게 나눈 발화의 재료**가 몇 건인지 센다.
#
#   [검토표 ③ 2026-09-29 · 발행자 승인 "제안 순서대로"] 2026-09-27 에는 scripts/measure_misclassified.py 가 이 일을 했고 발행자가 PC 에서
#   손으로 돌려 두 줄을 세션에 붙였다(첫 측정 2026-09-29 08:21 KST · 70 · 고침 4 · 미달). 화면(/changes)이 상시로 같은 수를 내려면
#   4층이 부를 수 있는 자리(ingest)에 있어야 한다 — 스크립트는 이 모듈을 부르는 콘솔 껍데기로 남긴다(정본 하나).
#
#   지시서 §5-2 는 "라이브 오분류 이력"을 비교 세트의 첫 재료로 꼽는데, 그런 이름의 기록은 없다. 있는 것은 원장의 **줄 순서**다 —
#   chat.message 는 append-only 라 한 발화(id)의 첫 줄에는 규칙이 제안한 초안이, 사람이 '다르게 적을까요?' 로 고르면 같은 id 의
#   뒷줄에 `사람이 고름` 초안이 남는다(list_messages 는 마지막 줄만 보므로 여기서는 파일을 그대로 읽는다). 편집(edit_of)도 같은 축의
#   신호다 — 원문이 틀렸거나 규칙이 틀렸거나, 어느 쪽이든 규칙이 본 적 없는 문장이 하나 생긴다.
#
#   세는 것 (2026-09-27 시점의 원장 구조 기준):
#     종류 고침   첫 줄 초안 종류 ≠ 마지막 줄 `사람이 고름` 초안 종류      ← 오분류 확정
#     편집        edit_of 로 이어진 쌍                                  ← 재료
#     기본값      첫 줄 초안이 서술문 기본값(why_key=statement)          ← 지시서 §7 트리거 후보 집합(오분류 아님)
#     미확인      어느 초안도 원장에 안 들어간 발화                       ← 오분류 신호 아님(그냥 아직 안 넣은 것)
#
#   문턱 30(지시서 §5-2)에 못 미치면 **그 자체가 결과**다 — 규칙이 못 나눈 사례가 드물다는 뜻.
#   규율: 아무것도 쓰지 않는다. `measure()` 의 재료 목록에는 발화 원문이 실리므로 화면은 **건수만**(`status_line`) 낸다(PII 규율).
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingest import chat

MIN_SET = 30                    # WO-LLM-01 §5-2 — 최소 비교 세트. 착수 전 발행자가 확정하면 그 값으로 바꾼다
STATEMENT_KEY = "statement"     # chat.PLAIN_BY_KEY 의 서술문 기본값 갈래


def _lines(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def _kind0(r: dict[str, Any]) -> str | None:
    d = r.get("drafts") or []
    return d[0].get("kind") if d else None


def measure(path: Path | None = None) -> dict[str, Any]:
    """원장 한 파일을 읽어 센다. 돌려주는 것은 수와 재료 목록(원문 포함) — 저장하지 않는다."""
    path = path or chat.index_path()
    first: dict[str, dict[str, Any]] = {}
    latest: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for r in _lines(path):
        if r.get("kind") != "chat.message":
            continue
        i = r.get("id")
        if i not in first:
            first[i] = r
            order.append(i)
        latest[i] = r
    farmer = [i for i in order if first[i].get("role") == "farmer"]
    chosen = []
    for i in farmer:
        f, l = first[i], latest[i]
        d = l.get("drafts") or []
        if d and d[0].get("why") == chat.CHOSEN_WHY and _kind0(f) != _kind0(l):
            chosen.append({"id": i, "text": f.get("text", ""), "rule": _kind0(f), "human": _kind0(l)})
    edits = []
    for i in farmer:
        src = first[i].get("edit_of")
        if src and src in first:
            edits.append({"id": i, "from": first[src].get("text", ""), "to": first[i].get("text", ""),
                          "rule_from": _kind0(first[src]), "rule_to": _kind0(first[i])})
    default = [i for i in farmer if (first[i].get("drafts") or [{}])[0].get("why_key") == STATEMENT_KEY]
    unconfirmed = [i for i in farmer if (latest[i].get("drafts") or []) and not latest[i].get("confirmed_refs")
                   and not any(d.get("confirmed_ref") for d in latest[i]["drafts"])]
    material = len(chosen) + len(edits)
    return {"path": str(path), "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "total": len(farmer),
            "chosen": chosen, "edits": edits, "default_statement": len(default), "unconfirmed": len(unconfirmed),
            "material": material, "min_set": MIN_SET, "enough": material >= MIN_SET}


def status_line(m: dict[str, Any]) -> str:
    """화면(/changes)용 한 줄 — **건수만**. 발화 원문·종류 이름은 싣지 않는다(PII · 안쪽 말). 문턱을 넘으면 발행자 결정을 부른다."""
    verdict = ("충족 — 발행자 결정 차례(트리거 D 를 정한 뒤 하네스)" if m["enough"]
               else "미달 — 그 자체가 결과(규칙이 못 나눈 사례가 드물다)")
    return (f"종류 고침 재료 {m['material']}건 (손으로 고친 종류 {len(m['chosen'])} · 편집 {len(m['edits'])}) — 문턱 {m['min_set']}: {verdict} · "
            f"농가 발화 {m['total']} · 기본값으로 떨어진 것 {m['default_statement']} · 아직 안 넣은 것 {m['unconfirmed']}")


def report(m: dict[str, Any]) -> str:
    """콘솔용 전체 보고 — 발화 원문이 실린다(저장하지 말고 판독 뒤 폐기)."""
    plain = chat.KIND_PLAIN
    out = [f"오분류 재료 측정 — {m['path']} · 측정 시점 {m['measured_at']}",
           f"  농가 발화                          {m['total']}",
           f"  종류 고침(규칙 ≠ 사람)             {len(m['chosen'])}   ← 오분류 확정",
           f"  편집(edit_of) 쌍                   {len(m['edits'])}   ← 재료",
           f"  기본값(서술문 → 본 것)으로 떨어짐   {m['default_statement']}   ← 지시서 §7 트리거 후보 집합(오분류 아님)",
           f"  확인 안 된 초안이 있는 발화         {m['unconfirmed']}   ← 오분류 신호 아님(아직 안 넣은 것)",
           ""]
    for c in m["chosen"]:
        out.append(f"  [고침] {plain.get(c['rule'], c['rule'])} → {plain.get(c['human'], c['human'])} | {c['text']}")
    for e in m["edits"]:
        out.append(f"  [편집] {plain.get(e['rule_from'], e['rule_from'])} → {plain.get(e['rule_to'], e['rule_to'])} | {e['from']} → {e['to']}")
    verdict = "충족" if m["enough"] else "미달 — 그 자체가 결과(WO-LLM-01 §5-2: 규칙이 못 나눈 사례가 드물다)"
    out += ["", f"재료 {m['material']}건 (고침 {len(m['chosen'])} · 편집 {len(m['edits'])}) — 문턱 {m['min_set']}: {verdict}",
            "기대 종류는 발행자가 붙인다(세션이 붙이면 채점자와 응시자가 같아진다). 이 출력은 저장하지 않는다."]
    return "\n".join(out)
