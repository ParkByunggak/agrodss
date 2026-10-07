# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-07] 11/10 로 미리 걸으니 「수확 언제 해요」 의 답이 이렇게 나왔다.
#
#     수확 기간 2026-10-14 ~ 2026-11-03 (±10.0일) · 근거: 짐작 · …
#
# 틀린 말은 하나도 없는데 **이미 일주일 지난 기간이 앞일처럼** 읽힌다. 같은 날 위험 쪽은 「수확 창을 7일 넘겼다」 를 알고 있었다 —
# 3층이 `position`(창 이전 · 창 안 · 창 지남)을 줄곧 계산하고 있었는데 **농가 줄이 그것을 읽지 않았다**(G1). 발행자 화면은 그 날말을
# 그대로 찍고 있었으니 소비자가 0 은 아니었다 — 「소비자 0」 으로 적었던 첫 판독을 전수로 고쳤고, 이 검사가 **두 소비자를 둘 다** 고정한다.
#
# 고정하는 것 일곱:
#   ① `position` 이 낼 수 있는 자리를 **재서** 사람 말 정본과 맞춘다(선언이 아니라 측정 — 3층에 자리가 늘면 여기가 터진다)
#   ② 농가 줄이 세 자리에서 **각각 다른 말**을 한다(창 지남이 창 안과 같은 말을 하면 원 결함 그대로다)
#   ③ 상대 날수는 **계산이다** — 두 날에서 각각 실제 차이와 같다(「7일 뒤」 를 박으면 다른 날에 틀린다)
#   ④ 절대 날짜가 먼저 있고 상대 말은 괄호에 — 상대만 있으면 달력에서 찾을 수 없다
#   ⑤ G1 양방향: `position` 이 없으면 그 말을 **하지 않는다**(빈 문자열 — 없는 자리를 지어내지 않는다)
#   ⑥ 층을 지킨다 — 3층은 날수만 주고(frontend 를 안 읽는다) 문장은 4층 정본 하나에서
#   ⑦ 사람 말 — 날말(「창」)이 농가 답에 그대로 나가지 않고, 되읽어도 안 바뀐다(plain 안정)
from __future__ import annotations

import ast
import re
from datetime import date, timedelta
from pathlib import Path

from frontend import words
from ingest import chat, media
from judge import harvest_timing
from tests.test_screen_speaks_plainly import JARGON

ROOT = Path(chat.__file__).resolve().parent.parent
Q = "수확 언제 해요"


def _subject() -> dict:
    return media.load_subjects()[0]


def _result(today: date) -> dict:
    e = harvest_timing.judge(_subject(), today=today)
    assert e.kind == "판단함", (today, e.kind)       # 조건부터 — 판단함이 아니면 아래 판정은 뜻이 없다
    return e.result


def _window() -> tuple[date, date]:
    r = _result(date(2026, 10, 7))
    return date.fromisoformat(r["window_start"]), date.fromisoformat(r["window_end"])


def _positions_measured() -> dict[str, date]:
    """3층이 **실제로 내는** 자리를 하루씩 걸어서 센다 — 자리 목록을 여기 박으면 3층이 늘 때 조용히 지나간다."""
    start, end = _window()
    out: dict[str, date] = {}
    for d in (start - timedelta(days=30), start - timedelta(days=1), start, start + timedelta(days=3),
              end, end + timedelta(days=1), end + timedelta(days=30)):
        out.setdefault(_result(d)["position"], d)
    return out


def test_the_positions_the_judgement_can_reach_are_all_said_in_people_words():
    """[①] 측정한 자리 전부가 사람 말 정본에 있다 — 양쪽 집합이 같다(한쪽만 늘면 터진다)."""
    measured = _positions_measured()
    assert set(measured) == set(words.WINDOW_SAID), (sorted(measured), sorted(words.WINDOW_SAID))
    assert len(measured) == 3, measured


def test_each_position_says_something_different_in_the_farmer_line():
    """[②] 세 자리가 농가 답에서 **각각 다른 말**을 한다 — 지난 기간이 앞일처럼 읽히던 것이 원 결함이다."""
    s = _subject()
    said: dict[str, str] = {}
    for pos, d in _positions_measured().items():
        line = chat.answer(s, Q, d)
        sentence = words.WINDOW_SAID[pos]
        assert sentence in line, (pos, d, line)
        said[pos] = sentence
    assert len(set(said.values())) == 3, said
    # 그리고 **다른 자리의 말은 같은 답에 없다** — 세 문장이 서로를 가리지 않는다
    for pos, d in _positions_measured().items():
        line = chat.answer(s, Q, d)
        for other, sentence in words.WINDOW_SAID.items():
            if other != pos:
                assert sentence not in line, (pos, other, line)


