# -*- coding: utf-8 -*-
# [소비자 재측정 2026-10-07] 밭 정보 값의 소비자 표는 10-05 에 다시 재서 늘었는데(용도 1→5 · 배수 1→2) **농사 값 쪽은 선언 그대로**였다 —
# 같은 문장(「넣으면 어느 판단이 읽습니다」)을 같은 함수로 내는데 한쪽만 측정이었다(§7.5 지점 축 · 처방이 한 곳에 갇힌 그 형태).
# 같은 방법으로 쟀다(값을 바꿔 날 셋 09-20 · 10-07 · 10-20 의 봉투 전부 대조 · 합집합):
#
#     인증     적힌 2 → 측정 **4**(자재 인용 · 웃거름 1회 · 웃거름 2회 · 계획 대 실제)  ※ 밑거름은 측정에 안 나왔다 — 못 잼(처방 원천 없음)
#     심은 날   적힌 3 → 측정 **11**(날짜를 세는 판단이 사실상 전부)
#
# 심은 날이 특히 나빴다 — 농가가 그 값을 넣을 때 화면은 셋만 말했는데 실제로는 가뭄 · 병해충 · 보식 · 파종 창 · 웃거름 둘 · 자재 인용 · 배수 경보가 함께 달라진다.
# 「경로 전수 예측은 늘 과소」 가 또 맞았다(1→5 · 1→2 · 2→4 · 3→11).
#
# 이 검사가 고정하는 것 다섯:
#   ① 표를 **다시 재서** 대조한다(선언을 믿지 않는다 · 값을 바꿔도 아무 판정이 안 달라지면 그것도 실패)
#   ② 못 잼(인증 → 밑거름)은 **지우지 않고** 사유를 남긴다 — 죽은 원천의 0 을 소비자 0 으로 읽으면 소비자를 지우게 된다
#   ③ 긴 목록은 앞 다섯과 **전체 수**로 말한다(수는 정본 길이에서 센다 — 줄이되 몇인지를 숨기지 않는다)
#   ④ 사람 말 · 조사 · 이름은 정본에서(검사에 이름을 박으면 재측정마다 거짓 실패다)
#   ⑤ 두 표가 같은 계약을 진다 — 새 농사 값이 생기면 소비자를 세기 전까지 관문이 빨갛다
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from frontend import words
from ingest import subjects
from judge import run as judge_run
from tests.test_screen_speaks_plainly import JARGON

ROOT = Path(subjects.__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
DAYS = (date(2026, 9, 20), date(2026, 10, 7), date(2026, 10, 20))
FLIPS = {"cert": ("관행", "유기"), "anchor": ("2026-08-25", "2026-08-10")}


def _with_subject(tmp_path, monkeypatch, field: str, value: str) -> dict[str, str]:
    doc = json.loads((ROOT / "data" / "subjects.json").read_text(encoding="utf-8"))
    rows = doc["subjects"] if isinstance(doc, dict) and "subjects" in doc else doc
    for s in rows:
        if s.get("id") == SID:
            s[field] = value
    p = tmp_path / f"s_{field}_{value}.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_SUBJECTS_PATH", str(p))
    monkeypatch.setenv("AGRODSS_SUBJECTS_LOCAL_PATH", str(tmp_path / "none_local.json"))
    return {}


def _envelopes(T: date) -> dict[str, str]:
    out = {}
    for _s, envs, _i in judge_run.all_judgments(T):
        for e in envs:
            ed = e.to_dict()
            out[ed["decision_id"]] = json.dumps({"k": ed["kind"], "r": ed.get("result"), "n": ed.get("notes")},
                                                ensure_ascii=False, sort_keys=True)
    return out


