# -*- coding: utf-8 -*-
# [발행자 2026-10-04 "argodss 는 질문의 문구 형태가 단문도 해석하지 못하고 있는지를 확인해 보자"] 이미 틀린 여섯이 전부 단문이었다 — 분류가 명사를 보고 사람의 물음은
# 동사·어미가 뜻을 정한다. 확인 틀: 「같은 명사 × 다른 어미」 「같은 뜻 × 다른 표현」 을 자기 점검 화면에 넣어 기대 종류와 실제를 대조한다(저장 없는 길 — 일지가 안 더럽혀진다).
#   기대 종류는 **발행자가** 붙인다 — 세션이 붙이면 채점자와 응시자가 같다. 그래서 이 검사는 "맞다" 를 단언하지 않는다 — 틀이 정직한가를 본다:
#   ① 문장마다 실제 종류·경로가 나온다(예외 0) ② 기대가 없는 줄은 「발행자가 붙일 것」 으로 보인다(세션이 채워 넣지 않았다) ③ 기대가 있는 줄만 맞다/다르다를 낸다
#   ④ 발행자 표의 여섯은 기대가 그대로다 ⑤ 화면이 아무것도 쓰지 않는다 ⑥ 다른 줄 수가 화면에 보인다(WO-LLM 비교 세트의 재료 — 실사용 측정(/changes)과 섞지 않는다).
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

from frontend import config, selfcheck, serve
from ingest import chat
from tests.test_brand_home import srv  # noqa: F401
from tests.test_selfcheck import _files_under, _get

TODAY = date(2026, 9, 24)
KINDS = {"question", "event", "observation.note", "plan.farmer", "plan.target_date", "feedback.request", "decision.noncompliance", "subject.end", "parcel.field", "subject.field"}
PUBLISHER_SIX = [
    ("잎 끝이 노란 형상을 어떻게 대처해야 하는가", "question", "symptom_triage"),
    ("지금 어떤 병충해를 관찰해야 하는가", "question", "risk_alert"),
    ("기상청 자료를 확인한 후 비없음 날수가 오늘 이전에 몇일인가", "question", None),
    ("이전에 관수를 일지에서 날짜별로 알려줘요", "question", chat.LOOKUP_ID),
    ("이 쪽파는 종구생산을 위한 목적이다", "parcel.field", None),
    ("고르신 종류(처음 제안과 다릅니다) · obs_93e9b4b67856 이미 있는데 왜 되묻는가?", "feedback.request", None),
]


def test_the_probe_file_is_the_publishers_frame_not_the_sessions_answers():
    doc = json.loads(Path(selfcheck.PROBES_PATH).read_text(encoding="utf-8"))
    rows = [r for g in doc["groups"] for r in g["rows"]]
    assert len({r["text"] for r in rows}) == len(rows) >= 20
    for r in rows:
        assert r["expected"] is None or r["expected"] in KINDS, r
        assert r["expected"] is None or r.get("by", "").startswith("발행자"), ("기대 종류는 발행자가 붙인다", r)   # 세션이 붙인 기대는 없다
    six = {r["text"]: (r["expected"], r["expected_route"]) for r in doc["groups"][0]["rows"]}
    assert six == {t: (k, rt) for t, k, rt in PUBLISHER_SIX}                                                      # 발행자 표 그대로
    names = [g["name"] for g in doc["groups"]]
    assert any("관수" in n for n in names) and any("배수" in n for n in names) and any("종구" in n for n in names) and any("같은 뜻" in n for n in names)


def test_every_probe_gets_an_actual_kind_and_route_and_only_rows_with_an_expectation_are_judged(monkeypatch):
    monkeypatch.setenv(config.TODAY_ENV, TODAY.isoformat())
    before = _files_under("AGRODSS_CHAT_DIR", "AGRODSS_EVENTS_DIR", "AGRODSS_FEEDBACK_DIR")
    u = selfcheck.utterances(TODAY, selfcheck.subject())
    assert _files_under("AGRODSS_CHAT_DIR", "AGRODSS_EVENTS_DIR", "AGRODSS_FEEDBACK_DIR") == before              # 읽기 전용
    rows = [r for g in u["groups"] for r in g["rows"]]
    assert rows and all(r["actual"] in KINDS for r in rows)                                                        # 예외 0 · 종류가 안 정해진 줄 0(규칙은 언제나 종류를 정한다)
    for r in rows:
        if r["expected"] is None:
            assert r["ok"] is None and r["actual_said"] and not r["expected_said"]                                  # 기대 없는 줄은 판정하지 않는다
        else:
            assert r["ok"] in (True, False)
        if r["actual"] == "question":
            assert r["route"] is not None or r["route_said"] == "어느 판단으로도 안 간다"
    assert u["with_expected"] == 6 and u["without_expected"] == len(rows) - 6 and u["ok"] + u["differ"] == 6
    by_text = {r["text"]: r for r in rows}
    assert by_text["이 쪽파는 종구생산을 위한 목적이다"]["ok"] is True                                              # 이미 고친 둘은 맞다
    assert by_text["이전에 관수를 일지에서 날짜별로 알려줘요"]["ok"] is True and by_text["이전에 관수를 일지에서 날짜별로 알려줘요"]["route"] == chat.LOOKUP_ID


def test_the_frame_is_on_the_selfcheck_screen_in_plain_words_and_says_who_fills_the_expectation(srv, monkeypatch):
    monkeypatch.setenv(config.TODAY_ENV, TODAY.isoformat())
    status, body = _get(srv, "/selfcheck")
    assert status == 200 and body.count('class="card chk"') == 5                                                  # 기존 다섯 줄 그대로
    text = re.sub(r"<[^>]*>", " ", body)
    assert selfcheck.PROBES_TITLE in text and selfcheck.FILL_ME in text                                           # 기대 없는 줄의 표지
    assert "같은 명사" in text and "관수해야 하나" in text and "기대 있는 줄 6" in text
    for bad in ("초안", "판단 불가", "격자", "원장", "분류", "레코드"):
        assert bad not in text, bad
    assert 'class="card utt"' in body and body.count('class="card utt"') >= 20


def test_a_row_whose_kind_matches_but_route_differs_is_judged_different(monkeypatch):
    """채점 논리의 검사 — 기대는 검사 안의 가짜 목록(데이터 파일에 세션이 기대를 붙이는 것이 아니다). 경로 기대가 있으면 종류만 맞아도 다르다."""
    fake = {"groups": [{"name": "x", "rows": [{"text": "물 줘야 하나", "expected": "question", "expected_route": "harvest_timing", "by": "검사"},
                                               {"text": "물 줘야 하나?", "expected": "question", "expected_route": "drought_alert", "by": "검사"},
                                               {"text": "오늘 물 줬다", "expected": "event", "expected_route": None, "by": "검사"}]}]}
    monkeypatch.setattr(selfcheck, "probes", lambda: fake)
    rows = selfcheck.utterances(TODAY, selfcheck.subject())["groups"][0]["rows"]
    assert [r["ok"] for r in rows] == [False, True, True] and rows[0]["route"] == "drought_alert"


def test_route_mirrors_the_answer_routing():
    s = selfcheck.subject()
    assert selfcheck.route_of("잎 끝이 노란 형상을 어떻게 대처해야 하는가", s) == "symptom_triage"
    assert selfcheck.route_of("이전에 관수를 일지에서 날짜별로 알려줘요", s) == chat.LOOKUP_ID
    assert selfcheck.route_of("물 줘야 하나", s) == "drought_alert" and selfcheck.route_of("오늘 상태 어때", s) is None
