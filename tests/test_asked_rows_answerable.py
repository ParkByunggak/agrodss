# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-18 W-48 · W-47] 할 일 답의 「놓침 — 사유를 묻는다」 가 묻는 줄 둘레의 두 결함.
#     W-48  용도가 자가(시험 재배)인데 같은 날 두 답이 갈렸다 — 「출하 언제 해요」 는 「이번엔 할 일이 아닙니다 … 출하·저장 판단이 없습니다」 인데
#           「오늘 뭐 해야 하나」 는 10-28 부터 날마다 「놓침 — 사유를 묻는다: … 출하 또는 단기 저장」 · 같은 거짓 놓침이 되먹임(evolve)의 놓친 목록에도 들어갔다.
#           문이 출하 판단 한 층에만 있었다(계획 줄에 같은 문이 없다). 창 안(10-24~27)의 「지금 할 것」 은 **남긴다** — 그 줄이 농가에게 가는 유일한 단기 저장 안내이고
#           (쪽파는 수일 안 · 격자 출처) 자가 작기에 그 안내가 필요 없다는 말은 어디에도 없다(D-8 은 몰 납품만 말한다 — 발행자 몫 W-49)
#     W-47  묻는 줄 중 채팅으로 답할 길이 없는 줄 — 촬영 넷(「촬영 못 했다」 · 「사진 못 찍었다」 → 본 것) · 잔사 정리(「잔사 정리 못 했다」 → 본 것 ·
#           「잔사 못 걷었다」 는 정리 이유가 됐지만 그 줄에 안 붙었다) · 「출하 못 했다」(납품 이유 — 그 줄에 안 붙었다) · 일 이름 없는 답(「비 때문에 못 했다」 → 본 것,
#           무엇을 더 적으면 되는지 말이 없다). 판정은 납품 · 정리 기록으로 그 줄을 세는데 잇는 쪽은 제 표를 따로 썼다(두 벌)
# 고정하는 것(양방향):
#   ① 출하 판단이 없는 작기의 문은 하나(plan_vs_actual.not_shipping) — 마감 뒤 출하 줄은 놓침도 사유 물음도 아니다 · 창 안은 그대로 할 일(저장 안내) ·
#      파는 말이 있으면 열어 둔다 · 한 기록은 한 일로 센다
#   ② 묻는 줄마다 「비 때문에 {그 줄 이름} 못 했다」 가 그 줄의 못 한 이유로 붙는다(답이 말하는 약속을 잰다) · 붙을 줄은 계획이 아직 할 일로 보는 줄만
#   ③ 촬영 · 잔사 · 일 이름 없는 말 — 읽는 것과 안 읽는 것을 둘 다 본다(본 것 · 한 일을 잃지 않는다)
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone

import pytest

from ingest import chat, events as ev, media, parcels, subjects
from judge import evolve, plan_vs_actual as PVA, run as judge_run, stage_decisions as SD
from judge.envelope import Envelope
from tests.test_brand_home import srv  # noqa: F401 — 격리 화면 서버(빈 포트 · 끝나면 내린다)

SID = "p001-jjokpa-2026f"
PID = "p001"
ANCHOR = date(2026, 8, 25)
SHIP_ROW = "출하 또는 단기 저장"
RESIDUE_ROW = "잔사 정리 · 후작 준비"


def _d(n: int) -> date:
    return date.fromordinal(ANCHOR.toordinal() + n)


DAYS = (_d(64), _d(71), _d(91))           # 10-28 · 11-04 · 11-24 — 출하 마감 다음 날 · 수확 마감 다음 날 · 달력 끝 다음 날


def _subject(**over) -> dict:
    raw = next(s for s in media.load_subjects() if s["id"] == SID)
    return {**parcels.enrich_subject(raw, parcels.by_id(PID)), **over}


def _sell() -> None:
    parcels.set_fields(PID, use="판매", mall_supply=True, overwrite=True)        # 파는 작기 — 출하 판단이 서는 쪽(반대 방향의 대조군)


def _pva(today: date) -> Envelope:
    return next(x for x in judge_run.judgments_for(SID, today=today) if x.decision_id == "plan_vs_actual")


def _row(today: date, task: str) -> dict:
    return next(r for r in _pva(today).result["rows"] if r["task"] == task)


def _say(text: str, today: date) -> dict:
    m, _r = chat.send(SID, text, today=today, now=datetime(today.year, today.month, today.day, 9, tzinfo=timezone.utc))
    return m


def _put(text: str, today: date) -> dict:
    m = _say(text, today)
    for i, d in enumerate(m["drafts"]):
        if d["kind"] != "question":
            chat.confirm(m["id"], i, day=today.isoformat() if d.get("needs") else None)
    return m


def _ask(q: str, today: date) -> str:
    return chat.answer(subjects.by_id(SID), q, today)


def _kinds(text: str, today: date = DAYS[-1]) -> list[tuple]:
    return [(d["kind"], d.get("task_type") or d.get("type"), d.get("why_key")) for d in chat._classify(text, today)]


# ── ① W-48 출하 판단이 없는 작기 — 문은 하나 ──────────────────────────────────────────────────────
@pytest.mark.parametrize("use,mall,closed", [
    ("시험 재배(자가)", False, True), ("시험 재배(자가)", True, True), ("자가 소비", None, True), ("종구 생산", True, True),   # 옛 문 그대로(D-8 · 종구)
    ("", False, True),                                                                                                    # 몰 납품을 안 한다 — 그 말로 닫는다
    ("판매", True, False), ("판매", None, False), ("", None, False), ("", True, False),                                      # 출하 판단이 서는 쪽
    ("자가 판매", True, False), ("시험 판매", None, False), ("몰 납품 시험", True, False), ("자가 직판", None, False),        # [넓힐 때 본 경계] 파는 말이 있으면 열어 둔다
    ("판매", False, False), ("몰 납품", False, False), ("직거래 판매", False, False),        # [검토] 용도 글자가 씨앗의 몰 납품 「아니오」 를 이긴다(그 값은 바꿀 길이 없다)
    ("시험 재배(판매 안 함)", None, True), ("자가 소비(출하 안 함)", None, True), ("자가용(판매하지 않음)", None, True),   # [검토] 부정된 파는 말은 파는 말이 아니다
    ("종구 판매", None, True), ("종구 생산 · 판매", True, True),                                  # [검토] 종구는 닫는다(그 용도의 출하 기준이 달력에 없다)
    # [검토 둘째] 부정된 파는 말의 다른 꼴(앞의 비 · 미 · 뒤의 조사 · 용 · 계획 + 부정) · 자가와 함께 다음 작기를 말한 파는 말(D-8 의 그 말) · 몰 납품 값이 비어도 닫는다
    ("시험 재배(비판매)", False, True), ("판매는 안 함", None, True), ("판매를 안 함", None, True), ("시험 재배(판매 X)", None, True),
    ("자가 소비 · 판매 계획 없음", None, True), ("자가(판매용 아님)", None, True), ("판매 불가", None, True), ("미판매", None, True),
    ("시험 재배(자가), 몰 납품은 봄 작기부터", False, True), ("판매 안 함", None, True), ("판매 안 함", True, True),
    ("판매도 안 함", None, True), ("판매용 아님", None, True), ("직판 계획 없음", None, True), ("시험 재배, 판매는 하지 않음", False, True), ("자가 소비, 납품 X", None, True),
    ("판매는 10월부터", None, False), ("판매(직거래)", False, False), ("판매 · 자가", None, False), ("판매가 주", False, False),   # 반대 방향 — 파는 말
    ("판매용", None, False), ("판매 예정", None, False), ("출하용 시험 재배", None, False), ("판매 안정이 목표", None, False),
])
def test_the_shipping_gate_is_one_and_the_shipping_decision_reads_it(use, mall, closed):
    """출하 판단(해당 없음)과 계획 대 실제의 출하 줄(마감 뒤 놓침이 아니다)이 **같은 문**을 쓴다 — 두 층이 같은 답 · 양방향(10-28 · 마감 다음 날)."""
    s = _subject(use=use, mall_supply=mall)
    assert (PVA.not_shipping(s) is not None) is closed, PVA.not_shipping(s)
    so = SD.judge_ship_or_store(s, DAYS[0])
    assert (so.kind == "해당 없음") is closed, (so.kind, so.result)
    e = PVA.judge(s, today=DAYS[0])
    row = next((r for r in e.result["rows"] if r["task"] == SHIP_ROW), None)
    if row is None:                                                                        # 종구 — 그 용도의 기준이 없는 칸이라 계획표에 줄 자체가 없다(use_gap · 앞 회차)
        assert "종구" in use and closed
        return
    assert row["status"] == ("기록 없음" if closed else "놓침"), row
    assert any(a["task"] == SHIP_ROW for a in e.result["ask_reason"]) is not closed
    if closed:
        assert so.result["summary"] == f"{PVA.not_shipping(s)} 출하 판단이 없습니다" and "D-8" in so.result["why"]      # 마감 다음 날 — 단기 저장 꼬리 없음
        assert PVA.not_shipping(s) in row["evidence"] and "출하 판단이 없습니다" in row["evidence"]


def _ship(today: date) -> Envelope:
    return next(x for x in judge_run.judgments_for(SID, today=today) if x.decision_id == "ship_or_store")


KEPT_TAIL = "단기 저장은 할 일에 그대로 있습니다(~10-27)"


