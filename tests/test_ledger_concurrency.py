# -*- coding: utf-8 -*-
# [칸 3 재측정 · 2026-09-20 / 코드 평가 C17] 화면 서버는 ThreadingHTTPServer 다 — 요청마다 스레드가 선다.
#   원장 가드는 대부분 **읽고 → 검사하고 → 덧붙이는** 꼴(재확인 방지 · sha 중복 · 예측 payload 대조 · 개선 항목 중복)이라
#   두 요청이 겹치면 둘 다 "없다"를 보고 둘 다 쓴다. 실사용 형태: **확인 단추 두 번 누르기**(모바일 더블탭 · 느린 응답 뒤 재시도).
#   같은 사건이 원장에 두 줄이면 계획 대 실제가 두 번 세고 되먹임 대조도 두 번 센다 — 판독·산출 오염.
#
# 줄 깨짐(C17 의 원래 서술)은 따로 쟀다: 4프로세스 × 300줄 · 레코드 340B~180KB 에서 깨진 줄 0
#   (2026-09-20 · Linux · O_APPEND). 발행자 PC(Windows)는 여기서 못 잰다 — 그 축은 등재로 남긴다.
from __future__ import annotations

import threading
from datetime import date

import pytest

from ingest import chat, events as ev, media

SID = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]["id"]
TODAY = date(2026, 9, 19)


def _send_one_draft(text: str = "9월 8일에 트랩 확인했다") -> str:
    me, _ = chat.send(SID, text, today=TODAY)
    assert me.get("drafts"), "초안이 없다 — 측정이 성립하지 않는다"
    return me["id"]


def _confirm_twice_at_once(msg_id: str) -> list[str]:
    """두 스레드가 같은 초안을 동시에 확인한다. 돌려주는 것은 거부 사유들."""
    ready, errs = threading.Barrier(2), []

    def go():
        ready.wait()
        try:
            chat.confirm(msg_id, 0)
        except Exception as e:                      # 한쪽이 거부되면 그것이 곧 가드다
            errs.append(f"{type(e).__name__}: {e}")

    ts = [threading.Thread(target=go) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return errs


def test_double_tapped_confirm_writes_one_record_not_two():
    msg_id = _send_one_draft()
    _confirm_twice_at_once(msg_id)
    recs = ev.list_records(SID)
    assert len(recs) == 1, f"같은 초안이 원장에 {len(recs)}줄 — 계획 대 실제·되먹임이 두 번 센다"


def test_the_draft_is_marked_once_so_the_screen_does_not_offer_it_again():
    msg_id = _send_one_draft()
    _confirm_twice_at_once(msg_id)
    m = next(x for x in chat.list_messages(SID) if x["id"] == msg_id)
    assert chat.confirmed_ref(m, 0), "확인 표지가 안 붙었다 — 화면이 같은 초안을 또 내민다"
    assert not [d for d in chat.pending_drafts(SID) if d[0]["id"] == msg_id]


def test_concurrent_outcome_writes_one_row():
    """되먹임 쪽 같은 형태 — 같은 (예측·판정·실제) 를 두 스레드가 동시에 적으면 한 줄이어야 한다."""
    from ingest import feedback as fb
    pred = fb.record_prediction(SID, "risk_alert", "판단함", {"horizon_days": 7, "alerts": []}, "2026-09-01")
    ready, made = threading.Barrier(2), []

    def go():
        ready.wait()
        made.append(fb.add_outcome(pred, "빗나감", "동시 기록", actual_ref="alert:과습 부패"))

    ts = [threading.Thread(target=go) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    rows = [o for o in fb.list_records("feedback.outcome", SID) if o["prediction_id"] == pred["id"]]
    assert len(rows) == 1, f"같은 판정이 {len(rows)}줄 — 개선 항목이 중복으로 붇는다"
    assert made.count(None) == 1, "한쪽은 '이미 있다'로 돌아와야 한다"


def test_every_check_then_append_guard_holds_the_canon_lock():
    """배선 래칫 — 잠금은 정본 하나(`sch.ledger_lock`)이고, 읽고-검사하고-쓰는 가드마다 그 안이어야 한다.
    한 곳만 빠지면 그 통로로 같은 형태가 그대로 샌다(§7.5 지점 축)."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    wanted = {
        "ingest/chat.py": ["def confirm("],
        "ingest/media.py": ["def register("],
        "ingest/feedback.py": ["def add_outcome(", "def propose(", "def record_prediction("],
    }
    for rel, fns in wanted.items():
        src = (root / rel).read_text(encoding="utf-8")
        src = re.sub(r'\"{3}.*?\"{3}', "", src, flags=re.S)          # 독스트링에 설명이 들어 있다(§7.1 4번)
        for fn in fns:
            i = src.index(fn)
            end = src.find("\ndef ", i + 5)
            blk = src[i:end if end != -1 else len(src)]
            assert "sch.ledger_lock" in blk, f"{rel} {fn}: 원장 잠금 정본을 안 쓴다"


def test_sequential_reconfirm_is_still_refused():
    # 반대편 — 동시성과 무관한 재확인 방지(C7)는 그대로여야 한다(막는 것을 검사하면 통과하는 것도 검사한다)
    msg_id = _send_one_draft()
    chat.confirm(msg_id, 0)
    with pytest.raises(Exception):
        chat.confirm(msg_id, 0)
    assert len(ev.list_records(SID)) == 1
