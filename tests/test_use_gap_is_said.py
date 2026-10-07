# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-07] 발행자가 **지금 하라고 안내받은 한 수**(용도 = 종구 생산)를 격리로 넣어 끝까지 걸었다. 대장 페이지의 약속은 지켜졌다.
#
#     경보   3 → 1       잎 기준 둘(첫 서리 · 수확 지연)이 멎고 과습만 남는다
#     수확   「종구 재배의 수확 때는 재배 달력에 아직 없습니다 — 잎 수확 기준으로는 말하지 않습니다」
#
# 그런데 그 다음이 문제였다: 「서리 오나」 의 답에서 **서리가 통째로 사라졌다.** 그 위험은 칸 5(수확)의 것이고 종구 기준이 없어 **안 낸 것**인데
# 답은 그 말을 하지 않는다 — 물은 축이 사라진 것을 농가가 알 길이 없다. 같은 자리에서 「다음 예정」 도 4 → 0 으로 비었다(놓침 6 은 그대로 · 처음엔
# 150자 자르기에 가려 「놓침이 늘었다」 로 잘못 읽었다 — 자른 글로 판정하지 않는다).
# 3층은 그 사실을 **메모에 적어 두고** 있었고 판단 화면은 보여 준다 — **농가 답만 침묵**했다(G1 셋째 형태: 흐르는데 표현 층이 말하지 않는다).
# 수확 시기 쪽은 이미 정직하게 말하고 있었으므로, 그 문면과 같은 결로 **위험·할 일**도 말하게 한다.
#
# 고정하는 것 일곱:
#   ① 약속 검증 — 용도를 넣으면 잎 기준 경보 둘이 멎는다(대장 페이지가 그렇게 약속한다)
#   ② 멎은 것을 **말한다** — 위험 답·할 일 답에 그 한 줄(양방향: 용도가 없으면 그 줄도 없다)
#   ③ 사실은 3층이 **구조로** 싣고(두 판정 같은 키) 문장은 4층 하나 · 자리는 답 말미 1회
#   ④ 안 낸 것의 이름은 판정마다 다르다 — `use_gap_stages` 를 내는 판정 **전부**가 표에 있다(전수)
#   ⑤ 칸 표기는 농가 꼴(「수확(5단계)」) · 되읽어도 안 바뀐다 · 안쪽 말 0
#   ⑥ 수확 시기 답은 **두 번 말하지 않는다**(그 쪽은 제 문장으로 이미 말한다)
#   ⑦ 대조군 — 용도가 종구가 아니면 그 줄이 없고 경보가 셋이다(측정이 살아있는지)
from __future__ import annotations

import ast
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from frontend import words
from ingest import chat, media
from judge import run as judge_run
from tests.test_screen_speaks_plainly import JARGON