@pytest.mark.parametrize("today,use,tail", [(_d(35), None, True), (_d(63), None, True), (_d(64), None, False), (_d(35), "종구 생산", False)])
def test_the_shipping_answer_does_not_deny_the_storage_cue_the_plan_keeps(today, use, tail):
    """[검토 2026-10-18] 출하 답이 「출하·저장 판단이 없습니다」 라 하는 같은 날 할 일 답은 「출하 또는 단기 저장(~10-27)」 을 지금 할 것으로 냈다. 없는 것은 **출하 판단**이고,
    계획에 그 줄이 할 일로 있는 동안(마감 10-27 까지)은 그 사실을 말한다 · 마감 뒤 · 종구(용도 문으로 그 칸 할 일이 없다)는 말하지 않는다.
    [검토 둘째] 그동안 머리는 「이번엔 할 일이 아닙니다」 가 아니다(본문이 저장은 할 일이라 한다 — 한 답 안의 두 말) · 실제 배선(judge.run)으로 잰다"""
    from frontend import words
    if use:
        parcels.set_fields(PID, use=use, overwrite=True)
    so = _ship(today)
    assert so.kind == "해당 없음" and "저장 판단" not in so.result["summary"]
    assert (KEPT_TAIL in so.result["summary"]) is tail, so.result["summary"]
    assert words.head(so.kind, so.result) == ("이번엔 출하 판단이 없습니다" if tail else words.said("해당 없음")), so.result
    a = _ask("저장할까", today)
    assert a.startswith(f"[{words.head(so.kind, so.result)}]") and (KEPT_TAIL in a) is tail, a


@pytest.mark.parametrize("day,said,status,tail", [
    (_d(60), "오늘 쪽파 거둬서 저온 창고에 저장했다", "이행", False), (_d(60), "바로 먹을 거라 저장은 안 하기로 했다", "사유 기록됨", False),
    (_d(56), "농사 끝났어요", "종료 뒤", False),
    (_d(61), "저장 못 했다", "미이행", True),                   # 반대 방향 — 못 함(아직 할 일)은 그 줄을 마감까지 닫지 않는다 · 꼬리도 남는다
])
def test_the_storage_tail_reads_the_plan_row_itself(day, said, status, tail):
    """[검토 2026-10-18 둘째] 첫 판은 날짜(마감까지)만 봐서 거둬 저장한 뒤 · 안 하기로 한 뒤 · 작기를 닫은 뒤에도 「할 일에 그대로 있습니다」 였다 — 같은 화면의 계획 표는
    이행이라 말했다(W-48 이 걷으려던 두 층의 엇갈림). 꼬리는 그 줄 **자신**의 상태(예정 · 미이행)를 읽는다(10-25)."""
    _put(said, day)
    assert _row(_d(61), SHIP_ROW)["status"] == status
    assert (KEPT_TAIL in _ship(_d(61)).result["summary"]) is tail, _ship(_d(61)).result
    assert (KEPT_TAIL in _ask("저장할까", _d(61))) is tail


def test_an_empty_use_does_not_claim_self_use():
    """[ⓐ] 용도가 비었는데 몰 납품만 안 한다고 적혀 있으면 전에는 「이번 작기는 자가 용도라」 로 단정했다 — 근거(몰 납품 안 함)를 말한다."""
    so = SD.judge_ship_or_store(_subject(use="", mall_supply=False), DAYS[0])
    assert so.kind == "해당 없음" and "자가" not in so.result["summary"] and "몰 납품" in so.result["summary"], so.result


@pytest.mark.parametrize("today", DAYS)
def test_a_self_use_season_does_not_count_or_ask_the_shipping_row_after_its_deadline(today):
    """W-48 — 씨앗 밭(시험 재배(자가))에서 마감(10-27)이 지난 출하 줄은 놓침이 아니고 사유를 묻지 않는다(10-28 · 11-04 · 11-24) · 되먹임의 놓친 목록에도 안 들어간다."""
    e = _pva(today)
    assert _row(today, SHIP_ROW)["status"] == "기록 없음"
    assert all(a["task"] != SHIP_ROW for a in e.result["ask_reason"])
    assert sum(e.result["counts"].values()) == len(e.result["rows"])
    assert SHIP_ROW not in _ask("오늘 뭐 해야 하나", today)
    assert SHIP_ROW not in evolve.payload_of(e)["missed"]


@pytest.mark.parametrize("today,status,said", [(_d(40), "예정", "다음 예정"), (_d(60), "미이행", "지금 할 것"), (_d(63), "미이행", "지금 할 것")])
def test_a_self_use_season_keeps_the_storage_cue_inside_its_window(today, status, said):
    """반대 방향 — 창 안(10-04 · 10-24 · 10-27)에서는 그대로 할 일이다. 그 줄이 농가에게 가는 **유일한 단기 저장 안내**다(쪽파는 수일 안 · 마감은 작업일 + 3) —
    자가 작기에 그 안내가 필요 없다는 말은 어디에도 없다(D-8 은 몰 납품만 말한다 · 발행자 몫 W-49). 문은 근거가 확실한 쪽(출하가 없다 → 놓침이 아니다)만 닫는다."""
    assert _row(today, SHIP_ROW)["status"] == status
    a = _ask("오늘 뭐 해야 하나", today)
    assert SHIP_ROW in a and a.index(said) < a.index(SHIP_ROW), a


@pytest.mark.parametrize("today", (_d(60), _d(64)))
def test_a_selling_season_still_has_the_shipping_row(today):
    """반대 방향 — 파는 작기(판매 · 몰 납품)면 출하 줄은 그대로 할 일이다(10-24 지금 할 것 · 10-28 놓침 — 사유를 묻는다)."""
    _sell()
    assert _row(today, SHIP_ROW)["status"] == ("미이행" if today < _d(64) else "놓침")
    assert SHIP_ROW in _ask("오늘 뭐 해야 하나", today)


def test_a_logged_storage_still_counts_as_done_in_a_self_use_season():
    """문은 할 일을 지우지 한 일을 지우지 않는다 — 자가 작기에도 저장을 적으면 그 줄은 이행(한 일은 한 일로 센다)."""
    _put("오늘 쪽파를 창고에 저장했다", _d(61))
    r = _row(_d(64), SHIP_ROW)
    assert r["status"] == "이행" and "저장" in r["evidence"], r


def test_the_judge_screen_shows_the_row_and_its_reason(srv, monkeypatch):
    """/judge 표(10-28) — 그 줄은 보이고(조용한 빈칸 금지) 「기록 없음」 과 까닭 · 무엇을 적으면 한 일로 세는지를 싣는다 · 창을 넘긴 작업 줄에는 없다."""
    import urllib.request
    monkeypatch.setenv("AGRODSS_TODAY", DAYS[0].isoformat())
    html = urllib.request.urlopen(f"http://127.0.0.1:{srv}/judge?s={SID}").read().decode("utf-8")
    assert "출하 판단이 없습니다 — 마감이 지나도 놓침으로 세지 않고" in html and "그 날짜로 적어 주시면 한 일로 셉니다" in html
    late = html[html.index("창을 넘긴 작업"):].split("</p>")[0]
    assert SHIP_ROW not in late and "예찰" in late, late


@pytest.mark.parametrize("use,mall,shown", [(None, None, False), ("판매", None, True), ("텃밭", None, False), ("텃밭", True, True)])
def test_the_walk_tool_can_still_measure_the_shipping_row(monkeypatch, use, mall, shown):
    """[자기 도구] 문이 서자 씨앗 밭(자가 · 몰 납품 아니오)에서 마감 지난 출하 줄이 안 보여 W-05(출하 마감 63 · 수확 마감 70)를 씨앗 그대로는 잴 수 없다 —
    파는 용도(--use 판매)면 다시 보인다(용도 글자가 이긴다) · 파는 말도 자가 말도 없는 용도(텃밭)는 몰 납품 여부가 가른다 — --mall 이 그 값을 격리 사본에 넣는다."""
    from scripts import answer_walk, verify_claims
    monkeypatch.setattr(verify_claims, "isolate", lambda: None)                       # conftest 가 이미 격리했다
    monkeypatch.setenv("AGRODSS_TODAY", _d(64).isoformat())
    rows = answer_walk.walk([_d(64)], use=use, asks=("오늘 뭐 해야 하나",), mall=mall)
    assert (SHIP_ROW in rows[-1]["answer"]) is shown, rows[-1]["answer"]
    head = answer_walk.render(rows).split("=====")[1]                                      # [검토] 넣은 조건이 머리에 — 조건을 떼면 다른 측정이 같아 보인다
    assert ("몰 납품 예" in head) is (mall is True) and ("몰 납품" in head) is (mall is not None), head
    with pytest.raises(SystemExit):                                                        # 고르는 값은 yes · no 둘(argparse 가 막는다)
        answer_walk.main(["--mall", "maybe"])


@pytest.mark.parametrize("flag,shown", [("yes", True), ("no", False)])
def test_the_walk_tool_command_line_maps_the_mall_flag(monkeypatch, capsys, flag, shown):
    """[검토 2026-10-18] 명령줄 그대로 — 「--mall yes」 가 몰 납품 예로 들어가는지(뒤집히거나 버려지면 다른 차림을 잰다 · 자기 도구)."""
    from scripts import answer_walk, verify_claims
    monkeypatch.setattr(verify_claims, "isolate", lambda: None)
    monkeypatch.setenv("AGRODSS_TODAY", _d(64).isoformat())
    parcels.set_fields(PID, mall_supply=not shown, overwrite=True)           # [검토 둘째] 씨앗이 이미 「아니오」 라 --mall no 를 버려도 같았다 — 반대 값에서 시작한다
    assert answer_walk.main(["--use", "텃밭", "--mall", flag, "--ask", "오늘 뭐 해야 하나", _d(64).isoformat()]) == 0
    assert parcels.by_id(PID).get("mall_supply") is shown
    out = capsys.readouterr().out
    assert (SHIP_ROW in out) is shown and f"몰 납품 {'예' if shown else '아니오'}" in out, out


