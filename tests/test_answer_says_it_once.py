# -*- coding: utf-8 -*-
# [길이 측정 2026-10-07] 다섯 회차 동안 농가 답에 줄을 **쌓았다**(카드 문장 · 기다리는 값 · 안 넣은 사건 · 되묻기). 그래서 오늘 상태로 **길이를 쟀다**:
#
#     실제 상태(일지 선언 둘 + 미확인 초안 셋 · 2026-10-07)   고치기 전 → 고친 뒤
#       「오늘 뭐 해야 하나」   651자 → **556자**   「'일지에 넣기' 를 누르면 판단이 읽습니다」 가 **세 번** 똑같이 나갔다(관수 · 방제 · 예찰)
#       「서리 오나」          502자 → **419자**   「… 아직 안 들어갔습니다(왼쪽 메뉴 … 에서 넣으면 다시 답합니다)」 가 **두 번**(용도 · 배수)
#
# 늘어난 것은 **정보가 아니라 꼬리**였다 — 값 이름과 건수만 다르고 나머지는 같은 말이다. 줄이면 「조건을 덜 말하는」 결함이 되므로
# **종류·건수·값은 다 말하고 꼬리는 한 번만** 말한다(`words.waiting_many` · `words.not_in_diary_many`).
#
# 이 검사가 고정하는 것 다섯:
#   ① 한 답 안에서 **같은 문장이 두 번 나오지 않는다**(쌓이는 쪽을 전수로 — 다음 회차에 줄을 더해도 여기가 먼저 터진다)
#   ② 꼬리가 한 번이어도 **정보는 다 남는다**(종류·건수·값 이름이 그대로 · 덜 말하면 다른 사실이다)
#   ③ 한 종류·한 값이면 **전과 같은 문장**이다(바꿀 이유가 없는 쪽은 안 바꾼다)
#   ④ 사람 말 · 조사 · 0건 금지는 그대로
#   ⑤ 길이는 측정값으로 못 박지 않는다 — 대신 **겹침 0** 과 그 자리의 문장 수로 본다(길이 상한을 박으면 다음 처방이 그 상한에 걸려 정보를 버린다)
from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from frontend import words
from ingest import chat, events as ev, subjects
from tests.test_screen_speaks_plainly import JARGON

