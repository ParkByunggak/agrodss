# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-14 W-14 · W-15] 수확 기간(10-14~11-03) **안**에서 농가가 적는 두 말이 계획과 어긋났다.
#     W-15  「오늘 쪽파 조금 수확했다」(10-14 · 10-18) → 넣어도 계획 수확 줄은 「다음 예정 10-24」 · 11-04 「놓침 — 사유를 묻는다: 수확」
#           계획은 작업일 − 3(10-21)부터 셌다 — 같은 날 수확 시기 판단은 「지금 기간 안」(10-14 부터) · 위험 경보와 되먹임은 그 기록을 이미 수확으로 셌다
#     W-14  「비 때문에 수확 못 했다」(10-14) → 열흘 뒤 계획 줄(10-24)의 사유로 붙어 그 줄을 닫았다 — 수확 할 일이 수확 기간 내내 사라졌다 ·
#           일지 · 넣은 배너는 그 사유를 10-24(앞날)에 세웠다
# 처방 직후 전수(§7.5)가 셋을 더 꺼냈다.
#     ① 할 일 열둘 중 열이 W-15 와 같은 꼴(칸이 열린 뒤 작업일 − 3 전에 한 일이 안 잡힌다)
#     ② 반대 방향 — 「못 캤다 · 수확은 비 때문에 못 했다 · 밭 못 둘러봤다 · 수확 미뤘다 · 수확할 수 없었다」 가 **한 일**(사건)이 되어 계획 줄을 이행으로 닫고
#        수확 지연 경보를 멎게 했다(직렬 게이트 — ①의 창을 넓히면 이 거짓 기록이 닫는 날도 넓어진다)
#     ③ 위험 경보가 수확 기록을 읽는데(창이 닫힌 뒤) 사건 소비자 표에 없었다 — 표를 잰 날 셋이 다 그 앞이었다(시점 축)
# 고정하는 것(양방향):
#   ① 한 일은 칸이 열리는 날부터 센다(정본 match_window — 계획 대 실제 · 웃거름 판단이 같은 창) · 사건 하나는 앞 줄 하나에만 · 근거는 처음 한 날
#   ② 못 한 이유는 창이 열린 줄에만 잇는다 · 조건부 줄에는 다른 줄이 없을 때만 · 날이 둘(계획 줄의 날 · 못 한 날)
#   ③ 「못 · 아직 · 미룸」 은 마감까지 줄을 닫지 않는다(근거에만) · 마감 뒤에는 닫는다(다시 안 묻는다) · 「안 하기로 · 주지 않고」 는 그 자리에서 닫는다(옛 규칙)
#   ④ 부정 · 불능 · 미룸 문장은 한 일이 아니다 — 한 일 문장은 그대로 한 일이다
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from frontend import chat_pages
from ingest import chat, events as ev, subjects
from judge import plan, plan_vs_actual, run as judge_run, stage_decisions as SD
from judge.envelope import reading_face
from tests.test_brand_home import srv  # noqa: F401 — 격리 화면 서버(빈 포트 · 끝나면 내린다)

