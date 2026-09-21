# -*- coding: utf-8 -*-
# FILE: judge/plan_vs_actual.py
# ROLE: [M-10 ③ · F 계획 대 실제 대조 · J 되먹임] 계획(격자)과 사건 원장을 대조한다 — "놓친 것을 아는 것도 판단".
#
#   이행      계획 작업일 ± tolerance 안에 같은 종류의 사건이 있다 (파종은 기준점 자체가 사건 · 촬영은 영상 원장)
#   예정      작업일이 아직 안 왔다
#   미이행    작업일이 지났고 사건이 없지만 재시도 마감 전 — 남은 날수를 낸다
#   놓침      마감도 지났다 — 불이행 사유를 묻는다(I-3 §5: 창이 지났을 때 묻는다). 사유가 있으면 '기록됨'
#
# 선제 발화(F): 예정 중 준비 착수일(임대 기준)이 오늘 안이면 표시한다.
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ingest import events as ev
from ingest import media
from judge import plan, registry
from judge.envelope import AxisUse, Envelope, weakest
from judge.harvest_timing import GRID_GRADE, _load_unit

DECISION_ID = "plan_vs_actual"

registry.register(registry.Decision(
    id=DECISION_ID,
    name="계획 대 실제 대조",
    required_axes=("anchor",),
    optional_axes=(),
    forbidden_axes=(),
    rule=("격자 작업 칸을 기준점으로 날짜화한 계획과 사건 원장을 대조한다. 작업일 ±tolerance 안 같은 종류의 사건이면 이행, "
          "작업일 전이면 예정, 지났고 마감 전이면 미이행(남은 날수), 마감도 지났으면 놓침 — 이때 불이행 사유를 묻는다. "
          "파종은 기준점이 곧 사건, 촬영은 영상 원장이 증거. 사건 원장은 축이 아니라 기록이다."),
    revisit_days=1,
    params={
        "tolerance_days": 3,
        "task_event_types": {"파종": ("파종",), "정식": ("정식",), "소독": ("소독", "방제"), "관수": ("관수",), "보식": ("보식", "파종"),
                             "예찰": ("예찰", "방제"), "웃거름": ("시비",), "밑거름": ("시비", "파종"), "제초": ("제초",),
                             "배수": ("배수",), "수확": ("수확",), "출하": ("납품", "저장"), "저장": ("저장", "납품"),
                             "잔사": ("정리",), "정리": ("정리",)},
        "source": "작업명 키워드 ↔ 사건 종류 대응 — 추론(격자 작업명 문면), 발행자 검토 대기",
    },
))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _types_for(task_name: str, params: dict[str, Any]) -> tuple[str, ...]:
    for k, v in params["task_event_types"].items():
        if k in task_name:
            return v
    return ()


_COND = re.compile(r"\((?:[^()]*\s)?시\)")   # "관수(건조 시)" · "웃거름 2회(필요 시)" — 격자 작업명의 조건 표기


def _conditional(task_name: str) -> bool:
    return bool(_COND.search(task_name or ""))