ROOT = Path(chat.__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
T = date(2026, 10, 7)
NOW = datetime(2026, 10, 7, 9, tzinfo=timezone.utc)
QUESTIONS = ("수확 언제 해요", "서리 오나", "병충해 뭐 봐야 하나", "물 줘야 하나", "오늘 뭐 해야 하나", "약 뭐 쳐요")


@pytest.fixture()
def loaded(tmp_path, monkeypatch):
    """실제 상태 — 용도 미기재(발행자 PC) + 일지 선언 둘 + 미확인 초안 셋. 쌓이는 줄이 전부 서는 자리다."""
    doc = json.loads((ROOT / "data" / "parcels_seed.json").read_text(encoding="utf-8"))
    rows = doc["parcels"] if isinstance(doc, dict) and "parcels" in doc else doc
    rows[0].pop("use", None)
    p = tmp_path / "parcels.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    shutil.copy(ROOT / "data" / "subjects.json", tmp_path / "subjects.json")
    for k, v in (("AGRODSS_PARCELS_PATH", p), ("AGRODSS_PARCELS_LOCAL_PATH", p), ("AGRODSS_PARCELS_LEGACY_PATH", tmp_path / "none.json"),
                 ("AGRODSS_SUBJECTS_PATH", tmp_path / "subjects.json"), ("AGRODSS_SUBJECTS_LOCAL_PATH", tmp_path / "subjects_local.json")):
        monkeypatch.setenv(k, str(v))
    ev.add_observation(SID, "종구생산을 위한 목적이다", "2026-10-04")
    ev.add_observation(SID, "고랑 물 빠짐이 잘 되고 있다", "2026-10-03")
    for said in ("어제 물 줬다", "그저께 약 쳤다", "10월 5일에 예찰했다"):
        chat.send(SID, said, today=T, now=NOW)
    assert [len(chat.unconfirmed_of(SID, k)) for k in ("관수", "방제", "예찰")] == [1, 1, 1]      # 조건부터(안 서면 아래 판정은 뜻이 없다)
    return tmp_path


def _clauses(said: str) -> list[str]:
    """꼬리가 겹치는지 보려면 **문장 단위**로 자른다 — ' · ' 로 이은 줄들과 「— …」 꼬리 둘 다."""
    parts = [c.strip() for c in said.split(" · ")]
    return [c for c in parts if len(c) >= 20]


def test_no_clause_is_said_twice_in_one_answer(loaded):
    """[①] 쌓이는 쪽을 전수로 — 여섯 물음 전부에서 같은 문장이 두 번 나오지 않는다."""
    for q in QUESTIONS:
        _m, r = chat.send(SID, q, today=T, now=NOW)
        said = r["text"]
        seen: dict[str, int] = {}
        for c in _clauses(said):
            seen[c] = seen.get(c, 0) + 1
        twice = {c: n for c, n in seen.items() if n > 1}
        assert not twice, (q, twice)
        for tail in ("누르면 판단이 읽습니다", "에서 넣으면 다시 답합니다"):          # 꼬리 자체도 한 번만
            assert said.count(tail) <= 1, (q, tail, said.count(tail))


def test_the_information_survives_the_shortening(loaded):
    """[②] 꼬리를 한 번만 말해도 **종류·건수·값은 다 남는다** — 줄이는 것이 조건을 버리는 것이 되면 안 된다(G1 반대형)."""
    _m, r = chat.send(SID, "오늘 뭐 해야 하나", today=T, now=NOW)
    said = r["text"]
    for kind in ("관수", "방제", "예찰"):
        assert f"{kind} 1건" in said, (kind, said[-300:])
    assert "아직 일지에 넣지 않은 기록이 있습니다" in said and "일지에 넣기" in said
    _m2, r2 = chat.send(SID, "서리 오나", today=T, now=NOW)
    assert "용도 · 배수 값 없이" in r2["text"] and "'종구 생산'" in r2["text"] and "'좋음'" in r2["text"]
    # [주입 D] 값만 보면 **읽은 날**이 사라져도 통과한다 — 날짜는 그 값의 출처다(조건을 떼면 근거가 날조로 보인다 · G1 반대형)
    for day in ("2026-10-04", "2026-10-03"):
        assert day in r2["text"], (day, r2["text"][-260:])


def test_one_kind_keeps_the_old_sentence(loaded):
    """[③] 한 종류면 전과 같은 문장이다 — 바꿀 이유가 없는 쪽을 바꾸면 옛 검사가 거짓 실패하고 농가도 다른 말을 읽는다."""
    _m, r = chat.send(SID, "물 줘야 하나", today=T, now=NOW)      # 가뭄 답은 관수 하나만 읽는다
    assert "아직 일지에 넣지 않은 관수 기록 1건이 있습니다 — '일지에 넣기' 를 누르면 판단이 읽습니다" in r["text"]
    assert words.not_in_diary("관수", 1, "일지에 넣기") == "아직 일지에 넣지 않은 관수 기록 1건이 있습니다 — '일지에 넣기' 를 누르면 판단이 읽습니다"
    one = words.waiting("use", "종구 생산", "2026-10-04")
    assert words.waiting_many([("use", "종구 생산", "2026-10-04")]) == one          # 하나면 같은 문장(두 벌 만들지 않는다)


def test_the_joined_sentences_are_plain_and_refuse_zero():
    """[④] 사람 말 · 조사 · 0건 금지 — 합친 꼴에도 그대로 선다."""
    many = words.not_in_diary_many([("관수", 1), ("방제", 2)], "일지에 넣기")
    assert words.plain(many) == many and not [w for w in JARGON if w in many]
    assert "'일지에 넣기' 를" in many                                               # 조사도 정본에서(기 → 를)
    with pytest.raises(ValueError):
        words.not_in_diary_many([("관수", 0)], "일지에 넣기")
    with pytest.raises(ValueError):
        words.not_in_diary_many([], "일지에 넣기")
    vals = words.waiting_many([("use", "종구 생산", "2026-10-04"), ("drainage", "좋음", "2026-10-03")])
    assert words.plain(vals) == vals and not [w for w in JARGON if w in vals]
    assert words.waiting_many([]) == ""                                            # 없으면 아무 말도 하지 않는다
    assert vals.count("에서 넣으면 다시 답합니다") == 1


def test_the_lines_are_built_in_one_place(loaded):
    """[배선] 2층이 문장을 다시 조립하면 꼬리가 또 늘어난다 — 합치는 일은 4층 정본이 한다(`*_many`)."""
    src = (ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")
    for fn, call in (("def pending_value_line", "_w.waiting_many("), ("def unconfirmed_line", "_w.not_in_diary_many(")):
        body = src[src.index(fn):]
        body = body[:body.index("\ndef ", 10)]
        assert call in body, (fn, call)
        assert '" · ".join(out)' not in body, (fn, "2층이 직접 이으면 꼬리가 줄마다 붙는다")


def test_the_answer_does_not_grow_without_saying_more(loaded):
    """[⑤] 길이 상한은 박지 않는다(다음 처방이 그 상한에 걸려 정보를 버린다) — 대신 **문장 수**로 본다: 쌓이는 줄은 많아야 둘(값 한 줄 · 사건 한 줄)."""
    for q in QUESTIONS:
        _m, r = chat.send(SID, q, today=T, now=NOW)
        said = r["text"]
        added = [c for c in _clauses(said) if c.startswith("이 답은") or c.startswith("아직 일지에 넣지 않은")]
        assert len(added) <= 2, (q, added)
        assert said.count("이 답은") <= 1 and said.count("아직 일지에 넣지 않은") <= 1, q