ROOT = Path(chat.__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
ANCHOR = date(2026, 8, 25)
HARVEST_ROW = "수확(뽑기) · 다듬기 · 세척"


def _d(n: int) -> date:
    return date.fromordinal(ANCHOR.toordinal() + n)


def _say(text: str, today: date) -> dict:
    m, _r = chat.send(SID, text, today=today, now=datetime(today.year, today.month, today.day, 9, tzinfo=timezone.utc))
    return m


def _put(text: str, today: date) -> list[dict]:
    m = _say(text, today)
    return [chat.confirm(m["id"], i, day=today.isoformat() if d.get("needs") else None)
            for i, d in enumerate(m["drafts"]) if d["kind"] != "question"]


def _pva(today: date):
    return next(x for x in judge_run.judgments_for(SID, today=today) if x.decision_id == "plan_vs_actual")


def _row(today: date, task: str) -> dict:
    return next(r for r in _pva(today).result["rows"] if r["task"] == task)


def _ask(q: str, today: date) -> str:
    return chat.answer(subjects.by_id(SID), q, today)


# ── ① 한 일을 세는 창 ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("said_on", [_d(50), _d(54)])
def test_a_harvest_in_the_first_week_fulfils_the_harvest_row(said_on):
    """W-15 — 수확 칸 첫날(경계일 50일 포함)과 첫 주의 수확 기록이 계획 수확 줄을 이행으로 만든다 · 그 줄은 놓침으로 사유를 묻지 않는다."""
    _put("오늘 쪽파 조금 수확했다", said_on)
    for today in (said_on, _d(60), _d(71)):
        r = _row(today, HARVEST_ROW)
        assert r["status"] == "이행" and said_on.isoformat() in r["evidence"], (today, r)
    assert all(a["task"] != HARVEST_ROW for a in _pva(_d(71)).result["ask_reason"])
    assert HARVEST_ROW not in _ask("오늘 뭐 해야 하나", _d(52))                           # 「다음 예정 수확」 이 안 남는다


def test_a_harvest_before_the_window_does_not_count():
    """양방향 — 수확 칸이 열리기 **전** 기록(48일)은 수확 줄을 채우지 않는다(창을 칸 첫날까지 넓혔지 칸 밖까지가 아니다)."""
    _put("오늘 쪽파 조금 수확했다", _d(48))
    assert _row(_d(60), HARVEST_ROW)["status"] == "미이행"


def test_every_task_row_counts_from_its_stage_start_and_both_layers_agree():
    """처방 직후 전수 — 할 일 줄마다 아래끝 = min(작업일 − 3, 칸 첫날) · 조건부 줄은 작업일 − 3 그대로(검토) · 웃거름 1회는 계획 대 실제와 웃거름 판단이 같은 창(한 벌)."""
    rows = [p for p in plan.from_unit(judge_run.grid_schema.load_unit(subjects.by_id(SID))[0], ANCHOR, "관행") if p["kind"] == "plan.task"]
    assert rows and all(p.get("stage_from_date") for p in rows)
    conditional = {p["task"] for p in rows if plan_vs_actual.conditional_of(p["task"]) is not None}
    assert conditional and conditional < {p["task"] for p in rows}                    # 둘 다 있다(양방향이 실제로 갈린다)
    for p in rows:
        lo, hi = plan_vs_actual.match_window(p, 3)
        wd = date.fromordinal(date.fromisoformat(p["work_date"]).toordinal() - 3)
        assert lo == (wd if p["task"] in conditional else min(wd, date.fromisoformat(p["stage_from_date"]))), p["task"]
    _put("오늘 웃거름 줬다", _d(12))                                                      # 칸 3(10일~) 안 · 작업일 − 3(19일) 전
    pva = _row(_d(20), "웃거름 1회")["status"]
    sd = next(e for e in judge_run.judgments_for(SID, today=_d(20)) if e.decision_id == "top_dressing_1").result["status"]
    assert pva == sd == "이행", (pva, sd)


def test_one_record_fills_one_row_the_earlier_one():
    """사건 하나는 앞 줄 하나에만(사진과 같은 약속 · B4) — 시비 30일은 웃거름 1회(마감 30)를 채우고 웃거름 2회는 그대로 ·
    농가의 보식 기록(8일 — 밑거름 · 파종 마감 안이고 보식 창 안)은 기준점이 이미 채운 밑거름 · 파종 줄이 아니라 보식 줄로."""
    _put("오늘 웃거름 줬다", _d(30))
    assert _row(_d(35), "웃거름 1회")["status"] == "이행" and _row(_d(35), "웃거름 2회(필요 시)")["status"] != "이행"
    _put("오늘 보식했다", _d(8))
    assert _row(_d(9), "밑거름 · 두둑 · 파종")["evidence"] == f"사건 파종 {ANCHOR.isoformat()}"
    assert _row(_d(9), "보식")["status"] == "이행"


def test_one_record_never_fills_two_overlapping_rows(monkeypatch):
    """[주입 D · E 미적발 → 추가] 이 격자에서는 같은 종류 줄의 창이 겹치는 자리가 기준점(파종 0일)이 늘 앞 줄을 먼저 채우는 한 곳뿐이라
    「한 기록은 앞 줄 하나에만」 이 관측되지 않았다(가드가 지금 자료에 가려졌다). 웃거름 2회를 조건부가 아닌 줄로 두면 두 줄의 창이 30일에서 겹친다 —
    시비 한 번(30일)은 1회만 채운다(사진과 같은 약속)."""
    monkeypatch.setattr(plan_vs_actual, "conditional_of", lambda *a, **k: None)
    _put("오늘 웃거름 줬다", _d(30))
    assert _row(_d(31), "웃거름 1회")["status"] == "이행" and _row(_d(31), "웃거름 2회(필요 시)")["status"] != "이행"


def test_a_conditional_row_is_not_widened():
    """[검토 2026-10-14] 조건부 줄은 넓히지 않는다 — 이틀에 걸쳐 심은 둘째 날 파종 기록(3일)이 보식 이행이 되고, 마감 넘긴 웃거름 1회(33일)가 2회 이행이 됐다."""
    _put("오늘 파종했다", _d(3))
    assert _row(_d(9), "보식")["status"] != "이행"
    _put("오늘 웃거름 줬다", _d(33))
    assert _row(_d(34), "웃거름 2회(필요 시)")["status"] != "이행"


def test_a_later_record_does_not_move_the_evidence():
    """근거는 처음 한 날 — 둘째 수확 기록은 판단의 면을 안 바꾼다(작업일에 가까운 것을 고르면 근거 날이 갈려 「누르면 판단이 읽습니다」 를 지었다)."""
    _put("오늘 쪽파 조금 수확했다", _d(51))
    before = reading_face(_pva(_d(56)))
    _put("오늘 쪽파 조금 수확했다", _d(55))
    assert reading_face(_pva(_d(56))) == before


# ── ② · ③ 못 한 이유 ──────────────────────────────────────────────────────────────────────
def test_cannot_harvest_today_keeps_the_harvest_task_until_its_deadline():
    """W-14 — 「비 때문에 수확 못 했다」(10-14)는 수확 줄에 붙되 그 줄을 마감까지 닫지 않는다 · 일지와 배너는 말한 날 · 마감 뒤에는 닫는다(다시 안 묻는다)."""
    m = _say("비 때문에 수확 못 했다", _d(50))
    d = m["drafts"][0]
    assert d["kind"] == "decision.noncompliance" and d.get("deferred") is True
    assert chat.plain_why(d).startswith("아직 못 한 일")                                 # 카드도 그 말 그대로(「하지 않은 일」 이 아니다)
    assert (d["planned_task"], d["planned_day"], d["observed_at"]) == (HARVEST_ROW, _d(60).isoformat(), _d(50).isoformat())
    rec = chat.confirm(m["id"], 0)
    assert rec["observed_at"] == _d(50).isoformat() and rec["planned_day"] == _d(60).isoformat() and rec.get("deferred") is True and rec.get("chat_ref")
    assert chat.saved_line(d, rec).endswith(_d(50).isoformat())                            # 넣은 배너가 앞날(10-24)을 말하지 않는다
    assert _row(_d(54), HARVEST_ROW)["status"] == "예정" and "비 때문에" in _row(_d(54), HARVEST_ROW)["evidence"]
    assert HARVEST_ROW in _ask("오늘 뭐 해야 하나", _d(54)) and HARVEST_ROW in _ask("오늘 뭐 해야 하나", _d(62))
    assert _row(_d(62), HARVEST_ROW)["status"] == "미이행" and "비 때문에" in _row(_d(62), HARVEST_ROW)["evidence"]
    after = _pva(_d(71))
    assert next(r for r in after.result["rows"] if r["task"] == HARVEST_ROW)["status"] == "사유 기록됨"
    assert all(a["task"] != HARVEST_ROW for a in after.result["ask_reason"])
    line = next(x for x in chat.diary(SID) if x["kind"] == "decision.noncompliance")
    assert line["day"] == _d(50).isoformat() and "못 한 이유" in line["text"] and line["from_chat"]


def test_a_decision_not_to_do_it_still_closes_at_once():
    """양방향 — 옛 규칙의 계기(안 하기로 한 결정)는 그대로 그 자리에서 닫는다 · 닫는 규칙은 하나(reason_closes)."""
    dl = _d(70)
    assert plan_vs_actual.reason_closes({"reason": "x"}, _d(55), dl) is True
    assert plan_vs_actual.reason_closes({"reason": "x", "deferred": True}, _d(55), dl) is False
    assert plan_vs_actual.reason_closes({"reason": "x", "deferred": True}, _d(71), dl) is True
    _put("수확을 하지 않기로 했다", _d(55))
    assert _row(_d(56), HARVEST_ROW)["status"] == "사유 기록됨"


def test_the_later_reason_is_what_the_row_says_now():
    """한 줄에 사유가 둘이면 나중에 넣은 것 — 「비 때문에 못 했다」 뒤에 「하지 않기로 했다」 를 넣으면 그 줄은 닫힌다(첫 사유가 이기면 계속 열려 있다)."""
    _put("비 때문에 수확 못 했다", _d(51))
    assert _row(_d(52), HARVEST_ROW)["status"] == "예정"
    _put("수확을 하지 않기로 했다", _d(52))
    assert _row(_d(53), HARVEST_ROW)["status"] == "사유 기록됨"


def test_the_top_dressing_layer_keeps_a_deferred_reason_open_too():
    """웃거름 판단도 같은 규칙 — 「비 때문에 웃거름 못 줬다」(작업일 뒤 · 마감 전)는 웃거름 1회를 닫지 않는다 · 두 층이 같은 상태."""
    _put("비 때문에 웃거름 못 줬다", _d(24))
    sd = next(e for e in judge_run.judgments_for(SID, today=_d(25)) if e.decision_id == "top_dressing_1").result
    assert sd["status"] == _row(_d(25), "웃거름 1회")["status"] == "미이행" and "비 때문에" in sd["summary"]


@pytest.mark.parametrize("today,said,attached", [
    (_d(46), "비 때문에 수확 못 했다", False),            # 수확 창이 아직 안 열렸다 — 앞날 줄에 잇지 않는다
    (_d(51), "10월 12일에 수확 못 했다", False),          # 말한 날(48일)이 창 전
    (_d(51), "어제 수확 못 했다", True),                  # 말한 날(50일)이 창 첫날
    (_d(75), "오늘 비 때문에 수확 못 했다", False),       # [검토] 말한 날(75일)이 마감(70일) 뒤 — 그 줄의 놓친 이유가 아니다
    (_d(75), "비 때문에 수확 못 했다", True),             # 날을 안 말하면 지금 묻는 줄(놓침)의 답일 수 있다
])
def test_a_reason_attaches_only_to_a_row_whose_window_has_opened(today, said, attached):
    d = _say(said, today)["drafts"][0]
    assert d["kind"] == "decision.noncompliance"
    assert (d["planned_task"] == HARVEST_ROW) is attached, d


def test_a_conditional_row_does_not_swallow_the_reason():
    """같은 종류의 회차 둘 — 지난 줄(놓침 · 사유를 묻는다)과 조건부 회차 — 중 사유는 보이는 줄로 간다(조건부 판정이 사유보다 앞이라 거기 붙으면 사라졌다)."""
    d = _say("비 때문에 웃거름 못 줬다", _d(42))["drafts"][0]
    assert d["planned_task"] == "웃거름 1회", d
    chat.confirm(_say("비 때문에 웃거름 못 줬다", _d(42))["id"], 0)
    assert _row(_d(42), "웃거름 1회")["status"] == "사유 기록됨"
    assert all(a["task"] != "웃거름 1회" for a in _pva(_d(42)).result["ask_reason"])


def test_the_card_date_is_the_day_it_was_not_done():
    """카드 날짜 칸 = 못 한 날(말한 날) · 계획 줄의 날은 글로 — 날짜 칸을 고쳐 넣어도 줄과 안 끊긴다."""
    m = _say("비 때문에 수확 못 했다", _d(50))
    h = chat_pages._draft_html(m, 0, m["drafts"][0])
    assert f'name="day" value="{_d(50).isoformat()}"' in h and f"계획 {_d(60).isoformat()} · 못 한 날" in h
    rec = chat.confirm(m["id"], 0, day=_d(49).isoformat())
    assert rec["planned_day"] == _d(60).isoformat() and rec["observed_at"] == _d(49).isoformat()


# ── ④ 부정 · 불능 · 미룸은 한 일이 아니다 ────────────────────────────────────────────────────
@pytest.mark.parametrize("said,kind_of_work", [
    ("비 때문에 못 캤다", "수확"), ("못 거뒀다", "수확"), ("못 다듬었다", "수확"), ("수확은 비 때문에 못 했다", "수확"),
    ("수확을 비가 와서 못 했다", "수확"), ("수확할 수 없었다", "수확"), ("비 때문에 수확할 수가 없었다", "수확"), ("수확 미뤘다", "수확"),
    ("수확 연기했다", "수확"), ("비가 와서 수확은 다음에 하기로 했다", "수확"), ("오늘 비 때문에 밭 못 둘러봤다", "예찰"), ("못 살펴봤다", "예찰"),
    ("오늘 비 때문에 못 다시 심었다", "보식"), ("못 옮겨 심었다", "정식"), ("아직 수확 못 했다", "수확"),
    # [검토] 미룸 꼴 하나하나 — 목록에 있는데 검사가 안 닿던 꼴
    ("수확 늦췄다", "수확"), ("수확 늦춤", "수확"), ("수확은 다음으로 미뤄 두었다", "수확"), ("수확 미룸", "수확"),
    ("수확은 다음 주로 미루기로 했다", "수확"), ("수확 연기함", "수확"), ("수확은 연기하기로 했다", "수확"), ("수확은 나중에 하기로 했다", "수확"),
])
def test_a_negated_or_postponed_sentence_is_a_reason_still_to_do(said, kind_of_work):
    ds = chat.classify(said, _d(55))
    assert ds[0]["kind"] == "decision.noncompliance" and ds[0]["task_type"] == kind_of_work and ds[0].get("deferred") is True, ds
    assert not any(d["kind"] == "event" for d in ds), ds


@pytest.mark.parametrize("said,kind", [
    ("오늘 쪽파 조금 수확했다", "event"), ("비가 안 와서 물 줬다", "event"), ("물 줬는데 충분하지 않다", "event"), ("수확했는데 많지 않다", "event"),
    ("안방에서 약 쳤다", "event"), ("수확 끝났다", "event"),
])
def test_a_done_sentence_stays_done(said, kind):
    """양방향 — 접기 글자를 어휘에서 세자 접히는 말이 늘었다. 한 일 문장은 그대로 한 일이다(다른 서술어의 부정 · 「안방」 은 접히지 않는다)."""
    assert chat.classify(said, _d(55))[0]["kind"] == kind


@pytest.mark.parametrize("said,deferred", [
    ("비 때문에 수확 못 했다", True), ("아직 안 심었어요", True), ("수확 미뤘다", True),
    ("수확 안 했다", False), ("제초 생략했다", False), ("수확을 하지 않기로 했다", False),
    ("쪽파 포장에는 웃거름 주지 않고 수분공급만 표면이 마르지 않게 해 줌. 그 근거는 토양검증 상태를 기준으로 함", False),
])
def test_still_to_do_is_told_from_decided_not_to(said, deferred):
    d = chat.classify(said, _d(55))[0]
    assert d["kind"] == "decision.noncompliance" and bool(d.get("deferred")) is deferred, d


@pytest.mark.parametrize("said,kind,task,deferred", [
    # [검토 2026-10-14] 첫 판이 깬 꼴 — 넓힌 접기 · 끝 서술어 규칙이 **다른 말**을 작업 부정으로 읽었다
    ("물 줬는데 비 때문에 더는 못 했다", "event", "관수", None),               # 작업 어휘에 제 과거 서술어가 있다 — 한 일
    ("수확했는데 아직 다 못 팔았다", "event", "수확", None),
    ("웃거름은 비 때문에 못 줬다", "decision.noncompliance", "시비", True),     # 끝 서술어가 하다가 아닌 작업 동사
    ("트랩을 못 구해서 예찰은 안 하기로 했다", "decision.noncompliance", "예찰", False),   # 결정을 밝힌 말이 이긴다
    ("비료를 못 구해서 웃거름을 주지 않기로 했다", "decision.noncompliance", "시비", False),
    ("웃거름은 안 주기로 했다. 아직 잎 색이 좋아서", "decision.noncompliance", "시비", False),   # 「안 주기로」 도 결정(하기로만 봤다)
    ("아직 비가 와서 수확은 생략했다", "decision.noncompliance", "수확", False),
    ("서리 맞아서 못 살렸다", "event", "피해", None),                         # 「살」 로 접으면 피해 보고가 「피해 없음」 이 됐다
    ("수확은 안 급하다", "observation.note", None, None),                     # 「급」 으로 접으면 수확 불이행(줄을 닫는다)이 됐다
    ("수확 날짜는 아직 안 정했다", "observation.note", None, None),           # 부정된 서술어의 과거 표지는 한 일의 표지가 아니다
    # [검토 둘째] 끝이 두 낱말(「-기로 했다」)이거나 일반 동사의 「-지 못」 인 결정 · 불능 — 전에는 한 일이었다
    ("웃거름은 비 때문에 못 주었다", "decision.noncompliance", "시비", True),
    ("웃거름은 비 때문에 주지 못했다", "decision.noncompliance", "시비", True),
    ("웃거름은 토양검정 결과를 보고 주지 않기로 했다", "decision.noncompliance", "시비", False),
    ("수확은 비 때문에 안 하기로 했다", "decision.noncompliance", "수확", False),
    # 앞에 한 일이 따로 있으면 그 한 일을 잃지 않는다 · 상태 서술의 「-지 않」 은 작업 부정이 아니다 · 「못 살았다」 등은 접지 않는다
    ("오늘 수확했는데 선별은 못 했다", "event", "수확", None),
    ("수확했지만 출하할 수가 없었다", "event", "수확", None),
    ("수확 다 했고 납품은 미뤘다", "event", "수확", None),
    ("어제 약 쳤는데 비가 와서 다시 할 수가 없었다", "event", "방제", None),
    ("오늘 수확했는데 비가 와서 더 할 수 없었다", "event", "수확", None),
    ("웃거름이 충분하지 않다", "observation.note", None, None),
    ("물을 줬는데 물이 안 줄었다", "event", "관수", None),
    ("못 살았다", "observation.note", None, None),
])
def test_the_shapes_the_first_version_broke(said, kind, task, deferred):
    d = chat.classify(said, _d(55))[0]
    assert d["kind"] == kind, (said, d)
    if task:
        assert (d.get("type") or d.get("task_type")) == task, (said, d)
    if deferred is not None:
        assert bool(d.get("deferred")) is deferred, (said, d)


def test_the_reason_form_on_the_records_screen_marks_still_to_do_too(srv):
    """/events 의 못 한 이유 폼도 같은 정본(chat.deferred_said) — 그 길로 넣은 「못 했다」 가 줄을 닫으면 W-14 가 거기서 그대로다(지점 축)."""
    import http.client
    from urllib.parse import urlencode
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=5)
    c.request("POST", "/events/reason", body=urlencode({"subject": SID, "planned_task": HARVEST_ROW, "planned_day": _d(60).isoformat(),
                                                         "reason": "비 때문에 수확 못 했다"}), headers={"Content-Type": "application/x-www-form-urlencoded"})
    c.getresponse().read()
    rec = [r for r in ev.list_records(SID, "decision.noncompliance")][-1]
    assert rec.get("deferred") is True and _row(_d(62), HARVEST_ROW)["status"] == "미이행"
    from frontend import config
    assert rec["observed_at"] <= config.today().isoformat()                    # 계획일이 앞날이어도 못 한 날은 앞날이 아니다(일지가 앞날에 세우지 않는다)


