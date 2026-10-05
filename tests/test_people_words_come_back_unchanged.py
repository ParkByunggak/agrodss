# -*- coding: utf-8 -*-
# [2026-10-05 실측] `frontend/words.py` 머리의 마지막 줄은 *"농가가 쓴 글에는 대지 않는다"* 다. 그런데 결정 화면이 페이지를 **통째로** 낱말 표에 넣고 있어
# 발행자가 쓴 메모가 바뀌어 돌아왔다 — 한 줄에서 여섯 곳:
#     쓴 말     「격자가 아니라 원장을 본다 · 신뢰 등급 추정 · 기준점 칸 3」
#     돌아온 말 「재배 달력이 아니라 일지를 본다 · 근거 추정 · 심은 날 3단계」
# 그 글은 **세션이 읽는 답**이다(「세션에 보낼 것」 묶음) — 바뀐 말이 작업 기록에 들어가면 쓰지 않은 말이 기록된다. 그래서 사람이 쓴 조각은
# `words.mine()` 으로 싸고 페이지는 `words.plain_outside()` 로 낸다.
#
# 이 검사가 고정하는 것 넷:
#   ① 표는 **싸지 않은 자리에서 그대로 살아 있다**(막는 것만 보지 않는다 — 양방향)
#   ② 표시 문자는 화면에 남지 않는다 · 쓴 글이 싸는 자리를 속일 수 없다
#   ③ 발행자가 쓴 메모는 **답 줄 · 보낼 것 묶음 · 되돌려 주는 칸 · 확인 줄** 넷 다에서 그대로다(처방 직후 전수: 여덟 자리)
#   ④ plain() 을 그냥 부르는 자리는 **시스템 문장만 싣는 곳**으로 한정된다 — 새 자리가 생기면 이 검사가 갈래를 묻는다(§7.5 지점 축)
from __future__ import annotations

import ast
import html
import http.client
import os
import pathlib
import threading
import urllib.parse

import pytest

from frontend import config, selfcheck, serve, words

NOTE = "격자가 아니라 원장을 본다 · 신뢰 등급 추정 · 기준점 칸 3"      # 실측에서 여섯 곳이 바뀐 그 줄
FRONTEND = pathlib.Path(words.__file__).resolve().parent

# plain() 을 그냥 부르는 자리 — **사람이 쓴 글이 안 실리는 곳**만. 새 자리를 추가하려면 여기에 이유를 적게 된다(그 판단이 이 검사의 목적이다).
SYSTEM_ONLY = {
    ("serve.py", "_render_env"): "3층 판단 블록의 시스템 문장 — 관찰은 건수와 id 만 싣는다(사람 문장이 아니다)",
    ("serve.py", "judge_page"): "예보·중기·장기·예찰 한 줄 — 3층이 만든 사유 문장",
}
# 사람이 쓴 글이 실리는 화면 — plain_outside 로 낸다
PEOPLE_TEXT = {("chat_pages.py", "decisions_main"), ("selfcheck.py", "main_html")}


def _call_sites() -> dict[str, set[tuple[str, str]]]:
    """frontend 전수 — (파일, 함수) 가 plain / plain_outside 중 무엇을 부르는가. 줄 번호·인자 꼴은 고정하지 않는다(구조로 자른다)."""
    out: dict[str, set[tuple[str, str]]] = {"plain": set(), "plain_outside": set()}
    for f in sorted(FRONTEND.glob("*.py")):
        if f.name == "words.py":                                  # 정본 자신 — plain_outside 가 plain 을 부른다
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in out:
                inner = max((x for x in fns if x.lineno <= n.lineno <= (x.end_lineno or x.lineno)), key=lambda x: x.lineno, default=None)
                out[n.func.attr].add((f.name, inner.name if inner else "<모듈>"))
    return out


