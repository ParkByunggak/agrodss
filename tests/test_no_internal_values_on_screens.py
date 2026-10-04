# -*- coding: utf-8 -*-
# [내부 값 전수 2026-10-04] 사람 말 래칫(test_screen_speaks_plainly.JARGON)은 **한글 목록**이라 영문 내부 값과 id 를 한 번도 못 잡았다. 전수로 재니 셋:
#   ① 재배 단위 id(p001-jjokpa-2026f)가 네 꼴에서 그대로 — /improve 요구 표 · /events 기록 표 · /media 등록 표 · /mall 머리
#   ② 고쳐 달라는 말의 **대상** 어휘가 영문 그대로(other · grid · decision …) · 게다가 화면이 그 어휘를 **사본**으로 박아 두었다(정본은 schema.records.TARGETS)
#   ③ 사용자 **역할**(farmer · publisher)이 배지 · 머리 · 폼에 그대로
# 처방은 사람 말 정본 하나(frontend.words.target · role · subject_label)이고 안쪽 값은 title 로 남는다(정확함을 안 버린다 — U-26 과 같은 가름).
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from urllib.parse import quote

from frontend import words
from ingest import chat, events as ev, feedback as fb, media, profile, subjects
from schema import records
from tests.test_media import make_mp4
from tests.test_screen_speaks_plainly import FARMER_PAGES, _get, _visible, srv  # noqa: F401

T = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
SID = "p001-jjokpa-2026f"
SUBJECT_ID_RE = re.compile(r"p\d{3}-[\w가-힣]+-\d{4}[\w가-힣]*")      # 재배 단위 id 꼴(p001-jjokpa-2026f · p001-대파-2026가을)
CODE_RE = re.compile(r"<code>.*?</code>", re.S)                      # 경로 · 파일 이름은 **인용된 기록**이다(실제 저장 경로가 media/<작목>/… 다) — /changes 가 커밋 제목을 걷는 것과 같은 가름


def _said(body: str) -> str:
    """화면이 **제 문장으로** 낸 글 — 기계 문자열(<code>: 경로 · 파일 이름 · 명령)은 걷는다."""
    return _visible(CODE_RE.sub(" ", body))


def _fill():
    """표가 비면 표 머리만 보고 칸은 안 보인다 — 네 화면에 한 줄씩 넣고 걷는다(영상 표 머리를 빈 표로 놓쳤던 전례)."""
    m, _ = chat.send(SID, "오늘 물 줬다", today=T, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)
    m2, _ = chat.send(SID, "답이 이상한데", today=T, now=NOW)
    chat.confirm(m2["id"], 0, now=NOW)
    ev.add_noncompliance(SID, "예찰", "트랩을 못 구했다", "2026-09-20")
    media.register(media.save_upload("c.mp4", make_mp4(datetime(2026, 10, 3, 1, 0, tzinfo=timezone.utc))), SID, note="두둑")


def test_no_screen_shows_a_raw_subject_id(srv):
    _fill()
    bad = {}
    for tmpl in list(FARMER_PAGES) + ["/changes"]:
        p = tmpl.format(sid=quote(SID))
        st, body = _get(srv, p)
        assert st == 200, p
        hits = sorted(set(SUBJECT_ID_RE.findall(_said(body))))
        if hits:
            bad[p] = hits
    assert bad == {}, f"화면이 재배 단위 id 를 그대로 낸다(그 농사의 이름을 낸다): {bad}"


def test_the_ids_are_still_there_exactly_in_the_title(srv):
    _fill()
    for p in (f"/improve", "/events", "/media", f"/mall/{quote(SID)}"):
        st, body = _get(srv, p)
        assert st == 200 and f'title="{SID}"' in body, p          # 정확한 id 는 버리지 않는다(title)
    assert words.subject_label(SID) == subjects.by_id(SID)["label"] and words.subject_label("없는것") == "없는것"
    assert words.subject_label(None) == "" and words.subject_label("") == ""


def test_no_screen_shows_the_raw_request_target_or_role(srv):
    _fill()
    for p in ("/improve", "/me"):
        st, body = _get(srv, p)
        seen = _said(body)
        raw = sorted({v for v in tuple(records.TARGETS) + tuple(profile.ROLES) if re.search(rf"(?<![A-Za-z_]){re.escape(v)}(?![A-Za-z_])", seen)})
        assert raw == [], f"{p}: 내부 어휘가 그대로 — {raw}"
    st, body = _get(srv, "/improve")
    seen = _visible(body)
    assert words.target("other") in seen and words.target("grid") in seen        # 사람 말로는 보인다(값을 숨기는 것이 아니다)
    st, body = _get(srv, "/me")
    assert words.role("farmer") in _visible(body)


def test_the_display_words_cover_every_inner_value_and_come_from_the_one_canon():
    assert set(words.TARGET_SAID) == set(records.TARGETS)                        # 어휘가 늘면 사람 말도 함께(적재 때 assert 가 또 본다)
    assert set(words.ROLE_SAID) == set(profile.ROLES)
    from frontend import chat_pages
    import inspect
    src = inspect.getsource(chat_pages.improve_main)
    assert "records.TARGETS" in src and "words.target(" in src and "words.subject_label(" in src
    assert '"other", "grid", "decision"' not in src                              # 화면에 사본을 두지 않는다