def test_a_draft_from_before_the_upgrade_is_measured_again_when_put():
    """고치기 전에 선 초안(표지 없음)도 넣을 때 원문으로 다시 잰다 — 표지가 없다고 옛 규칙으로 닫지 않는다."""
    m = _say("비 때문에 수확 못 했다", _d(51))
    old = dict(chat.get_message(m["id"]))
    old["drafts"] = [{k: v for k, v in d.items() if k != "deferred"} for d in old["drafts"]]
    old.pop("schema_version", None)
    chat._append(old)
    rec = chat.confirm(m["id"], 0)
    assert rec.get("deferred") is True


def test_a_cannot_dig_sentence_no_longer_silences_the_late_harvest_alert():
    """반대 방향 W-14 의 끝 — 전에는 「못 캤다」 가 수확 사건이 되어 수확 줄을 이행으로 닫고 창이 닫힌 뒤 「수확 지연」 경보를 멎게 했다."""
    _put("오늘 비 때문에 못 캤다", _d(60))
    assert _row(_d(62), HARVEST_ROW)["status"] == "미이행"
    risk = next(e for e in judge_run.judgments_for(SID, today=_d(71)) if e.decision_id == "risk_alert")
    assert any(a.get("risk", "").startswith("수확 지연") for a in risk.result.get("alerts", [])), risk.result


