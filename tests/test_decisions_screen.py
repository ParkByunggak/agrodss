# -*- coding: utf-8 -*-
# [WO-PB-01 다음 한 수 · 발행자 승인 2026-09-29] 일괄 결정 화면 /me/decisions — 발행자만 답할 수 있는 것(P1)을 제안값과 함께 한 화면에.
# 발행자 셋: 「모르겠다」 1급 선택지(쌓이면 P4 신호) · 제안값의 출처 표시(추론은 맞다를 눌러도 남는다) · 맨 위 D-2.
# 계약: 항목은 측정(P1 판정)과 같다 · 제안값의 출처 문면은 저장소 문서에 실재한다 · 답은 덮개(git 밖)에만 · 틀리면 안 쓴다 · 멱등 ·
# 화면은 항목을 닫지 않는다(작업 기록 바이트 불변). 거부와 통과 둘 다.
from __future__ import annotations

import hashlib
import http.client
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest

from frontend import chat_pages
from ingest import decisions as dc
from scripts import measure_publisher_bottleneck as pb
from tests.test_brand_home import srv  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc)
# P1 인데 결정이 아니라 **사람의 손·상태·경험 목록**인 것 — 화면에 안 놓는다(맞다/다르다로 답할 물음이 아니다). 새 P1 이 생기면 여기든 화면이든 한쪽에 있어야 한다.
P1_NOT_A_DECISION = {"U-18", "U-22", "I-6", "I-7", "H-①", "H-키", "H-채팅", "R-ⓑ", "H-후보",
                     "M-11"}     # M-11 은 결정이 아니라 결정(D-2 · D-3)에 매달린 일 — 답할 물음이 없다(그 답은 D-2 · D-3 카드가 받는다)
DOCS = [ROOT / "docs" / "agrodss_backlog.md", ROOT / "docs" / "handover_20260919.md", ROOT / "docs" / "review_jjokpa_20260918.md",
        ROOT / "docs" / "wo_pb01_publisher_bottleneck.md", ROOT / "scripts" / "build_ledger_page.py"]


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.read().decode("utf-8")