def test_the_gate_is_wired_where_both_layers_read_it():
    """배선 — 출하 판단과 계획 대 실제가 그 문을 **부르고**, 문은 용도와 몰 납품을 읽는다. 출하 판단에 제 사본(용도 글자 검사)이 다시 생기면 붉다.
    [검토 2026-10-18] 호출형까지만 본다(인자 표현식 · 조건 줄 전체를 박으면 같은 뜻의 리팩터에 깨진다 — 래칫 규율) · 뜻은 위 양방향 검사들이 진다."""
    import re
    so_src = inspect.getsource(SD.judge_ship_or_store)
    assert re.search(r"\bplan_vs_actual\.not_shipping\(", so_src) and "SELF_USE_WORDS" not in so_src
    j = inspect.getsource(PVA.judge)
    assert re.search(r"\bnot_shipping\(", j) and "SHIP_TASK_KEY" in j
    gate = inspect.getsource(PVA.not_shipping)
    # [검토 2026-10-18 둘째] 호출형 · 읽는 값만 본다 — 글자 순서 · 「"종구" in」 리터럴을 박으면 같은 뜻의 리팩터에 깨진다(래칫 규율). 차례(종구 → 파는 말 → 자가 · 시험 →
    # 몰 납품)는 위 양방향 매개변수 검사가 진다(그 차례를 바꾼 주입이 거기서 붉다)
    assert all(re.search(p, gate) for p in (r"(?<![.\w])sold\(", r"\bSELF_USE_WORDS\b", r'\.get\(\s*"mall_supply"', r'\.get\(\s*"use"')), gate
    assert SD.SELF_USE_WORDS is PVA.SELF_USE_WORDS                                           # 같은 이름은 같은 것
    assert "sale_negated_at(" in inspect.getsource(PVA.sold)                                 # [검토 둘째] 파는 말의 부정은 한 정본 — 채팅 용도 선언도 그것을 읽는다(아래)


def test_the_storage_tail_the_head_and_the_chat_declaration_are_wired():
    """[검토 2026-10-18 둘째] 배선 — ① 출하 답의 저장 꼬리는 계획 대 실제 봉투의 그 줄을 읽고 그 봉투는 judge.run 이 넘긴다(None 을 넘기면 꼬리가 영영 안 선다 —
    관문의 입력) ② 머리를 내는 자리 셋(채팅 답 · 대화 옆 카드 · /judge)이 같은 하나(words.head)를 부른다(한 곳만 고치면 같은 판정이 화면마다 다른 머리)
    ③ 채팅 용도 선언이 출하 문과 같은 부정 정본을 읽는다(부정을 떼고 「판매」 로 넣으면 문은 서 있고 그 입력이 샌다)."""
    import re
    from pathlib import Path
    from tests.test_gate_inputs import _all_judgments_body, _call
    m = re.search(r"\bplan_env\s*=\s*([\w\[\]]+)", _call(_all_judgments_body(), "stage_decisions.judge_all("))
    assert m and m.group(1) != "None", m
    assert re.search(r"\bjudge_ship_or_store\([^)]*\bplan_env\b", inspect.getsource(SD.judge_all))
    so = inspect.getsource(SD.judge_ship_or_store)
    assert "_ship_row_to_do(" in so and '"head"' in so
    root = Path(__file__).resolve().parent.parent
    for rel, fn in (("ingest/chat.py", "def summarize_envelope("), ("frontend/chat_pages.py", "def _env_card("), ("frontend/serve.py", "def _render_env(")):
        src = (root / rel).read_text(encoding="utf-8")
        body = src[src.index(fn):src.index("\ndef ", src.index(fn) + 10)]
        assert "words.head(" in body and not re.search(r"words\.said\(\s*e[\.\[]", body), (rel, fn)
    decl = inspect.getsource(parcels.use_declared) + inspect.getsource(parcels._sale_negated)
    assert "_sale_negated(" in inspect.getsource(parcels.use_declared) and "plan_vs_actual.sale_negated_at(" in decl
    assert "sale_declined(" in inspect.getsource(chat._classify)


# ── ② W-47 묻는 줄마다 채팅으로 답할 수 있다 — 답이 말하는 약속을 잰다 ───────────────────────────────
@pytest.mark.parametrize("today", DAYS)
def test_every_asked_row_takes_a_reason_from_chat(today):
    """할 일 답이 사유를 묻는 줄마다 「비 때문에 {그 줄 이름} 못 했다」 를 보내면 **그 줄**의 못 한 이유로 붙는다.
    같은 이름의 줄이 여럿이면(촬영 넷) 날을 말하지 않은 말은 가장 늦게 열린 줄에 붙는다(지금 창 안의 촬영일 수 있다 — 10-28 의 칸 5) — 그 날을 말하면 그 줄에 붙는다."""
    # [검토 2026-10-18] 첫 판은 같은 이름의 줄에 **답에 없는 날짜**를 붙여 보냈다(답은 「촬영(2단계)」 만 보인다) — 그래서 단계를 안 읽어 칸 5 에 붙는 결함을 못 봤다.
    # 이제 **답에 보인 그대로**(답 문장에서 잘라) 보낸다
    ask = _pva(today).result["ask_reason"]
    a_text = _ask("오늘 뭐 해야 하나", today)
    items = a_text.split("사유를 묻는다: ", 1)[1].split(" — ", 1)[0].split(", ")
    assert ask and len(items) == len(ask), (items, ask)
    for item, a in zip(items, ask):
        said = f"비 때문에 {item} 못 했다"
        d = chat._attach_plan(SID, chat._classify(said, today), today)[0]
        assert (d["kind"], d["planned_task"], d["planned_day"]) == ("decision.noncompliance", a["task"], a["work_date"]), (said, d)


@pytest.mark.parametrize("today", (_d(56), _d(64)))
def test_a_stage_said_picks_that_capture_row_not_the_open_one(today):
    """10-20 · 10-28 — 칸 5 촬영 창이 열려 있어도 「촬영(2단계) 못 했다」 · 「2단계 촬영 못 했다」 는 칸 2 줄에 붙는다(전에는 가장 늦게 열린 칸 5 에 붙어
    묻던 칸 2 는 계속 묻고 칸 5 에 남의 이유가 섰다) · 단계를 안 말하면 지금 창의 줄(칸 5 — 오늘 찍을 것)."""
    two = next(r for r in _pva(today).result["rows"] if r["task"] == "촬영" and r["stage"].startswith("2."))
    for said in ("비 때문에 촬영(2단계) 못 했다", "2단계 촬영 못 했다", "칸 2 사진 못 찍었다"):
        d = chat._attach_plan(SID, chat._classify(said, today), today)[0]
        assert (d["planned_task"], d["planned_day"]) == ("촬영", two["work_date"]), (said, d)
    d = chat._attach_plan(SID, chat._classify("사진 못 찍었다", today), today)[0]
    assert d["planned_day"] == "2026-10-14", d


@pytest.mark.parametrize("said,task", [("비 때문에 웃거름 1회 못 줬다", "웃거름 1회"), ("웃거름 2회 못 줬다", "웃거름 2회(필요 시)")])
def test_the_row_name_words_pick_among_rows_of_one_type(said, task):
    """[검토 2026-10-18] 같은 종류(시비)의 줄이 여럿이면 말 안의 줄 이름 낱말(1회 · 2회)이 가른다 — 전에는 「웃거름 2회 못 줬다」 도 1회 줄을 닫았다."""
    d = chat._attach_plan(SID, chat._classify(said, _d(64)), _d(64))[0]
    assert d["planned_task"] == task, d


def test_a_reason_naming_a_closed_row_does_not_close_another_row():
    """「비 때문에 밑거름 못 줬다」 — 밑거름 줄은 이미 이행(심은 날)이다. 같은 종류(시비)의 열린 줄(웃거름 1회)에 붙이지 않는다(전에는 그 물음을 닫았다)."""
    d = chat._attach_plan(SID, chat._classify("비 때문에 밑거름 못 줬다", _d(64)), _d(64))[0]
    assert d["planned_task"] == "시비" and "미완 작업이 없다" in d["why"], d


PARTS = [("세척", "수확(뽑기) · 다듬기 · 세척"), ("다듬기", "수확(뽑기) · 다듬기 · 세척"), ("뽑기", "수확(뽑기) · 다듬기 · 세척"),
         ("선별", "종구 선별 · 소독"), ("육안 확인", "예찰(트랩 · 육안)"), ("트랩", "예찰(트랩 · 육안)"), ("후작 준비", RESIDUE_ROW),
         ("배수 관리", "배수 관리(고랑 정비)"), ("고랑 정비", "배수 관리(고랑 정비)"), ("웃거름 1회", "웃거름 1회"),
         ("수확(뽑기) · 다듬기 · 세척(5단계)", "수확(뽑기) · 다듬기 · 세척"), ("종구 선별 · 소독(1단계)", "종구 선별 · 소독"),
         ("다듬기(5단계)", "수확(뽑기) · 다듬기 · 세척"), ("선별(1단계)", "종구 선별 · 소독")]      # [검토 둘째] 작업 어휘 없는 조각 + 단계(이름 조각 길의 단계 조각)