def conditional_of(task_name: str, notes: list[dict[str, Any]] | None = None,
                   since: str | None = None) -> tuple[bool, str] | None:
    """이 격자 작업이 **조건부인가**, 그리고 그 조건이 **채워졌는가** — 조건 판정의 정본 하나.

    출처가 둘이고 아는 것의 깊이가 다르다(두 벌 진실이 아니라 두 층위다).

      ① 격자 작업명의 괄호 표기 "(… 시)"   조건부라는 것만 안다 — 조건 판정 규칙이 없다 → 언제나 '조건부'
      ② 결정 등록부의 `conditional_task`   조건이 무엇인지도 안다 → **채워졌으면 보통 경로**(놓침이 살아 있다)

    ②가 이 회차에 생긴 이유: '보식' 은 이름에 표기가 없어 ①에 안 걸렸고, 그래서 계획 대 실제는 '놓침 — 사유를 묻는다',
    `judge_replant` 는 '출현 관찰이 없으니 판단 불가(데이터)' 로 **한 작업에 두 층이 다른 답**을 냈다.
    조건이 무엇인지는 결정 등록부가 이미 알고 있었다 — 계획 대 실제가 그것을 안 읽었을 뿐이다.

    돌려주는 값: 조건부가 아니면 None, 맞으면 (조건이 채워졌는가, 화면에 적을 사유).
    """
    if _COND.search(task_name or ""):
        return False, "조건('… 시')이 붙은 작업 — 조건 판정 규칙 없음, 놓침으로 세지 않는다"
    for d in registry.all_decisions().values():
        key = d.params.get("conditional_task")
        if not key or key not in (task_name or ""):
            continue
        words = tuple(d.params.get("words") or ())
        seen = [o for o in (notes or [])
                if (not since or (o.get("observed_at") or "") >= since) and any(w in (o.get("text") or "") for w in words)]
        if seen:
            # 조건이 섰다 → **보통 경로로 돌려보낸다**(그때는 안 한 것이 진짜 놓침이고 사유를 묻는 것이 맞다).
            # 조건부를 넓히면서 이 갈래를 안 두면 막는 것만 보고 통과하는 것을 안 보는 상태가 된다(게이트는 양방향).
            return True, f"조건({d.params.get('condition')}) 관찰 {len(seen)}건 — 조건이 섰다"
        # [발행자 계약 지적 2026-09-21] 첫 판은 *"안 한 것이 아니라 **할 일이 없었던 것**"* 이라고 적었다 — 아는 것보다 더 단정했다.
        # 원장에 관찰이 없다는 것은 **조건이 없었다는 뜻이 아니라 아무도 안 적었다는 뜻**일 수 있다. 결주가 실제로 있었는데
        # 안 본 경우를 그 문장이 가린다. I-1 §2-6 의 '해당 없음' 은 *"아무리 채워도 안 바뀐다"* 인데 이쪽은 **채우면 바뀐다** —
        # 곧 계약상 '판단 불가(데이터)' 자리다. 그래서 문면도 그렇게 적는다: 없는 것은 관찰이고, 넣으면 답이 바뀐다.
        return False, (f"{d.params.get('condition')}이 원장에 없다 — 안 했다고 보지 않고 사유도 묻지 않는다. "
                       f"보신 것이 있으면 적어 주시면(채팅 한 줄) 답이 바뀐다({d.params.get('condition_source')})")
    return None


def reason_for(reasons: list[dict[str, Any]], task: str, work_date: str) -> dict[str, Any] | None:
    """계획표 한 줄(작업명 · 계획일)에 기록된 불이행 사유. 계획 대 실제와 단계 결정(웃거름 등)이 **같은 키**로 잇는다 — 한 벌."""
    return next((r for r in reasons if r.get("kind", "decision.noncompliance") == "decision.noncompliance"
                 and r.get("planned_task") == task and r.get("planned_day") == work_date), None)


def _matched_event(p: dict[str, Any], evts: list[dict[str, Any]], tol: int, params: dict[str, Any]) -> dict[str, Any] | None:
    types = _types_for(p["task"], params)
    if not types:
        return None
    wd = date.fromisoformat(p["work_date"])
    lo, hi = wd - timedelta(days=tol), (date.fromisoformat(p["deadline_date"]) if p.get("deadline_date") else wd + timedelta(days=tol))
    for e in evts:
        if e.get("type") in types and lo <= date.fromisoformat(e["observed_at"][:10]) <= hi:
            return e
    return None


