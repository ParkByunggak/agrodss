# -*- coding: utf-8 -*-
# [발행자 화면 판독 2026-09-21] 발행자가 계획 대 실제 답을 읽고 세 가지를 지적했다. 재서 갈랐다 — 하나는 맞고 둘은 아니었다.
#
#   ① "웃거름 1회가 아직 '지금 할 것'에 있다 — 확인을 안 했거나 배선 결함이다"
#      → **배선은 멀쩡하다.** 사유를 넣으면 행이 '사유 기록됨'이 되고 미이행이 4→3 으로 줄어 그 묶음에서 빠진다(아래 검사).
#        곧 그 초안이 아직 원장에 안 들어간 것이다.
#   ② "촬영이 세 상태에 동시에 나오는데 칸 번호가 없어 구분이 안 된다"
#      → **맞다.** 촬영은 칸 1·2·3·4·5 다섯 줄이고 상태가 다 다르다. 칸이 없으면 같은 일이 세 번 밀린 것처럼 읽힌다.
#   ③ "칸 1 촬영이 놓침으로 나온다 — B13 회귀일 수 있다"
#      → **아니다.** 칸 1 촬영은 '기록 없음'(기준점 이전 소급 불가)이고, 놓침인 촬영은 **칸 2** 다.
#
# ②가 ③을 낳았다는 것이 이 회차의 값이다 — 표기가 없어서 **정확한 독자가 없는 회귀를 봤다**.
# 읽는 사람이 구별할 수 없으면 화면이 답을 못 한 것과 같다(G1 표현 층).
from __future__ import annotations

from datetime import date

from ingest import chat, media, parcels
from judge import plan_vs_actual as pva

TODAY = date(2026, 9, 21)
_RAW = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
SUBJ = parcels.enrich_subject(_RAW, parcels.by_id("p001"))


def _rows(reasons=()):
    e = pva.judge(SUBJ, today=TODAY, evts=list(reasons), videos=[], reasons=list(reasons))
    return e, {(r["stage"].split(".", 1)[0], r["task"]): r["status"] for r in e.result["rows"]}


def test_the_same_task_name_appears_in_several_stages_with_different_states():
    """전제 — 이 지적이 성립하는 화면인가. 촬영은 여러 칸에 있고 상태가 다르다."""
    _, by = _rows()
    shots = {k: v for k, v in by.items() if k[1] == "촬영"}
    assert len(shots) >= 4 and len(set(shots.values())) >= 3, shots


def test_stage_one_capture_is_not_a_miss_and_the_missed_one_is_stage_two():
    """③ 판정 — 기준점 이전 촬영은 '기록 없음'이다(B13 회귀 아님). 놓침인 촬영은 칸 2."""
    _, by = _rows()
    assert by[("1", "촬영")] == "기록 없음", by[("1", "촬영")]
    assert by[("2", "촬영")] == "놓침", by[("2", "촬영")]


def test_the_answer_tells_the_stage_so_the_same_name_can_be_told_apart():
    """② 처방 — 답의 모든 묶음이 칸을 말한다. 안 그러면 같은 이름이 세 번 밀린 것처럼 읽힌다."""
    e, _ = _rows()
    text = chat.summarize_envelope(e)
    assert "촬영(칸 2)" in text and "촬영(칸 3)" in text and "촬영(칸 4)" in text, text
    for group in ("지금 할 것", "다음 예정", "놓침"):
        assert group in text
    assert "촬영(~" not in text and "촬영," not in text, "칸 없이 나오는 자리가 남았다"


def test_a_recorded_reason_takes_the_task_out_of_what_to_do_now():
    """① 판정 — 사유가 원장에 들어가면 '지금 할 것'에서 빠진다(배선은 멀쩡하다)."""
    before, _ = _rows()
    assert "웃거름 1회(칸 3)" in chat.summarize_envelope(before)
    reason = {"kind": "decision.noncompliance", "subject": SUBJ["id"], "id": "nc_x", "source": "farmer",
              "planned_task": "웃거름 1회", "reason": "토양검정 상태 기준 — 주지 않음",
              "observed_at": "2026-09-16", "planned_day": "2026-09-16"}
    after, by = _rows([reason])
    assert by[("3", "웃거름 1회")] == "사유 기록됨"
    assert after.result["counts"]["미이행"] == before.result["counts"]["미이행"] - 1
    assert "웃거름 1회(칸 3)" not in chat.summarize_envelope(after)
