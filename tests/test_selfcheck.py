# -*- coding: utf-8 -*-
# [검토표 ①⑤a 2026-09-29 · 발행자 승인 "제안 순서대로"] 자기 점검 화면 /selfcheck — 발행자가 손으로 치던 확인(㉡ 증상 두 문장 · ㉢ /judge 카드 · ⑤a 날씨 한 줄)을
# 화면이 스스로 돌린다. 계약: 읽기 전용(일지·원장에 0 쓰기) · 맞다/다르다는 기대와 실제의 대조에서만 · 카드는 /judge **화면**에서 본다 · ㉠(엔터)은 못 본다고 말한다 ·
# 재료(심은 날 있는 목록)가 없으면 그렇다고 말한다 · 모든 화면의 메뉴에서 닿는다.
from __future__ import annotations

import http.client
import os
import re
from datetime import date
from pathlib import Path

from frontend import chat_pages, config, selfcheck, serve, words
from ingest import chat, media
from tests.test_brand_home import srv  # noqa: F401

TODAY = date(2026, 9, 24)      # 걷기(walk.sh)와 같은 오늘 — 격자 칸 3(발행자 감별 규칙)이 열려 있어 증상 물음이 판단함이다


def _files_under(*envs: str) -> int:
    return sum(len(list(Path(os.environ[e]).rglob("*"))) for e in envs if os.environ.get(e) and Path(os.environ[e]).exists())


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=90)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.read().decode("utf-8", "replace")


def test_the_checks_run_on_the_real_grid_and_write_nothing(monkeypatch):
    monkeypatch.setenv(config.TODAY_ENV, TODAY.isoformat())
    before = _files_under("AGRODSS_CHAT_DIR", "AGRODSS_EVENTS_DIR", "AGRODSS_FEEDBACK_DIR")
    r = selfcheck.run(TODAY, serve.judge_page()[1])
    assert _files_under("AGRODSS_CHAT_DIR", "AGRODSS_EVENTS_DIR", "AGRODSS_FEEDBACK_DIR") == before     # 읽기 전용 — 물음은 answer 로만(send 는 원장에 쓴다)
    assert r["subject"]["id"] == media.load_subjects()[0]["id"] and r["total"] == 5
    ids = [c["id"] for c in r["checks"]]
    assert ids == ["㉡", "㉡", "㉢", "⑤a", "⑤b"]
    for c in r["checks"][:2]:                                                                             # 증상 두 문장 — 다른 말, 같은 답
        assert c["ok"] and c["actual"].startswith(f"[{words.said('판단함')}]") and "원인 후보" in c["actual"], c
    assert r["checks"][2]["ok"] and r["checks"][2]["actual"] == "있다"
    w = r["checks"][3]
    assert not w["ok"] and w["actual"] and w["sec"] >= 0                                                  # 격리 환경엔 좌표·키가 없다 — 못 받은 이유가 실제 칸에 그대로
    dr = r["checks"][4]                                                                                   # [D-20] 실제 격자엔 임계가 없다 — 「기준이 없습니다」 는 아는 상태라 맞다
    assert dr["ok"] and dr["actual"].startswith(f"[{words.said('판단 불가(지식)')}]") and dr["sec"] >= 0
    assert r["ok"] == 4


def test_the_drought_row_differs_when_no_rain_source_reaches_the_judge(monkeypatch):
    """[D-20 2026-09-29] 관측 키·좌표가 없고 농가 기록도 없으면 「마지막으로 비 온 날 …」(판단 불가(데이터)) — 그것은 원천이 하나도 안 닿은 것이라 다르다 · 이유를 덧붙인다."""
    monkeypatch.setenv(config.TODAY_ENV, TODAY.isoformat())
    real = chat.answer
    monkeypatch.setattr(chat, "answer", lambda s, q, today: f"[{words.said('판단 불가(데이터)')}] 마지막으로 비 온 날이나 관수한 날을 알면 판단합니다" if q == selfcheck.DROUGHT_QUESTION else real(s, q, today))
    r = selfcheck.run(TODAY, serve.judge_page()[1])
    dr = r["checks"][4]
    assert not dr["ok"] and dr["actual"].endswith("비 온 날의 원천이 하나도 안 닿았다(관측 키 · 좌표)")
    monkeypatch.setattr(chat, "answer", lambda s, q, today: f"[{words.said('판단함')}] 마지막 비·관수 2026-09-25(기상청 관측 지점 131) 뒤 무강수 4일 — 임계 7일 미만" if q == selfcheck.DROUGHT_QUESTION else real(s, q, today))
    assert selfcheck.run(TODAY, serve.judge_page()[1])["checks"][4]["ok"]


