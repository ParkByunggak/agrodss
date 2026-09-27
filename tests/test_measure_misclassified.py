# -*- coding: utf-8 -*-
# [WO-LLM-01 착수 전 측정 2026-09-27] 지시서 §5-2 의 "라이브 오분류 이력" 은 기록으로는 없고 원장의 줄 순서에 있다 — 한 발화(id)의
# 첫 줄은 규칙의 초안, '다르게 적을까요?' 로 고르면 같은 id 의 뒷줄에 `사람이 고름` 초안. 그것을 세는 도구가 실제로 세는지,
# 아무것도 쓰지 않는지, 그리고 그 표지가 **choose_kind 가 쓰는 그 표지**인지(어휘 두 벌 금지)를 본다. 거부·통과 둘 다.
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

from ingest import chat, media
from scripts import measure_misclassified as mm

T = date(2026, 9, 24)
NOW = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


def _sid():
    return media.load_subjects()[0]["id"]


def _statement_sentence() -> str:
    """서술문 기본값(why_key=statement)으로 떨어지는 문장을 규칙에서 **찾는다** — 박아 두면 규칙이 자라며 검사가 거짓 실패한다."""
    for s in ("그냥 그렇다", "별일 없다", "오늘은 조용하다", "하늘이 맑다"):
        ds = chat.classify(s, T)
        if ds and ds[0].get("why_key") == mm.STATEMENT_KEY:
            return s
    raise AssertionError("서술문 기본값으로 떨어지는 문장을 못 찾았다 — 후보를 늘린다")


def test_counts_kind_corrections_edits_and_the_trigger_set():
    sid = _sid()
    stmt = _statement_sentence()
    m1, _ = chat.send(sid, stmt, today=T, now=NOW)                         # 규칙: 본 것(기본값) → 사람이 사건으로 고침 = 오분류 확정
    chat.choose_kind(m1["id"], "event", today=T)
    m2, _ = chat.send(sid, "별일 없었다 오늘도", today=T, now=NOW)          # 사람이 **같은** 종류를 고르면 오분류가 아니다(통과 쪽)
    chat.choose_kind(m2["id"], chat.classify("별일 없었다 오늘도", T)[0]["kind"], today=T)
    m3, _ = chat.send(sid, "어제 웃거름 줬다", today=T, now=NOW)            # 확인까지 — 미확인에 안 센다
    chat.confirm(m3["id"], 0, now=NOW)
    m4, _ = chat.send(sid, "쪽파는 언제 캐면 되나?", today=T, now=NOW, edit_of=m3["id"])   # 편집 쌍
    r = mm.measure()
    assert r["total"] == 4 and r["default_statement"] >= 1 and r["path"].endswith("index.jsonl") and r["measured_at"]
    assert [(c["rule"], c["human"], c["text"]) for c in r["chosen"]] == [("observation.note", "event", stmt)]
    assert [(e["from"], e["to"]) for e in r["edits"]] == [("어제 웃거름 줬다", "쪽파는 언제 캐면 되나?")]
    assert r["material"] == 2 and not r["enough"] and r["min_set"] == 30
    assert r["unconfirmed"] == 3                                            # m1 · m2 · m4 — m3 만 원장에 들어갔다
    rep = mm.report(r)
    assert "미달" in rep and stmt in rep and "→" in rep and "저장하지 않는다" in rep and "observation.note" not in rep   # 화면 말로


def test_it_reads_only_and_nothing_else_writes():
    sid = _sid()
    chat.send(sid, "어제 웃거름 줬다", today=T, now=NOW)
    d = chat.chat_dir()
    before = {p.name: hashlib.sha1(p.read_bytes()).hexdigest() for p in d.rglob("*") if p.is_file()}
    mm.report(mm.measure())
    after = {p.name: hashlib.sha1(p.read_bytes()).hexdigest() for p in d.rglob("*") if p.is_file()}
    assert before == after and before
    src = (ROOT / "scripts" / "measure_misclassified.py").read_text(encoding="utf-8")
    assert "write_text" not in src and "write_bytes" not in src and 'open(' not in src.replace("path.exists()", "")   # 쓰는 호출형이 없다
    assert mm.measure(Path("/nonexistent/index.jsonl"))["total"] == 0                                                # 원장이 없으면 0


def test_the_marker_it_reads_is_the_one_choose_kind_writes():
    """어휘 한 벌 — 측정기의 표지와 choose_kind 의 표지가 갈리면 측정이 조용히 0 이 된다(한쪽으로 쏠린 결과는 도구 버그의 표지)."""
    src = (ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")
    assert src.count('"사람이 고름"') == 1                                    # 정의 한 곳뿐 — 리터럴을 두 번 쓰지 않는다
    msrc = (ROOT / "scripts" / "measure_misclassified.py").read_text(encoding="utf-8")
    assert "chat.CHOSEN_WHY" in msrc and "사람이 고름" not in msrc.split("def measure")[1]
    sid = _sid()
    m, _ = chat.send(sid, "어제 웃거름 줬다", today=T, now=NOW)
    assert chat.choose_kind(m["id"], "observation.note", today=T)["drafts"][0]["why"] == chat.CHOSEN_WHY