@pytest.mark.parametrize("part,task", PARTS)
def test_a_part_of_an_asked_row_name_is_that_row(part, task):
    """[검토 2026-10-18] 「일 이름과 함께」 라는 약속 — 농가는 답에 보인 이름의 **조각**을 쓴다(「세척 못 했다」 · 「선별 못 했다」 · 「후작 준비 못 했다」).
    작업 어휘가 아닌 조각도 열린 줄 하나의 이름이면 그 줄의 못 한 이유다(11-24 · 그 줄들이 다 사유를 묻는 날) · 답에 보인 그대로(단계 붙은 이름)도."""
    d = chat._attach_plan(SID, chat._classify(f"비 때문에 {part} 못 했다", DAYS[-1]), DAYS[-1])[0]
    assert (d["kind"], d.get("planned_task")) == ("decision.noncompliance", task), d
    assert d.get("deferred") is True and chat.plain_why(d) == "아직 못 한 일과 그 이유로 읽었습니다"


@pytest.mark.parametrize("said", ["세척이 충분하지 않다", "사진 정리 못 했다", "정리 못 했다", "준비 못 했다", "선별이 안 된다", "비 때문에 관리 못 했다",
                                  "10월 1일에 비 때문에 세척 못 했다"])      # [검토 둘째] 흔한 낱말 「관리」 · 말한 날이 그 줄 창(10-14~) 앞
def test_a_name_part_without_a_negated_doing_or_too_common_is_not_a_row(said):
    """반대 방향 — 이름 조각 바로 뒤가 하다의 부정이 아니면(「충분하지 않다」 · 「안 된다」 — 상태) · 흔한 낱말(정리 · 준비)뿐이면 줄에 잇지 않는다(「사진 정리」 가 잔사 줄로 가지 않게)."""
    d = chat._attach_plan(SID, chat._classify(said, DAYS[-1]), DAYS[-1])[0]
    assert d["kind"] == "observation.note", d


def test_a_name_part_shared_by_two_open_rows_is_not_guessed(monkeypatch):
    """조각이 서로 다른 열린 줄 둘에 걸리면 고르지 않는다(되묻기) — 「트랩」 이 예찰 줄과 다른 줄에 다 있으면."""
    rows = [{"task": "예찰(트랩 · 육안)", "kind": "plan.task", "work_date": "2026-09-08", "status": "놓침", "match_from": "2026-09-05", "match_to": "2026-09-24"},
            {"task": "트랩 교체", "kind": "plan.task", "work_date": "2026-09-10", "status": "놓침", "match_from": "2026-09-07", "match_to": "2026-09-20"}]
    monkeypatch.setattr(judge_run, "judgments_for", lambda *a, **k: _fake(rows))
    assert chat._plan_row_for(SID, "", DAYS[-1], said="비 때문에 트랩 못 했다", by_name=True) is None
    assert chat._plan_row_for(SID, "", DAYS[-1], said="비 때문에 육안 못 했다", by_name=True)["task"] == "예찰(트랩 · 육안)"


@pytest.mark.parametrize("day,said,task", [
    (_d(64), "쪽파는 원래 세척 안 해요", "수확(뽑기) · 다듬기 · 세척"), (_d(64), "세척은 안 했다", "수확(뽑기) · 다듬기 · 세척"),
    (_d(64), "요즘은 다들 세척 안 한다", "수확(뽑기) · 다듬기 · 세척"),
    (_d(71), "올해는 후작은 안 한다", RESIDUE_ROW), (_d(71), "후작 안 함", RESIDUE_ROW), (_d(71), "후작 준비는 안 한다", RESIDUE_ROW),
])
def test_a_plain_no_on_one_part_of_a_row_does_not_close_the_row(day, said, task):
    """[검토 2026-10-18 둘째] 이름 조각 하나에 그냥 「안 하다」 는 줄 전부를 닫았다 — 「쪽파는 원래 세척 안 해요」 가 수확 · 다듬기 · 세척 줄을(거둔 기록은 없는데) ·
    「올해는 후작은 안 한다」 가 잔사 정리 줄을. 버릇 · 남 얘기 · 줄의 한 조각이다 — 잇는 것은 답의 예문 꼴(못 · 아직 · 미룸)만. 반대 방향은 PARTS(「비 때문에 세척 못 했다」 는 잇는다)."""
    before = _row(day, task)["status"]
    m = _put(said, day)
    assert m["drafts"][0]["kind"] == "observation.note", m["drafts"][0]
    assert _row(day, task)["status"] == before and before in ("미이행", "예정", "놓침"), before


@pytest.mark.parametrize("said", ["3단계 촬영은 했는데 4단계 촬영은 못 했다", "촬영(3단계)은 찍었고 촬영(4단계)은 못 찍었다", "웃거름 1회(3단계) 못 줬고 촬영(4단계)도 못 했다",
                                  # [주입 7 미적발 → 추가] 절을 자르면 단계가 하나만 남아 「가장 가까운 단계」 가드가 가려졌다(가드 둘에 검사 하나) — 한 절 안에 단계가 둘인 꼴
                                  "3단계 촬영 다음 4단계 촬영을 못 했다", "3단계 대신 4단계 촬영을 못 했다"])
def test_the_stage_next_to_the_negation_picks_the_row(said):
    """[검토 2026-10-18 둘째] 단계를 둘 말한 문장에서 첫 단계(한 일)를 읽어 「찍었다」 는 칸 3 줄을 닫고 칸 4 줄은 계속 물었다 — 부정에 가장 가까운 단계 · 못 한 그 절(11-24)."""
    four = next(r for r in _pva(DAYS[-1]).result["rows"] if r["task"] == "촬영" and r["stage"].startswith("4."))
    d = chat._attach_plan(SID, chat._classify(said, DAYS[-1]), DAYS[-1])[0]
    assert (d["kind"], d["planned_task"], d["planned_day"]) == ("decision.noncompliance", "촬영", four["work_date"]), d


@pytest.mark.parametrize("said", ["파종 때 밑거름 넣고 웃거름은 비 때문에 못 줬다", "두둑 만들고 밑거름 넣은 뒤로 웃거름은 비 때문에 못 줬다",
                                  "웃거름은 못 줬고 밑거름은 넣었다"])           # 부정 **뒤**의 말(한 일)도 그 절이 아니다 — 부정 끝에서 자른다
def test_a_closed_row_named_in_passing_does_not_win(said):
    """[검토 2026-10-18 둘째] 줄 이름 낱말을 문장 전체에서 세어 지나가는 말(밑거름 · 두둑 · 파종 — 이행 줄)이 이겨 이유가 아무 줄에도 안 붙었다(전에는 웃거름 1회에 붙었다) —
    못 한 그 절(…고 · …뒤로 뒤)에서 센다 · 그 절이 닫힌 줄을 대면 그대로 아무 줄에도 안 붙는다(test_a_reason_naming_a_closed_row_does_not_close_another_row)."""
    d = chat._attach_plan(SID, chat._classify(said, DAYS[-1]), DAYS[-1])[0]
    assert d["planned_task"] == "웃거름 1회", d


@pytest.mark.parametrize("said,task", [("벌레가 많아서 선별 못 했다", "종구 선별 · 소독"), ("잎이 젖어서 세척 못 했다", "수확(뽑기) · 다듬기 · 세척")])
def test_a_name_part_in_an_observed_note_reaches_its_row_and_so_does_the_hand_choice(said, task):
    """[검토 2026-10-18 둘째] 관찰 어휘(벌레 · 잎이)가 낀 이름 조각은 본 것(observed)이라 이름 조각의 길을 안 탔고, 손으로 「못 한 이유」 를 고르면 종류가 원문이라 아무 줄에도
    안 붙었다(고친 길이 이유를 버렸다). 둘 다 같은 규칙(못 · 미룸 + 열린 줄 하나)으로 그 줄에 잇는다(11-24)."""
    m = _say(said, DAYS[-1])
    assert (m["drafts"][0]["kind"], m["drafts"][0].get("planned_task")) == ("decision.noncompliance", task), m["drafts"][0]
    rec = chat.choose_kind(m["id"], "decision.noncompliance", today=DAYS[-1])
    assert rec["drafts"][0]["planned_task"] == task and rec["drafts"][0].get("deferred") is True, rec["drafts"][0]


def test_a_capture_named_up_front_reaches_its_row():
    """[검토 2026-10-18 둘째] 이름을 앞에 내건 꼴 — 작업 줄은 「종구 선별 · 소독(1단계)은 비 때문에 못 했다」 를 잇는데 「촬영(2단계)은 비 때문에 못 했다」 는 본 것이었다."""
    two = next(r for r in _pva(DAYS[-1]).result["rows"] if r["task"] == "촬영" and r["stage"].startswith("2."))
    d = chat._attach_plan(SID, chat._classify("촬영(2단계)은 비 때문에 못 했다", DAYS[-1]), DAYS[-1])[0]
    assert (d["kind"], d["planned_task"], d["planned_day"], d.get("deferred")) == ("decision.noncompliance", "촬영", two["work_date"], True), d


@pytest.mark.parametrize("said,want", [("촬영은 했는데 세척은 못 했다", "수확(뽑기) · 다듬기 · 세척"), ("촬영은 비 때문에 세척을 못 했다", "수확(뽑기) · 다듬기 · 세척"),
                                       ("촬영은 안 해도 된다", None)])
