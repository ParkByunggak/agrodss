# -*- coding: utf-8 -*-
# [M-13 · 발행자 2026-09-19] 채팅 목록 최하단 사용자 정보 탭 — 등록부 하나 · PII 거부 · 격리 · /me 화면.
from __future__ import annotations

import http.client
import threading
from pathlib import Path
from urllib.parse import urlencode

import pytest

from frontend import chat_pages, config, serve
from ingest import profile
from schema import records as sch
from tests.test_brand_home import ROUTES, srv  # noqa: F401 — 경로 목록·서버 픽스처는 브랜드 검사와 한 벌(매 페이지의 정의가 두 벌이 되지 않게)


# [발행자 2026-09-19] "채팅 목록 하단에 있는 사용자 정보는 매 페이지마다 있어야 한다" — 채팅 셸 · 표 화면(render.page) · 404 전부
@pytest.mark.parametrize("path", ROUTES)
def test_every_screen_has_the_user_tab_last_in_the_list(srv, path):
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
    c.request("GET", path)
    body = c.getresponse().read().decode("utf-8")
    assert 'id="user-tab"' in body and 'href="/me"' in body, path
    end = body.index("</aside>") if '<aside class="side">' in body else body.index("</nav>")
    tab = body.index('id="user-tab"')
    assert tab < end and body.rfind("<a ", 0, end) == body.rfind("<a ", 0, tab + 1), path      # 목록의 마지막 링크가 사용자 탭


def test_profile_default_then_save_and_pii_refused():
    u = profile.load()
    assert u["name"] == "" and u["role"] == "farmer"
    with pytest.raises(profile.ProfileError, match="비어"):
        profile.save("", "farmer")
    with pytest.raises(profile.ProfileError, match="역할"):
        profile.save("박병각", "admin")
    with pytest.raises(profile.ProfileError, match="PII"):
        profile.save("박병각 010-1234-5678", "farmer")
    with pytest.raises(profile.ProfileError, match="PII"):
        profile.save("박병각", "farmer", note="me@example.com")
    u = profile.save("박병각", "publisher", note="괴산 쪽파 첫 농가")
    assert u["parcels"] == ["p001"] and u["kind"] == "user" and sch.validate(profile.load(), kind="user")
    assert Path(profile.path()).resolve() != profile.PATH.resolve()          # 운영 파일에 쓰지 않는다


def test_sidebar_has_user_tab_at_bottom():
    profile.save("박병각", "farmer")
    side = chat_pages.sidebar("/c/x", [], __import__("datetime").date(2026, 9, 19))
    assert 'id="user-tab"' in side and side.rstrip().endswith("</a>") and side.rindex('id="user-tab"') > side.rindex('class="grp"')
    assert "박병각" in side and 'href="/me"' in side


def test_me_page_get_and_post(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        port = s.server_address[1]
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.request("GET", "/me")
        r = c.getresponse()
        body = r.read().decode("utf-8")
        assert r.status == 200 and "사용자 정보" in body and "휴대폰 동기화" in body and "꺼짐" in body
        c.request("POST", "/me", body=urlencode({"name": "박병각", "role": "farmer", "note": ""}), headers={"Content-Type": "application/x-www-form-urlencoded"})
        r = c.getresponse()
        body = r.read().decode("utf-8")
        assert r.status == 200 and "저장됨" in body and profile.load()["name"] == "박병각"
        c.request("POST", "/me", body=urlencode({"name": "x@y", "role": "farmer"}), headers={"Content-Type": "application/x-www-form-urlencoded"})
        r = c.getresponse()
        assert r.status == 400 and "PII" in r.read().decode("utf-8")
    finally:
        s.shutdown()
        s.server_close()
