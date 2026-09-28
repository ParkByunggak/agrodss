# -*- coding: utf-8 -*-
# [WO-LLM-01 사전 측정 2026-09-28] 제안 트리거('기본값으로 떨어진 발화') 집합을 저장소 안 문장으로 재는 도구가 스크래치패드에만 있었다 — 저장소로.
# 본다: 셈이 맞는가(합성 말뭉치) · 말뭉치가 규칙에 맞춰진 것이라 기본값이 틀린 것은 0 인가(상태 — 늘면 규칙이 말뭉치를 놓친 것) · 아무것도 쓰지 않는가.
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from scripts import measure_default_trigger as mdt
from tests.test_chat_corpus import CORPUS
from tests.test_never_ask_the_kind import HARD

ROOT = Path(__file__).resolve().parent.parent


def test_it_counts_default_hits_and_misses_on_a_synthetic_corpus():
    corpus = [("그냥 그렇다", "observation.note", None), ("하늘이 맑다", "event", None), ("지금 뭘 해야 하죠", "question", "plan_vs_actual")]
    m = mdt.measure(corpus, ["ㅋㅋ", "지금 뭘 해야 하죠"])
    assert [t for t, _, _ in m["default_ok"]] == ["그냥 그렇다"] and [t for t, _, _ in m["default_bad"]] == ["하늘이 맑다"]
    assert m["non_default_wrong"] == [] and m["hard_default"] == ["ㅋㅋ"] and m["corpus"] == 3 and m["hard"] == 2
    rep = mdt.report(m)
    assert "기본값이 틀림) 1" in rep and "'하늘이 맑다' 기대 event / 규칙 observation.note" in rep


def test_on_the_real_corpus_the_default_is_never_wrong_and_fragments_dominate_the_hard_inputs():
    """상태 — 말뭉치는 규칙에 맞춰진 것이라 기본값이 틀린 문장이 0 이어야 한다(늘면 규칙이 말뭉치를 놓친 것 · 말뭉치 검사가 먼저 붉는다).
    어려운 입력은 조각이라 대부분 기본값이다 — 그것이 지시서 §7 트리거를 그대로 쓰면 안 되는 이유."""
    m = mdt.measure(CORPUS, HARD)
    assert m["default_bad"] == [] and m["non_default_wrong"] == []
    assert len(m["hard_default"]) >= len(HARD) // 2, (len(m["hard_default"]), len(HARD))


def test_the_cli_prints_the_table_and_writes_nothing():
    watched = sorted(ROOT.glob("tests/*.py")) + sorted(ROOT.glob("scripts/*.py")) + sorted(ROOT.glob("data/*.json"))
    before = hashlib.sha1(b"".join(p.read_bytes() for p in watched)).hexdigest()
    r = subprocess.run([sys.executable, "-B", "-m", "scripts.measure_default_trigger"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "기본값(statement)으로 떨어진 문장" in r.stdout and "어려운 입력" in r.stdout, r.stderr
    assert hashlib.sha1(b"".join(p.read_bytes() for p in watched)).hexdigest() == before
    src = (ROOT / "scripts" / "measure_default_trigger.py").read_text(encoding="utf-8")
    assert "write_text" not in src and "write_bytes" not in src and "open(" not in src
