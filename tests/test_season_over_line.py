# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-07] 재배 달력의 **끝 뒤로** 걸었다(심은 날 + 91일 · + 107일). 답이 이랬다.
#
#     「오늘 뭐 해야 하나」  [이렇게 보입니다] 놓침 12 — 사유를 묻는다: 종구 선별 · 소독(1단계), … 잔사 정리 · 후작 준비(6단계)
#     「서리 오나」          [이렇게 보입니다] 경보 수확 지연(5. 수확) · 근거: 짐작 · 다시 보는 날 2026-12-11
#
# **날마다 영구히** 그렇다. 멎게 하는 길은 둘 다 있었다 — 수확 기록을 넣거나, 마쳤다고 말하면 그 뒤 계획을 놓침으로 세지 않는다(2026-09-20 처방).
# 그런데 그 길을 **농가에 말하는 자리가 하나도 없었다**: 화면에는 상태 색 하나뿐이고 답은 한 번도 그 말을 하지 않는다. 길이 있는데 모르면 길이 없는
# 것과 같다(「0 은 두 가지다」 의 안내 판). **닫는 것은 사람 몫 그대로** — 시스템이 대신 닫지 않는다. 이 묶음이 한 일은 그 수를 보이게 한 것뿐이다.
#
# 고정하는 것 아홉:
#   ① 경계 **양방향** — 달력 마지막 날에는 말하지 않고, 그 다음 날부터 말한다(막는 쪽만 보면 열어 놓고 깨진 것을 못 본다)
#   ② 이미 닫힌 뒤에는 말하지 않는다 · 달력이 없는 작목(대파)에도 말하지 않는다(없는 수를 권하지 않는다)
#   ③ 마지막 날은 **달력에서 센다** — 칸을 늘리면 따라온다(90을 박으면 다음 달력에서 거짓이 된다) · `max(to_day)` 는 정본 한 곳뿐
#   ④ 두 지점이 **같은 문장** — 채팅 답과 판단 화면(한쪽만 고치면 다른 쪽이 침묵한다 · §7.5 지점 축)
#   ⑤ 농가에 보여 주는 **적을 말**은 분류가 정말 종료 선언으로 읽는다(어휘 두 벌 금지 · 검사의 검사)
#   ⑥ 사람 말 — 「작기」 같은 안쪽 말이 없고 되읽어도 안 바뀐다
#   ⑦ 넣으면 **어디로 가는가**를 종류 전수로 — `confirm()` 이 쓰는 종류 전부가 표에 있다(안 넣으면 자리를 말하지 않는다)
#   ⑧ 일지로 **안 가는** 종류가 일지라고 말하지 않는다(그 카드로 농가를 보내는 줄이 ①에서 생겼다 — 거짓이면 그 줄이 거짓을 가리킨다)
#   ⑨ 조사는 값이 고른다 — 「납품 날짜(으)로」 가 그대로 나가던 자리
from __future__ import annotations

import ast
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from frontend import serve, words
from grid import schema as grid_schema
from ingest import chat, media
from tests.test_screen_speaks_plainly import JARGON

ROOT = Path(chat.__file__).resolve().parent.parent
Q = "오늘 뭐 해야 하나"


def _subject() -> dict:
    return media.load_subjects()[0]


def _last_day() -> int:
    unit, miss = grid_schema.load_unit(_subject())
    assert unit and miss is None, miss
    last = grid_schema.last_day(unit)
    assert isinstance(last, int), last
    return last


def _day(n: int) -> date:
    return date.fromisoformat(_subject()["anchor"]) + timedelta(days=n)


