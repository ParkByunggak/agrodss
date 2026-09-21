# -*- coding: utf-8 -*-
# [실측 2026-09-21] 발행자는 밭에서 일하고 **돌아와서** 적는다. 9/24 마감이 지난 뒤에 적을 때 날짜가 안 잡히면
# **밭에 다녀온 일이 '놓침' 으로 남는다** — 시스템이 농가를 벌주는 형태다.
#
# 재 보니 어제 · 그저께 · "9월 23일" · "9/23" 은 잡혔고 **세 형태가 비어 있었다**.
#
#   이틀 전에 물 줬다       `_AGO` 가 **숫자만** 봤다 — 한글 수사(하루 · 이틀 · 사흘 …)가 안 걸렸다
#   23일에 예찰했다         달 없이 일만 — 달을 지어내지 않으려면 **가장 가까운 그 날**을 고르면 된다
#   지난 금요일에 제초했다   요일
#
# 되묻는 것 자체는 정직하지만(지어내지 않는다), **마찰이 그대로 기록 누락**이 된다. 추론한 날짜는 확인 폼에
# 그대로 보이므로 사람이 보고 고친다 — 조용히 박는 대리값과 다른 점이 그것이다.
#
# **함정을 먼저 막고 만들었다**: `23일차`(파종 경과일) · `23일째` · `10일 뒤`(앞날) · `3일 걸렸다`(기간) ·
# `5일 남았다` · `30일 넘게`. 날짜가 아닌 것을 날짜로 읽으면 **원장이 조용히 틀린다**(되묻는 쪽이 낫다).
from __future__ import annotations

from datetime import date, timedelta

import pytest

from ingest import chat, events as ev, parcels, media
from judge import plan_vs_actual as pva

TODAY = date(2026, 9, 26)          # 예찰 마감(9/24)이 **지난** 뒤 — 늦게 적는 상황 그대로
SID = "p001-jjokpa-2026f"


@pytest.mark.parametrize("text, want", [
    ("이틀 전에 물 줬다", "2026-09-24"),
    ("사흘 전에 제초했다", "2026-09-23"),
    ("열흘 전에 소독했다", "2026-09-16"),
    ("하루 전에 트랩 확인했다", "2026-09-25"),
    ("23일에 예찰했다", "2026-09-23"),
    ("지난 금요일에 제초했다", "2026-09-18"),
    ("금요일에 제초했다", "2026-09-25"),
    # 이미 되던 것 — 넓히면서 깨뜨리지 않는다(반대편)
    ("어제 트랩 확인했다", "2026-09-25"),
    ("그저께 트랩 확인했다", "2026-09-24"),
    ("9월 23일 트랩 확인했다", "2026-09-23"),
    ("9/23 트랩 확인했다", "2026-09-23"),
    ("오늘 트랩 확인했다", "2026-09-26"),
])
def test_a_date_written_after_the_fact_is_read_as_the_day_it_happened(text, want):
    assert chat.parse_day(text, TODAY, past=True) == want, text


@pytest.mark.parametrize("text", [
    "파종 23일차 사진", "파종 23일째", "10일 뒤에 웃거름", "3일 후에 제초",
    "작업이 3일 걸렸다", "제초가 2일 걸려서 힘들었다", "마감까지 5일 남았다",
    "30일 넘게 비가 안 왔다", "7일 정도 지났다", "트랩 확인했다",
])
def test_things_that_are_not_dates_are_not_read_as_dates(text):
    """[게이트는 양방향] 날짜가 아닌 것을 날짜로 읽으면 **원장이 조용히 틀린다** — 그때는 되묻는 쪽이 낫다."""
    assert chat.parse_day(text, TODAY, past=True) is None, text


def test_a_plan_written_with_a_bare_day_looks_forward_not_back():
    """계획은 앞날이 맞다 — 같은 '25일' 이 사건이면 지난 25일, 계획이면 다음 25일이다."""
    assert chat.parse_day("25일에 웃거름 줄 것", TODAY, past=False) == "2026-10-25"
    assert chat.parse_day("25일에 웃거름 줬다", TODAY, past=True) == "2026-09-25"


def test_the_late_entry_is_counted_as_done_not_missed():
    """이 회차의 이유 — 늦게 적어도 **그날 한 일**이면 이행이어야 한다(마감이 지난 뒤 적었다고 놓침이 아니다)."""
    raw = next(s for s in media.load_subjects() if s["id"] == SID)
    subj = parcels.enrich_subject(raw, parcels.by_id("p001"))
    drafts = chat.classify("이틀 전에 트랩 확인했다", TODAY)
    d = drafts[0]
    assert d["kind"] == "event" and d["observed_at"] == "2026-09-24"          # 마감일 그날 — 창 안이다
    evt = {"kind": "event", "id": "e_late", "subject": SID, "type": "예찰",
           "observed_at": d["observed_at"], "source": "farmer"}
    rows = {r["task"]: r["status"] for r in pva.judge(subj, today=TODAY, evts=[evt], videos=[], reasons=[], notes=[]).result["rows"]}
    assert rows["예찰(트랩 · 육안)"] == "이행", rows
    # 반대편 — 아무 날짜도 못 읽었으면 오늘(9/26)로 잡혀 **마감을 넘긴다**. 그것이 원 결함의 모습이다
    late = {**evt, "observed_at": TODAY.isoformat()}
    rows2 = {r["task"]: r["status"] for r in pva.judge(subj, today=TODAY, evts=[late], videos=[], reasons=[], notes=[]).result["rows"]}
    assert rows2["예찰(트랩 · 육안)"] == "놓침", rows2