def _post(port, path, data):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("POST", path, body=urlencode(data), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.read().decode("utf-8")


def _text(body: str) -> str:
    return re.sub(r"<[^>]*>", " ", body)


# ── 항목 = 측정의 P1 판정 ──
def test_every_item_is_a_p1_judgment_and_every_p1_decision_is_on_the_screen():
    judged = {i.id: i for i in pb.judged(pb.date(2026, 9, 29))}
    p1 = {k for k, v in judged.items() if v.branch == "P1"}
    on_screen = set(dc.IDS)
    grouped = {i for i in on_screen if i.startswith("H-후보")}                      # 측정은 후보 셋을 한 행(H-후보 · n=3)으로 — 화면은 셋으로 편다
    assert grouped == {"H-후보㉠", "H-후보㉡", "H-후보㉢", "H-후보㉣"} and "H-후보" in p1 and judged["H-후보"].n == len(grouped)   # 측정 행의 문항 수 = 화면의 후보 수
    for i in on_screen - grouped - set(dc.DECIDED):                                   # 답이 선 카드는 화면에 남고(지우기는 발행자 몫) 측정에서는 닫힌 행이다
        assert i in p1, f"{i}: 측정에서 P1 이 아닌 것이 맞다/다르다 화면에 있다 — 외부 정본(P2)·내부 논리(P3)는 답을 사람에게 묻지 않는다"
    for i in dc.DECIDED:
        assert i in on_screen and i not in judged, f"{i}: 결정된 항목은 화면에 남되 측정(열린 행)에서는 빠진다"
    missing = p1 - (on_screen - grouped) - P1_NOT_A_DECISION
    assert missing == set(), f"P1 인데 화면에도 손 목록에도 없다: {sorted(missing)}"
    assert P1_NOT_A_DECISION <= p1


def test_d2_is_first_and_names_what_hangs_on_it():
    assert dc.IDS[0] == "D-2" and "D-3" in dc.item("D-2")["unblocks"] and "M-11" in dc.item("D-2")["unblocks"]
    assert len(dc.IDS) == len(set(dc.IDS))


def test_each_default_says_where_it_comes_from_and_the_source_text_really_exists():
    corpus = "\n".join(p.read_text(encoding="utf-8") for p in DOCS)
    for it in dc.ITEMS:
        assert it["basis"] in dc.BASIS_KINDS, it["id"]
        assert len(it["basis_from"]) >= 6 and it["basis_from"] in corpus, f"{it['id']}: 제안값의 출처 문면이 저장소 문서에 없다 — 지어낸 출처"
        assert it["default"].strip() and it["ask"].strip() and it["unblocks"].strip()
    assert any(it["basis"] == dc.BASIS_INFERRED for it in dc.ITEMS) and any(it["basis"] == dc.BASIS_RECOMMENDED for it in dc.ITEMS)
    for k in dc.BASIS_KINDS:
        assert k in dc.BASIS_SAID and "정본" not in dc.BASIS_SAID[k]


def test_the_inference_mark_is_on_the_screen_and_stays_after_a_yes(tmp_path, monkeypatch):
    monkeypatch.setenv("AGRODSS_DECISIONS_LOCAL_PATH", str(tmp_path / "d.json"))
    inferred = next(it for it in dc.ITEMS if it["basis"] == dc.BASIS_INFERRED)
    recommended = next(it for it in dc.ITEMS if it["basis"] == dc.BASIS_RECOMMENDED)
    dc.answer(inferred["id"], "맞다", now=NOW)
    html = chat_pages.decisions_main()
    card = html[html.index(f'<b>{inferred["id"]} · '):]                                       # 카드 제목(다른 카드의 '풀리는 것' 문면에도 id 가 나온다)
    card = card[:card.index('<div class="card', 10)] if '<div class="card' in card[10:] else card
    assert dc.BASIS_INFERRED in card and dc.BASIS_SAID[dc.BASIS_INFERRED] in card and "답: 맞다" in card      # 맞다를 눌러도 추론 표시가 남는다
    rcard = html[html.index(f'<b>{recommended["id"]} · '):]
    rcard = rcard[:rcard.index('<div class="card', 10)] if '<div class="card' in rcard[10:] else rcard
    assert dc.BASIS_SAID[dc.BASIS_RECOMMENDED] in rcard and dc.BASIS_SAID[dc.BASIS_INFERRED] not in rcard


# ── 답 — 검증 · 멱등 · 덮개 ──
def test_a_wrong_answer_is_refused_with_the_reason_and_nothing_is_written(tmp_path):
    p = tmp_path / "d.json"
    for args, word in ((("D-99", "맞다"), "없는 항목"), (("D-2", "글쎄"), "중 하나"), (("D-2", "다르다"), "무엇"), (("D-2", "다르다", " "), "무엇")):
        with pytest.raises(ValueError) as e:
            dc.answer(*args, p=p, now=NOW)
        assert word in str(e.value)
    assert not p.exists()


def test_an_answer_is_written_once_replaced_when_changed_and_removable(tmp_path):
    p = tmp_path / "d.json"
    r1 = dc.answer("D-2", "맞다", p=p, now=NOW)
    b1 = p.read_bytes()
    r2 = dc.answer("D-2", "맞다", p=p, now=datetime(2026, 9, 30, tzinfo=timezone.utc))
    assert r2 == r1 and p.read_bytes() == b1                                                   # 더블탭 — 두 줄이 안 난다 · 시각도 안 바뀐다
    r3 = dc.answer("D-2", "다르다", note="첫 시즌부터 보인다", p=p, now=NOW)
    assert r3["verdict"] == "다르다" and dc.load(p)["D-2"]["note"] == "첫 시즌부터 보인다"
    assert dc.remove("D-2", p=p)["verdict"] == "다르다" and dc.load(p) == {}
    with pytest.raises(ValueError):
        dc.remove("D-2", p=p)


def test_unknown_is_a_first_class_choice_and_is_counted_as_a_p4_signal(tmp_path, monkeypatch):
    monkeypatch.setenv("AGRODSS_DECISIONS_LOCAL_PATH", str(tmp_path / "d.json"))
    assert dc.UNKNOWN in dc.VERDICTS and len(dc.VERDICTS) == 3
    dc.answer("R-W", dc.UNKNOWN, now=NOW)                                                          # 처음 지으신 밭이면 경험이 없다 — 답이 안 나온다
    dc.answer("D-16", "맞다", now=NOW)
    sm = dc.summary(dc.load())
    assert sm["answered"] == 2 and sm["counts"][dc.UNKNOWN] == 1 and sm["unknown_ids"] == ["R-W"]
    html = _text(chat_pages.decisions_main())
    assert "모르겠다 1건(R-W)" in html and "신호" in html
    assert dc.to_session_text(dc.load()) == "D-16 맞다\nR-W 모르겠다"                              # 답한 것만 · 항목 순서


def test_the_answers_live_in_a_gitignored_overlay_and_tests_are_isolated():
    assert subprocess.run(["git", "check-ignore", "-q", "data/decisions_local.json"], cwd=ROOT).returncode == 0
    assert dc.LOCAL_PATH.name == "decisions_local.json"
    assert dc.local_path() != dc.LOCAL_PATH                                                       # conftest 가 tmp 로 돌린다
    conftest = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "AGRODSS_DECISIONS_LOCAL_PATH" in conftest


# ── 화면 흐름 ──
def test_the_screen_flow_get_answer_refuse_delete_and_the_ledger_stays_untouched(srv):
    backlog = ROOT / "docs" / "agrodss_backlog.md"
    before = hashlib.sha256(backlog.read_bytes()).hexdigest()
    status, body = _get(srv, "/me/decisions")
    assert status == 200 and "결정 — 한 화면에서 답하기" in body
    pos = [body.index(f"{i} · ") for i in dc.IDS]
    assert pos == sorted(pos) and body.count('class="card dec"') == len(dc.IDS)                  # 전부 · 화면 순서 = 항목 순서(맨 위 D-2)
    assert body.count('value="모르겠다"') == len(dc.IDS) - len(dc.DECIDED) and "아직 답이 없다" in body     # 결정된 카드에는 폼이 없다(답한 카드로만 남는다)
    status, body = _post(srv, "/me/decisions", {"id": "D-2", "verdict": "맞다", "note": ""})
    assert status == 200 and "적었다 — D-2 맞다" in body and "답: 맞다" in body
    status, body = _post(srv, "/me/decisions", {"id": "D-3", "verdict": "다르다", "note": ""})
    assert status == 400 and "저장하지 않았다" in body and "무엇" in body and "D-3" not in dc.to_session_text(dc.load())
    assert 'value="다르다" checked' in body                                                       # 친 것은 남는다
    status, body = _post(srv, "/me/decisions", {"id": "D-3", "verdict": "다르다", "note": "첫 시즌부터 받는다"})
    assert status == 200 and "D-2 맞다\nD-3 다르다 — 첫 시즌부터 받는다" in _text(body)
    status, body = _post(srv, "/me/decisions/delete", {"id": "D-2"})
    assert status == 200 and "지움 — D-2" in body and dc.to_session_text(dc.load()) == "D-3 다르다 — 첫 시즌부터 받는다"
    assert hashlib.sha256(backlog.read_bytes()).hexdigest() == before                             # 화면은 항목을 닫지 않는다


def test_a_corrupt_answer_file_is_said_on_the_screen_not_a_500_and_is_never_overwritten(srv, tmp_path, monkeypatch):
    """[2026-09-30 실측] load() 예외 → 화면 통째로 500. 이제 (빈 답, 이유) — 폼은 그대로, 저장은 거부, 파일은 그대로, /changes 에도 뜬다(U-21 형태)."""
    from ingest import dropped
    p = Path(dc.local_path())
    assert p != dc.LOCAL_PATH                                        # conftest 의 tmp — 운영 덮개가 아니다
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    raw = p.read_bytes()
    answers, why = dc.read_for_screen()
    assert answers == {} and why and "못 읽었다" in why
    status, body = _get(srv, "/me/decisions")
    assert status == 200 and "답 파일을 못 읽었다" in body and body.count('class="card dec"') == len(dc.IDS)   # 500 이 아니라 이유 + 폼 전부
    status, body = _post(srv, "/me/decisions", {"id": "D-2", "verdict": "맞다", "note": ""})
    assert status == 400 and "저장하지 않았다" in body and p.read_bytes() == raw                             # 덮어쓰지 않는다
    assert any(d["where"] == dc.DROP_WHERE for d in dropped.all_drops())
    _, changes = _get(srv, "/changes")
    assert dc.DROP_WHERE in changes
    p.write_text('{"answers": {}}', encoding="utf-8")
    assert dc.read_for_screen() == ({}, None)                                                                  # 고치면 바로 읽힌다


def test_the_answer_time_is_shown_in_the_viewers_clock_not_a_utc_date_slice(tmp_path, monkeypatch):
    """[C16 형태] 저녁 답(UTC 23:30 = KST 다음날 08:30)이 어제 날짜로 뜨던 자르기 — 화면 시각은 render.local_time 하나."""
    from frontend import render
    monkeypatch.setenv("AGRODSS_DECISIONS_LOCAL_PATH", str(tmp_path / "d.json"))
    at = datetime(2026, 9, 29, 23, 30, tzinfo=timezone.utc)
    dc.answer("D-2", "맞다", now=at)
    html = chat_pages.decisions_main()
    assert render.local_time(at.isoformat(timespec="seconds")) in html
    assert "2026-09-29</span>" not in html                                                                    # UTC 날짜 조각이 그대로 나가지 않는다


def test_the_screen_is_linked_from_the_menu_and_me_and_speaks_plainly(srv):
    _, me = _get(srv, "/me")
    _, body = _get(srv, "/me/decisions")
    assert 'href="/me/decisions"' in me and 'href="/me/decisions"' in body
    seen = _text(body)
    for bad in ("초안", "판단 불가", "격자", "원장", "분류", "정본", "대장"):
        assert bad not in seen, bad
    for v in dc.VERDICTS:
        assert v in seen