def test_the_table_still_works_outside_and_never_inside():
    """양방향 — 싸지 않은 말은 그대로 바뀌고(표가 죽지 않았다), 싼 말은 한 글자도 안 바뀐다."""
    changed = 0
    for a, b in words.SWAPS:
        if a == b:
            continue
        assert words.plain_outside(f"앞 {a} 뒤") == f"앞 {b} 뒤", a         # 표가 살아 있다
        assert words.plain_outside(f"앞 {words.mine(a)} 뒤") == f"앞 {a} 뒤", a
        changed += 1
    assert changed >= 40, changed
    assert words.plain_outside("칸 3") == "3단계" and words.plain_outside(words.mine("칸 3")) == "칸 3"
    assert words.plain_outside(words.mine(NOTE)) == NOTE
    assert words.plain_outside(NOTE) != NOTE                               # 안 싸면 바뀐다 — 이것이 원 결함이다


def test_every_entry_says_its_own_word():
    """[2026-10-05 전수 53항목 중 2] 짧은 말이 앞에 있으면 긴 말은 영원히 안 걸린다 — 「추론 초안」 이 「추론 적을 것」 으로, 「미확인 초안」 이
    「아직 모름 적을 것」 으로 나가고 있었다(/judge). 차단 지점이 주입 지점보다 앞이면 무효인 것과 같은 순서 함정이라, 표 자체를 양방향으로 고정한다."""
    for a, b in words.SWAPS:
        assert words.plain(a) == b, (a, b, words.plain(a), "앞에 걸린 것", [x for x, _ in words.SWAPS if x != a and x in a])
        assert words.plain(words.plain(a)) == words.plain(a), (a, "두 번 대면 또 바뀐다")


def test_the_markers_never_reach_the_screen():
    assert words.MINE_OPEN not in words.plain_outside(words.mine("가")) and words.MINE_CLOSE not in words.plain_outside(words.mine("가"))
    sneaky = f"격자{words.MINE_CLOSE} 밖으로 나가는 격자 {words.MINE_OPEN}격자"      # 쓴 글이 싸는 자리를 속이려 해도
    out = words.plain_outside(f"앞 {words.mine(sneaky)} 뒤 격자")
    assert words.MINE_OPEN not in out and words.MINE_CLOSE not in out
    assert "격자 밖으로 나가는 격자 격자" in out and out.endswith("뒤 재배 달력")      # 싼 쪽은 그대로 · 바깥은 바뀐다


def _server():
    config.PORT = 0
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def _post(s, path: str, data: dict[str, str]) -> str:
    c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=60)
    c.request("POST", path, urllib.parse.urlencode(data), {"Content-Type": "application/x-www-form-urlencoded"})
    return c.getresponse().read().decode("utf-8", "replace")


@pytest.fixture()
def answers_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AGRODSS_DECISIONS_LOCAL_PATH", str(tmp_path / "decisions_local.json"))
    monkeypatch.setenv(config.TODAY_ENV, "2026-10-05")
    return tmp_path


def test_the_decision_note_comes_back_exactly(answers_file):
    """세 자리 전부 — 답 줄 · 「세션에 보낼 것」 묶음 · 적었다 확인 줄. 그리고 같은 쪽에서 시스템 말은 여전히 사람 말로 바뀐다(양방향)."""
    s = _server()
    try:
        body = _post(s, "/me/decisions", {"id": "D-2", "verdict": "다르다", "note": NOTE})
    finally:
        s.shutdown()
        s.server_close()
    esc = html.escape(NOTE)
    assert body.count(esc) >= 3, [body.count(esc), esc]
    assert f"답: 다르다 — {esc}" in body                                   # 답 줄
    assert f"D-2 다르다 — {esc}</pre>" in body                             # 보낼 것 묶음(세션이 읽는 글)
    assert f"적었다 — D-2 다르다 — {esc}" in body                          # 확인 줄
    assert "재배 달력" in body and words.MINE_OPEN not in body             # 표는 여전히 산다 · 표시 문자는 안 나간다


def test_the_echoed_note_comes_back_exactly(answers_file):
    """틀린 줄을 되돌려 줄 때도 쓴 그대로 — 바뀐 말이 칸에 들어오면 다시 쳐야 한다."""
    s = _server()
    try:
        body = _post(s, "/me/decisions", {"id": "D-2", "verdict": "", "note": NOTE})
    finally:
        s.shutdown()
        s.server_close()
    assert f'value="{html.escape(NOTE)}"' in body
    assert "저장하지 않았다" in body