def test_it_says_differs_only_from_the_comparison_not_by_default(monkeypatch):
    monkeypatch.setenv(config.TODAY_ENV, TODAY.isoformat())
    judge_html = serve.judge_page()[1]
    monkeypatch.setattr(chat, "answer", lambda s, q, today: f"[{words.said('판단 불가(지식)')}]. 기준이 없습니다.")
    r = selfcheck.run(TODAY, judge_html)
    assert [c["ok"] for c in r["checks"]] == [False, False, True, False, True] and r["ok"] == 2        # 답이 달라지면 두 줄이 다르다 — 카드 줄은 화면을 보므로 그대로 · 가뭄 줄은 「기준이 없습니다」 라 맞다
    html = selfcheck.main_html(r, TODAY)
    assert "다른 것 3" in html and "전부 맞다" not in html
    r2 = selfcheck.run(TODAY, "")                                                                        # 카드는 /judge 화면에서 본다 — 화면에 없으면 없다
    assert not r2["checks"][2]["ok"] and "없다" in r2["checks"][2]["actual"]


def test_a_right_answer_without_the_observation_card_is_still_different(monkeypatch):
    """답은 맞는데 '본 것' 카드가 안 서면(계획표를 꺼내던 09-26 형태의 반쪽) 그것도 다르다 — 주입 K 가 처음엔 통과했다(조건 하나에 검사 하나)."""
    monkeypatch.setenv(config.TODAY_ENV, TODAY.isoformat())
    judge_html = serve.judge_page()[1]
    monkeypatch.setattr(chat, "classify", lambda text, today, subject=None: [{"kind": "question"}])
    r = selfcheck.run(TODAY, judge_html)
    for c in r["checks"][:2]:
        assert not c["ok"] and c["actual"].startswith(f"[{words.said('판단함')}]") and c["actual"].endswith("'본 것' 카드 없음"), c


def test_the_card_check_reads_the_screen_label_not_the_decision_id():
    label = chat_pages.DECISION_LABEL[selfcheck.CARD_DECISION]
    assert label == "증상 → 원인 좁히기"
    r = selfcheck.run(TODAY, f"<h2>{label} <span>x</span></h2>")
    assert r["checks"][2]["ok"]


def test_no_subject_with_an_anchor_is_said_not_hidden(monkeypatch):
    monkeypatch.setattr(media, "load_subjects", lambda: [{"id": "x", "label": "계획만", "anchor": None}])
    r = selfcheck.run(TODAY, "")
    assert r["subject"] is None and r["checks"] == [] and r["total"] == 0
    assert selfcheck.NO_SUBJECT in selfcheck.main_html(r, TODAY)


def test_the_page_is_reachable_from_every_menu_and_speaks_plainly(srv, monkeypatch):
    monkeypatch.setenv(config.TODAY_ENV, TODAY.isoformat())
    status, body = _get(srv, "/selfcheck")
    assert status == 200 and "자기 점검" in body and body.count('class="card chk"') == 5                    # 줄 5 — 카드(표는 390px 에서 넘쳤다)
    assert "다른 것 1" in body and "4/5 맞음" in body                                                       # 격리 환경: 날씨만 못 받는다(가뭄은 임계 없음 = 아는 상태)
    assert selfcheck.BROWSER_ONLY.split(" — ")[0] in body and "걷기 도구" in body                            # ㉠ 은 못 본다고 말한다
    assert re.search(r"\d+\.\d초", body)                                                                    # 걸린 시간 — 원천이 죽어 있으면 여기서 보인다
    _, me = _get(srv, "/me")                                                                                # "/" 는 첫 채팅으로 넘긴다(본문 없음)
    assert 'href="/selfcheck"' in me and 'href="/selfcheck"' in body                                       # 모든 화면의 메뉴
    for bad in ("초안", "판단 불가", "격자", "원장", "분류"):
        assert bad not in re.sub(r"<[^>]*>", " ", body), bad


def test_the_questions_are_the_publishers_confirmation_sentences():
    assert selfcheck.SYMPTOM_QUESTIONS == ("잎 끝이 누렇게 되는데 왜 그런가요", "잎이 노래지는데 어떻게 해야 하나") and selfcheck.WEATHER_QUESTION == "내일 날씨 어때"
    for q in selfcheck.SYMPTOM_QUESTIONS:
        assert chat.symptom_in(q)                                                                          # 둘 다 증상 문으로 간다(라우팅 어휘 정본)
    assert chat.topic_of(selfcheck.WEATHER_QUESTION) == "forecast_citation"