ROOT = Path(chat.__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
T = date(2026, 10, 7)
LEAF = ("첫 서리 · 한파로 잎 손상", "수확 지연 — 잎 노화 · 도복")


def _use(tmp_path, monkeypatch, value: str | None) -> None:
    """발행자 PC 상태에서 용도만 바꾼다(격리 — 운영 등록부는 건드리지 않는다)."""
    doc = json.loads((ROOT / "data" / "parcels_seed.json").read_text(encoding="utf-8"))
    rows = doc["parcels"] if isinstance(doc, dict) and "parcels" in doc else doc
    if value is None:
        rows[0].pop("use", None)
    else:
        rows[0]["use"] = value
    p = tmp_path / "parcels.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    shutil.copy(ROOT / "data" / "subjects.json", tmp_path / "subjects.json")
    for k, v in (("AGRODSS_PARCELS_PATH", p), ("AGRODSS_PARCELS_LOCAL_PATH", p),
                 ("AGRODSS_PARCELS_LEGACY_PATH", tmp_path / "none.json"),
                 ("AGRODSS_SUBJECTS_PATH", tmp_path / "subjects.json"), ("AGRODSS_SUBJECTS_LOCAL_PATH", tmp_path / "sl.json")):
        monkeypatch.setenv(k, str(v))


def _alerts(today: date = T) -> list[str]:
    e = next(x for x in judge_run.judgments_for(SID, today=today) if x.decision_id == "risk_alert")
    return [str(a.get("risk")) for a in (e.result.get("alerts") or [])]


def _env(did: str, today: date = T):
    return next(x for x in judge_run.judgments_for(SID, today=today) if x.decision_id == did)


def test_the_promise_on_the_page_holds(tmp_path, monkeypatch):
    """[①] 용도를 넣으면 잎 기준 경보 둘이 멎는다 — 발행자에게 그렇게 약속해 두었다."""
    _use(tmp_path, monkeypatch, None)
    before = _alerts()
    assert all(x in before for x in LEAF), before                     # 조건부터 — 넣기 전에는 둘이 선다
    _use(tmp_path, monkeypatch, "종구 생산")
    after = _alerts()
    assert not [x for x in after if x in LEAF], after
    assert len(after) < len(before) and after, (before, after)         # 과습은 용도와 무관하게 남는다(다 꺼지는 것이 아니다)
    said = chat.answer(media.load_subjects()[0], "수확 언제 해요", T)
    assert "종구 재배의 수확 때는 재배 달력에 아직 없습니다" in said, said


def test_what_was_withheld_is_said(tmp_path, monkeypatch):
    """[②] 안 낸 것을 말한다 — 위험 답과 할 일 답 둘 다(양방향)."""
    _use(tmp_path, monkeypatch, "종구 생산")
    s = media.load_subjects()[0]
    for q, did in (("서리 오나", "risk_alert"), ("오늘 뭐 해야 하나", "plan_vs_actual")):
        e = _env(did)
        want = words.use_gap_said(str(e.result.get("use_gap_use") or ""), list(e.result.get("use_gap_stages") or []), did)
        assert want, (did, e.result.get("use_gap_stages"))
        assert want in chat.answer(s, q, T), (q, chat.answer(s, q, T))
    _use(tmp_path, monkeypatch, None)                                  # 용도가 없으면 그 줄이 없다(빈칸을 지어내지 않는다)
    s2 = media.load_subjects()[0]
    for q in ("서리 오나", "오늘 뭐 해야 하나"):
        assert "기준이 오면 냅니다" not in chat.answer(s2, q, T), q


def test_the_fact_is_structured_and_the_sentence_is_one(tmp_path, monkeypatch):
    """[③] 3층은 구조로(두 판정 **같은 키**) · 2층은 메모를 파싱하지 않는다 · 문장은 4층 하나."""
    _use(tmp_path, monkeypatch, "종구 생산")
    for did in ("risk_alert", "plan_vs_actual"):
        r = _env(did).result
        assert r.get("use_gap_stages") and r.get("use_gap_use"), (did, sorted(r))
    fn = next(n for n in ast.walk(ast.parse((ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "use_gap_line")
    # **독스트링은 걷는다** — 이 고침의 기록이 거기 적혀 있어 그대로 세면 검사가 헛돈다(§7.1 4번 · 이 트랙에서 일곱 번째)
    # `ast.get_docstring` 은 **다듬은 글**을 주므로 원문 상수와 같지 않다(값으로 걷으려다 한 번 헛돌았다) — **자리**로 걷는다(첫 문장)
    first = fn.body[0]
    doc_node = first.value if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) else None
    said = [c.value for c in ast.walk(fn) if isinstance(c, ast.Constant) and isinstance(c.value, str) and c is not doc_node]
    assert not [x for x in said if "기준" in x or "내지" in x], f"2층이 문장을 다시 쓴다: {said}"
    assert "notes" not in "".join(said), "메모 문장을 파싱하면 어휘가 두 벌이 된다"


def test_every_judgement_that_withholds_has_a_word_for_it(tmp_path, monkeypatch):
    """[④] 전수 — `use_gap_stages` 를 내는 판정 전부가 표에 있다(빈칸을 내는 판정이 늘면 여기가 터진다)."""
    _use(tmp_path, monkeypatch, "종구 생산")
    emits = {e.decision_id for e in judge_run.judgments_for(SID, today=T) if (e.result or {}).get("use_gap_stages")}
    assert emits, "이 상태에서 빈칸을 내는 판정이 있어야 전수가 뜻을 갖는다"
    assert emits <= set(words.USE_GAP_WHAT), sorted(emits - set(words.USE_GAP_WHAT))
    for did in words.USE_GAP_WHAT:
        assert words.use_gap_said("종구", ["5. 수확"], did), did


def test_the_sentence_is_in_people_words():
    """[⑤] 칸 표기는 농가 꼴 · 되읽어도 안 바뀐다 · 안쪽 말 0."""
    said = words.use_gap_said("종구", ["5. 수확", "6. 수확 후 · 후작"], "plan_vs_actual")
    assert "수확(5단계)" in said and "5. 수확" not in said, said
    assert words.plain(said) == said, said
    for bad in (*JARGON, "by_use", "use_gap"):
        assert bad not in said, (bad, said)
    assert words.use_gap_said("종구", ["엉뚱한 꼴"], "risk_alert").count("엉뚱한 꼴") == 1      # 모르는 꼴은 그대로 둔다(지어내지 않는다)


def test_the_harvest_answer_does_not_say_it_twice(tmp_path, monkeypatch):
    """[⑥] 수확 시기 답은 제 문장으로 이미 말한다 — 같은 말을 두 번 붙이지 않는다."""
    _use(tmp_path, monkeypatch, "종구 생산")
    said = chat.answer(media.load_subjects()[0], "수확 언제 해요", T)
    assert "기준이 오면 수확 때를 냅니다" in said, said
    assert "기준이 오면 냅니다 —" not in said and said.count("기준이 오면") == 1, said


def test_the_control_shows_the_instrument_is_alive(tmp_path, monkeypatch):
    """[⑦] 대조군 — 용도가 종구가 아니면 경보가 그대로 셋이고 그 줄도 없다(값을 바꿔 봉투를 다시 돌린다)."""
    _use(tmp_path, monkeypatch, "식용 잎 수확")
    after = _alerts()
    assert [x for x in after if x in LEAF] == list(LEAF), after
    assert (_env("risk_alert").result.get("use_gap_stages") or []) == []
    assert "기준이 오면 냅니다" not in chat.answer(media.load_subjects()[0], "서리 오나", T)