# ── 사건 소비자 · 도구 ──────────────────────────────────────────────────────────────────────
def test_the_risk_answer_says_a_waiting_harvest_record_would_change_it():
    """위험 경보가 수확 기록을 읽는다(창이 닫힌 뒤) — 넣지 않은 수확 초안이 있으면 위험 답이 그 말을 한다(전에는 표에 없어 침묵)."""
    assert "risk_alert" in ev.EVENT_CONSUMERS["수확"]
    _say("어제 쪽파 다 수확했다", _d(72))
    a = _ask("위험한 거 있나", _d(72))
    assert "아직 일지에 넣지 않은 수확 기록 1건" in a and "누르면 판단이 읽습니다" in a, a[-300:]


# 그 결함의 꼴 둘 — 트리 이름(ROOT · REPO · TREE · BASE)을 절대 경로로 세우기 · 절대 경로가 **있으면** 그것을 쓰기(.exists()). 함수에 넘기는 가짜 경로 값(Path("/r"))은 트리가 아니다
TREE_LITERAL = __import__("re").compile(r"""\b(?:ROOT|REPO|TREE|BASE)\w*\s*=[^\n]*['"](?:/|[A-Za-z]:[\\/])|Path\(\s*r?['"](?:/|[A-Za-z]:[\\/])[^'"]*['"]\s*\)\.exists\(\)""")


