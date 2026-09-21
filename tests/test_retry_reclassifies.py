# -*- coding: utf-8 -*-
# [발행자 2026-09-21 "다시 시도"] 앞 회차에 제가 대장 페이지에 **"다시 시도 말고 새로 쳐서 보내라"** 고 적었다. 재니 **틀린 안내였다.**
#
#   측정 2026-09-21: 저장된 초안을 일부러 오염시킨 뒤 그 메시지의 '다시 시도' 폼이 보내는 것을 그대로 보냈더니
#   새 메시지의 초안은 **오염된 것이 아니라 새로 분류된 것**이었다(question). 곧 다시 시도는 분류를 **다시 돌린다**.
#
# 내가 구별한 "다시 시도 vs 새로" 는 애초에 없는 구별이었다 — 둘 다 같은 코드로 다시 분류한다. 그 문장이 실제로 갈렸던 이유는
# **서버 프로세스가 옛 코드였기** 때문이고, 그때는 새로 쳐도 똑같이 옛 답이 나온다. 안내가 재현 조건을 틀리게 지목한 것이다
# (지표를 재료로 쓰기 전에 어느 경로에서 나온 것인지 본다 — 조건 불일치 계열).
#
# 그래서 이 파일은 두 가지를 고정한다. ① 다시 시도가 분류를 다시 돌린다(누가 성능을 이유로 초안을 베끼게 고치면 깨진다)
# ② 다시 시도 단추는 **질문만이 아니라 모든 농가 발화**에 있다 — 잘못 분류된 발화야말로 다시 시도의 대상이다.
from __future__ import annotations

import http.client
from urllib.parse import quote, urlencode

from frontend import config
from ingest import chat
from tests.test_brand_home import srv  # noqa: F401

SID = "p001-jjokpa-2026f"
QUESTION = "쪽파를 현재 관리해야 할 항목들을 알려줘요"
TODAY = "2026-09-21"


def _post(port, path, form):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("POST", path, body=urlencode(form), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.read().decode("utf-8")


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.read().decode("utf-8")


def _farmer(sid=SID):
    return [m for m in chat.list_messages(sid) if m.get("role") != "system"]


def _system(sid=SID):
    return [m for m in chat.list_messages(sid) if m.get("role") == "system"]


def test_retry_runs_the_classifier_again_instead_of_copying_the_old_drafts(srv, monkeypatch):
    """원 결함이 있다면 이 검사가 잡는다 — 저장된 초안을 오염시켜 두고, 베끼는지 본다."""
    monkeypatch.setenv(config.TODAY_ENV, TODAY)
    _post(srv, f"/c/{quote(SID)}/send", {"text": QUESTION})
    first = _farmer()[-1]
    assert [d["kind"] for d in first["drafts"]] == ["question"]

    chat.get_message(first["id"])["drafts"]                      # 존재 확인
    poisoned = [{"kind": "observation.note", "text": "오염된 초안", "observed_at": "2026-01-01",
                 "why": "측정용 오염", "needs": []}]
    chat._append({**chat.get_message(first["id"]), "drafts": poisoned})   # 원장은 append-only — 최신 줄이 이긴다
    assert chat.get_message(first["id"])["drafts"] == poisoned

    st, _ = _post(srv, f"/c/{quote(SID)}/send", {"text": QUESTION, "retry_of": first["id"]})
    again = _farmer()[-1]
    assert st == 302 and again["id"] != first["id"]
    assert again.get("retry_of") == first["id"]                  # 출처를 잇는다
    assert [d["kind"] for d in again["drafts"]] == ["question"]  # **다시 분류했다**
    assert "오염된 초안" not in str(again["drafts"])
    assert chat.get_message(first["id"]) is not None             # 원문은 지우지 않는다(append-only)


def test_retry_and_a_freshly_typed_sentence_give_the_same_answer(srv, monkeypatch):
    """내가 발행자에게 그은 '다시 시도 vs 새로' 구별은 **없는 구별**이다 — 같은 코드가 같은 답을 낸다."""
    monkeypatch.setenv(config.TODAY_ENV, TODAY)
    _post(srv, f"/c/{quote(SID)}/send", {"text": QUESTION})
    first = _farmer()[-1]
    by_retry_start = len(_system())
    _post(srv, f"/c/{quote(SID)}/send", {"text": QUESTION, "retry_of": first["id"]})
    retried = _system()[-1]["text"]
    _post(srv, f"/c/{quote(SID)}/send", {"text": QUESTION})       # 새로 친 것
    fresh = _system()[-1]["text"]
    assert len(_system()) == by_retry_start + 2
    assert retried == fresh and "지금 할 것" in fresh


def test_every_farmer_message_can_be_retried_not_only_questions(srv, monkeypatch):
    """잘못 분류된 발화야말로 다시 시도의 대상이다 — 단추가 질문에만 있으면 고칠 길이 막힌다."""
    monkeypatch.setenv(config.TODAY_ENV, TODAY)
    _post(srv, f"/c/{quote(SID)}/send", {"text": QUESTION})                 # 질문
    _post(srv, f"/c/{quote(SID)}/send", {"text": "잎 끝이 누렇다"})            # 관찰
    st, body = _get(srv, f"/c/{quote(SID)}")
    assert st == 200
    for m in _farmer()[-2:]:
        i = body.index(f'id="t-{m["id"]}"')
        seg = body[i:body.index("</div></div>", i)]                        # 그 메시지 덩이만 — 구조로 자른다
        assert f'name="retry_of" value="{m["id"]}"' in seg, m["text"]
        assert 'data-act="retry"' in seg and f'value="{m["text"]}"' in seg  # 폼이 원문을 싣는다(빈 채로 다시 보내지 않는다)
