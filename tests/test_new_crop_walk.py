# -*- coding: utf-8 -*-
# [대파 걷기 2026-10-04] 발행자 화면에 둘째 작목(대파 · 2026 가을 · 심은 지 3일)이 섰다 — 재배 달력이 없는 작목이 처음으로 실사용에 들어왔다. 그 농가가 받을 답을 미리 걸으니 둘:
#   ① 「작목·작기 재배 달력**가** 서면 판정이 열린다」 — 낱말 표가 「격자」 를 「재배 달력」 으로 바꾸며 조사를 안 맞췄다(받침 있는 말로 바뀌면 가→이 · 를→을 · 는→은 · 로→으로 · 와→과).
#      같은 형태를 전수로 세니 넷(격자 · 봉투 · 원장 · 등급) — 「원장은→일지는」 하나만 돼 있었다.
#   ② 달력 없는 작목의 판단은 「서면 열린다」 만 말하고 **누가 · 어디서**가 없었다(§2 요구 문장) — 깨진 파일(unreadable)만 요구가 있었다. 달력은 지식이라 발행자 몫이다.
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from frontend import words
from grid import schema as grid_schema
from ingest import chat, parcels, subjects
from judge import need as N
from judge import run as judge_run, units

T = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("src, want", [
    ("격자가 서면 판정이 열린다", "재배 달력이 서면 판정이 열린다"), ("격자를 읽는다", "재배 달력을 읽는다"), ("격자는 그대로", "재배 달력은 그대로"),
    ("격자로 센다", "재배 달력으로 센다"), ("격자와 사건", "재배 달력과 사건"), ("격자 정본 없음", "재배 달력 기준 없음"),
    ("봉투가 바뀐다", "판단이 바뀐다"), ("봉투를 낸다", "판단을 낸다"), ("원장이 비었다", "일지가 비었다"), ("원장을 읽는다", "일지를 읽는다"),
    ("등급이 낮다", "근거가 낮다"), ("등급을 본다", "근거를 본다"), ("원장은 그대로", "일지는 그대로"),
])
def test_the_plain_words_keep_korean_particles_when_the_final_consonant_changes(src, want):
    assert words.plain(src) == want


def test_a_crop_without_a_calendar_tells_the_farmer_who_makes_it_and_speaks_well():
    sid = subjects.add("대파", "2026 가을", status="재배 중", parcel="p001", anchor="2026-10-01")["id"]        # 발행자 화면의 둘째 작목 그대로
    assert subjects.by_id(sid).get("grid_unit") is None
    envs = judge_run.judgments_for(sid, today=T)
    gridless = [e for e in envs if (e.result or {}).get("grid_unit_miss") == "unlinked"]
    assert len(gridless) >= 10
    for e in gridless:
        assert e.kind == "판단 불가(지식)" and not e.missing                                  # 봉투 계약 — missing 은 데이터 쪽만
        who = e.result["who"]
        assert who.startswith("발행자 — 이 작목·작기의 재배 달력 만들기") and N.PLACES["publisher"] in who and "달력이 서야" in who
    m, r = chat.send(sid, "지금 뭐 해야 하나", today=T, now=NOW)
    assert "재배 달력이 서면 판정이 열린다" in r["text"] and "달력가" not in r["text"] and "격자" not in r["text"]
    assert "발행자 — 이 작목·작기의 재배 달력 만들기" in r["text"]                              # 채팅 답도 누가 · 어디서를 말한다
    # 셋 다 발행자 몫이지만 종류가 다르다 — 깨진 파일(데이터 · missing) · 이름 어긋남 · 없음(지식 · who)
    for reason, kind, word in (("unreadable", "판단 불가(데이터)", "깨진 재배 달력 파일 고치기"), ("no_file", "판단 불가(지식)", "이름 어긋남"), ("unlinked", "판단 불가(지식)", "만들기")):
        miss = grid_schema.UnitMiss(reason, "x-y", "why", "summary", fixer="data/grid/x_y.json 가 깨졌다")
        env = units.envelope_for(miss, "harvest_timing", sid, "2026-10-04T00:00:00+09:00")
        sentence = env.missing[0]["who_can_fill"] if env.missing else env.result.get("who", "")
        assert env.kind == kind and word in sentence and sentence.startswith("발행자"), (reason, sentence)