def test_the_last_day_of_the_calendar_is_counted_not_typed(monkeypatch):
    """[③] 칸을 하나 늘리면 마지막 날이 따라온다 — 수를 박으면 다음 달력에서 거짓이 된다."""
    base = {"stages": [{"window": {"from_day": 0, "to_day": 10}}, {"window": {"from_day": 10, "to_day": 30}}]}
    assert grid_schema.last_day(base) == 30
    grown = {"stages": base["stages"] + [{"window": {"from_day": 30, "to_day": 44}}]}
    assert grid_schema.last_day(grown) == 44
    assert grid_schema.last_day({"stages": []}) is None                     # 칸이 없으면 셀 것이 없다(0 이라고 하지 않는다)
    assert grid_schema.last_day({"stages": [{"window": grid_schema.NA}]}) is None
    # 그리고 이 셈은 정본 한 곳이다 — 다른 모듈이 또 max 를 돌면 칸이 늘 때 한쪽만 따라온다
    others = []
    for d in ("judge", "ingest", "frontend", "scripts"):
        for f in sorted((ROOT / d).glob("*.py")):
            for m in re.finditer(r"max\([^\n]*to_day", f.read_text(encoding="utf-8")):
                others.append(f"{f.name}: {m.group(0)[:60]}")
    assert others == [], others


def test_the_line_starts_the_day_after_the_calendar_ends(monkeypatch):
    """[①] 경계 양방향 — 마지막 날엔 없고 그 다음 날부터 있다."""
    last = _last_day()
    s = _subject()
    assert grid_schema.past_calendar(s, _day(last)) is None, "달력이 아직 말하는 날에는 그 말을 하지 않는다"
    assert grid_schema.past_calendar(s, _day(last + 1)) == (last + 1, last)
    assert grid_schema.past_calendar(s, _day(last + 17)) == (last + 17, last)
    assert chat.season_over_line(s, _day(last)) == ""
    said = chat.season_over_line(s, _day(last + 1))
    assert said.startswith(" · ") and str(last) in said and str(last + 1) in said, said
    # 답에도 같은 경계 — 마지막 날의 답에는 그 말이 없고 다음 날의 답에는 있다
    before, after = chat.answer(s, Q, _day(last)), chat.answer(s, Q, _day(last + 1))
    assert "재배 달력은 심은 날부터" not in before, before
    assert "재배 달력은 심은 날부터" in after, after


def test_it_says_nothing_once_the_season_is_closed_or_when_there_is_no_calendar(monkeypatch):
    """[②] 이미 닫혔으면 · 달력이 없으면 말하지 않는다 — 없는 수를 권하지 않는다."""
    last = _last_day()
    ended = dict(_subject(), status="종료", ended_at=_day(last + 2).isoformat())
    assert grid_schema.past_calendar(ended, _day(last + 30)) is None
    assert chat.season_over_line(ended, _day(last + 30)) == ""
    no_anchor = {k: v for k, v in _subject().items() if k != "anchor"}
    assert grid_schema.past_calendar(no_anchor, _day(last + 30)) is None
    # 달력 없는 작목 — 발행자 PC 의 둘째 작목(대파)이 그 꼴이다. 저장소 등록부에는 쪽파뿐이라 **그 조건**을 만들어 본다(격자 미연결)
    no_grid = {k: v for k, v in _subject().items() if k != "grid_unit"}
    assert grid_schema.load_unit(no_grid)[0] is None, "이 갈래는 격자가 안 이어진 상태다"
    assert grid_schema.past_calendar(no_grid, _day(last + 30)) is None
    assert chat.season_over_line(no_grid, _day(last + 30)) == ""


def test_both_places_say_the_same_sentence(monkeypatch):
    """[④] 채팅 답과 판단 화면이 **같은 문장** — 한 지점만 고치면 다른 쪽이 침묵한다."""
    last = _last_day()
    said = words.season_over(last + 17, last, chat.END_SAY)
    assert said in chat.answer(_subject(), Q, _day(last + 17))
    monkeypatch.setenv("AGRODSS_TODAY", _day(last + 17).isoformat())
    st, html = serve.judge_page()
    assert st == 200
    import html as _h
    assert said in _h.unescape(html), [l for l in _h.unescape(html).splitlines() if "재배 달력은" in l][:2]