def test_no_test_measures_a_tree_other_than_its_own():
    """[자기 도구 오류 2026-10-14] 검사 하나가 다른 경로(본 클론)를 재고 있었다 — 고친 코드를 한 번도 안 봤다. 검사는 제 트리를 잰다
    (절대 경로로 Path 를 세우거나 ROOT 를 박지 않는다 — 작은따옴표 · r 문자열 · 윈도 경로도 · 검토 2026-10-14)."""
    hits = [p.name for p in (ROOT / "tests").glob("test_*.py")
            if TREE_LITERAL.search(p.read_text(encoding="utf-8")) and p.name != Path(__file__).name]
    assert not hits, hits
    for bad in ('ROOT = Path("/home/user/agrodss")', "ROOT = Path(r'D:\\agrodss')", "if Path('/root/repo').exists():"):   # 규칙이 살아 있다
        assert TREE_LITERAL.search(bad), bad
    for ok in ('monkeypatch.setenv("AGRODSS_WATCH_DIRS", "C:\\\\없는\\\\폴더;")', 'autopull.loop(stop, 0.01, Path("/r"), "origin")'):
        assert not TREE_LITERAL.search(ok), ok                                            # 경로 값(없는 폴더 · 가짜 저장소)은 트리가 아니다


def test_the_walk_tool_can_say_and_put():
    """카드 렌즈의 행을 저장소 도구로 다시 잰다 — 「날짜:문장」 · 꼴이 틀리면 이유와 함께 멈춘다."""
    from scripts import answer_walk
    assert answer_walk.say_spec("2026-10-14:비 때문에: 수확 못 했다") == (date(2026, 10, 14), "비 때문에: 수확 못 했다")
    with pytest.raises(ValueError):
        answer_walk.say_spec("비 때문에 수확 못 했다")