def test_a_capture_named_up_front_does_not_take_another_negation(said, want):
    """반대 방향 — 촬영을 했다고 했거나(했는데) · 못 한 것이 다른 일(세척을)이거나 · 해도 되는 꼴이면 촬영 못 한 이유가 아니다."""
    d = chat._attach_plan(SID, chat._classify(said, DAYS[-1]), DAYS[-1])[0]
    assert d.get("task_type") != "촬영" and d.get("planned_task") == want, d


def _plan_env(rows: list[dict], ask: list[dict]) -> Envelope:
    return Envelope("판단함", "plan_vs_actual", SID, "2026-11-24T00:00:00+00:00", grade="관측", result={"rows": rows, "ask_reason": ask})


@pytest.mark.parametrize("today", DAYS)
def test_the_answer_says_how_to_give_the_reason_only_when_it_asks(today):
    """묻는 답은 어떻게 답하는지를 말한다 — 그 예문은 실제로 이유로 읽힌다. 묻는 것이 없으면 말하지 않는다."""
    a = _ask("오늘 뭐 해야 하나", today)
    assert "사유를 묻는다" in a and chat.REASON_HOW_TAIL in a
    example = a.split("— '", 1)[1].split("' " + chat.REASON_HOW_TAIL, 1)[0]                 # 답이 든 예 — 지금 묻는 첫 줄로 만든다(검토)
    first = _pva(today).result["ask_reason"][0]
    d = chat._attach_plan(SID, chat._classify(example, today), today)[0]
    assert (d["kind"], d["planned_task"], d["planned_day"], d.get("deferred")) == ("decision.noncompliance", first["task"], first["work_date"], True), (example, d)
    missed = {"stage": "5. 수확", "task": "수확", "status": "놓침", "work_date": "2026-10-24", "deadline_date": "2026-11-03"}
    assert chat.REASON_HOW_TAIL in chat._judged_line(_plan_env([missed], [missed]), _plan_env([missed], [missed]).result, "[머리]")
    assert chat.REASON_HOW_TAIL not in chat._judged_line(_plan_env([missed], []), _plan_env([missed], []).result, "[머리]")     # 놓쳤어도 묻지 않으면(사유 기록됨 뒤) 말하지 않는다
    d = chat._classify(chat.REASON_SAY, today)[0]                                                     # 묻는 줄이 없을 때의 고정 예문도 이유로 읽힌다
    assert d["kind"] == "decision.noncompliance" and d["task_type"] == "수확" and d.get("deferred") is True


def test_the_no_name_card_gives_an_example_from_a_row_it_asks():
    """일 이름 없는 말의 카드도 지금 묻는 줄로 예를 든다(11-24) — 그 예를 그대로 적으면 그 줄에 붙는다."""
    d = chat._attach_plan(SID, chat._classify("비 때문에 못 했다", DAYS[-1]), DAYS[-1])[0]
    assert d.get("why_key") == "unnamed_negation" and d.get("example"), d
    assert d["example"] in chat.plain_why(d) and chat.REASON_HOW_TAIL in chat.plain_why(d)
    first = _pva(DAYS[-1]).result["ask_reason"][0]
    e = chat._attach_plan(SID, chat._classify(d["example"], DAYS[-1]), DAYS[-1])[0]
    assert (e["planned_task"], e["planned_day"]) == (first["task"], first["work_date"]), e


def test_a_capture_reason_closes_one_capture_row_after_the_deadline():
    """11-24 「촬영 못 했다」 를 넣으면 묻던 촬영 줄 하나가 닫힌다(마감 뒤의 못 한 이유 = 놓친 이유 — 다시 안 묻는다)."""
    before = [a for a in _pva(DAYS[-1]).result["ask_reason"] if a["task"] == "촬영"]
    m = _put("촬영 못 했다", DAYS[-1])
    assert m["drafts"][0]["kind"] == "decision.noncompliance" and m["drafts"][0]["planned_task"] == "촬영"
    after = [a for a in _pva(DAYS[-1]).result["ask_reason"] if a["task"] == "촬영"]
    assert len(after) == len(before) - 1 and len(before) >= 2


def test_a_capture_reason_inside_the_window_keeps_the_row_open():
    """10-20(칸 5 촬영 창 안) 「사진 못 찍었다」 — 그 줄은 마감까지 지금 할 것으로 남고 이유는 근거에(못 · 아직 = 아직 할 일)."""
    _put("사진 못 찍었다", _d(56))
    rows = [r for r in _pva(_d(56)).result["rows"] if r["task"] == "촬영" and r["status"] == "미이행"]
    assert rows and any("사진 못 찍었다" in (r["evidence"] or "") for r in rows), rows


@pytest.mark.parametrize("said", ["잔사 정리 못 했다", "잔사 못 걷었다", "잔사 정리하지 못했다"])
def test_a_residue_reason_reaches_the_residue_row(said):
    """잔사 정리 줄 — 「잔사 정리 못 했다」 는 본 것이었고 「잔사 못 걷었다」 는 정리 이유였지만 그 줄에 안 붙었다(판정의 표 — 잔사 → 정리)."""
    before = len(_pva(DAYS[-1]).result["ask_reason"])
    m = _put(said, DAYS[-1])
    assert m["drafts"][0]["planned_task"] == RESIDUE_ROW, m["drafts"][0]
    assert all(a["task"] != RESIDUE_ROW for a in _pva(DAYS[-1]).result["ask_reason"]) and len(_pva(DAYS[-1]).result["ask_reason"]) == before - 1


def test_a_shipping_reason_reaches_the_shipping_row_in_a_selling_season():
    """파는 작기 10-28 「출하 못 했다」(납품) — 판정이 납품 기록으로 세는 그 줄에 붙는다(전에는 「계획표에 같은 종류의 미완 작업이 없다」)."""
    _sell()
    m = _put("출하 못 했다", _d(64))
    assert m["drafts"][0]["task_type"] == "납품" and m["drafts"][0]["planned_task"] == SHIP_ROW, m["drafts"][0]
    assert _row(_d(64), SHIP_ROW)["status"] == "사유 기록됨"


def test_a_storage_reason_attaches_inside_the_window_and_not_after_it_in_a_self_use_season():
    """자가 작기의 「저장 못 했다」 — 창 안(10-25)에서는 할 일인 그 줄에 붙고, 마감 뒤(10-28)에는 묻지 않는 줄(기록 없음)이라 붙지 않는다."""
    d = chat._attach_plan(SID, chat._classify("저장 못 했다", _d(61)), _d(61))[0]
    assert d["kind"] == "decision.noncompliance" and d["planned_task"] == SHIP_ROW, d
    d = chat._attach_plan(SID, chat._classify("저장 안 했다", _d(64)), _d(64))[0]
    assert d["kind"] == "decision.noncompliance" and d["planned_task"] == "저장" and "미완 작업이 없다" in d["why"], d


# ── 붙을 줄 — 계획이 아직 할 일로 보는 줄만 · 표는 판정의 것 ───────────────────────────────────────
def _fake(rows: list[dict]):
    return [_plan_env(rows, [])]


@pytest.mark.parametrize("status,linked", [("놓침", True), ("미이행", True), ("예정", True), ("기록 없음", False), ("종료 뒤", False),
                                           ("이행", False), ("사유 기록됨", False)])
def test_a_reason_attaches_only_to_a_row_the_plan_still_holds(monkeypatch, status, linked):
    row = {"task": "촬영", "kind": "plan.capture", "work_date": "2026-08-20", "deadline_date": "2026-08-24", "status": status,
           "match_from": "2026-08-20", "match_to": "2026-08-24"}
    monkeypatch.setattr(judge_run, "judgments_for", lambda *a, **k: _fake([row]))
    assert (chat._plan_row_for(SID, chat.CAPTURE_TYPE, DAYS[-1]) is not None) is linked


@pytest.mark.parametrize("et,task,kind,ok", [
    ("촬영", "촬영", "plan.capture", True), ("촬영", "촬영", "plan.task", False), ("수확", "촬영", "plan.capture", False),
    ("납품", SHIP_ROW, "plan.task", True), ("저장", SHIP_ROW, "plan.task", True), ("정리", RESIDUE_ROW, "plan.task", True),
    ("방제", "예찰(트랩 · 육안)", "plan.task", False),          # 첫 종류만 — 약 못 친 것이 안 본 것의 이유가 되지 않는다(판정은 방제로도 예찰 줄을 센다)
    ("예찰", "예찰(트랩 · 육안)", "plan.task", True), ("소독", "종구 선별 · 소독", "plan.task", True), ("시비", "웃거름 1회", "plan.task", True),
])
def test_which_reason_answers_which_row(et, task, kind, ok):
    assert chat._answers_row(et, {"task": task, "kind": kind}) is ok


@pytest.mark.parametrize("said,ok", [("사진을 아직 못 보냈어요", False), ("문자를 못 보냈다", False), ("출하 못 했다", True), ("납품 못 했다", True),
                                     ("단기 저장 못 했다", True)])
def test_a_row_reached_only_by_its_first_type_needs_its_name_in_the_words(said, ok):
    """[검토 2026-10-18 둘째] 첫 종류로**만** 맞는 줄(「출하 또는 단기 저장」 ← 납품)은 말에 줄 이름의 낱말이나 종류 이름이 있을 때만 — 납품의 「보냈」 은 사진 · 문자도 보낸다."""
    assert chat._answers_row("납품", {"task": SHIP_ROW, "kind": "plan.task"}, said) is ok


