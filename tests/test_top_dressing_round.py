# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-13 — 수확 창 여는 날(10-14) 하루 전] 「웃거름 언제 줘요」 · 「추비 해야 하나」 · 「웃거름 2회 줘야 하나」 가 전부 웃거름 **1회**로 가서
# 2회 때(10-04~10-14) 안에 「웃거름 때가 지났습니다 — 마감 2026-09-24」 가 나갔다. 같은 날 카드·/judge 는 2회 때가 열려 있다고 말했다.
# 둘이 겹쳐 있었다:
#   ① 경로 — 회차를 말하지 않은 물음이 한 회차에 묶였다(2026-09-29 병·벌레 물음 「칸 비특정」 과 같은 형태 · 그 처방이 병·벌레에만 닿았다 — §7.5 지점)
#   ② 문면 — 「웃거름 때가 지났습니다」 가 **회차를 뗐다**(반대형 — 조건 탈락: 1회가 지난 것을 웃거름 전부가 지난 것으로 읽는다)
# 처방: 회차 묶음(stage_decisions.ROUNDS) · 때가 안 지난 첫 회차를 고른다(봉투가 이미 가른 '지났다' 를 읽는다 — 마감 셈을 두 벌 두지 않는다) ·
# 회차를 말한 물음은 그 회차로 · 지난 줄은 회차 이름을 싣는다 · 고른 회차의 이름을 답이 말한다.
#
# 날짜를 박지 않는다 — 때와 마감은 재배 달력(격자)에서 다시 센다(격자가 바뀌면 검사가 따라온다).
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest

from frontend import selfcheck, words
from grid import schema as grid_schema
from ingest import chat, media
from judge import registry
from judge import run as judge_run
from judge import stage_decisions as SD

FAMILY = "top_dressing"


def _subject():
    return media.load_subjects()[0]


def _windows() -> dict[str, tuple[date, date]]:
    """회차마다 (작업일, 마감일) — 격자에서 센다."""
    s = _subject()
    unit, miss = grid_schema.load_unit(s)
    assert unit and not miss, miss
    a = date.fromisoformat(s["anchor"])
    out = {}
    for did in SD.ROUNDS[FAMILY]:
        p = registry.get(did).params
        stage = next(st for st in unit["stages"] if int(st["order"]) == int(p["stage_order"]))
        t = SD._task(stage, p["task_key"])
        out[did] = (a + timedelta(days=int(t["work_day"])), a + timedelta(days=SD._deadline_day(t)))
    return out


def test_the_grid_really_has_two_rounds_with_a_gap_between_their_deadlines():
    """전제가 서 있는가 — 1회 마감이 2회 마감보다 앞이어야 이 검사가 뜻을 갖는다."""
    w = _windows()
    (_, dl1), (wd2, dl2) = w["top_dressing_1"], w["top_dressing_2"]
    assert dl1 < dl2 and dl1 < wd2 <= dl2, w


@pytest.mark.parametrize("q", ["웃거름 언제 줘요", "추비 해야 하나", "웃거름 지금 줘도 되는지"])
def test_inside_the_second_window_the_answer_is_the_second_round_not_the_first_deadline(q):
    w = _windows()
    (_, dl1), (wd2, dl2) = w["top_dressing_1"], w["top_dressing_2"]
    assert chat.topic_of(q) == FAMILY
    for day in (dl2 - timedelta(days=1), dl2):                                     # 10-13 · 10-14(마지막 날)
        a = chat.answer(_subject(), q, day)
        assert "때가 지났습니다" not in a, (day, a)
        assert dl1.isoformat() not in a, (day, a)                                  # 1회 마감을 웃거름 전체의 마감처로 말하지 않는다
        assert f"{wd2.isoformat()}~{dl2.isoformat()}" in a, (day, a)
        assert f"「{words.decision('top_dressing_2')}」" in a, (day, a)           # 어느 회차의 답인지 말한다


def test_the_answer_and_the_card_say_the_same_window_on_the_same_day():
    """한 사실을 두 화면이 반대로 말하던 것 — 답은 그날 카드(같은 봉투)의 줄을 싣는다."""
    day = _windows()["top_dressing_2"][1] - timedelta(days=1)
    card = next(e for e in judge_run.judgments_for(_subject()["id"], today=day) if e.decision_id == "top_dressing_2")
    a = chat.answer(_subject(), "웃거름 언제 줘요", day)
    assert words.plain(card.result["summary"]) in a, (card.result["summary"], a)


def test_inside_the_first_window_the_answer_is_still_the_first_round():
    """양방향 — 1회 때에는 전과 같은 답(1회 봉투)이고, 회차 이름이 붙는다."""
    (wd1, dl1) = _windows()["top_dressing_1"]
    a = chat.answer(_subject(), "웃거름 언제 줘요", wd1)
    assert f"작업일 {wd1.isoformat()}" in a and f"마감 {dl1.isoformat()}" in a, a
    assert f"「{words.decision('top_dressing_1')}」" in a, a
    assert a.startswith(f"[{words.said('판단함')}]"), a


def test_after_every_round_has_passed_it_names_the_last_round_and_its_deadline():
    w = _windows()
    (_, dl1), (_, dl2) = w["top_dressing_1"], w["top_dressing_2"]
    a = chat.answer(_subject(), "웃거름 언제 줘요", dl2 + timedelta(days=1))
    assert f"{words.decision('top_dressing_2')} 때가 지났습니다 — 마감 {dl2.isoformat()}" in a, a
    assert dl1.isoformat() not in a, a
    assert a.count(words.decision("top_dressing_2")) == 1, a                       # 본문이 이미 이름을 싣고 있으면 꼬리를 또 붙이지 않는다