def test_the_words_we_tell_the_farmer_to_type_are_read_as_the_end_declaration():
    """[⑤] 보여 주는 예가 정말 종료 선언으로 읽히는가 — 예를 지어내면 적어도 아무 일이 안 난다(어휘 두 벌 금지)."""
    assert any(w in chat.END_SAY for w in chat.END_WORDS), (chat.END_SAY, chat.END_WORDS)
    t = date(2026, 12, 10)
    drafts = chat.classify(chat.END_SAY, t)
    assert [d["kind"] for d in drafts] == ["subject.end"], drafts
    assert chat.classify("농사 끝나기 전에 웃거름을 줬다", t)[0]["kind"] != "subject.end"   # 종속절은 선언이 아니다(원 규율 유지)


def test_the_sentence_is_in_people_words():
    """[⑥] 안쪽 말이 없고 되읽어도 안 바뀐다."""
    last = _last_day()
    said = words.season_over(last + 1, last, chat.END_SAY)
    assert words.plain(said) == said, said
    for bad in ("작기", "재배 단위", *JARGON):
        assert bad not in said, (bad, said)
    with pytest.raises(ValueError):
        words.season_over(last, last, chat.END_SAY)                          # 끝나지 않은 날에 이 말을 만들 길이 없다


def test_the_promise_matches_what_closing_actually_does(tmp_path, monkeypatch):
    """[⑩] 약속과 동작을 **대조한다** — 적고 단추를 누르면 무엇이 멎고 무엇이 남는가.

    [직렬 게이트] 첫 판 문장은 「그 뒤 계획을 못 한 일로 세지 않고」 였는데, 눌러 보니 수확 지연은 멎고 **놓침은 그대로**였다(마친 날 전의 계획이라서).
    문장이 거짓은 아니어도 농가는 *"멎는다"* 로 읽는다 — 그래서 멎는 것과 남는 것을 둘 다 말하고, **그 둘을 여기서 잰다**(닫는 뜻을 바꾸면 여기가 터진다).
    """
    import json
    import shutil
    from ingest import subjects
    shutil.copy(ROOT / "data" / "subjects.json", tmp_path / "subjects.json")
    for k, v in (("AGRODSS_SUBJECTS_PATH", tmp_path / "subjects.json"), ("AGRODSS_SUBJECTS_LOCAL_PATH", tmp_path / "local.json")):
        monkeypatch.setenv(k, str(v))
    last = _last_day()
    t = _day(last + 17)
    sid = _subject()["id"]
    before = chat.answer(subjects.by_id(sid), Q, t)
    assert "놓침" in before and "재배 달력은 심은 날부터" in before, before          # 조건부터 — 두 줄이 다 서야 대조가 성립한다
    subjects.set_status(sid, "종료", ended_at=t.isoformat())                      # 농가가 적고 누른 것과 같은 길(chat.confirm 이 부르는 그 함수)
    s2 = subjects.by_id(sid)
    after = chat.answer(s2, Q, t)
    assert "재배 달력은 심은 날부터" not in after, after                           # 닫힌 뒤에는 그 말을 다시 하지 않는다
    said = words.season_over(last + 17, last, chat.END_SAY)
    # ① 멎는다고 한 것은 멎는다 — 수확이 늦었다는 알림
    assert "수확이 늦었다는 알림이 멎고" in said
    assert "수확 지연" not in chat.answer(s2, "서리 오나", t), chat.answer(s2, "서리 오나", t)
    # ② 남는다고 한 것은 남는다 — 마친 날 **전**의 못 한 일(이 줄이 없으면 문장이 약속을 키운다)
    assert "마친 날 전에 못 한 일은 그대로 남습니다" in said
    assert "놓침" in after, after
    assert json.loads((tmp_path / "subjects.json").read_text(encoding="utf-8"))      # 운영 등록부가 아니라 tmp 에 썼다(원장 3칙)