@pytest.mark.parametrize("day,said,sell", [(_d(61), "사진을 아직 못 보냈어요", False), (_d(64), "사진 못 보냈다", True), (_d(64), "문자를 못 보냈다", True)])
def test_a_photo_not_sent_does_not_answer_the_shipping_row(day, said, sell):
    """촬영 줄을 묻게 되자 「사진 못 보냈다」 가 자연스러운 답인데 그 말(납품으로 읽힌다 — 이 묶음 전부터)이 출하 줄의 이유가 됐다(자가 10-25 · 파는 작기 10-28)."""
    if sell:
        _sell()
    before = _row(day, SHIP_ROW)["status"]
    m = _put(said, day)
    assert m["drafts"][0].get("planned_task") != SHIP_ROW, m["drafts"][0]
    assert _row(day, SHIP_ROW)["status"] == before


def test_the_row_table_is_the_judgment_s():
    """배선 — 잇는 쪽이 판정의 표(primary_type)를 읽는다 · 붙을 줄은 열린 줄 목록 하나 · 첫 종류는 판정이 그 줄을 세는 표의 첫째."""
    src = inspect.getsource(chat._answers_row)
    assert "primary_type(" in src
    prf = inspect.getsource(chat._plan_row_for)
    assert "_answers_row(" in prf and "_OPEN_ROW" in prf and "_narrowed(" in prf
    for task in (SHIP_ROW, RESIDUE_ROW, "수확(뽑기) · 다듬기 · 세척", "예찰(트랩 · 육안)"):
        assert PVA.primary_type(task) == PVA._types_for(task, PVA.registry.get(PVA.DECISION_ID).params)[0]
    assert PVA.primary_type("촬영") is None


# ── ③ 읽는 말과 안 읽는 말 ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("said", ["촬영 못 했다", "사진 못 찍었다", "사진을 찍지 못했다", "사진은 비 때문에 못 찍었다", "못 찍었다",
                                  "촬영을 하지 못했다", "사진 찍을 수 없었다", "수확 전에 사진 못 찍었다", "사진은 안 찍기로 했다", "촬영은 나중에 하기로 했다",
                                  "비 와서 못 찍음", "사진 찍을 시간이 없었다", "사진 찍지는 못했다",
                                  # [검토 2026-10-18 둘째] 답에 보인 꼴(단계 · 칸)을 분류만으로 · 다시 찍었다는 말이 아니라 둘 다 못 한 말 · 여유
                                  "촬영(2단계) 못 했다", "촬영(칸 2) 못 했다", "촬영 못 했고 사진도 못 찍었다", "사진 찍을 여유가 없었다"])
def test_capture_negations_are_capture_reasons(said):
    assert _kinds(said)[0][:2] == ("decision.noncompliance", "촬영"), _kinds(said)


@pytest.mark.parametrize("said,want", [
    ("사진에 잎이 안 보인다", "observation.note"),             # 안 보인다 — 본 것
    ("사진 찍었다", "observation.note"),                       # 사진 없이 찍었다는 말을 한 일로 셀지는 판정의 증거 규칙(발행자 몫) — 그대로 본 것
    ("수확했는데 사진은 못 찍었다", "event"),                    # 거둔 기록을 잃지 않는다(한 문장에 초안 하나)
    ("물 줬는데 사진은 못 찍었다", "event"),
    # [검토 2026-10-18] 부정된 서술어가 찍다 · 촬영이 아니면 촬영 못 한 이유가 아니다 — 첫 판은 맨 이름 「사진」 이 남의 부정을 가져가 묻던 촬영 줄을 닫았다
    ("사진 찍고 나서 비 때문에 못 했다", "observation.note"), ("사진만 찍고 아무것도 못 했다", "observation.note"),
    ("사진 보시면 알겠지만 비 때문에 아무것도 못 했어요", "observation.note"), ("사진 보니 비 때문에 못 했다", "observation.note"),
    ("사진 보정은 안 했다", "observation.note"), ("사진 정리 못 했다", "observation.note"), ("사진 업로드를 못 했다", "observation.note"),
    ("사진이 안 찍혀서 다시 찍었다", "observation.note"), ("사진이 잘 안 찍혔다", "observation.note"),             # 찍히다 — 결과
    ("처음엔 사진을 못 찍었는데 나중에 찍었다", "observation.note"), ("사진은 못 찍었지만 나중에 다시 찍었다", "observation.note"),   # 다시 찍었다
    ("사진 정리를 미뤘다", "observation.note"), ("사진 올리기는 미뤘다", "observation.note"), ("사진 인화를 못 했다", "observation.note"),   # 찍은 뒤의 일
    ("사진 보내기를 미뤘다", "observation.note"),
])
def test_capture_words_without_a_capture_negation_stay_as_they_were(said, want):
    assert _kinds(said)[0][0] == want, _kinds(said)
    assert _kinds(said)[0][2] != "unnamed_negation", _kinds(said)          # [검토 둘째] 사진 말이 있으면 「일 이름이 없다」 고도 하지 않는다(종류만 보면 그 가드가 안 보인다)


@pytest.mark.parametrize("said,want", [
    ("이 쪽파는 종구생산을 위한 목적이라 사진은 안 찍었다", "parcel.field"), ("이 쪽파는 종구생산을 위한 목적이라 촬영은 생략했다", "parcel.field"),
    ("이 밭은 유기 인증을 받아서 사진은 안 찍었다", "subject.field"),
])
def test_a_declaration_with_a_capture_negation_keeps_the_declaration(said, want):
    """[검토 2026-10-18] 촬영 갈래가 용도 · 인증 선언보다 앞이라 선언을 잃었다(한 문장에 초안 하나) — 선언은 상태를 바꾸고 못 한 이유는 고르는 것이다(선언이 먼저)."""
    assert _kinds(said)[0][0] == want, _kinds(said)


@pytest.mark.parametrize("said,want", [
    ("잔사 정리 못 했다", ("decision.noncompliance", "정리")), ("잔사 정리를 하지 못했다", ("decision.noncompliance", "정리")),
    ("잔사를 정리 못 했다", ("decision.noncompliance", "정리")), ("잔사를 정리하지 못했다", ("decision.noncompliance", "정리")),   # [검토] 조사가 끼는 꼴
    ("잔사를 걷지 못했다", ("decision.noncompliance", "정리")), ("잔사를 못 치웠다", ("decision.noncompliance", "정리")),
    ("잔사 정리했다", ("event", "정리")), ("잔사를 치웠다", ("event", "정리")), ("잔사정리 못 했다", ("decision.noncompliance", "정리")),
    ("잔사가 많이 남았다", ("observation.note", None)),         # 맨 「잔사」 는 두지 않았다 — 이름 + 다른 동사의 과거가 정리한 일이 되지 않게
    ("정리함을 샀다", ("observation.note", None)),
])
def test_residue_words(said, want):
    assert _kinds(said)[0][:2] == want, _kinds(said)


@pytest.mark.parametrize("said,et", [("잔사 정리할 시간이 없었다", "정리"), ("물 줄 시간이 없었다", "관수"), ("수확할 틈이 없었다", "수확"), ("수확할 수 없었다", "수확")])
def test_no_time_to_do_it_is_not_doing_it(said, et):
    """[검토 2026-10-18 · W-46 의 남은 꼴] 「-ㄹ 시간이 없었다」 가 **한 일**이었다(없었 의 ㅆ) — 넣으면 잔사 줄이 이행. 「-ㄹ 수 없」 과 같은 불능 · 아직 할 일."""
    d = chat._classify(said, DAYS[-1])[0]
    assert (d["kind"], d.get("task_type"), d.get("deferred")) == ("decision.noncompliance", et, True), d


def test_no_time_without_a_work_word_is_not_a_reason():
    """반대 방향 — 작업 어휘가 없는 「쉴 시간이 없었다」 는 그 갈래가 아니다(무슨 일을 못 했는지 모른다)."""
    assert _kinds("쉴 시간이 없었다")[0][0] == "observation.note", _kinds("쉴 시간이 없었다")


@pytest.mark.parametrize("said,et", [("수확하느라 밥 먹을 시간도 없었다", "수확"), ("수확하느라 쉴 시간이 없었다", "수확"), ("수확하느라 밥 먹을 틈도 없었다", "수확"),
                                     ("방제하느라 쉴 틈이 없었다", "방제"), ("수확이 많아서 쉴 틈이 없었다", "수확"), ("수확 끝내고 나니 잠잘 시간도 없었다", "수확"),
                                     ("수확하느라 쉴 수가 없었다", "수확"), ("수확하느라 사진 찍을 시간이 없었다", "수확")])
def test_too_busy_with_the_work_is_doing_the_work(said, et):
    """[검토 2026-10-18 둘째] 「-ㄹ 시간 · 틈이 없었다」 를 불능으로 읽자 바빴다는 말이 못 한 이유가 됐다(거둔 기록이 사라진다) — 그 「-ㄹ」 은 다른 일(먹을 · 쉴 · 잠잘)이다.
    작업 어휘가 그 「-ㄹ」 낱말에 닿을 때만(수확할 · 물 줄 · 수확을 할) 불능이다 · 「수 없」 의 옛 꼴도 같은 규칙(이 묶음 전부터 틀렸다) · 한 일이 촬영 못 한 것보다 앞(한 문장에 초안 하나)."""
    assert _kinds(said)[0][:2] == ("event", et), _kinds(said)