def judge(subject: dict[str, Any], today: date | None = None, evts: list[dict[str, Any]] | None = None,
          videos: list[dict[str, Any]] | None = None, reasons: list[dict[str, Any]] | None = None,
          notes: list[dict[str, Any]] | None = None) -> Envelope:
    today = today or date.today()
    as_of = _now()
    sid = subject.get("id", "?")
    d = registry.get(DECISION_ID)
    unit = _load_unit(subject)
    if unit is None:
        return Envelope("해당 없음", DECISION_ID, sid, as_of, result={"why": "격자 단위가 없다"})
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", DECISION_ID, sid, as_of,
                        missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일(사건 입력)"}], result={"why": "기준점이 없다"})
    anchor_d = date.fromisoformat(anchor)
    evts = evts if evts is not None else ev.list_records(sid, "event")
    videos = videos if videos is not None else media.list_records(sid)
    reasons = reasons if reasons is not None else ev.list_records(sid, "decision.noncompliance")
    # [§7.5 관문의 입력 2026-09-21] 조건 판정이 읽을 관찰 — 호출부가 안 넘기면 조건부 갈래가 **아무것도 못 거르고 통과시킨다**
    # (관문은 멀쩡히 서 있고 하는 일이 없는 상태). 그래서 기본값은 None 이 아니라 원장에서 직접 읽는다.
    notes = notes if notes is not None else ev.list_records(sid, "observation.note")
    # 기준점은 그 자체가 사건이다(농가 행위 기준점)
    evts = list(evts) + [{"type": "파종", "observed_at": anchor, "id": "anchor", "source": subject.get("source", "farmer")}]
    tol = int(d.params["tolerance_days"])
    rows = []
    counts = {"이행": 0, "예정": 0, "미이행": 0, "놓침": 0, "사유 기록됨": 0, "조건부": 0, "기록 없음": 0, "종료 뒤": 0}
    ended = subject.get("ended_at") if subject.get("status") == "종료" else None   # [시점 걷기 2026-09-20] 작기 종료 뒤 계획은 놓침이 아니다
    ask = []
    prep = []
    for p in plan.from_unit(unit, anchor_d, subject.get("cert")):
        wd = date.fromisoformat(p["work_date"])
        dl = date.fromisoformat(p["deadline_date"]) if p.get("deadline_date") else wd + timedelta(days=tol)
        status, evidence = None, None
        if p["kind"] == "plan.capture":
            hit = [v for v in videos if p["work_date"] <= (v.get("observed_at") or "")[:10] <= p["deadline_date"]]
            if hit:
                status, evidence = "이행", f"영상 {hit[0].get('id')} ({hit[0].get('observed_at', '')[:10]})"
        else:
            m = _matched_event(p, evts, tol, d.params)
            if m:
                status, evidence = "이행", f"사건 {m.get('type')} {m.get('observed_at', '')[:10]}"
        cond = conditional_of(p["task"], notes, since=anchor) if status is None else None
        if cond and not cond[0]:
            # [코드 평가 B13 + 두 층 불일치 2026-09-21] 조건부 작업은 안 했다고 놓친 것이 아니다 — 사유를 묻지 않고 '조건부'로 둔다.
            # 조건이 **채워졌으면**(cond[0]) 여기서 걸리지 않고 보통 경로로 내려간다 — 그때는 놓침이 맞고 사유를 묻는 것이 맞다
            status, evidence = "조건부", cond[1]
        elif status is None and p["kind"] == "plan.capture" and wd < anchor_d:
            # 기준점 이전 촬영(종구 준비 칸) — 기준점을 뒤에 등록한 재배 단위는 소급 촬영이 있을 수 없다. 놓침이 아니라 기록 없음
            status, evidence = "기록 없음", "기준점 이전 작업 — 소급 촬영 불가, 사유를 묻지 않는다"
        if status is None and ended and p["work_date"] > ended:
            status, evidence = "종료 뒤", f"작기 종료({ended}) 뒤의 계획 — 놓침으로 세지 않고 사유를 묻지 않는다"
        if status is None:
            rec = reason_for(reasons, p["task"], p["work_date"])
            if rec:
                # [발행자 2026-09-20 "웃거름 주지 않고 …"] 안 하기로 한 이유가 기록됐으면 마감 전이라도 '미이행'이 아니다 —
                # 전에는 마감 뒤에만 봐서, 마감 안에 말한 사유가 닷새 동안 '미이행'으로 보였다. 작목 무관(계획표 줄과 같은 키로 잇는다)
                status, evidence = "사유 기록됨", rec["reason"]
            elif today < wd:
                status = "예정"
                pr = p.get("prep_date_rental")
                if pr and date.fromisoformat(pr) <= today:
                    prep.append({"task": p["task"], "work_date": p["work_date"], "prep_date": pr})
            elif today <= dl:
                status, evidence = "미이행", f"마감까지 {(dl - today).days}일 (재시도 {'가능' if p['retry_possible'] else '불가'})"
            else:
                status, evidence = "놓침", f"마감 {p['deadline_date'] or p['work_date']} 지남 — 불이행 사유를 묻는다"
                ask.append({"task": p["task"], "work_date": p["work_date"], "stage": p["stage"]})
        counts[status] += 1
        rows.append({"stage": p["stage"], "task": p["task"], "work_date": p["work_date"], "deadline_date": p.get("deadline_date"),
                     "status": status, "evidence": evidence, "materials": p.get("materials"), "kind": p["kind"]})
    inputs = [AxisUse("anchor", anchor, subject.get("source", "farmer"), "cultivation_unit", "관측")]
    grades = ["관측", GRID_GRADE.get(unit["unit"].get("confidence", "하"), "추정")]
    return Envelope(
        "판단함", DECISION_ID, sid, as_of, inputs=inputs, grade=weakest(grades),
        revisit_at=(today + timedelta(days=d.revisit_days)).isoformat(),
        result={"days_since_anchor": (today - anchor_d).days, "counts": counts, "rows": rows,
                "ask_reason": ask, "prep_now": prep,
                "events_used": len(evts) - 1, "videos_used": len(videos), "reasons_used": len(reasons)},
        notes=[f"격자 출처: {unit['unit'].get('source', '?')}", f"작업↔사건 대응: {d.params['source']}",
               "사건 원장·영상 원장은 축이 아니라 기록 — inputs 에 축으로 싣지 않는다"],
    )
