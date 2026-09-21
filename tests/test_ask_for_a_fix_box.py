# -*- coding: utf-8 -*-
# [발행자 2026-09-22] 발행자가 답변 아래 '개선 요구' 를 눌렀고, 돌아온 것은 이 한 줄이었다.
#
#   개선 요구 접수 req_c4b1589043e7 — 개선 항목이 되면 /improve 에 보인다. 채택은 사람이 한다(D-14).
#
# 발행자: *"이 때 개선요구를 선택하면 … 사용자가 **직접 입력해서** 개선 사항을 시스템에 전하는 **입력창이 필요하다**."*
#
# 재 보니 받는 쪽 `chat.request_improvement(reply_id, text)` 은 **처음부터 `text` 를 받고 있었고**, 라우트도
# `form.get("text")` 를 넘기고 있었다 — **보내는 쪽에 칸이 없었다.** 그래서 단추 한 번이 언제나 시스템이 지어낸
# 문장("이 답변이 틀리거나 부족하다: …")만 접수시켰고, **무엇이 틀렸는지는 아무 데도 안 남았다.**
#
# G1("정본이 있는데 소비자가 0")의 거울이다 — 여기서는 받는 자리가 있는데 **입구**가 없었다.
from __future__ import annotations

import http.client
import re
import threading
from datetime import date, datetime, timezone
from urllib.parse import quote, urlencode

import pytest

from frontend import chat_pages, config, serve
from ingest import chat, feedback as fb, media

T = date(2026, 9, 19)
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


@pytest.fixture
def srv(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    monkeypatch.setenv(config.TODAY_ENV, T.isoformat())
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1]
    s.shutdown()
    s.server_close()


def _post(port, path, form):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("POST", path, body=urlencode(form), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.read().decode("utf-8")


def _an_answer(sid: str) -> dict:
    _, reply = chat.send(sid, "수확 언제 하나요?", today=T, now=NOW)
    assert reply and reply["role"] == "system"
    return reply


def test_the_button_opens_a_box_instead_of_filing_a_made_up_sentence():
    """단추만 있으면 시스템이 지어낸 한 줄만 들어간다 — 적을 자리가 있어야 그 사람의 말이 남는다."""
    m = {"id": "msg_x", "subject": "s1", "text": "[이렇게 보입니다] 수확 기간 2026-10-14 ~ 2026-11-03"}
    html = chat_pages._answer_actions(m)
    assert "<details" in html and "<textarea" in html and 'name="text"' in html
    assert 'name="reply" value="msg_x"' in html, "어느 답에 대한 말인지 안 붙는다"
    assert "required" in html, "빈 채로 보내면 또 지어낸 문장이 들어간다"
    assert "수확 기간" in html, "무엇에 대한 말인지 화면이 안 보여 준다"


def test_the_box_quotes_the_answer_but_does_not_carry_the_whole_wall():
    """무엇에 대한 말인지 보이되, 긴 답을 통째로 싣지 않는다(적는 칸이 밀려난다)."""
    long = "가" * 300
    html = chat_pages._answer_actions({"id": "m", "subject": "s", "text": long})
    assert "…" in html and html.count("가") <= 90


def test_what_the_person_typed_becomes_the_request(srv):
    """**끝에서 끝까지** — 적은 말이 그대로 요구가 되고, 답은 사람 말로 돌아온다."""
    sid = media.load_subjects()[0]["id"]
    reply = _an_answer(sid)
    said = "수확 시기를 날짜 말고 '언제쯤' 으로 알려 주세요"
    st, body = _post(srv, f"/c/{quote(sid)}/request", {"reply": reply["id"], "text": said})
    assert st == 200
    reqs = fb.list_records("feedback.request")
    assert [r["text"] for r in reqs] == [said], "적은 말이 안 남았다 — 시스템이 지어낸 문장이 대신 들어갔다"
    assert reqs[0]["target_ref"] == reply["id"]
    # 보이는 글자만 본다 — `/improve` 는 링크 주소로 남아 있어야 하고(누르면 가는 곳), **말**로 나오면 안 된다
    seen = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", body))
    for w in ("개선 요구", "접수", "D-14", "/improve"):
        assert w not in seen, f"돌아온 말이 안쪽 말이다 — '{w}'"


def test_an_empty_box_still_does_not_invent_what_was_wrong(srv):
    """빈 채로 와도(프로그램 호출 등) **지어내지 않는다** — 답을 그대로 인용한다고 밝힌다."""
    sid = media.load_subjects()[0]["id"]
    reply = _an_answer(sid)
    st, _ = _post(srv, f"/c/{quote(sid)}/request", {"reply": reply["id"]})
    assert st == 200
    r = fb.list_records("feedback.request")[0]
    assert r["text"].startswith("이 답변이 틀리거나 부족하다:") and reply["text"][:20] in r["text"]