def test_the_walk_tool_says_on_its_day_not_before(monkeypatch):
    """[검토 2026-10-14] 말한 날 **이전**의 답은 그 기록을 모른다 — 처음엔 다 넣고 걸어서 앞날 기록을 읽었다. 그리고 --say 가 실제로 원장에 닿는다(파서만이 아니다)."""
    from scripts import answer_walk, verify_claims
    monkeypatch.setattr(verify_claims, "isolate", lambda: None)                       # conftest 가 이미 격리했다(전역 환경을 또 바꾸지 않는다)
    monkeypatch.setenv("AGRODSS_TODAY", _d(52).isoformat())                            # walk 가 바꾸는 날 — 끝나면 되돌린다
    rows = answer_walk.walk([_d(51), _d(53)], asks=("오늘 뭐 해야 하나",), says=((_d(52), "오늘 쪽파 조금 수확했다"),))
    by = {r["date"]: r["answer"] for r in rows if r["ask"] == "오늘 뭐 해야 하나"}
    assert HARVEST_ROW in by[_d(51).isoformat()] and HARVEST_ROW not in by[_d(53).isoformat()], by
    assert any(r["ask"].startswith("적고 넣음") and r["date"] == _d(52).isoformat() for r in rows)


def test_the_evidence_is_the_earliest_day_not_the_ledger_order():
    """근거는 **처음 한 날** — 원장 차례가 아니다(늦게 넣은 이른 날의 기록이 근거가 된다 · 원장 차례로 고르면 둘째 검사와 구분이 안 된다)."""
    _put("오늘 쪽파 조금 수확했다", _d(54))
    _put("10월 15일에 수확했다", _d(55))                                                # 늦게 넣었지만 더 이른 날(51일)
    assert _row(_d(56), HARVEST_ROW)["evidence"] == f"사건 수확 {_d(51).isoformat()}"


def test_the_stated_day_is_the_day_it_was_not_done():
    """말한 날(어제)이 못 한 날이다 — 오늘로 메우지 않는다 · 이은 줄의 날은 그대로."""
    d = _say("어제 비 때문에 수확 못 했다", _d(52))["drafts"][0]
    assert (d["observed_at"], d["planned_day"]) == (_d(51).isoformat(), _d(60).isoformat())


def test_choosing_the_kind_by_hand_measures_still_to_do_the_same_way():
    """손으로 「못 한 이유」 를 골라도 같은 정본(deferred_said) — 「비 때문에 못 했다」(작업 말 없음 · 본 것)를 못 한 이유로 고치면 아직 할 일."""
    m = _say("비 때문에 못 했다", _d(52))
    assert m["drafts"][0]["kind"] == "observation.note"
    d = chat.choose_kind(m["id"], "decision.noncompliance", today=_d(52))["drafts"][0]
    assert d["kind"] == "decision.noncompliance" and d.get("deferred") is True


def test_a_bad_day_is_refused_not_stored():
    with pytest.raises(ev.EventError):
        ev.add_noncompliance(SID, HARVEST_ROW, "비 때문에", _d(60).isoformat(), observed_at="어제")
