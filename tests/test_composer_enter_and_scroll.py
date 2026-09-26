# -*- coding: utf-8 -*-
# [발행자 2026-09-26] 채팅 입력칸 둘.
#   ① "다시 시도하거나 새로운 질문을 하면 커서의 위치가 첫 질문의 위치로 가지 않고, 현재의 커서 위치에 있어야 한다."
#      보내기·다시 시도·넣기는 전부 화면을 다시 그리고, 브라우저는 새 문서를 맨 위에서 연다 — 새 답은 맨 아래에 있다.
#   ② "엔터키를 치면 보내기를 하지 않아도 문자가 전송이 되야 한다."
# 화면 스크립트는 여기서 실행하지 못한다 — 계약을 **구조**로 잰다(어느 요소에 · 어느 사건에 · 무엇을 하는가), 문면이 아니라.
from __future__ import annotations

import http.client
import re
from urllib.parse import quote

from frontend import chat_pages
from ingest import media
from tests.test_brand_home import srv  # noqa: F401


def _script() -> str:
    return chat_pages.ACTION_JS


def _enter_handler() -> str:
    """입력칸(#text)에 건 keydown 처리기 한 덩이 — 문자 범위(창)가 아니라 구조로 자른다."""
    src = _script()
    m = re.search(r'ta\.addEventListener\("keydown",\s*\((\w+)\)\s*=>\s*\{(.*?)\}\);', src, re.S)
    assert m, "입력칸에 keydown 처리기가 없다"
    return m.group(2)


def test_enter_sends_and_shift_enter_does_not_and_ime_composition_is_left_alone():
    body = _enter_handler()
    assert '"Enter"' in body and "shiftKey" in body and "isComposing" in body, body
    assert "preventDefault" in body and "requestSubmit" in body, "엔터가 줄바꿈이 되거나 보내기 검사(빈 글 거부)를 건너뛴다"
    assert body.index("isComposing") < body.index("requestSubmit"), "한글 조합 중 엔터를 거르지 않고 보낸다 — 마지막 글자가 잘린다"


def test_the_page_opens_at_the_newest_answer_with_the_cursor_in_the_box():
    src = _script()
    head = src[:src.index('document.addEventListener("click"')]                  # 사건 처리기보다 앞 — 문서를 열자마자
    assert "scrollTo(" in head and "scrollHeight" in head, "새 답이 있는 아래로 가지 않는다 — 첫 질문 자리에 선다"
    assert "ta.focus()" in head and "setSelectionRange" in head, "커서가 입력칸에 서지 않는다"


def test_the_script_is_wired_into_the_chat_page(srv):
    """함수만 보면 배선이 빠진다 — 실제 화면에 그 스크립트가 실린다."""
    sid = media.load_subjects()[0]["id"]
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", f"/c/{quote(sid)}")
    r = c.getresponse()
    page = r.read().decode("utf-8", "replace")
    assert r.status == 200
    assert 'id="text"' in page and 'addEventListener("keydown"' in page and "requestSubmit" in page and "scrollTo(" in page
    assert "Shift+Enter" in page                                                   # 사람이 알 수 있게 — 줄바꿈 길을 말한다
