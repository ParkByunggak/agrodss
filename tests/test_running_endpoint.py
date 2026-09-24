# -*- coding: utf-8 -*-
# [발행자 실측 2026-09-23] update.bat 이 *"the screen SHOULD now be running ed45339"* 라고 **주장**했다.
# pull 이 닿아도 이미 떠 있는 프로세스는 옛 빌드를 낸다(R-6) — 그것을 아무도 말해 주지 않아 며칠을 잃었다.
# VELA 의 `running_commit` 규율과 같은 형태다(커밋 완료 ≠ 반영 완료): **화면에게 물을 수 있어야 한다.**
#
# `/running` 은 배치가 읽는 줄이다 — ASCII 키=값. 한글은 못 싣는다(cmd 가 cp949 로 읽는다).
from __future__ import annotations

import http.client

from frontend import serve
from tests.test_brand_home import srv  # noqa: F401


def _get(port: int, path: str):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.getheader("Content-Type") or "", r.read()


def test_running_answers_in_ascii_key_value_lines(srv):
    status, ctype, raw = _get(srv, "/running")
    assert status == 200 and ctype.startswith("text/plain")
    assert all(b < 128 for b in raw), "배치가 읽는 줄에 ASCII 밖 글자가 있다 — cp949 에서 깨진다"
    lines = dict(ln.split("=", 1) for ln in raw.decode("ascii").split())
    assert lines["head"] == serve.RUNNING_HEAD and lines["repo"] == serve.git_head_short()
    assert "port" in lines


def test_running_reports_the_process_not_the_repository(srv, monkeypatch):
    """묻는 것은 **프로세스가 기동한 코드**다 — 저장소 HEAD 를 되돌려 주면 드리프트를 못 본다(그게 옛 꼬리의 결함)."""
    monkeypatch.setattr(serve, "git_head_short", lambda: "0000000")
    _, _, raw = _get(srv, "/running")
    lines = dict(ln.split("=", 1) for ln in raw.decode("ascii").split())
    assert lines["head"] == serve.RUNNING_HEAD and lines["repo"] == "0000000"
