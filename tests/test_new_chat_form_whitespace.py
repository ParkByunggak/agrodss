# -*- coding: utf-8 -*-
# [발행자 실사용 2026-09-28] 새 채팅 폼 — 작목 대파 · 작기 2026 가을 · 계획 · 기준점 '2026-09-30 '(끝 공백) · 유기 · p001 → "기준점(anchor)은 YYYY-MM-DD 여야 한다: '2026-09-30 '".
# 휴대폰 자판·자동완성이 붙이는 양끝 공백은 사람이 친 값의 뜻이 아니다 — 입구(subjects.add) 한 곳에서 걷는다. 거부·통과 둘 다: 공백은 걷고, 진짜 틀린 날짜는 여전히 거부.
from __future__ import annotations

import http.client
from urllib.parse import urlencode

import pytest

from ingest import subjects
from tests.test_brand_home import srv  # noqa: F401


def _post(port, path, data):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    body = urlencode(data)
    c.request("POST", path, body=body, headers={"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(body))})
    r = c.getresponse()
    return r.status, r.getheader("Location") or "", r.read().decode("utf-8", "replace")


def test_the_publisher_form_with_a_trailing_space_creates_the_subject(srv):
    st, loc, body = _post(srv, "/c/new", {"crop": "대파", "season": "2026 가을", "status": "계획", "anchor": "2026-09-30 ", "cert": "유기 ", "parcel": "p001"})
    assert st in (302, 303) and loc.startswith("/c/"), (st, body[:300])
    s = next(x for x in subjects.load() if x["crop"] == "대파" and x["season"] == "2026 가을")
    assert s["anchor"] == "2026-09-30" and s["cert"] == "유기" and s["status"] == "계획"


def test_add_strips_what_a_person_typed_but_keeps_real_errors():
    s = subjects.add(" 대파", " 2026 가을 ", " 계획 ", parcel=" p001 ", anchor="  2026-09-30  ", cert=" 유기 ")
    assert s["anchor"] == "2026-09-30" and s["cert"] == "유기" and s["status"] == "계획" and s["crop"] == "대파" and s["season"] == "2026 가을"
    assert "anchor" not in subjects.add("배추", "2026 가을", "계획", parcel="p001", anchor="   ")      # 공백만이면 없는 것(계획)
    with pytest.raises(Exception, match="YYYY-MM-DD"):
        subjects.add("도라지", "2026 가을", "계획", parcel="p001", anchor="2026-9-30")                  # 진짜 틀린 꼴은 여전히 거부
