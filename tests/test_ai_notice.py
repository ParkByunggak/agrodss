# -*- coding: utf-8 -*-
# [발행자 2026-09-21] "AGRODSS는 AI이므로 실수를 할 수 있습니다. 응답을 다시 한번 확인해 주세요." — 이 문장을 화면 하단에.
#
# 문면은 발행자가 준 그대로 싣고, **정본은 한 줄**(`serve.AI_NOTICE`)이다. 꼬리를 만드는 자리가 여섯인데 각자 적으면
# 언젠가 어긋난다(이 트랙의 '두 벌 진실' 계열). 그래서 꼬리 정본 `footer_text()` 하나가 그것을 싣고, 검사는
# **모든 화면**에서 실제로 보이는지를 본다 — 한 화면만 보면 나머지가 숨는다(§7.5 지점 축).
from __future__ import annotations

import http.client

import pytest

from frontend import serve
from tests.test_brand_home import ROUTES, srv  # noqa: F401

NOTICE = "AGRODSS는 AI이므로 실수를 할 수 있습니다. 응답을 다시 한번 확인해 주세요."


def test_the_notice_text_is_exactly_what_the_publisher_gave():
    assert serve.AI_NOTICE == NOTICE


@pytest.mark.parametrize("path", ROUTES)
def test_every_screen_carries_the_notice_at_the_bottom(srv, path):
    """채팅 셸 · 표 화면 · 404 — 꼬리가 있는 화면은 전부. 한 곳만 검사하면 나머지가 숨는다."""
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    body = r.read().decode("utf-8")
    if r.status == 404:
        return                                            # 없는 경로는 꼬리가 없다(그 자체가 계약)
    assert NOTICE in body, path


def test_the_notice_rides_the_one_footer_canon_not_a_second_copy():
    """정본이 하나인가 — 꼬리 문자열이 노티스를 싣고, 화면 코드가 따로 적지 않는다."""
    assert NOTICE in serve.footer_text()
    src = (serve.Path(serve.__file__).parent / "serve.py").read_text(encoding="utf-8")
    assert src.count(NOTICE) == 1, "노티스 문면이 두 곳 이상에 적혀 있다 — 어긋날 자리다"
    assert "실행 중" in serve.footer_text()                # 드리프트 표기는 그대로 남는다(둘 다 필요하다)
