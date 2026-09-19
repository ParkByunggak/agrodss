# -*- coding: utf-8 -*-
# [코드 평가 칸 2 ⓒ 반입 경계 · 2026-09-19] C6 연도 없는 월/일(과거형) · C7 재확인 방지 · C8 stamp → 이동 순서 · C9 잘린 mvhd ·
#   C10 예보 비숫자 값 · C12 관측일 없는 예찰 항목 · C13 불이행 사유 날짜 검증.
from __future__ import annotations

import struct
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from ingest import chat, events as ev, kma, media, ncpms
from tests.test_media import _atom  # noqa: F401 — 같은 아톰 조립기

SID = "p001-jjokpa-2026f"
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def test_past_month_day_rolls_to_last_year_but_plans_stay_ahead():
    jan = date(2026, 1, 5)
    assert chat.parse_day("12월 20일에 심었다", jan, past=True) == "2025-12-20"
    assert chat.parse_day("12월 20일에 심으려고", jan) == "2026-12-20"
    assert chat.classify("12월 20일에 종구 심었다", jan)[0]["observed_at"] == "2025-12-20"        # 사건 — 지난해
    assert chat.classify("12월 20일에 심을 예정", jan)[0]["planned_day"] == "2026-12-20"          # 계획 — 올해
    assert chat.parse_day("9월 1일에 물 줬다", date(2026, 9, 19), past=True) == "2026-09-01"     # 오늘 이전이면 올해


def test_confirm_twice_is_refused():
    m, _ = chat.send(SID, "오늘 물 줬다", today=date(2026, 9, 19), now=NOW)
    rec = chat.confirm(m["id"], 0, now=NOW)
    with pytest.raises(chat.ChatError, match="이미 확인된"):
        chat.confirm(m["id"], 0, now=NOW)
    assert [e["id"] for e in ev.list_records(SID, "event")] == [rec["id"]]                    # 원장에 한 줄


def test_register_stamps_before_moving_file():
    src = Path(media.__file__).read_text(encoding="utf-8")
    blk = src[src.index("def register("):]
    blk = blk[:blk.index("\ndef ", 10)]
    assert blk.index("sch.stamp(rec)") < blk.index("shutil.move(") and blk.index("sch.stamp(rec)") < blk.index("shutil.copy2(")


def test_truncated_mvhd_reports_error_instead_of_raising(tmp_path):
    bad = _atom(b"ftyp", b"isom") + _atom(b"moov", _atom(b"mvhd", b""))                       # 페이로드 0 바이트
    p = tmp_path / "bad.mp4"
    p.write_bytes(bad)
    pr = media.probe_mp4(p)
    assert pr.error and "mvhd" in pr.error and pr.creation_time is None


def test_forecast_non_numeric_value_is_missing_not_fatal():
    items = [{"fcstDate": "20260920", "fcstTime": "0600", "category": "TMX", "fcstValue": "", "baseDate": "20260919", "baseTime": "0500"},
             {"fcstDate": "20260920", "fcstTime": "0600", "category": "TMN", "fcstValue": "3.0", "baseDate": "20260919", "baseTime": "0500"},
             {"fcstDate": "20260920", "fcstTime": "0600", "category": "POP", "fcstValue": "-", "baseDate": "20260919", "baseTime": "0500"}]
    payload = {"response": {"body": {"items": {"item": items}}}}
    recs = kma.parse_vilage(payload, 69, 107, fetched_at="2026-09-19T05:00:00")
    assert recs and recs[0]["values"]["tmin"] == 3.0 and recs[0]["values"]["tmax"] is None


def test_pest_item_without_date_is_dropped():
    xml = "<r><item><kncrNm>파</kncrNm><dbyhsNm>고자리파리</dbyhsNm><frcstDvsnNm>주의</frcstDvsnNm></item></r>"
    assert ncpms.parse_forecast(xml, "쪽파") == []


def test_noncompliance_requires_a_date():
    with pytest.raises(ev.EventError, match="날짜 형식"):
        ev.add_noncompliance(SID, "예찰", "비가 와서", "다음에", now=NOW)
    with pytest.raises(ev.EventError):
        ev.add_noncompliance(SID, "예찰", "비가 와서", "", now=NOW)
    r = ev.add_noncompliance(SID, "예찰", "비가 와서", "2026-09-08", now=NOW)
    assert r["observed_at"] == "2026-09-08" and r["planned_day"] == "2026-09-08"