def _measure(tmp_path, monkeypatch, field: str) -> set[str]:
    a, b = FLIPS[field]
    seen: set[str] = set()
    for T in DAYS:
        _with_subject(tmp_path, monkeypatch, field, a)
        before = _envelopes(T)
        _with_subject(tmp_path, monkeypatch, field, b)
        after = _envelopes(T)
        assert len(before) >= 10, (T, sorted(before))      # 판정이 거의 안 돌았으면 측정이 닿지 않은 것이다(0 을 사실로 읽지 않는다)
        seen |= {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    return seen


@pytest.mark.parametrize("field", sorted(FLIPS))
def test_the_subject_table_says_exactly_the_judgments_that_change(tmp_path, monkeypatch, field):
    """[①②] 재서 대조한다 — 못 잼으로 적어 둔 짝만 빼고."""
    measured = _measure(tmp_path, monkeypatch, field)
    declared = set(subjects.SUBJECT_FIELD_CONSUMERS[field])
    unmeasurable = set(subjects.SUBJECT_CONSUMERS_UNMEASURABLE.get(field, ()))
    assert measured, (field, "값을 바꿨는데 아무 판정도 안 달라졌다 — 선언이 거짓이거나 측정이 닿지 않은 것이다")
    assert measured == declared - unmeasurable, (field, sorted(measured), sorted(declared), sorted(unmeasurable))
    assert unmeasurable <= declared, (field, sorted(unmeasurable - declared))      # 못 잼도 표에 남는다(지우지 않는다)


def test_the_unmeasurable_pair_keeps_its_reason_in_the_source():
    """[②] **안 하기로 한 것**과 **빠뜨린 것**을 가른다 — 다음 사람이 「측정에 안 나오니 지우자」 로 읽지 않게."""
    src = (ROOT / "ingest" / "subjects.py").read_text(encoding="utf-8")
    assert "측정 한계" in src and "처방 원천" in src
    for field, names in subjects.SUBJECT_CONSUMERS_UNMEASURABLE.items():
        assert names and all(n in subjects.SUBJECT_FIELD_CONSUMERS[field] for n in names), (field, names)


def test_a_long_list_says_how_many_without_hiding_it():
    """[③] 열한 이름을 한 줄에 늘어놓으면 농가가 안 읽고, 줄이면 「조건을 덜 말하는」 결함이 된다 — 앞 다섯과 **수**를 함께 말한다."""
    ids = subjects.SUBJECT_FIELD_CONSUMERS["anchor"]
    said = words.opened("anchor", "2026-08-25")
    assert len(ids) > words.NAMES_SHOWN
    assert f"{len(ids)}가지" in said, said                                  # 수는 정본 길이에서 센다(표가 늘면 문장도 따라 늘어난다)
    for d in ids[:words.NAMES_SHOWN]:
        assert words.decision(d) in said, d
    assert words.decision(ids[-1]) not in said                              # 다 늘어놓지는 않는다
    short = words.opened("drainage", "나쁨")                                 # 반대편 — 짧으면 그대로 다 말한다(수를 붙이지 않는다)
    assert "가지" not in short and "비롯해" not in short, short
    assert re.search(r"(을|를) 비롯해", said), said                          # 조사도 정본에서
    # 조사가 **계산되는지**를 양쪽으로 — 받침 있는 이름(…용)과 없는 이름(…계)에서 갈려야 한다(하드코딩이면 한쪽이 틀린다)
    long_with_batchim = ("a", "b", "c", "d", "자재 인용", "f")
    long_without = ("a", "b", "c", "d", "병해충 경보(3단계)", "f")
    assert words._names_said(long_with_batchim).endswith("자재 인용을 비롯해 6가지")
    assert words._names_said(long_without).endswith("병해충 경보(3단계)를 비롯해 6가지")


def test_the_sentence_is_plain_and_the_names_come_from_the_canon():
    """[④] 이름을 검사에 박지 않는다 — 재측정이 표를 고치면 문장도 따라 고쳐져야 하고, 검사는 그 사실만 본다."""
    for field, value in (("anchor", "2026-08-25"), ("cert", "유기")):
        said = words.opened(field, value)
        assert words.plain(said) == said and not [w for w in JARGON if w in said], (field, said)
        assert subjects.SUBJECT_FIELD_WORDS[field] in said and f"'{value}'" in said
        assert said.endswith("다음 답부터 그 근거에 실립니다.")
        assert words.opened(field, value, pending=True).startswith("넣으면")
    for ids in subjects.SUBJECT_FIELD_CONSUMERS.values():                   # 등록된 결정 이름이어야 한다(오타가 조용히 지나가지 않게)
        from judge import registry, stage_decisions  # noqa: F401 — 등록부 적재
        import ingest.chat  # noqa: F401
        known = registry.all_decisions()
        assert all(d in known for d in ids), [d for d in ids if d not in known]


def test_both_consumer_tables_carry_the_same_contract():
    """[⑤] 밭 정보 값과 농사 값은 같은 문장을 같은 함수로 낸다 — 계약도 같아야 한다(한쪽만 측정이면 다른 쪽이 거짓을 말한다)."""
    from ingest import parcels
    assert set(subjects.SUBJECT_FIELD_CONSUMERS) == set(subjects.SUBJECT_FIELD_WORDS), "농사 값이 늘면 소비자를 세기 전까지 여기가 빨갛다"
    assert all(v for v in subjects.SUBJECT_FIELD_CONSUMERS.values())
    both = set(parcels.FIELD_CONSUMERS) & set(subjects.SUBJECT_FIELD_CONSUMERS)
    assert not both, f"같은 이름이 두 표에 있으면 `words.opened` 가 어느 쪽을 쓸지 모른다: {sorted(both)}"
    src = (ROOT / "frontend" / "words.py").read_text(encoding="utf-8")
    body = src[src.index("def opened("):]
    body = body[:body.index("\ndef ", 10)]
    assert "parcels.FIELD_CONSUMERS" in body and "subjects.SUBJECT_FIELD_CONSUMERS" in body and "_names_said(" in body
