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
