# -*- coding: utf-8 -*-
# [칸 3 재측정 · 2026-09-20 / 코드 평가 C16] 원장이 두 시계로 적힌다 — 채팅·이름후보·프로필은 지역 시각, 사건·영상·되먹임은 UTC.
#   둘 다 오프셋을 싣고 있으니 **저장은 틀리지 않았다**. 틀린 것은 화면이 `ts[:16]` 으로 잘라 찍은 것 — 오프셋을 버리고
#   앞부분만 쓰니 UTC 원장이 아홉 시간 어긋나 보였다. 실측(KST): 09-21 08:00 에 적은 한 줄이 사건 표에 '09-20 23:00'.
#   **날짜가 하루 어긋난다** — 발행자가 곧 적을 예찰 한 줄이 정확히 이 형태다(아침 기록).
# 처방은 표현 층 하나(G1 세 번째 형태 — 정본은 옳은데 표기가 배반한다). 저장은 안 건드린다(이관 없음 · 되돌리기 쉬움):
#   `ingest/chat._now` 주석이 지역 시각 저장을 **이 표기를 피하려던 우회**로 기록해 두었다 — 게이트가 막던 것을 읽고 남긴다.
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from frontend import render

ROOT = Path(__file__).resolve().parent.parent


def test_both_ledger_clocks_render_to_the_same_instant():
    # 같은 한 순간을 두 저장형으로 적고, 화면 표기가 같은지 본다(기계의 지역 시각이 무엇이든)
    moment = datetime(2026, 9, 20, 23, 0, tzinfo=timezone.utc)
    as_utc = moment.isoformat(timespec="seconds")
    as_local = moment.astimezone(timezone(timedelta(hours=9))).isoformat(timespec="seconds")   # 발행자 PC 형태(KST)
    assert as_utc[:10] != as_local[:10], "전제: 두 저장형의 날짜가 다른 순간이어야 검사가 성립한다"
    assert render.local_time(as_utc) == render.local_time(as_local)


def test_offset_is_applied_not_truncated():
    kst = timezone(timedelta(hours=9))
    ts = datetime(2026, 9, 21, 8, 0, tzinfo=kst).isoformat(timespec="seconds")
    got = render.local_time(ts)
    expected = datetime(2026, 9, 21, 8, 0, tzinfo=kst).astimezone().strftime("%Y-%m-%d %H:%M")
    assert got == expected
    assert got != ts[:16].replace("T", " ") or datetime.now().astimezone().utcoffset() == timedelta(hours=9)


def test_bad_or_missing_timestamp_does_not_break_a_screen():
    assert render.local_time(None) == "" and render.local_time("") == ""
    assert render.local_time("언젠가") == "언젠가"


def test_no_screen_slices_a_timestamp_by_hand():
    # 래칫 — 표기 정본 하나. 자르기가 다시 생기면 같은 결함이 다른 화면에서 난다(§7.5 지점 축)
    for py in sorted((ROOT / "frontend").glob("*.py")) + sorted((ROOT / "mall").glob("*.py")):
        code = "\n".join(ln.split("#", 1)[0] for ln in py.read_text(encoding="utf-8").splitlines())
        hit = re.search(r"(recorded_at|fetched_at|last_seen_at)[^\n]{0,40}\[:\s*1[0-9]\s*\]", code)
        assert not hit, f"{py.name}: 시각을 손으로 자른다 — render.local_time() 으로 ({hit.group(0) if hit else ''})"
