# -*- coding: utf-8 -*-
# [작목별 메뉴 처방 직후 전수 2026-10-04] 작목 줄(labels.CROP_SCREENS)이 농가를 보내는 화면은 **전부 농가 화면**이다 — 메뉴를 만든 회차(c5a2889)에 사람 말 래칫(FARMER_PAGES)을
# 안 넓혀, 둘째 작목(대파)으로 걸으니 한 일 · 영상 · 몰 세 화면이 기준점 · 불이행 · 재배 단위 · 격자를 그대로 냈다(§7.5 지점 — 처방이 한 곳에만).
#   ① 작목 줄의 모든 주소 꼴이 FARMER_PAGES 에 있다(래칫의 래칫 — 다음 화면이 줄에 들어오면 여기서 붉다)
#   ② 재배 달력 없는 작목(대파)으로도 그 화면들이 안쪽 말을 안 한다(쪽파로만 걸으면 「재배 달력 또는 심은 날 없음」 줄이 안 나온다)
#   ③ 채팅 답의 두 문장(판정 재료가 없을 때)이 사람 말을 쓴다 — 전엔 "판단 불가(데이터) — … 재료(기준점·격자)" 를 그대로 냈다
from __future__ import annotations

from datetime import date, datetime, timezone

from ingest import chat, media, subjects
from judge import run as judge_run
from schema import labels
from tests.test_media import make_mp4
from tests.test_screen_speaks_plainly import FARMER_PAGES, JARGON, _get, _visible, srv  # noqa: F401

T = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
SID = "p001-jjokpa-2026f"


def test_every_crop_screen_is_a_farmer_page():
    shapes = {labels.crop_screen_href(k, "{sid}").replace("%7Bsid%7D", "{sid}") for k, _ in labels.CROP_SCREENS}
    missing = sorted(s for s in shapes if s not in FARMER_PAGES)
    assert missing == [], f"작목 줄이 보내는 화면이 사람 말 래칫 밖에 있다: {missing}"


def test_crop_screens_speak_plainly_for_a_crop_without_a_calendar(srv):
    sid2 = subjects.add("대파", "2026 가을", status="재배 중", parcel="p001", anchor="2026-10-01")["id"]
    # 표가 비어 있으면 표 머리(안쪽 말이 숨던 자리)가 안 그려진다 — 주입 G(영상 표 머리 「재배 단위」)가 빈 표로 통과했다. 한 일 하나 · 영상 하나를 먼저 넣고 걷는다
    m, _ = chat.send(sid2, "오늘 물 줬다", today=T, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)
    media.register(media.save_upload("clip.mp4", make_mp4(datetime(2026, 10, 3, 1, 0, tzinfo=timezone.utc))), SID, note="두둑 전경")
    for sid in (SID, sid2):
        for key, _ in labels.CROP_SCREENS:
            status, body = _get(srv, labels.crop_screen_href(key, sid))
            assert status == 200, (key, sid)
            seen = _visible(body)
            found = sorted({w for w in JARGON if w in seen})
            assert found == [], f"{key} {sid}: {found}"


def test_the_no_material_answers_speak_plainly(monkeypatch):
    s = subjects.by_id(SID)
    monkeypatch.setattr(judge_run, "judgments_for", lambda *a, **k: [])        # 판정이 하나도 안 서는 농사 — 두 갈래(증상 물음 · 주제 물음)가 각자 문장을 낸다
    for q in ("잎 끝이 노란데 왜 그런가", "물 줘야 하나"):
        text = chat.answer(s, q, T)
        found = sorted({w for w in JARGON if w in text})
        assert found == [], (q, text, found)
        assert "아직 모릅니다" in text and "심은 날 · 재배 달력" in text, text