def test_the_relative_days_are_counted_not_written():
    """[③] 두 날에서 각각 **실제 차이**와 같다 — 한 날만 보면 박아 넣은 수와 구별이 안 된다(「7일 뒤」 전례)."""
    start, end = _window()
    for back in (7, 10, 25):
        d = start - timedelta(days=back)
        r = _result(d)
        assert r["days_to_start"] == back and r["days_past_end"] == 0, (d, r["days_to_start"], r["days_past_end"])
        assert f"{back}일 뒤" in words.where_in_window(r), (d, words.where_in_window(r))
    for past in (1, 7, 21):
        d = end + timedelta(days=past)
        r = _result(d)
        assert r["days_past_end"] == past and r["days_to_start"] == 0, (d, r["days_past_end"], r["days_to_start"])
        assert f"{past}일 전" in words.where_in_window(r), (d, words.where_in_window(r))
    # 하루·이틀은 수가 아니라 사람 말이다
    assert "내일" in words.where_in_window(_result(start - timedelta(days=1)))
    assert "모레" in words.where_in_window(_result(start - timedelta(days=2)))
    # 0일은 말하지 않는다 — 그 날은 이미 「창 안」 이라 셀 것이 없다
    for d in (start, end, start + timedelta(days=2)):
        assert "0일" not in words.where_in_window(_result(d)), d


def test_the_absolute_day_comes_first_and_the_relative_one_is_in_the_brackets():
    """[④] 「7일 뒤」 만 있으면 달력에서 못 찾는다 — 여는 날·끝난 날이 숫자로 함께 있다(대장 페이지 `when()` 과 같은 규율)."""
    start, end = _window()
    before, inside, after = words.where_in_window(_result(start - timedelta(days=7))), words.where_in_window(_result(start)), words.where_in_window(_result(end + timedelta(days=7)))
    assert f"{start.month}/{start.day}" in before, before
    assert f"{end.month}/{end.day}" in inside and f"{end.month}/{end.day}" in after, (inside, after)
    for said in (before, inside, after):
        assert said.count("(") == 1 and said.endswith(")"), said          # 괄호 하나 — 꼬리가 두 겹이면 길이만 늘고 읽히지 않는다
        assert re.search(r"\d+/\d+", said.split("(", 1)[1]), said


def test_without_a_position_the_line_says_nothing_about_today():
    """[⑤] G1 양방향 — 자리를 모르면 **지어내지 않는다**. 막는 쪽만 보면 열어 놓고 깨진 것을 못 본다."""
    assert words.where_in_window({}) == ""
    assert words.where_in_window(None) == ""                              # type: ignore[arg-type]
    assert words.where_in_window({"position": "창 밖"}) == ""              # 격자 쪽 다른 날말 — 이 자리의 말이 아니다
    start, _end = _window()
    r = dict(_result(start - timedelta(days=7)))
    assert words.where_in_window(r) != ""                                 # 같은 입력에서 자리만 뺀다(부분 주입 금지 — 원 결함 상태로 되돌린다)
    r.pop("position")
    assert words.where_in_window(r) == "", r
    s, head = _subject(), "[이렇게 보입니다]"
    line = chat.answer(s, Q, start - timedelta(days=7))
    assert line.startswith(head) and "—" in line                           # 꼬리를 붙이는 자리가 맞는지(아래 ⑥ 과 짝)


def test_the_judgement_gives_numbers_and_the_words_come_from_the_screen_layer():
    """[⑥] 3층은 날수만 준다 — frontend 를 읽지 않고, 문장 정본은 4층 하나다(층을 넘으면 말이 두 벌이 된다)."""
    src = (ROOT / "judge" / "harvest_timing.py").read_text(encoding="utf-8")
    assert not re.findall(r"^\s*(?:from|import)\s+frontend", src, re.M), [l for l in src.splitlines() if "frontend" in l]
    r = _result(date(2026, 10, 7))
    for k in ("position", "days_to_start", "days_past_end"):
        assert k in r, (k, sorted(r))
    assert not any(said in str(r.values()) for said in words.WINDOW_SAID.values())      # 3층 산출에 사람 문장이 섞이지 않는다
    # 소비자 전수 — 농가 줄(2층)과 발행자 화면(4층) **둘 다** 이 자리를 읽는다. 하나가 사라지면 여기가 터진다
    fn = next(n for n in ast.walk(ast.parse((ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "_judged_line")
    called = [a for a in ast.walk(fn) if isinstance(a, ast.Assign) and isinstance(a.value, ast.Call)
              and getattr(a.value.func, "attr", getattr(a.value.func, "id", "")) == "where_in_window"]
    assert len(called) == 1, "농가 줄이 이 자리를 한 번 부른다"
    name = called[0].targets[0].id                                         # 인자 표현식·줄 위치는 고정하지 않는다 — 부른 값이 **답으로 나가는지**만 본다
    used = [r for r in ast.walk(fn) if isinstance(r, ast.Return)
            for v in ast.walk(r) if isinstance(v, ast.Name) and v.id == name]
    assert used, f"{name} 을 부르고 답에 안 쓴다 — 원 결함 그대로다"
    serve = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")
    card = serve[serve.index('e["decision_id"] == "harvest_timing"'):]
    assert "position" in card[:900], card[:900]


def test_the_sentence_is_in_people_words():
    """[⑦] 날말(「창」)이 농가 답에 안 나가고, 되읽어도 안 바뀐다 — 사람 말 정본의 공통 규율."""
    start, end = _window()
    for d in (start - timedelta(days=7), start, end + timedelta(days=7)):
        said = words.where_in_window(_result(d))
        assert words.plain(said) == said, said
        for bad in ("창 이전", "창 안", "창 지남", "수확 창", *JARGON):
            assert bad not in said, (said, bad)
        line = chat.answer(_subject(), Q, d)
        for bad in ("창 이전", "창 안", "창 지남"):
            assert bad not in line, (d, bad, line)
