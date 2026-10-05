# -*- coding: utf-8 -*-
# [2026-10-05 §7.5 지점 축] 앞 회차에 「그대로 복사해 쓰실 줄」 묶음을 **한 곳**에 넣고 닫았다. 전수를 세니 「세션에 붙이면」 이라고 말하는 자리가 **셋**이었고
# 한 번 눌러 전체가 잡히는 꼴은 **하나뿐**이었다 — 나머지 둘(결정 화면의 「세션에 보낼 것」 · 화면 오류의 한 줄)은 여러 줄을 손으로 끌어 골라야 했다.
# 처방이 한 곳에 갇힌 그 형태다. 꼴은 정본 하나(`render.paste_block`)로 모으고, 이 검사가 **새 화면이 자기 꼴을 또 쓰는 것**을 막는다.
from __future__ import annotations

import ast
import http.client
import os
import pathlib
import threading

import pytest

from frontend import config, render, serve

FRONTEND = pathlib.Path(render.__file__).resolve().parent
# 붙일 묶음을 내는 함수 — 셋 다 정본을 부른다(어느 자리인지까지 고정한다. 꼴만 맞고 자리가 비면 사람은 또 손으로 끈다)
SITES = {("chat_pages.py", "decisions_main"): "결정 화면 「세션에 보낼 것」 — 발행자 답을 세션에 넘기는 글",
         ("selfcheck.py", "_fill_block"): "문장 형태 점검 「그대로 복사해 쓰실 줄」 — 기대 종류를 채워 보내는 줄",
         ("serve.py", "_guarded"): "화면 오류 한 줄 — 붙이면 고치는 글"}


def test_one_press_grabs_the_whole_block():
    out = render.paste_block("한 줄\n두 줄")
    assert "user-select:all" in render.PASTE_STYLE and render.PASTE_STYLE in out
    assert out.startswith("<pre ") and out.endswith("</pre>") and "한 줄\n두 줄" in out


def test_the_text_cannot_become_a_tag():
    assert "<b>" not in render.paste_block("<b>굵게</b>") and "&lt;b&gt;" in render.paste_block("<b>굵게</b>")


def test_empty_says_so_instead_of_an_empty_box():
    assert "아직 답이 없다" in render.paste_block("", empty="아직 답이 없다")
    assert "아직 답이 없다" in render.paste_block("   \n ", empty="아직 답이 없다")      # 빈칸만 있는 것도 빈 것이다
    assert render.paste_block("D-2 맞다", empty="아직 답이 없다").count("아직 답이 없다") == 0


def _sites() -> set[tuple[str, str]]:
    """전수 — (파일, 함수) 가 정본을 부르는가. 줄 번호·인자 꼴은 고정하지 않는다(구조로 자른다)."""
    found = set()
    for f in sorted(FRONTEND.glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "paste_block":
                inner = max((x for x in fns if x.lineno <= n.lineno <= (x.end_lineno or x.lineno)), key=lambda x: x.lineno, default=None)
                found.add((f.name, inner.name if inner else "<모듈>"))
    return found


def test_every_place_that_says_paste_it_uses_the_canon():
    assert set(SITES) <= _sites(), (set(SITES) - _sites(), SITES)


def test_no_screen_writes_its_own_block():
    """정본 밖에서 `<pre` 를 직접 쓰면 꼴이 또 갈린다 — 문서 원문 자리(render.md_to_html)만 예외이고 그것도 같은 파일 안이다."""
    mine = {f.name: f.read_text(encoding="utf-8").count("<pre") for f in sorted(FRONTEND.glob("*.py"))}
    assert {k: v for k, v in mine.items() if v} == {"render.py": 2}, mine      # 정본 하나 + 문서 원문 자리 하나


def _get(s, path: str) -> str:
    c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=120)
    c.request("GET", path)
    return c.getresponse().read().decode("utf-8", "replace")


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("AGRODSS_DECISIONS_LOCAL_PATH", str(tmp_path / "decisions_local.json"))
    monkeypatch.setenv(config.TODAY_ENV, "2026-10-05")
    config.PORT = 0
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        yield s
    finally:
        s.shutdown()
        s.server_close()


def test_the_three_screens_serve_it(server, monkeypatch):
    for path, word in (("/me/decisions", "세션에 보낼 것"), ("/selfcheck", "그대로 복사해 쓰실 줄")):
        body = _get(server, path)
        assert word in body and render.PASTE_STYLE in body, path
    from frontend import chat_pages

    def boom(*a, **k):
        raise RuntimeError("일부러 낸 오류")

    monkeypatch.setattr(chat_pages, "decisions_main", boom)      # 오류 쪽도 같은 꼴이어야 한다 — 그 한 줄이 세션에 붙는 글이다
    body = _get(server, "/me/decisions")
    assert "화면 오류" in body and render.PASTE_STYLE in body and "일부러 낸 오류" in body