@pytest.mark.parametrize("said,et", [("수확을 할 시간이 없었다", "수확"), ("수확을 좀 할 시간이 없었다", "수확"), ("물을 줄 여유도 없었다", "관수"),
                                     ("수확할 여유가 없었다", "수확"), ("물 줄 여유가 없었다", "관수"), ("약 칠 여유가 없었다", "방제"), ("잔사 정리할 여유가 없었다", "정리"),
                                     ("물 줄 여유는 없었다", "관수"), ("물 줄 틈이 없었다", "관수"), ("물 줄 짬은 없었다", "관수"), ("물 줄 여유 없었다", "관수"),
                                     ("잔사 정리할 시간적 여유가 없었다", "정리"), ("약 칠 시간적 여유가 없었다", "방제"), ("수확할 일손이 없었다", "수확"),
                                     ("촬영할 여유가 없었다", "촬영")])
def test_no_room_to_do_it_is_not_done_yet_with_every_particle(said, et):
    """[검토 2026-10-18 둘째] 불능을 알아보는 쪽은 조사 「이 · 가 · 는 · 은 · 도」 를 다 받는데 미룸(아직 할 일)을 가르는 쪽은 「가 · 는」 이 빠져 「여유가 없었다」 가
    **결정**(줄을 바로 닫는다)이 됐다 — 같은 말 두 벌. 「시간적 여유」 · 「일손」 도 같은 불능이다(한 일로 남았다)."""
    d = chat._classify(said, DAYS[-1])[0]
    assert (d["kind"], d.get("task_type"), d.get("deferred")) == ("decision.noncompliance", et, True), d


@pytest.mark.parametrize("said,want", [
    ("잔사 정리하러 갔는데 비가 와서 못 했다", ("decision.noncompliance", "정리", True)), ("수확하러 갔는데 비가 와서 못 했다", ("decision.noncompliance", "수확", True)),
    ("잔사 정리를 하다 말았다", ("decision.noncompliance", "정리", True)), ("수확하다가 말았다", ("decision.noncompliance", "수확", True)),
    ("잔사 정리가 덜 됐다", ("decision.noncompliance", "정리", True)), ("수확이 덜 됐다", ("decision.noncompliance", "수확", True)),
    ("잔사 정리 중에 비가 왔다", ("observation.note", None, None)), ("잔사 정리하러 갔다", ("observation.note", None, None)), ("수확하러 왔다", ("observation.note", None, None)),
    ("수확하러 갔다가 다 캤다", ("event", "수확", None)), ("물 줬는데 비가 와서 더는 못 했다", ("event", "관수", None)),     # 반대 방향 — 한 일은 한 일
])
def test_going_to_do_it_or_stopping_halfway_is_not_doing_it(said, want):
    """[검토 2026-10-18 둘째] 잔사 어휘를 두자 「정리하러 갔는데 … 못 했다」 · 「하다 말았다」 · 「덜 됐다」 · 「정리 중에」 가 **정리한 일**이 됐다 — 묻는 그 줄을 이행으로 닫는다.
    목적 + 움직임(러 갔)의 ㅆ 는 간 것이고 · 덜 끝난 일 · 하다 그친 일은 아직 할 일 · 하던 중은 한 일이 아니다(수확 쪽 쌍둥이는 이 묶음 전부터 틀렸다)."""
    d = chat._classify(said, DAYS[-1])[0]
    assert (d["kind"], d.get("task_type") or d.get("type"), d.get("deferred")) == want, d


@pytest.mark.parametrize("said,deferred", [("사진은 나중에 찍기로 했다", True), ("사진은 다음에 찍기로 했다", True), ("사진은 나중에 찍기로 했어요", True),
                                           ("촬영은 다음에 하기로 했다", True), ("사진은 미뤘다", True), ("사진은 안 찍기로 했다", None)])
def test_putting_the_photo_off_keeps_the_row(said, deferred):
    """[검토 2026-10-18 둘째] 「사진은 나중에 찍기로 했다」 를 촬영 미룸으로 알아보고도 미룸을 가르는 쪽은 「하기로」 만 알아 **결정**(줄을 닫는다)이 됐다 — 말한 것의 반대.
    두 쪽이 한 조각(_LATER)을 쓴다 · 「안 찍기로」 는 결정 그대로."""
    d = chat._classify(said, DAYS[-1])[0]
    assert (d["kind"], d.get("task_type"), d.get("deferred")) == ("decision.noncompliance", "촬영", deferred), d


@pytest.mark.parametrize("said", ["카메라가 안 찍힌다", "사진이 안 찍힘", "흔들려서 잘 안 찍힌다", "어두워서 안 찍힐 것 같다", "폰이 고장나서 사진이 안 찍힌다",
                                  "사진 안 찍어도 된다고 들었다", "사진 안 찍어도 된다", "이번에는 사진 안 찍어도 된다고 했다", "사진은 안 찍어도 될 것 같다",
                                  "사진을 찍지 않아도 된다", "촬영 안 해도 된다", "촬영 안 하면 안 된다", "사진 안 찍으면 안 된다"])
def test_a_photo_that_will_not_take_or_need_not_be_taken_is_not_a_reason(said):
    """[검토 2026-10-18 둘째] 찍히다는 활용 전부가 결과다(첫 판은 찍히 · 찍혀 · 찍혔 셋만 뺐다) · 「안 찍어도 된다」 · 「안 하면 안 된다」 는 안 한 일을 말하지 않는다 —
    둘 다 묻던 촬영 줄을 농가가 안 한 이유로 닫았다. 반대 방향은 test_capture_negations_are_capture_reasons."""
    assert _kinds(said)[0][0] == "observation.note", _kinds(said)


@pytest.mark.parametrize("said", ["이번 작기는 판매 안 할 것이다", "이번엔 안 팔 것이다"])
def test_a_use_declaration_that_says_no_sale_does_not_store_sale(said):
    """[검토 2026-10-18 둘째 · §7.5 관문의 입력] 부정을 떼고 용도 「판매」 로 들어가 출하 문을 열었다 — 값은 넣지 않고(무엇에 쓰는지는 말하지 않았다) 할 일 카드도 아니다."""
    assert parcels.use_declared(said) is None and parcels.sale_declined(said)
    assert _kinds(said)[0][0] == "observation.note", _kinds(said)
    use = parcels.by_id(PID).get("use")
    _put(said, _d(56))                                                                          # 넣어도 용도는 그대로 · 출하 문은 닫힌 채(10-28)
    assert parcels.by_id(PID).get("use") == use and _ship(DAYS[0]).kind == "해당 없음"
    assert SHIP_ROW not in _ask("오늘 뭐 해야 하나", DAYS[0])


def test_a_use_declaration_that_says_sale_still_opens_the_gate():
    """반대 방향 — 「이번 작기는 팔 것이다」 를 넣으면 용도 「판매」 · 출하 판단이 선다(납품 계획일을 묻는다)."""
    _put("이번 작기는 팔 것이다", _d(56))
    assert parcels.by_id(PID).get("use") == "판매" and _ship(DAYS[0]).kind == "판단 불가(데이터)"


@pytest.mark.parametrize("said,use", [("이번 작기는 팔 것이다", "판매"), ("판매 목적이다", "판매"), ("종구 생산 목적이라 판매는 안 한다", "종구 생산"), ("자가 소비용이다", "자가")])
def test_a_use_declaration_still_reads_what_it_says(said, use):
    """반대 방향 — 파는 말은 그대로 「판매」 · 부정된 파는 말 곁의 다른 용도는 그 용도(전에는 둘이 걸려 고르지 않았다)."""
    assert parcels.use_declared(said) == use and _kinds(said)[0][0] == "parcel.field", _kinds(said)
    assert parcels.sale_declined(said) is ("안 한다" in said)


@pytest.mark.parametrize("said", ["비 때문에 못 했다", "아직 못 했어요", "미뤘다", "아무것도 안 했다", "아직 하지 못했다", "오늘은 비 때문에 못 해요", "비가 와서 못 했다",
                                  "아무것도 하지 않았다", "비 때문에 하지 못했다", "비 때문에 하지못했다",
                                  # [검토 2026-10-18 둘째] 낱말 그대로만 맞춰 같은 말의 다른 꼴이 빠졌다(안내가 고르게 안 갔다)
                                  "아직도 못 했어요", "아직은 못 했다", "아직까지 못 했다", "여태 못 했다", "그냥 못 했다", "결국엔 못 했다", "일요일이라 안 했다",
                                  "명절이라 못 했다", "비 오는 바람에 못 했다", "날씨 탓에 못 했다", "비로 인해 못 했다", "일손 부족으로 못 했다", "비가 오길래 안 했다",
                                  "비가 오니 못 했다", "비가 와가지고 못 했어요", "비가 와서인지 못 했다", "비 때문에 제대로 못 했다", "비가 와서 일을 하나도 못 했다",
                                  "오늘은 일을 많이 못 했다", "어제는 비가 와서 아무 것도 못 했다", "오전에는 못 했다", "비와서못했다", "오늘은 못 했다", "그건 못 했다"])
def test_a_reason_without_a_work_name_asks_for_it(said):
    """일 이름이 없는 못 한 이유 — 어느 줄인지 고르지 않고(되묻기) 본 것으로 두되 무엇을 더 적으면 되는지 말한다."""
    d = chat._classify(said, DAYS[-1])[0]
    assert (d["kind"], d.get("why_key")) == ("observation.note", "unnamed_negation"), d
    assert chat.REASON_HOW_TAIL in chat.plain_why(d)