@pytest.mark.parametrize("q,did", [("웃거름 1회 언제", "top_dressing_1"), ("웃거름1회 줬나", "top_dressing_1"), ("추비 1회", "top_dressing_1"),
                                   ("웃거름 2회 언제", "top_dressing_2"), ("웃거름 2회 줘야 하나", "top_dressing_2"), ("2회 웃거름 언제", "top_dressing_2")])
def test_a_question_that_names_its_round_goes_to_that_round(q, did):
    assert chat.topic_of(q) == did, (q, chat.topic_of(q))


def test_the_first_round_asked_by_name_says_its_own_round_has_passed():
    (_, dl1), (_, dl2) = _windows()["top_dressing_1"], _windows()["top_dressing_2"]
    a = chat.answer(_subject(), "웃거름 1회 언제", dl2 - timedelta(days=1))
    assert f"{words.decision('top_dressing_1')} 때가 지났습니다 — 마감 {dl1.isoformat()}" in a, a
    assert "회차를 말씀하지 않으면" not in a, a                                     # 회차를 말한 물음엔 고른 회차 안내가 없다


@pytest.mark.parametrize("did", ["top_dressing_1", "top_dressing_2"])
def test_the_past_line_carries_its_round_and_its_deadline(did):
    """반대형(조건 탈락) — 「웃거름 때가 지났습니다」 는 회차를 뗀 말이다. 카드·/judge·답이 같은 봉투를 쓰니 여기 한 곳."""
    dl = _windows()[did][1]
    e = SD.judge_top_dressing(_subject(), did, dl + timedelta(days=1))
    assert e.kind == "해당 없음", e
    assert e.result["summary"] == f"{registry.get(did).name} 때가 지났습니다 — 마감 {dl.isoformat()}", e.result
    assert e.result["deadline"] == dl.isoformat()                                  # 회차 고르기가 '지났다' 를 이것으로 가른다


def _env(did, kind, deadline=None):
    return SD.Envelope(kind, did, "s", "t", grade=("관측" if kind == "판단함" else None),
                       result=({"deadline": deadline} if deadline else {}))


@pytest.mark.parametrize("envs,want", [
    ([_env("top_dressing_1", "해당 없음", "d1"), _env("top_dressing_2", "판단 불가(지식)", "d2")], "top_dressing_2"),
    ([_env("top_dressing_1", "판단함", "d1"), _env("top_dressing_2", "판단 불가(지식)", "d2")], "top_dressing_1"),
    ([_env("top_dressing_1", "판단 불가(데이터)"), _env("top_dressing_2", "판단 불가(데이터)")], "top_dressing_1"),   # 심은 날 없음 — 전과 같은 길
    ([_env("top_dressing_1", "해당 없음", "d1"), _env("top_dressing_2", "해당 없음", "d2")], "top_dressing_2"),
    ([_env("top_dressing_1", "해당 없음", "d1"), _env("top_dressing_2", "해당 없음")], "top_dressing_1"),          # 2회를 선언 안 한 격자 — 지난 게 아니다
    ([], "top_dressing_1"),
])
def test_the_round_is_chosen_from_what_the_envelopes_already_decided(envs, want):
    assert SD.round_now(FAMILY, envs) == want


def test_every_task_split_into_rounds_is_a_round_family_and_its_bare_name_routes_to_the_family():
    """§7.5 형태 래칫 — 등록부에서 「…N회」 작업을 다시 세어, 한 작업이 회차로 나뉘었으면 묶음이어야 하고 회차 없는 물음은 묶음으로 간다.
    회차 결정이 새로 등록되면(예: 웃거름 3회) 여기서 먼저 터진다 — 한 곳에만 닿은 처방이 다음 회차에서 또 새지 않게."""
    groups: dict[str, list[tuple[int, str]]] = {}
    for did, d in registry.all_decisions().items():
        m = re.fullmatch(r"(.*\S)\s*(\d+)회", str((d.params or {}).get("task_key") or ""))
        if m:
            groups.setdefault(m.group(1), []).append((int(m.group(2)), did))
    split = {base: tuple(did for _, did in sorted(v)) for base, v in groups.items() if len(v) > 1}
    assert split, "회차로 나뉜 작업이 하나도 안 세어진다 — 측정이 죽었다(웃거름 1회 · 2회가 있어야 한다)"
    assert sorted(split.values()) == sorted(SD.ROUNDS.values()), (split, SD.ROUNDS)
    for base, ids in split.items():
        fam = next(k for k, v in SD.ROUNDS.items() if v == ids)
        assert chat.topic_of(f"{base} 언제") == fam, (base, chat.topic_of(f"{base} 언제"))
        for n, did in enumerate(ids, 1):
            assert chat.topic_of(f"{base} {n}회 언제") == did, (base, n, chat.topic_of(f"{base} {n}회 언제"))


def test_the_family_has_a_plain_name_where_a_route_is_shown():
    """자기 점검의 경로 칸 — 묶음은 판단이 아니라서 등록부 이름이 없다. 날것의 id 가 나가지 않고 회차 이름에서 지은 말이 나간다."""
    said = words.decision(FAMILY)
    assert said != FAMILY and words.plain(said) == said, said
    assert all(words.decision(d) in said for d in SD.ROUNDS[FAMILY]), said
    assert selfcheck._route_said(FAMILY) == said