def test_the_probe_sentences_and_notes_come_back_exactly():
    """[오늘은 0 · 구조는 위험] 스무 줄 중 바뀌는 문장은 지금 없다. 그러나 조회 물음(「원장을 보여줘」)이 들어오면 묶음이 「일지를 보여줘」 를 돌려주고,
    그 줄로 답한 기대는 목록과 안 맞는다 — 같은 결함에 같은 처방이 닿으므로 지금 넓힌다(보수적 = 범위가 좁은 쪽이 아니다)."""
    sentence, note, group = "원장을 보여줘", "격자 쪽 물음이다", "기준점 묶음"
    u = {"groups": [{"name": group, "rows": [
            {"text": sentence, "actual": "question", "actual_said": "물음", "route": None, "route_said": "",
             "expected": "question", "expected_said": "물음", "expected_route": None, "expected_route_said": "",
             "expected_note": note, "ok": True},
            {"text": "격자를 보여줘", "actual": "question", "actual_said": "물음", "route": None, "route_said": "",
             "expected": None, "expected_said": "", "expected_route": None, "expected_route_said": "",
             "expected_note": "", "ok": None}]}],
         "with_expected": 1, "without_expected": 1, "ok": 1, "differ": 0}
    out = words.plain_outside(selfcheck._utterance_html(u, html.escape))
    assert sentence in out and note in out and group in out
    assert "격자를 보여줘 — " in out                                        # 복사 묶음의 줄도 쓴 그대로
    assert "일지" not in out and "재배 달력" not in out
    assert selfcheck.PROBES_TITLE in out                                   # 시스템 머리말은 그대로 실린다


def test_the_selfcheck_page_keeps_the_list_file_words(tmp_path, monkeypatch):
    """화면 쪽도 본다 — 목록 파일(발행자가 쓴다)에 조회 물음이 들어온 꼴. 이 줄이 없으면 selfcheck 쪽 처방은 **아무 검사도 안 닿는 가드**가 된다
    (오늘 목록 스무 줄 중 바뀌는 것이 0 이라 실물 목록으로는 증명이 안 된다 — 그래서 목록을 갈아 끼운다)."""
    from datetime import date

    from ingest import probes

    doc = {"groups": [{"name": "원장 물음", "rows": [{"text": "원장을 보여줘"}, {"text": "격자를 보여줘", "expected": "question", "expected_note": "초안 쪽 물음"}]}]}
    path = tmp_path / "utterance_probes.json"
    path.write_text(__import__("json").dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(probes, "PATH", path)
    body = selfcheck.main_html({"subject": None, "utterances": selfcheck.utterances(date(2026, 10, 5), None)}, date(2026, 10, 5))
    for said in ("원장 물음", "원장을 보여줘", "격자를 보여줘", "초안 쪽 물음"):
        assert said in body, said
    assert "일지를 보여줘" not in body and "재배 달력을 보여줘" not in body and "적을 것 쪽 물음" not in body
    assert selfcheck.PROBES_TITLE in body and words.MINE_OPEN not in body


def test_every_site_is_classified():
    """§7.5 지점 축 — plain() 을 그냥 부르는 자리는 시스템 문장만 싣는 곳뿐이고, 사람 글이 실리는 화면은 plain_outside 로 낸다.
    새 자리가 생기면 여기서 갈래를 적게 된다(그 판단을 건너뛰면 또 사람 말이 바뀐다)."""
    sites = _call_sites()
    assert sites["plain"] == set(SYSTEM_ONLY), (sites["plain"], set(SYSTEM_ONLY))
    assert PEOPLE_TEXT <= sites["plain_outside"], (sites["plain_outside"], PEOPLE_TEXT)
    assert not (sites["plain"] & sites["plain_outside"])                    # 한 함수가 두 길을 같이 쓰면 어느 쪽이 사람 글인지 알 수 없다
