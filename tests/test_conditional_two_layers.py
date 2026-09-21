# -*- coding: utf-8 -*-
# [두 층 불일치 2026-09-21] 한 작업에 두 층이 **다른 답**을 하고 있었다.
#
#   계획 대 실제   보식 → '놓침 — 불이행 사유를 묻는다'      (할 일이었는데 안 했다)
#   judge_replant  보식 → '판단 불가(데이터) — 출현 관찰 없음' (할 일인지 아직 모른다)
#
# 발행자가 화면에서 본 '놓침 셋' 중 하나가 이것이다. 원인은 **조건부라는 사실이 격자 작업명의 괄호 표기에만** 있었다는 것 —
# "관수(건조 시)" 는 걸리고 "보식" 은 이름에 표기가 없어 안 걸렸다. 조건이 무엇인지는 결정 등록부가 **이미 알고 있었다**
# (`REPLANT.rule` = "관찰이 있으면 … 없으면 판단 불가(데이터)"). 곧 조건 여부가 문자열에만 실린 **두 벌 진실**이었다.
#
# 처방: 조건을 결정 등록부(`params.conditional_task`)에 선언하고, 계획 대 실제가 **그것을 읽는다**. 두 층이 같은 것을 본다.
# 그리고 조건이 **섰을 때는 놓침이 되살아난다** — 조건부를 넓히면서 그 갈래를 안 두면 막는 것만 보고 통과하는 것을 안 보는
# 상태가 된다(게이트는 양방향).
#
# [§7.5 처방 직후 전수 · 같은 형태 ≠ 같은 급] 고친 자리에서 같은 형태를 여덟 시점 × 세 작업으로 셌더니 셋이 더 걸렸다 —
# 웃거름 1회가 창이 지난 뒤 '놓침' vs '해당 없음'. **그러나 급이 다르다**: 웃거름의 '해당 없음' 은 *"마감을 지났다"*(할 일이었다)이고
# 보식의 '해당 없음' 은 *"조건이 선 적 없다"*(할 일이 아니었다)이다. 두 층이 서로 다른 물음에 답하는 것이지 모순이 아니다.
# 내 탐지기가 '해당 없음' 을 한 말로 읽은 것이 문제였다(탐지 축 오선택 계열). 아래 마지막 검사가 그 구분을 고정한다.
from __future__ import annotations

from datetime import date, timedelta

from ingest import media, parcels
from judge import plan_vs_actual as PVA
from judge import stage_decisions as SD

SID = "p001-jjokpa-2026f"
_RAW = [s for s in media.load_subjects() if s["id"] == SID][0]
SUBJ = parcels.enrich_subject(_RAW, parcels.by_id("p001"))
A = date.fromisoformat(SUBJ["anchor"])
SAW_GAPS = [{"kind": "observation.note", "id": "n1", "text": "군데군데 결주가 보인다",
             "observed_at": (A + timedelta(days=8)).isoformat()}]


def _row(today: date, notes=()) -> dict:
    env = PVA.judge(SUBJ, today=today, evts=[], videos=[], reasons=[], notes=list(notes))
    return env, next(r for r in env.result["rows"] if r["task"] == "보식")


def test_without_the_observation_the_row_says_what_is_missing_not_that_nothing_was_due():
    """[발행자 계약 지적 2026-09-21] 첫 판은 *"할 일이 없었던 것"* 이라고 적었다 — **아는 것보다 더 단정했다.**

    원장에 관찰이 없다는 것은 *조건이 없었다*는 뜻이 아니라 *아무도 안 적었다*는 뜻일 수 있다. 결주가 실제로 있었는데
    안 본 경우를 그 문장이 **가린다**. I-1 §2-6 의 '해당 없음' 은 "아무리 채워도 안 바뀐다" 인데 이쪽은 **채우면 바뀐다** —
    곧 계약상 '판단 불가(데이터)' 자리다. 그래서 행은 **없는 것이 관찰이라는 사실**과 **넣으면 바뀐다는 것**을 말해야 한다.
    """
    t = A + timedelta(days=27)
    env, row = _row(t)
    assert row["status"] == "조건부", row
    assert "결주" in row["evidence"] and "원장에 없다" in row["evidence"]          # 없는 것이 무엇인지 말한다
    assert "답이 바뀐다" in row["evidence"]                                       # 채우면 바뀐다고 말한다(판단 불가(데이터)의 성격)
    assert "할 일이 없었" not in row["evidence"], "아는 것보다 더 단정한다 — 관찰이 없는 것과 조건이 없던 것은 다르다"
    assert not any(a["task"] == "보식" for a in env.result["ask_reason"])          # '왜 안 했나'는 묻지 않는다
    assert SD.judge_replant(SUBJ, t).kind in ("해당 없음", "판단 불가(데이터)")     # 두 층이 어긋나지 않는다


