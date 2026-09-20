# -*- coding: utf-8 -*-
# [발행자 화면 2026-09-21] 발행자가 보낸 화면의 꼬리에 `HEAD 8de761d` 가 찍혀 있었다. 재보니 그 해시는 **저장소 HEAD** 였다 —
#   꼬리가 매 요청마다 `git_head_short()` 를 다시 불러 찍고 있었으므로, 프로세스가 옛 코드를 돌고 있어도 꼬리는 늘 최신처럼 보인다.
#   드리프트 지표가 **발행자가 온종일 보는 자리**에서 눈을 감고 있던 것이다(VELA "커밋 완료 ≠ 반영 완료"의 화면 판).
#   /changes 에는 대조가 있었지만, 그 화면은 일부러 찾아가야 한다.
# 처방: 꼬리 정본 하나 — 실행 중 코드를 찍고, 저장소가 앞서면 그 자리에서 '뒤처짐'이라고 말한다.
from __future__ import annotations

import re
from pathlib import Path

from frontend import serve

ROOT = Path(__file__).resolve().parent.parent


def test_footer_names_the_running_code(monkeypatch):
    monkeypatch.setattr(serve, "git_head_short", lambda: serve.RUNNING_HEAD)
    f = serve.footer_text()
    assert serve.RUNNING_HEAD in f and "실행 중" in f and "뒤처짐" not in f


def test_footer_says_behind_when_the_repo_moved_ahead(monkeypatch):
    monkeypatch.setattr(serve, "git_head_short", lambda: "deadbee")
    f = serve.footer_text()
    assert "뒤처짐" in f and serve.RUNNING_HEAD in f and "deadbee" in f, f


def test_every_screen_footer_goes_through_the_canon():
    """소비자 전수 래칫 — 꼬리를 손으로 조립하면 같은 결함이 그 화면에서 되살아난다(§7.5 지점 축)."""
    code = "\n".join(ln.split("#", 1)[0] for ln in (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8").splitlines())
    code = re.sub(r'\"{3}.*?\"{3}', "", code, flags=re.S)
    assert 'footer = f"HEAD' not in code, "꼬리를 손으로 조립한다 — footer_text() 로"
    body = code[code.index("def footer_text"):]
    body = body[:body.index("\ndef ", 10)]
    assert "RUNNING_HEAD" in body and "git_head_short()" in body      # 둘을 견주는 자리는 여기 하나
    # 꼬리를 쓰는 화면은 전부 정본을 부른다(표 화면 · /changes · 채팅 셸)
    assert code.count("footer_text()") >= 6, code.count("footer_text()")


def test_chat_shell_shows_the_running_code_too(monkeypatch):
    """채팅 화면이 발행자가 가장 오래 보는 자리다 — 거기 꼬리가 먼저 말해야 한다."""
    monkeypatch.setattr(serve, "git_head_short", lambda: "deadbee")
    html = serve._shell("/c/x", "<div></div>", None, "t")
    assert "뒤처짐" in html and serve.RUNNING_HEAD in html
