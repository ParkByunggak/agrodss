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
    # [2026-09-20 메뉴] 목록의 마지막 항목이 사용자 탭 블록이고(그 뒤에 다른 목록 항목이 없다), 메뉴 링크는 그 블록 **안**에 있다
    assert tab < end and body.rfind('class="grp"', 0, end) < tab and body.rfind("<a ", 0, tab) < tab, path
    assert body.rstrip()[:end].rstrip().endswith("</details>"), path
    for href, _, _ in (it for it in chat_pages.USER_MENU if it):
        assert f'href="{href}"' in body[tab:end], (path, href)


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
    assert 'id="user-tab"' in side and side.rstrip().endswith("</details>") and side.rindex('id="user-tab"') > side.rindex('class="grp"')
    assert "박병각" in side and 'href="/me"' in side


# [발행자 2026-09-20 화면 형식] 메뉴 항목은 전부 실재 경로다 — 없는 기능(언어 · 팀 · 로그아웃)은 넣지 않았고, 넣은 것은 200/302 로 열린다
def test_user_menu_items_all_resolve(srv):
    for href, label, _ in (it for it in chat_pages.USER_MENU if it):
        c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
        c.request("GET", href.split("#")[0])
        r = c.getresponse()
        r.read()
        assert r.status in (200, 302), (href, label, r.status)
    assert [it[1] for it in chat_pages.USER_MENU if it][:2] == ["설정", "도움 받기"]        # 스크린샷 형식의 첫 두 항목
    # 스크린샷 형식 → agrodss 실재 항목 대응표(고정 기대 — 목록 자체를 기대로 쓰면 항목이 빠져도 못 잡는다: 주입 F 실측)
    assert {it[0] for it in chat_pages.USER_MENU if it} == {"/me", "/doc/m13_chat_screen.md", "/", "/judge", "/events", "/media", "/improve",
                                                            "/me#sync", "/changes", "/doc/agrodss_backlog.md"}
    assert not any(w in " ".join(it[1] for it in chat_pages.USER_MENU if it) for w in ("언어", "팀", "로그아웃"))


def test_changes_page_shows_running_head_vs_repo_head_and_commit_titles(srv):
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
    c.request("GET", "/changes")
    body = c.getresponse().read().decode("utf-8")
    assert "변경 로그" in body and serve.RUNNING_HEAD in body and ("반영됨" in body or "뒤처짐" in body)
    lines = serve.git_log_lines(5)
    assert lines and all(len(h) >= 7 and len(d) == 10 for h, d, _ in lines) and lines[0][2] in body
    assert serve.git_log_lines.__doc__ and "제목만" in serve.git_log_lines.__doc__      # 본문은 싣지 않는다
    for w in ("갈금", "010-", "@"):                                                       # 커밋 제목에 PII 가 없어야 화면에도 없다
        assert w not in "".join(s for _, _, s in serve.git_log_lines(50)), w
    c.request("GET", "/me")
    assert 'id="sync"' in c.getresponse().read().decode("utf-8")                          # 메뉴 '휴대폰 동기화' 앵커


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
