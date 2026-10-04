# -*- coding: utf-8 -*-
# [발행자 2026-10-04] 채팅 목록을 붙여 보이며 *"이 메뉴가 작목마다 있어야 한다"* — 「화면」 묶음(고쳐 달라는 말 · 판단 전체 · 자기 점검 · 결정 · 밭 정보·설정 · 영상 반입 · 한 일 · 몰)이
# 전체로만 있고 작목(대파 · 쪽파)별로는 없었다. 그날 발행자 화면엔 작목이 둘(쪽파 · 대파 — 심은 지 3일)이라 전체 화면은 두 작목이 섞인다.
#   처방: 채팅 목록의 각 작목 아래 그 작목으로 좁힌 화면 한 줄(판단 · 일지 · 한 일 · 영상 · 고쳐 달라는 말 · 몰) — 이름·주소는 화면 이름 계약(schema.labels.CROP_SCREENS) 하나 ·
#   화면 넷(/judge · /events · /media · /improve)이 ?s=<재배 단위> 를 받아 그 작목만 보이고 폼의 목록 칸도 그 작목으로 미리 골라진다 · 전체 묶음은 「화면 — 전체」 로 남는다.
from __future__ import annotations

import html as _html
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

from frontend import chat_pages
from ingest import chat, events as ev, feedback as fb, media, subjects
from schema import labels
from tests.test_screen_speaks_plainly import JARGON, _get, _visible, srv  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
T = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)


def _second() -> str:
    return subjects.add("대파", "2026 가을", status="재배 중", parcel="p001", anchor="2026-10-01")["id"]   # 발행자 화면의 둘째 작목(심은 지 3일)


def test_every_crop_in_the_list_has_its_own_screen_row_from_the_label_contract():
    sid2 = _second()
    side = _html.unescape(chat_pages.sidebar(f"/c/{SID}", [], T))
    for sid in (SID, sid2):
        for key, lab in labels.CROP_SCREENS:
            assert f'href="{labels.crop_screen_href(key, sid)}">{lab}</a>' in side, (sid, key)
    assert side.count('class="crop-screens"') == 2 and labels.CROP_GROUP in side          # 작목마다 한 줄 · 전체 묶음은 남는다
    for key, lab in labels.CROP_SCREENS:
        assert lab in labels.menu_labels() and not [w for w in JARGON if w in lab], lab
    assert labels.crop_screen_href("judge", "a b") == "/judge?s=a%20b" and labels.crop_screen_href("diary", SID) == f"/diary/{quote(SID)}"


def test_the_four_screens_narrow_to_one_crop_and_preselect_it(srv):
    sid2 = _second()
    m, _ = chat.send(sid2, "오늘 물 줬다", today=T, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)
    m2, _ = chat.send(SID, "오늘 트랩 확인했다", today=T, now=NOW)
    chat.confirm(m2["id"], 0, now=NOW)
    fb.add_request("대파 답이 이상하다", subject=sid2)
    fb.add_request("쪽파 답이 이상하다", subject=SID)
    lab2 = subjects.by_id(sid2)["label"]
    st, body = _get(srv, f"/judge?s={quote(sid2)}")
    seen = _visible(body)
    assert st == 200 and lab2 in seen and "괴산 연풍 텃밭 · 쪽파" not in seen and "전체 보기" in seen       # 그 작목만
    st, body = _get(srv, "/judge")
    assert st == 200 and lab2 in _visible(body) and "쪽파 · 2026 가을" in _visible(body)                   # 전체는 그대로 둘 다
    st, body = _get(srv, f"/events?s={quote(sid2)}")
    seen = _visible(body)
    assert st == 200 and "오늘 물 줬다" in seen and "오늘 트랩 확인했다" not in seen and f'value="{sid2}" selected' in body   # 기록도 폼의 목록 칸도 그 작목(종류 목록의 '예찰' 은 폼 선택지)
    st, body = _get(srv, f"/media?s={quote(sid2)}")
    assert st == 200 and lab2 in _visible(body) and "전체 보기" in _visible(body)
    st, body = _get(srv, f"/improve?s={quote(sid2)}")
    seen = _visible(body)
    assert st == 200 and "대파 답이 이상하다" in seen and "쪽파 답이 이상하다" not in seen and f'value="{sid2}" selected' in body
    st, body = _get(srv, "/improve")
    seen = _visible(body)
    assert "대파 답이 이상하다" in seen and "쪽파 답이 이상하다" in seen                                  # 전체는 둘 다
    st, body = _get(srv, f"/judge?s={quote('없는-id')}")
    assert st == 200 and "전체 보기" in _visible(body)                                                   # 없는 id 는 빈 화면 — 500 이 아니다


def test_crop_screen_names_live_in_the_contract_only():
    files = [p for d in ("frontend", "ingest", "judge", "scripts") for p in (ROOT / d).glob("*.py")]
    for lit in ("crop-screens", "화면 — 전체"):
        where = sorted(p.relative_to(ROOT).as_posix() for p in files if lit in re.sub(r"#.*", "", p.read_text(encoding="utf-8")))
        assert where in ([], ["frontend/chat_pages.py"]), (lit, where)                                 # 글자는 계약 또는 그것을 그리는 한 자리
    assert "CROP_SCREENS" in (ROOT / "frontend" / "chat_pages.py").read_text(encoding="utf-8")
    assert "crop_screen_href(" in (ROOT / "frontend" / "chat_pages.py").read_text(encoding="utf-8")   # 주소도 계약에서(경로 글자를 두 벌 두지 않는다)
