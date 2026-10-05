# -*- coding: utf-8 -*-
# [2026-10-05] 문장 형태 점검의 기대 종류 열넷은 열흘 가까이 발행자 몫으로 막혀 있었고, 그 비용의 대부분이 **문장을 다시 치는 것**이었다 —
# 화면에는 줄이 흩어져 있고 보내는 꼴은 「문장 — 종류」 다. 그래서 화면이 **그대로 복사할 묶음**을 낸다(종이만 준다).
# 지키는 것 셋:
#   ① 종류 자리는 **비워 둔다** — 세션이 채우면 채점자와 응시자가 같아진다(발행자 규율). 묶음에 종류가 하나라도 적혀 있으면 이 검사가 터진다.
#   ② 줄은 **기대 없는 줄 전부와 정확히 같다**(이미 기대가 붙은 줄은 안 넣는다 — 다시 답하게 만들지 않는다)
#   ③ 보이는 종류 말은 **이 틀이 받는 종류**(probes.KINDS)뿐이고 말은 화면 정본(chat.KIND_PLAIN)에서 온다 —
#      전부 보이면 틀이 거부하는 말(영상 · 새 목록)을 적게 되고, 그러면 목록 파일이 안 실리는데 발행자는 이유를 모른다.
from __future__ import annotations

import html
import re
from datetime import date

from frontend import selfcheck
from ingest import chat, probes

T = date(2026, 10, 5)


def _block() -> str:
    u = selfcheck.utterances(T, selfcheck.subject())
    return selfcheck._fill_block(u, html.escape)


def _lines(block: str) -> list[str]:
    pre = re.search(r"<pre[^>]*>(.*?)</pre>", block, re.S)
    assert pre, "복사 묶음이 없다"
    return [ln for ln in html.unescape(pre.group(1)).splitlines() if ln.strip()]


def test_the_block_lists_exactly_the_rows_that_have_no_expectation():
    u = selfcheck.utterances(T, selfcheck.subject())
    blank = [r["text"] for g in u["groups"] for r in g["rows"] if r["expected"] is None]
    assert [ln.removesuffix(" — ").strip() for ln in _lines(_block())] == blank
    assert len(blank) == u["without_expected"]


def test_no_line_carries_a_kind_already():
    """세션이 기대를 붙이지 않는다 — 줄 끝은 비어 있다(발행자 규율: 채점자와 응시자가 같아지지 않게)."""
    said = set(chat.KIND_PLAIN.values())
    for ln in _lines(_block()):
        assert ln.rstrip().endswith("—"), ln
        tail = ln.split("—", 1)[1].strip()
        assert tail == "", f"종류가 미리 적혀 있다: {ln}"
        assert not any(w in tail for w in said)


def test_the_offered_words_are_exactly_what_the_frame_accepts():
    block = _block()
    offered = block.split("쓸 수 있는 말:", 1)[1].split("</p>", 1)[0]
    offered = [w.strip() for w in re.sub(r"<[^>]*>", "", offered).split("·")]
    expect = [chat.KIND_PLAIN[k] for k in dict.fromkeys(probes.KINDS) if k in chat.KIND_PLAIN]
    assert offered == expect, (offered, expect)
    for k in ("observation.video", "subject.new"):          # 틀이 안 받는 종류의 말은 보이지 않는다
        assert chat.KIND_PLAIN[k] not in offered


def test_the_guidance_does_not_show_the_publisher_an_answer():
    """[2026-10-05 발견] 발행자 몫 줄에 **예시 답**이 둘 적혀 있었다(「관수를 알려줘 — 조회(일지)」 · 「관수가 필요한가 — 물음(가뭄)」) — 세션이 답을 보이면
    채점자와 응시자가 같아진다(발행자 규율). 안내는 **꼴**만 말하고, 쓸 수 있는 말은 화면이 띄운다. 기대 없는 줄의 문장이 안내에 종류와 **붙어** 나오면 터진다."""
    import importlib
    page = importlib.import_module("scripts.build_ledger_page")
    said = " ".join(h + " " + b for h, b in page.NEXT_PUBLISHER)
    u = selfcheck.utterances(T, selfcheck.subject())
    blank = [r["text"] for g in u["groups"] for r in g["rows"] if r["expected"] is None]
    for sentence in blank:
        i = said.find(sentence)
        if i < 0:
            continue
        tail = said[i + len(sentence): i + len(sentence) + 14]
        assert "—" not in tail, f"안내가 답을 보인다: {sentence} …{tail}"


def test_the_block_is_on_the_page_and_speaks_plainly():
    import threading, http.client, os
    from frontend import config, serve
    config.PORT = 0
    os.environ[config.TODAY_ENV] = "2026-10-05"
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=60)
        c.request("GET", "/selfcheck")
        body = c.getresponse().read().decode("utf-8", "replace")
    finally:
        s.shutdown()
        s.server_close()
    assert "그대로 복사해 쓰실 줄" in body and selfcheck.FILL_HOW in body
    for ln in _lines(_block()):
        assert html.escape(ln.removesuffix(" — ").strip()) in body
