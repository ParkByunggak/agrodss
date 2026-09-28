# -*- coding: utf-8 -*-
# FILE: scripts/measure_default_trigger.py
# ROLE: [WO-LLM-01 사전 측정 · 읽기 전용] 지시서의 제안 트리거 '기본값(statement)으로 떨어진 발화' 집합이 저장소 안 문장에서 얼마나 큰가.
#
#   재료  tests/test_chat_corpus.py CORPUS(기대 종류 있음) · tests/test_never_ask_the_kind.py HARD(어려운 입력 · 기대 없음).
#   셈    기본값으로 떨어진 문장 중 기대가 '본 것' 이면 기본값이 맞은 것, 아니면 틀린 것(= LLM 이 받을 몫). 기본값이 아닌데 기대와 다른 것은 트리거 밖 오분류.
#   실측  2026-09-27(HEAD 5f28db7): 말뭉치 104 중 3(셋 다 맞음 · 틀림 0) · 어려운 입력 25 중 22(조각). 대장 WO-LLM-01 행 · 핸드오버 §5 ③.
#   [2026-09-28] 이 측정이 스크래치패드에만 있었다(U-35 형태) — 말뭉치가 자라면 다시 재야 하므로 저장소로. 아무것도 쓰지 않는다.
#   쓰는 법  python -m scripts.measure_default_trigger
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest import chat  # noqa: E402

STATEMENT_KEY = "statement"
T = date(2026, 9, 24)      # 말뭉치 검사와 같은 고정 날짜(시점 축 — 날짜 어휘가 있는 문장이 있다)


def measure(corpus: list[tuple], hard: list[str]) -> dict[str, Any]:
    default_ok, default_bad, non_default_wrong = [], [], []
    for row in corpus:
        text, expected = row[0], row[1]
        ds = chat.classify(text, T)
        k0, why = (ds[0]["kind"], ds[0].get("why_key")) if ds else (None, None)
        if why == STATEMENT_KEY:
            (default_ok if expected == "observation.note" else default_bad).append((text, expected, k0))
        elif k0 != expected:
            non_default_wrong.append((text, expected, k0))
    hard_default = [h for h in hard if (chat.classify(h, T) or [{}])[0].get("why_key") == STATEMENT_KEY]
    return {"corpus": len(corpus), "default_ok": default_ok, "default_bad": default_bad, "non_default_wrong": non_default_wrong,
            "hard": len(hard), "hard_default": hard_default}


def report(m: dict[str, Any]) -> str:
    out = [f"말뭉치 {m['corpus']}문장 (기대 종류 있음)",
           f"  기본값(statement)으로 떨어진 문장   {len(m['default_ok']) + len(m['default_bad'])}",
           f"    그중 기대도 본 것(기본값이 맞음)   {len(m['default_ok'])}",
           f"    그중 기대가 다른 종류(기본값이 틀림) {len(m['default_bad'])}   ← 제안 트리거가 LLM 에 넘길 몫"]
    out += [f"      {t!r} 기대 {e} / 규칙 {k}" for t, e, k in m["default_bad"]]
    out.append(f"  기본값 아닌데 기대와 다름            {len(m['non_default_wrong'])}   (규칙이 '자신 있게' 틀린 것 — 트리거 밖)")
    out += [f"      {t!r} 기대 {e} / 규칙 {k}" for t, e, k in m["non_default_wrong"]]
    out.append(f"어려운 입력 {m['hard']} 중 기본값으로 떨어짐 {len(m['hard_default'])}: {m['hard_default']}")
    return "\n".join(out)


def main() -> int:
    sys.path.insert(0, str(ROOT / "tests"))
    from test_chat_corpus import CORPUS  # noqa: E402
    from test_never_ask_the_kind import HARD  # noqa: E402
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(report(measure(CORPUS, HARD)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
