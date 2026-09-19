# -*- coding: utf-8 -*-
# [코드 평가 D3 · D4 · A12 · 2026-09-19] 값 하나가 화면 전체를 무응답으로 만들지 않는다.
#   D3  기준점(anchor) 형식을 스키마가 검사한다 — 등록부 편집 경로(add · set_anchor) 둘 다 sch.validate 를 지나므로 한 곳이면 된다.
#   A12 상태 어휘도 스키마가 본다(파일 직접 편집도 걸린다).
#   D4  핸들러 총괄 예외 → 500 페이지(메시지 이스케이프) · 다음 요청은 정상.
from __future__ import annotations

import http.client
import threading

import pytest

from frontend import config, serve
from ingest import subjects
from schema import records as sch
from tests.test_brand_home import srv  # noqa: F401 — 서버 픽스처 한 벌
from tests.test_chat_diary import reg  # noqa: F401 — 등록부 픽스처 한 벌

SUBJ = [s for s in subjects.load() if s["id"] == "p001-jjokpa-2026f"][0]


def test_schema_rejects_non_iso_anchor_and_bad_status():
    for bad in ("2026-9-20", "20260920", "2026-09-20T00:00", "어제", ""):
        with pytest.raises(sch.SchemaError, match="YYYY-MM-DD"):
            sch.validate({**SUBJ, "anchor": bad}, kind="subject")
    assert sch.validate({**SUBJ, "anchor": "2026-09-20"}, kind="subject")
    with pytest.raises(sch.SchemaError, match="상태가 어휘 밖"):
        sch.validate({**SUBJ, "status": "끝"}, kind="subject")


def test_registry_paths_refuse_bad_anchor(reg):
    with pytest.raises(sch.SchemaError, match="YYYY-MM-DD"):
        subjects.add("배추", "2026 가을", status="재배 중", anchor="2026-9-1")
    s = subjects.add("배추", "2026 가을", status="계획")
    with pytest.raises(sch.SchemaError, match="YYYY-MM-DD"):
        subjects.set_anchor(s["id"], "9월 1일")
    assert subjects.by_id(s["id"]).get("anchor") is None                      # 실패한 set_anchor 는 등록부를 안 바꾼다


def test_handler_exception_becomes_500_page_and_server_survives(srv, monkeypatch):
    def boom():
        raise RuntimeError("의도한 실패 <b>x</b>")
    monkeypatch.setattr(serve, "judge_page", boom)
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
    c.request("GET", "/judge")
    r = c.getresponse()
    body = r.read().decode("utf-8")
    assert r.status == 500 and "화면 오류" in body and "RuntimeError" in body
    assert "&lt;b&gt;x&lt;/b&gt;" in body and "<b>x</b>" not in body                # 메시지는 이스케이프
    assert 'class="brand" href="/"' in body and 'id="user-tab"' in body            # 오류 화면도 매 페이지 규칙
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
    c.request("GET", "/me")
    assert c.getresponse().status == 200                                            # 다음 요청은 산다
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
    c.request("POST", "/c/nope/send", body="text=x", headers={"Content-Type": "application/x-www-form-urlencoded", "Content-Length": "abc"})
    assert c.getresponse().status == 500                                            # POST 도 같은 방어선(Content-Length 비정수)