@pytest.mark.parametrize("said", ["날씨가 좋지 못했다", "잎이 안 자랐다", "싹이 안 났다", "잘 안 된다", "비가 와서 좋았다",
                                  # [검토 2026-10-18] 앞말을 안 보던 첫 판이 평가 · 생각을 「어느 일인지 알아볼 말이 없어」 로 받았다
                                  "날씨가 좋지는 못했다", "기대만큼 크지는 못했다", "올해 작황이 작년만 못하다", "서리가 올 줄은 생각도 못 했다", "서리는 예상 못 했다",
                                  "비가 와서 물 걱정은 안 했다", "정리 못 했다",
                                  # [검토 2026-10-18 둘째] 일을 댔다(목적 + 움직임) — 어휘가 그 꼴을 못 읽어도 「어느 일인지 알아볼 말이 없어」 는 거짓 안내다
                                  "약 치러 갔는데 비가 와서 못 했다", "물 주러 갔는데 비가 와서 못 했다", "약 치려다 비가 와서 못 했다", "작년만큼은 못 했다"])
def test_other_negations_are_not_asked_for_a_work_name(said):
    assert _kinds(said)[0][2] != "unnamed_negation", _kinds(said)


def test_choosing_a_reason_for_a_capture_sentence_keeps_the_capture_row():
    """「다른 종류 → 못 한 이유」 로 고른 촬영 말도 촬영 줄에 잇는다(전에는 계획 작업명이 문장 그대로였다)."""
    m = _say("사진 못 찍었다", DAYS[-1])
    rec = chat.choose_kind(m["id"], "decision.noncompliance", today=DAYS[-1])
    assert rec["drafts"][0]["task_type"] == "촬영" and rec["drafts"][0]["planned_task"] == "촬영", rec["drafts"][0]


def test_choosing_a_reason_for_a_mixed_sentence_takes_what_was_not_done():
    """[검토 2026-10-18] 「수확했는데 사진은 못 찍었다」(한 일로 읽힌다)를 못 한 이유로 고르면 못 한 것은 **촬영**이다 — 전에는 작업 어휘가 먼저라 수확 줄이 닫혔다(놓침 10 → 9).
    고른 종류도 분류와 같은 차례(부정된 작업 → 부정된 촬영 → 말 안의 작업)."""
    m = _say("수확했는데 사진은 못 찍었다", DAYS[1])
    assert m["drafts"][0]["kind"] == "event"
    rec = chat.choose_kind(m["id"], "decision.noncompliance", today=DAYS[1])
    assert (rec["drafts"][0]["task_type"], rec["drafts"][0]["planned_task"]) == ("촬영", "촬영"), rec["drafts"][0]
    harvest = "수확(뽑기) · 다듬기 · 세척"
    assert any(a["task"] == harvest for a in _pva(DAYS[1]).result["ask_reason"])
    chat.confirm(rec["id"], 0)
    assert any(a["task"] == harvest for a in _pva(DAYS[1]).result["ask_reason"])            # 수확 줄은 그대로 묻는다(못 한 것이 수확이 아니다)


@pytest.mark.parametrize("said", ["비 때문에 수확 못 하고 사진도 못 찍었다", "사진 못 찍었다", "잔사 정리 못 했다", "촬영(2단계) 못 했다", "비 때문에 세척 못 했다"])
def test_choosing_a_reason_by_hand_agrees_with_the_classifier(said):
    """[검토 2026-10-18 둘째] 분류가 이미 못 한 이유로 읽은 말을 손으로 「못 한 이유」 로 다시 고르면 같은 종류 · 같은 줄이다(고른 종류의 차례가 분류와 다르면
    「비 때문에 수확 못 하고 사진도 못 찍었다」 를 분류는 수확 · 고른 쪽은 촬영으로 읽는다 — 차례를 바꾼 주입이 그 꼴로만 보인다)."""
    m = _say(said, DAYS[-1])
    d = m["drafts"][0]
    assert d["kind"] == "decision.noncompliance", d
    rec = chat.choose_kind(m["id"], "decision.noncompliance", today=DAYS[-1])
    assert (rec["drafts"][0]["task_type"], rec["drafts"][0]["planned_task"]) == (d["task_type"], d["planned_task"]), (d, rec["drafts"][0])


def test_the_example_carries_the_stage_when_a_shared_name_is_asked_first():
    """[검토 2026-10-18 둘째] 묻는 첫 줄이 늘 이름이 하나뿐인 줄(종구 선별 · 소독)이라 예문의 단계 표기를 아무 검사도 안 봤다 — 그 줄의 이유를 넣어 같은 이름의 촬영 줄이
    먼저 묻게 한 뒤 답의 예와 되묻기 카드의 예가 그 줄(그 날)에 붙는지 잰다(11-24)."""
    _put("비 때문에 종구 선별 · 소독(1단계) 못 했다", DAYS[-1])
    first = _pva(DAYS[-1]).result["ask_reason"][0]
    assert first["task"] == "촬영", first
    a = _ask("오늘 뭐 해야 하나", DAYS[-1])
    example = a.split("— '", 1)[1].split("' " + chat.REASON_HOW_TAIL, 1)[0]
    card = chat._attach_plan(SID, chat._classify("비 때문에 못 했다", DAYS[-1]), DAYS[-1])[0]["example"]
    for ex in (example, card):
        d = chat._attach_plan(SID, chat._classify(ex, DAYS[-1]), DAYS[-1])[0]
        assert (d["planned_task"], d["planned_day"]) == (first["task"], first["work_date"]), (ex, d)


def test_the_asking_answer_ends_its_sentence_before_the_next_one():
    """[검토 2026-10-18] 묻는 말(「… 남습니다」) 뒤에 고칠 수 있다는 말이 마침표 없이 붙어 한 문장으로 읽혔다(10-28)."""
    a = _ask("오늘 뭐 해야 하나", DAYS[0])
    assert chat.REASON_HOW_TAIL in a and "검토 전 추론" in a, a
    assert f"{chat.REASON_HOW_TAIL}. " in a and f"{chat.REASON_HOW_TAIL} 「" not in a, a


def test_the_capture_rule_reads_the_negated_verb_and_sits_after_the_done_and_declaration_branches():
    """배선 — 촬영 부정은 **부정된 서술어**(찍다 · 촬영)를 본다(작업 부정의 걷기는 끝 앞 가장 가까운 이름을 읽어 맨 「사진」 이 남의 부정을 가져갔다 · 검토) · 다시 찍었으면 아니다 ·
    한 일 갈래와 용도 · 인증 선언 **뒤**에 선다(앞이면 거둔 기록 · 선언을 잃는다) · 일 이름 없는 말은 관찰 어휘보다 앞 · 이름 조각은 열린 줄 하나일 때만(_attach_plan)."""
    import re
    cap = inspect.getsource(chat._capture_negated)
    assert "_CAPTURE_NEG.search(" in cap and "_captured_after(" in cap and "_negated_in(" not in cap
    src = inspect.getsource(chat._classify)
    # 호출형의 자리만 본다(조건 줄 전체 · 인자 표현식 · `if et:` 같은 글자는 박지 않는다 — 검토 2026-10-18 · 둘째 검토가 같은 뜻 리팩터 다섯에 깨지는 것을 보였다).
    # 용도 선언 · 작업 어휘 메모와의 차례는 행동 검사가 진다(test_a_declaration_with_a_capture_negation_keeps_the_declaration · 「수확 전에 사진 못 찍었다」)
    order = [re.search(p, src).start() for p in (r"_done_outside_negation\(", r"\bcert_declared\(", r"\b_capture_negated\(", r"\bunnamed_work_negated\(")]
    assert order == sorted(order), order
    assert re.search(r"\bunnamed_work_negated\(", src).start() < re.search(r"\bOBS_WORDS\b", src).start()
    assert "_noncompliance_drafts(" in src and '"kind": "decision.noncompliance"' not in src           # 초안은 한 벌(작업 부정 · 촬영 부정이 같은 하나 — 분류 안에 사본이 없다)
    att = inspect.getsource(chat._attach_plan)
    assert re.search(r"\bby_name\s*=", att) and "unnamed_negation" in att and "reason_example(" in att
    # [검토 2026-10-18 둘째] 같은 말을 두 벌 두지 않는다 — 미룸 · 불능 낱말은 알아보는 쪽(끝 부정 · 촬영 부정)과 가르는 쪽(_DEFERRED)이 한 조각
    for piece in (chat._UNABLE_NOUN, chat._UNABLE_PART, chat._LATER):
        assert piece in chat._DEFERRED.pattern and piece in chat._CAPTURE_NEG.pattern, piece
    assert chat._UNABLE_NOUN in chat._UNABLE_TAIL.pattern and chat._UNDONE in chat._NEG_TAIL.pattern and chat._UNDONE in chat._DEFERRED.pattern
    assert "_reaches(" in inspect.getsource(chat._tail_negation)                                    # 「-ㄹ」 낱말에 닿는 작업 어휘만(바빴다는 말이 못 한 이유가 되지 않게)
    assert "_PURPOSE_GO" in inspect.getsource(chat._done_outside_negation) and "_PURPOSE_GO" in inspect.getsource(chat._last_work_before)
    assert "_during(" in src and "deferred_said(" in att and "_said_part(" in att and "_PURPOSE_FORM" in inspect.getsource(chat.unnamed_work_negated)