def test_when_the_condition_did_stand_the_miss_comes_back():
    """[게이트는 양방향] 결주를 봤는데 안 심었으면 그것은 **진짜 놓침**이다 — 조건부로 덮어 버리면 신호가 사라진다."""
    t = A + timedelta(days=27)
    env, row = _row(t, SAW_GAPS)
    assert row["status"] == "놓침", row
    assert any(a["task"] == "보식" for a in env.result["ask_reason"])
    assert SD.judge_replant(SUBJ, A + timedelta(days=14), observations=SAW_GAPS).kind == "판단함"   # 창 안이면 결정도 권고한다


def test_the_condition_is_read_from_the_decision_registry_not_from_the_task_name():
    """두 벌 금지 — '보식' 이라는 이름에는 조건 표기가 없다. 조건은 결정 등록부가 말한다."""
    assert not PVA._conditional("보식")                                        # 이름만 보면 조건부가 아니다
    assert SD.REPLANT.params["conditional_task"] == "보식"
    assert PVA.conditional_of("보식", [], since=SUBJ["anchor"])[0] is False     # 등록부를 읽어 조건부로 본다
    assert PVA.conditional_of("보식", SAW_GAPS, since=SUBJ["anchor"])[0] is True
    assert PVA.conditional_of("수확(뽑기) · 다듬기 · 세척", []) is None          # 조건부가 아닌 작업은 그대로
    name_only = PVA.conditional_of("관수(건조 시)", [])
    assert name_only == (False, PVA.conditional_of("관수(건조 시)", SAW_GAPS)[1])  # 이름 표기는 관찰과 무관하게 언제나 조건부


def test_the_observations_reach_the_gate_from_the_screen_path():
    """[§7.5 관문의 입력] 관문을 세워도 호출부가 값을 안 넘기면 아무것도 안 거른다 — 배선을 본다(게이트 지난 원장에서 온다)."""
    src = (__import__("pathlib").Path(__file__).resolve().parent.parent / "judge" / "run.py").read_text(encoding="utf-8")
    block = src[src.index("envs = ["):src.index("envs += stage_decisions")]      # 거리가 아니라 구조로 자른다
    assert "plan_vs_actual.judge(" in block and "notes=" in block
    assert 'recs["ledger"]' in block and '"observation.note"' in block           # 원장을 직접 읽지 않고 게이트를 지난 것에서


def test_a_window_that_passed_is_not_the_same_as_a_condition_that_never_stood():
    """[같은 형태 ≠ 같은 급] 전수가 셋을 더 짚었지만 그것은 모순이 아니다 — '해당 없음' 이 두 가지 뜻이기 때문이다.

    웃거름 1회: 창이 지나 '해당 없음' 인데 계획 대 실제는 '놓침' — **할 일이었고 안 했다**(둘 다 맞다, 물음이 다르다).
    보식:       조건이 선 적 없어 '해당 없음' 이고 계획 대 실제도 '조건부' — **할 일이 아니었다**.
    """
    t = A + timedelta(days=40)
    env, replant_row = _row(t)
    top = next(r for r in env.result["rows"] if r["task"] == "웃거름 1회")
    e_top, e_rep = SD.judge_top_dressing(SUBJ, "top_dressing_1", t), SD.judge_replant(SUBJ, t)
    assert e_top.kind == e_rep.kind == "해당 없음"                               # 겉보기는 같다
    assert "마감" in e_top.result["why"] and "창" in e_rep.result["why"]          # 사유가 갈린다
    assert top["status"] == "놓침" and replant_row["status"] == "조건부"          # 그래서 계획 층의 답도 갈린다
    assert any(a["task"] == "웃거름 1회" for a in env.result["ask_reason"])       # 웃거름은 사유를 묻는다
    assert not any(a["task"] == "보식" for a in env.result["ask_reason"])         # 보식은 묻지 않는다
