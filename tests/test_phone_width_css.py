# -*- coding: utf-8 -*-
# [U-34 2026-09-26] 실제 브라우저(Chromium + Playwright)로 화면 열 개를 390px 폭에서 걸으니 넷이 옆으로 넘쳤다 —
#   /improve 832 · /me 475(그리드 항목 min-width:auto 가 안쪽 폼 폭에 밀림) · /events 452(size=40 입력칸) · /media 399(긴 code)
# 그리고 화면마다 favicon 404 가 콘솔 오류로 찍혔다.
# 브라우저 실측이 정본이고(재현: scratchpad live_overflow.cjs — 격리 서버), 여기는 그 처방이 빠지지 않게 **구조로** 고정한다.
from __future__ import annotations

import http.client
import re
from urllib.parse import quote

from frontend import chat_pages, render
from ingest import media
from tests.test_brand_home import srv  # noqa: F401


def _rule(css: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, f"규칙이 없다: {selector}"
    return m.group(1)


def _phone_block(css: str) -> str:
    """720px 이하 미디어 블록 전부를 이어 붙인다 — 어느 블록에 있든 상관없다(자리를 고정하지 않는다).
    중괄호를 세어 자른다 — 첫 판의 `\\{(.*?)\\}` 는 안쪽 규칙의 첫 `}` 에서 멈춰 뒤 규칙을 잃었다(자기 도구 오류)."""
    out = []
    for m in re.finditer(r"@media \(max-width:720px\)\s*\{", css):
        depth, i = 1, m.end()
        while i < len(css) and depth:
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out.append(css[m.end():i - 1])
    return "\n".join(out)


def test_the_chat_shell_does_not_let_a_wide_form_push_the_page_sideways():
    css = chat_pages.CSS
    assert "min-width:0" in _rule(css, "main.thread"), "그리드 항목이 안쪽 폼 폭에 밀린다(/improve 832px)"
    assert "max-width:100%" in _rule(css, ".msgs input, .msgs select, .msgs textarea"), "입력칸이 화면보다 넓다(768px 에서도 넘쳤다 — 폭 전부)"
    phone = _phone_block(css)
    assert "overflow-x:auto" in _rule(phone, "table.tb"), "표가 제자리에서 옆으로 밀리지 않고 화면을 넘긴다"


def test_the_table_screens_fit_a_phone():
    css = render.CSS
    assert "max-width:100%" in _rule(css, "input, select"), "size=40 입력칸이 화면을 넘긴다(/events 452px)"
    assert "overflow-wrap:anywhere" in _rule(css, "code"), "긴 code 가 줄을 안 바꾼다(/media 399px)"
    phone = _phone_block(css)
    assert "flex-direction:column" in _rule(phone, ".wrap"), "좁은 화면에서 왼쪽 메뉴 240px 이 본문을 눌러 150px 만 남는다"
    # 표 화면의 폼(.reg)은 grid 인데 열이 auto 라 항목의 max-width:100% 가 무효였다(순환) — 열을 minmax(0,1fr) 로.
    # 그 스타일은 serve.py 에 **두 벌** 인라인이다(지점 축) — 한 벌만 고치면 다른 화면이 그대로 넘친다. 전부를 센다.
    from frontend import serve
    src = open(serve.__file__, encoding="utf-8").read()
    rules = re.findall(r"\.reg\{[^}]*\}", src)
    assert rules and all("grid-template-columns:minmax(0,1fr)" in r for r in rules), rules


def test_no_page_asks_for_a_favicon_it_does_not_have(srv):
    """콘솔의 404 한 줄 — 없는 파일을 매번 청한다. 빈 아이콘을 선언해 청하지 않게 한다(두 껍데기 다)."""
    sid = media.load_subjects()[0]["id"]
    for p in (f"/c/{quote(sid)}", "/judge"):
        c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
        c.request("GET", p)
        r = c.getresponse()
        head = r.read().decode("utf-8", "replace").split("</head>", 1)[0]
        assert r.status == 200 and 'rel="icon"' in head, p
