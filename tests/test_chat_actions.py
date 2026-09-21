# -*- coding: utf-8 -*-
# [M-13 · 발행자 2026-09-19] 음성 질문(브라우저 내장 인식 → 끝나면 텍스트로 전송) · 질문 아래 복사/편집/다시 시도 ·
#        답변 아래 복사/개선 요구/소리 내어 읽기. 원장은 append-only — 편집·다시 시도는 출처를 잇는 새 줄.
from __future__ import annotations

import http.client
import threading
from datetime import date, datetime, timezone
from urllib.parse import quote, urlencode

import pytest

from frontend import chat_pages, config, serve
from ingest import chat, feedback as fb
from schema import records as sch

SID = "p001-jjokpa-2026f"
T = date(2026, 9, 19)
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def test_retry_and_edit_link_to_origin_and_keep_original():
    m, _ = chat.send(SID, "언제 캐면 되나?", today=T, now=NOW)
    r, _ = chat.send(SID, "언제 캐면 되나?", today=T, now=NOW, retry_of=m["id"])
    e, _ = chat.send(SID, "쪽파는 언제 캐면 되나?", today=T, now=NOW, edit_of=m["id"], input_mode="voice")
    assert r["retry_of"] == m["id"] and e["edit_of"] == m["id"] and e["input_mode"] == "voice"
    assert chat.get_message(m["id"])["text"] == "언제 캐면 되나?"                # 원문은 남는다
    assert [x["id"] for x in chat.list_messages(SID) if x["role"] != "system"] == [m["id"], r["id"], e["id"]]
    with pytest.raises(chat.ChatError, match="없는 메시지"):
        chat.send(SID, "x", today=T, now=NOW, retry_of="msg_nope")
    with pytest.raises(chat.ChatError, match="입력 방식"):
        chat.send(SID, "x", today=T, now=NOW, input_mode="telepathy")
    for x in chat.list_messages(SID):
        sch.validate(x)


def test_request_improvement_on_answer_lands_in_feedback_and_chat():
    m, reply = chat.send(SID, "언제 캐면 되나?", today=T, now=NOW)
    req, note = chat.request_improvement(reply["id"], now=NOW)
    assert req["kind"] == "feedback.request" and req["target"] == "decision" and req["target_ref"] == reply["id"] and req["subject"] == SID
    assert req["status"] == "접수" and fb.latest_by_id("feedback.request")[req["id"]]["status"] == "접수"
    assert note["role"] == "system" and note["request_ref"] == req["id"] and note["reply_ref"] == reply["id"]
    with pytest.raises(chat.ChatError, match="시스템 답변"):
        chat.request_improvement(m["id"])


def test_question_and_answer_action_bars_and_voice_button_in_page():
    m, reply = chat.send(SID, "언제 캐면 되나?", today=T, now=NOW)
    html = chat_pages.thread_main({"id": SID, "label": "x"}, T)
    q = html.split(f'id="t-{m["id"]}"')[1].split('class="msg sys"')[0]
    assert 'data-act="copy"' in q and 'data-act="edit"' in q and 'data-act="retry"' in q and f'name="retry_of" value="{m["id"]}"' in q
    a = html.split(f'id="t-{reply["id"]}"')[1].split("</div></div></div>")[0]
    # [발행자 2026-09-22] '고쳐 달라기' 는 이제 **칸을 연다** — 단추만 있으면 무엇이 틀렸는지가 아무 데도 안 남는다
    assert 'data-act="copy"' in a and 'data-act="speak"' in a and f'name="reply" value="{reply["id"]}"' in a
    assert "<details" in a and 'name="text"' in a and "<textarea" in a, "고쳐 달라는 말을 적을 칸이 없다"
    assert 'id="mic"' in html and "SpeechRecognition" in html and "speechSynthesis" in html and 'name="input_mode"' in html
    assert "rec.onend" in html and "submit()" in html                        # 말이 끝나면 자동 전송


@pytest.fixture
def srv(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1]
    s.shutdown()
    s.server_close()


def _post(port, path, form):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("POST", path, body=urlencode(form), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.getheader("Location"), r.read().decode("utf-8")


def test_http_retry_voice_and_request(srv):
    st, loc, _ = _post(srv, f"/c/{quote(SID)}/send", {"text": "언제 캐면 되나?", "input_mode": "voice"})
    assert st == 302
    msgs = chat.list_messages(SID)
    m, reply = msgs[0], msgs[1]
    assert m["input_mode"] == "voice"
    st, _, _ = _post(srv, f"/c/{quote(SID)}/send", {"text": m["text"], "retry_of": m["id"]})
    assert st == 302 and chat.list_messages(SID)[2]["retry_of"] == m["id"]
    # 적은 말이 **그대로** 요구가 된다(전에는 시스템이 지어낸 한 줄만 들어갔다)
    st, _, body = _post(srv, f"/c/{quote(SID)}/request", {"reply": reply["id"], "text": "수확 시기를 날짜로 말해 주세요"})
    assert st == 200 and "말씀 받았습니다" in body
    reqs = fb.list_records("feedback.request")
    assert len(reqs) == 1 and reqs[0]["text"] == "수확 시기를 날짜로 말해 주세요"
    st, _, body = _post(srv, f"/c/{quote(SID)}/request", {"reply": m["id"]})
    assert st == 400 and "시스템 답변" in body
