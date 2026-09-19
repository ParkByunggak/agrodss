# -*- coding: utf-8 -*-
# [발행자 2026-09-19] 좌측 상단 탭 = AGRODSS(대문자) · 홈(/) 링크 · 모든 화면에 있다 — 채팅 셸과 표 화면(render.page) 둘 다.
from __future__ import annotations

import http.client
import threading
from urllib.parse import quote

import pytest

from frontend import chat_pages, config, serve

SID = "p001-jjokpa-2026f"
ROUTES = ("/c/new", f"/c/{quote(SID)}", f"/diary/{quote(SID)}", "/improve", "/me", "/judge", "/media", "/events", f"/doc/{config.LEDGER_DOC}", "/nope")


@pytest.fixture
def srv(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1]
    s.shutdown()
    s.server_close()


def test_brand_is_uppercase_home_link():
    assert chat_pages.BRAND == "AGRODSS" and 'href="/"' in chat_pages.BRAND_HTML and ">AGRODSS " in chat_pages.BRAND_HTML
    assert "agrodss <small>" not in chat_pages.BRAND_HTML


@pytest.mark.parametrize("path", ROUTES)
def test_every_screen_has_the_brand_home_tab(srv, path):
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    body = r.read().decode("utf-8")
    assert 'class="brand" href="/"' in body and ">AGRODSS " in body, path
    assert "<title>AGRODSS" in body or r.status == 404, path


def test_home_redirects_to_first_chat(srv):
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
    c.request("GET", "/")
    r = c.getresponse()
    assert r.status == 302 and r.getheader("Location", "").startswith("/c/")