def _confirm_kinds() -> set[str]:
    """`confirm()` 이 **실제로 받는** 종류 — 소스에서 분기를 세어 온다(목록을 검사에 박으면 종류가 늘 때 조용히 지나간다)."""
    fn = next(n for n in ast.walk(ast.parse((ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "_confirm_locked")
    out: set[str] = set()
    for cmp_ in (n for n in ast.walk(fn) if isinstance(n, ast.Compare)):
        if not (isinstance(cmp_.left, ast.Name) and cmp_.left.id == "k"):
            continue
        for c in cmp_.comparators:
            if isinstance(c, ast.Constant) and isinstance(c.value, str):
                out.add(c.value)
            elif isinstance(c, (ast.Tuple, ast.List, ast.Set)):
                out.update(x.value for x in c.elts if isinstance(x, ast.Constant) and isinstance(x.value, str))
    assert len(out) >= 7, out
    return out


def test_every_kind_that_can_be_confirmed_says_where_it_goes():
    """[⑦] 자리 표가 **전수**다 — 넣을 수 있는 종류 전부가 표에 있거나 밭·농사 정보 분기에 있다."""
    own = {"parcel.field", "subject.field"}                                  # 자리와 고칠 곳을 함께 말하는 분기(카드 함수 안)
    missing = _confirm_kinds() - set(chat.PLACE_SAID) - own
    assert missing == set(), f"넣을 수 있는데 어디로 가는지 말하지 않는 종류: {sorted(missing)}"
    extra = set(chat.PLACE_SAID) - _confirm_kinds()
    assert extra == set(), f"넣을 수 없는 종류가 표에 있다(죽은 줄): {sorted(extra)}"
    # 모르는 종류에는 **아무 자리도 말하지 않는다** — 틀린 자리를 말하는 것이 침묵보다 나쁘다
    said = chat.card_line({"kind": "없는종류", "why": "x"})
    tail = said.split("누르면", 1)[1]                                        # 단추 말(기본값)은 그대로 — 판정은 **자리를 말하는 꼬리**에 대해서다
    assert "들어갑니다" not in tail and "일지" not in tail, said


def test_the_kinds_that_do_not_go_to_the_diary_do_not_say_diary():
    """[⑧] 일지로 안 가는 종류가 일지라고 말하지 않는다 — 그 카드로 농가를 보내는 줄이 이 묶음에서 생겼다."""
    diary = {"event", "observation.note", "plan.farmer", "decision.noncompliance"}      # 일지 화면이 스스로 펼친다고 적은 것들
    for kind in _confirm_kinds() - {"parcel.field", "subject.field"}:
        said = chat.card_line({"kind": kind, "why": "x", "text": "x", "task": "관수", "reason": "비", "ended_at": "2026-12-10"})
        if kind in diary:
            assert "영농일지" in said, (kind, said)
        else:
            assert "영농일지" not in said, (kind, said)
            place = chat.PLACE_SAID.get(kind)
            assert place, (kind, "자리 표에 없다 — 어디로 가는지 말하지 않는 종류다")
            assert place.split("(")[0].rstrip(".").split(" — ")[0] in said, (kind, said)
    end = chat.card_line({"kind": "subject.end", "why": "x", "ended_at": "2026-12-10"})
    assert "닫습니다" in end and chat.confirm_label("subject.end") in end, end


def test_the_particle_follows_the_word():
    """[⑨] 「납품 날짜(으)로 읽었습니다」 가 그대로 나가던 자리 — 조사는 값이 고른다(열여섯 자리 처방의 다음 한 곳)."""
    for word in chat.KIND_PLAIN.values():
        said = f"{word} 로 읽었습니다"
        assert "(으)로" not in said
    for kind in chat.KIND_PLAIN:
        said = chat.plain_why({"kind": kind, "why": "x", "text": "x"})
        assert "(으)로" not in said and "(이)" not in said, (kind, said)
    assert chat.plain_why({"kind": "plan.target_date"}).startswith("납품 날짜로"), chat.plain_why({"kind": "plan.target_date"})
