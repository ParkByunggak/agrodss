# -*- coding: utf-8 -*-
# FILE: scripts/measure_misclassified.py
# ROLE: [WO-LLM-01 착수 전 측정 · 읽기 전용] 채팅 원장에서 **규칙이 틀리게 나눈 발화의 재료**가 몇 건인지 센다.
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
#   규율: 아무것도 쓰지 않는다. 출력은 콘솔뿐이고 발화 원문이 실리므로 파일로 저장하지 말고 판독 뒤 폐기한다(PII 규율).
#   쓰는 법:  python -m scripts.measure_misclassified        (발행자 PC · 운영 원장)
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest import chat  # noqa: E402

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


def report(m: dict[str, Any]) -> str:
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


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(report(measure()))
