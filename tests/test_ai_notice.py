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


def _footer_of(body: str) -> str | None:
    """꼬리 **요소만** 잘라 낸다 — 페이지 전체를 세면 문서 본문과 겹친다.

    [§7.1 4번 실측 2026-09-21] 처음엔 페이지 전체에서 문면을 셌는데 `/doc/agrodss_backlog.md` 가 2 였다 —
    **대장 문서에 이 노티스 문면을 적어 두었기 때문**이다(검사 문자열이 검사 대상 밖에도 있었다).
    거리가 아니라 구조로 자른다: 표 화면은 `<footer>`, 채팅 셸은 화면 하단 고정 div.
    """
    if "<footer>" in body:
        return body[body.rindex("<footer>") + len("<footer>"):body.rindex("</footer>")]
    key = "position:fixed;bottom:4px"
    if key in body:
        i = body.index(key)
        return body[body.index(">", i) + 1:body.index("</div>", i)]
    return None


@pytest.mark.parametrize("path", ROUTES)
def test_the_footer_is_rendered_once_and_not_re_assembled_by_the_screen(srv, path):
    """[발행자 화면 2026-09-21] 발행자가 붙여 주신 꼬리가 결함을 그대로 보여 주었다:

        HEAD 실행 중 225cf9f · 127.0.0.1:8765 · 외부 배포 없음(D-6) · 127.0.0.1:8765 · 외부 배포 없음(D-6)

    채팅 셸이 **꼬리 정본을 받아 놓고** 호스트·포트·D-6 을 한 번 더 붙이고 앞에 낡은 `HEAD ` 를 달았다.
    정본이 '실행 중' 으로 바뀐 뒤에도 사본의 `HEAD` 는 안 바뀌어, 읽는 사람에게는 *저장소 HEAD* 로 보였다
    (두 벌 진실의 표현 층 판 — 표 화면은 정본을 그대로 실어서 멀쩡했고 **발행자가 온종일 보는 채팅 화면만** 틀렸다).
    """
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    body = r.read().decode("utf-8")
    if r.status == 404:
        return
    foot = _footer_of(body)
    assert foot is not None, f"꼬리 요소를 못 찾았다: {path}"
    assert foot.count("외부 배포 없음(D-6)") == 1, f"꼬리가 두 벌이다: {path} → {foot}"
    assert foot.count(serve.AI_NOTICE) == 1, f"{path} → {foot}"
    assert "HEAD 실행 중" not in foot, "낡은 'HEAD ' 접두가 남아 저장소 HEAD 처럼 읽힌다"


def test_the_notice_rides_the_one_footer_canon_not_a_second_copy():
    """정본이 하나인가 — 꼬리 문자열이 노티스를 싣고, 화면 코드가 따로 적지 않는다."""
    assert NOTICE in serve.footer_text()
    src = (serve.Path(serve.__file__).parent / "serve.py").read_text(encoding="utf-8")
    assert src.count(NOTICE) == 1, "노티스 문면이 두 곳 이상에 적혀 있다 — 어긋날 자리다"
    assert "실행 중" in serve.footer_text()                # 드리프트 표기는 그대로 남는다(둘 다 필요하다)
