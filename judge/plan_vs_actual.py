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

from grid import schema as grid_schema
from ingest import events as ev
from ingest import media
from judge import plan, registry, units
from judge.envelope import AxisUse, Envelope, weakest
from judge.need import need_anchor
from judge.harvest_timing import GRID_GRADE
from schema import records as sch      # 조사 정본(sch.josa) — 조건 문면이 격자에서 오는 값이다

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


def primary_type(task_name: str) -> str | None:
    """그 계획 줄의 **첫** 사건 종류 — 못 한 이유를 그 줄에 잇는 열쇠(chat._plan_row_for). 한 일을 세는 표(task_event_types)와 한 벌이다.
    [W-47 2026-10-18] 잇는 쪽이 제 표(작업 어휘가 줄 이름에 들었는가)를 따로 써서 「출하 못 했다」(납품) · 「잔사 못 걷었다」(정리)가 그 줄에 안 붙었다 —
    판정은 납품 · 정리 기록으로 그 줄을 이행으로 세는데. 첫 종류만 보는 이유: 「약 못 쳤다」(방제)가 예찰 줄(예찰 · 방제로 이행)에 붙으면 안 본 것이 이유가 된다."""
    t = _types_for(task_name or "", registry.get(DECISION_ID).params)
    return t[0] if t else None


# [W-48 2026-10-18] 출하 판단이 없는 작기 — 출하 또는 저장 판단(stage_decisions)과 계획 대 실제의 출하 줄이 **같은 하나**를 쓴다.
# 전에는 그 문이 출하 판단에만 있어 같은 날 「출하 언제 해요」 는 「이번엔 할 일이 아닙니다」 인데 할 일 답은 10-28 부터 날마다 「놓침 — 사유를 묻는다: … 출하 또는
# 단기 저장」 이었다(같은 문이 계획 줄에 없다). 문을 둘째 층으로 옮기며 그 문이 막던 것을 다시 읽었다(§7.5 직렬 게이트 — 넓힐 때 경계를 본다):
#   ① 용도 글자에 「자가 · 시험」 이 **들어 있기만** 해도 닫혀 「자가 판매」 · 「시험 판매」 · 「몰 납품 시험」 이 출하 판단을 잃었다(측정 2026-10-18) — 파는 말이 있으면 열어 둔다
#   ② 계획 줄은 **출하 또는 단기 저장**이다 — 쪽파는 수일 안에 낸다(격자 출처 「저장성 낮음 — 수일 안」 · 마감은 작업일 + 3). 자가 작기에 거둔 뒤 단기 저장 안내가 필요
#      없다는 말은 어디에도 없다(D-8 은 「이번 작기 시험 재배(자가), 몰 납품은 봄 작기부터」 — 출하 · 저장 판단이 없다는 것은 세션의 읽기다). 그 줄은 농가에게 가는
#      **유일한 저장 안내**라 지우지 않는다: 창 안에서는 그대로 할 일이고, 마감이 지나도 **놓침으로 세지 않고 이유를 묻지 않는다**(출하가 없는 작기라 안 한 것이 놓친 것이
#      아니다 — 근거가 확실한 쪽만). 자가 작기에 저장 안내를 낼지는 발행자 몫(walk_findings W-49)
#   ③ [검토 2026-10-18] 몰 납품 여부(mall_supply)는 씨앗에만 있고 화면 · 채팅으로 바꿀 길이 없다 — 농가가 용도를 「몰 납품」 · 「판매」 로 넣어도 씨앗의 「아니오」 가 이겨
#      「몰 납품을 안 하는 작기라」 로 닫히고 출하 줄도 마감 뒤 말이 없었다. 용도 글자는 그 뒤에 농가가 적은 값이라 **파는 말이 이긴다** · 부정된 파는 말(「판매 안 함」)은
#      파는 말이 아니다 · 종구는 파는 말이 있어도 닫는다(그 용도의 출하 기준이 재배 달력에 없다 — 열면 답할 수 없는 납품일을 묻는다 · 계획에도 그 칸 할 일이 없다)
SELF_USE_WORDS = ("자가", "시험", "종구")      # 종구 — [발행자 전달 2026-10-03] 종구 생산은 출하 대상이 아니다(씨알을 남긴다)
SALE_WORDS = ("판매", "직판", "직거래", "납품", "출하")
_SALE_WORD = re.compile("|".join(SALE_WORDS))
# [검토 2026-10-18 둘째] 부정된 파는 말이 바로 뒤 「안 · 않 …」 만 봐서 「시험 재배(비판매)」 · 「판매는 안 함」 · 「판매 X」 · 「판매 계획 없음」 · 「판매용 아님」 · 「판매 불가」 ·
# 「미판매」 가 파는 말로 읽혀 자가 작기에 납품일을 묻고 마감 뒤 놓친 이유를 물었다. 앞의 비 · 미 · 안 · 못, 뒤의 조사 · 용 · 계획 + 부정을 본다.
# 자가 · 시험과 함께 「…부터」(「몰 납품은 봄 작기부터」 — D-8 의 그 말)면 이번 작기 얘기가 아니다(자가 쪽 · 근거가 확실한 쪽)
_SALE_NEG_BEFORE = re.compile(r"(?:(?<![가-힣])(?:안|못)\s*|[비미])$")
_SALE_NEG_AFTER = re.compile(r"(?:\s*(?:은|는|을|를|도|이|가|할|하는|용|용으로|목적|계획|예정))*\s*"
                             r"(?:하지\s*(?:않|말)|지\s*(?:않|말)|안(?=\s|[함해할한하])|않|없|아님|아니|금지|불가|[Xx×](?![가-힣A-Za-z]))")
_LATER_SEASON = re.compile(r"(?:은|는)?\s*(?:[^\s,·()]+\s+){0,2}[^\s,·()]*부터")
SHIP_TASK_KEY = "출하"                         # 격자 칸 5 「출하 또는 단기 저장」 — 출하 또는 저장 판단이 마감을 읽는 그 작업


def sale_negated_at(text: str, start: int, end: int) -> bool:
    """text[start:end] 의 파는 말(판매 · 팔 · 납품 …)이 부정됐는가 — 출하 문(not_shipping)과 채팅 용도 선언(parcels.use_declared)이 같은 하나를 쓴다."""
    return bool(_SALE_NEG_BEFORE.search(text[:start]) or _SALE_NEG_AFTER.match(text, end))


def sold(text: str) -> bool | None:
    """용도 글에 이번 작기에 **판다**는 말이 있는가 — True(부정 안 된 파는 말) · False(파는 말이 있으나 전부 부정 · 자가와 함께 다음 작기) · None(파는 말 없음)."""
    t = text or ""
    self_said = any(w in t for w in SELF_USE_WORDS)
    found = False
    for m in _SALE_WORD.finditer(t):
        found = True
        if sale_negated_at(t, m.start(), m.end()) or (self_said and _LATER_SEASON.match(t, m.end())):
            continue
        return True
    return False if found else None


def not_shipping(subject: dict[str, Any]) -> str | None:
    """이번 작기에 출하 판단이 **없으면** 그 까닭(농가 말 · 「…라」 까지), 있으면 None — 정본 하나(D-8 · 출하 판단 규칙 「필지 용도가 자가·시험이면 해당 없음」).
    종구 → 닫는다 · 파는 말(부정 안 된) → 연다 · 자가 · 시험 · 부정된 파는 말 → 닫는다 · 몰 납품을 안 한다고 적혀 있으면(mall_supply False) 닫는다 · 아니면 연다.
    [ⓐ 2026-10-18] 용도가 비었는데 몰 납품만 안 한다고 적혀 있으면 전에는 「이번 작기는 자가 용도라」 로 단정했다 — 근거는 몰 납품 안 함이라 그 말을 한다.
    [검토 2026-10-18 둘째] 「판매 안 함」 은 몰 납품 값이 비어 있어도 닫는다 — 새 밭은 그 값이 늘 비어 있고 넣을 길이 없어, 판매 안 한다고 적은 농가에게 납품일을 물었다"""
    use = str(subject.get("use") or "")
    if "종구" in use:
        return f"이번 작기는 {use} 용도라"
    said_sold = sold(use)
    if said_sold:
        return None
    if said_sold is False or any(w in use for w in SELF_USE_WORDS):
        return f"이번 작기는 {use} 용도라"
    if subject.get("mall_supply") is False:
        return "이번 작기는 몰 납품을 안 하는 작기라"
    return None


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
        return False, (f"{d.params.get('condition')}{sch.josa(d.params.get('condition'), '이')} 원장에 없다 — 안 했다고 보지 않고 사유도 묻지 않는다. "
                       f"보신 것이 있으면 적어 주시면(채팅 한 줄) 답이 바뀐다({d.params.get('condition_source')})")
    return None


def reason_for(reasons: list[dict[str, Any]], task: str, work_date: str) -> dict[str, Any] | None:
    """계획표 한 줄(작업명 · 계획일)에 기록된 불이행 사유. 계획 대 실제와 단계 결정(웃거름 등)이 **같은 키**로 잇는다 — 한 벌.
    [W-14 2026-10-14] 한 줄에 사유가 여럿이면 **나중에 넣은 것**(원장은 넣은 차례로 쌓인다) — 「비 때문에 못 했다」 뒤에 「안 하기로 했다」 를 넣으면 뒤의 말이 그 줄의 지금이다.
    전에는 첫 사유가 이겼다(못 한 이유가 줄을 닫던 때에는 두 번째 사유가 붙을 자리가 없어 드러나지 않았다)."""
    hits = [r for r in reasons if r.get("kind", "decision.noncompliance") == "decision.noncompliance"
            and r.get("planned_task") == task and r.get("planned_day") == work_date]
    return hits[-1] if hits else None


def reason_closes(rec: dict[str, Any], today: date, deadline: date) -> bool:
    """그 사유가 계획 줄을 **지금** 닫는가 — 계획 대 실제와 웃거름 판단이 같은 하나를 쓴다(두 벌이면 두 층이 다른 답을 낸다).

    [W-14 2026-10-14] 「비 때문에 수확 못 했다」(10-14)를 넣으면 수확 줄이 그 자리에서 '사유 기록됨' 이 되어 할 일 답에서 **수확 기간 내내 사라졌다**.
    줄을 닫던 규칙(2026-09-20)의 계기는 「웃거름 주지 않고 수분공급만」 — **안 하기로 한** 결정이었다. 그 조건이 코드에서 떨어져
    「못 했다 · 아직 · 미뤘다」(그 일은 아직 할 일이다)까지 닫았다(G1 반대형 — 조건 탈락). 그래서 갈래를 되살린다:
      안 하기로 함(deferred 없음)   넣은 그 자리에서 닫는다 — 옛 규칙 그대로(시스템이 결정을 대신 내리지 않는다)
      못 함 · 미룸(deferred)        마감까지는 줄을 그대로 두고(할 일에 남는다) 사유는 근거에 싣는다 · 마감이 지나면 닫는다(그 사유가 놓친 이유다 — 다시 묻지 않는다)
    """
    return not rec.get("deferred") or today > deadline


def match_window(p: dict[str, Any], tol: int) -> tuple[date, date]:
    """계획 줄 하나가 **한 일을 세는 날들**(양끝 포함) — 정본 하나. 계획 대 실제 · 웃거름 판단 · 못 한 이유 잇기(chat._plan_row_for)가 같은 창을 본다.

    위끝은 마감(재시도 마감 — 없으면 작업일 + 허용 폭). 아래끝은 작업일 − 허용 폭과 **그 칸이 열리는 날** 중 이른 날.
    [W-15 2026-10-14] 아래끝이 작업일 − 3 뿐이라 수확 칸 첫날(10-14)부터 거둔 기록이 10-20 까지 계획에 안 잡혔다 — 같은 날 수확 시기 판단은
    「지금 기간 안」 이었다. 처방 직후 전수: 할 일 열둘 중 열이 같은 꼴이었다(칸이 열린 뒤 작업일 − 3 전에 한 일이 안 잡힌다 — 예찰 경보는 칸 3 첫날부터 ·
    보식 판단은 칸 2 첫날부터 · 수확은 칸 5 첫날부터 그 일을 말한다). 칸 창은 양끝 포함이라 경계일은 앞 칸 줄과 겹칠 수 있다 — 사건 하나는 **앞 줄 하나**에만
    붙는다(judge 의 used_events · 사진의 used_media 와 같은 약속 · B4 「경계일은 앞 칸」).
    [검토 2026-10-14] **조건부 줄**(… 시 · 결정 등록부의 조건부 작업 — 보식 · 웃거름 2회(필요 시) · 관수(건조 시))은 넓히지 않는다 — 그 줄은 사유를 묻지 않으므로
    넓혀서 고칠 것이 없고, 넓히면 다른 뜻의 기록이 그 줄을 채웠다(이틀에 걸쳐 심은 둘째 날의 파종 기록 → 보식 이행 · 마감 넘긴 웃거름 1회 → 2회 이행)."""
    wd = date.fromisoformat(p["work_date"])
    lo = wd - timedelta(days=tol)
    if p.get("stage_from_date") and conditional_of(p.get("task", "")) is None:
        lo = min(lo, date.fromisoformat(p["stage_from_date"]))
    hi = date.fromisoformat(p["deadline_date"]) if p.get("deadline_date") else wd + timedelta(days=tol)
    return lo, hi


def _matched_event(p: dict[str, Any], evts: list[dict[str, Any]], tol: int, params: dict[str, Any],
                   used: set[int] | None = None) -> dict[str, Any] | None:
    """그 줄을 이행한 사건 — 창 안의 같은 종류 중 **가장 이른 것**(그 일을 처음 한 날 · 같은 날이면 원장 차례). used 에 든 사건(앞 줄이 이미 쓴 것)은 건너뛴다.
    [W-15] 창이 칸 첫날까지 넓어지자 한 사건이 두 줄에 걸릴 자리가 생겼다(시비 30일 = 웃거름 1회 마감 = 웃거름 2회 칸 첫날 · 파종 1~14일 = 밑거름 · 파종 마감 안 = 보식 칸).
    이른 것을 고르는 이유 둘: ① 기준점(파종 0일)과 농가의 파종 기록(5일)이 둘 다 있을 때 앞 줄(밑거름 · 파종)이 기준점을 쓰고 기록은 보식 줄에 남는다
    ② 뒤에 넣은 기록이 근거를 바꾸지 않는다 — 작업일에 가까운 것을 고르면 둘째 수확 기록이 근거 날짜를 갈아 「누르면 판단이 읽습니다」(넣은 셈)가 근거만 바뀐 것을 읽음으로 셌다"""
    types = _types_for(p["task"], params)
    if not types:
        return None
    lo, hi = match_window(p, tol)
    hits = [(e["observed_at"][:10], n, e) for n, e in enumerate(evts)
            if e.get("type") in types and id(e) not in (used or set()) and lo <= date.fromisoformat(e["observed_at"][:10]) <= hi]
    return min(hits, key=lambda h: h[:2])[2] if hits else None


def judge(subject: dict[str, Any], today: date | None = None, evts: list[dict[str, Any]] | None = None,
          videos: list[dict[str, Any]] | None = None, reasons: list[dict[str, Any]] | None = None,
          notes: list[dict[str, Any]] | None = None) -> Envelope:
    today = today or date.today()
    as_of = _now()
    sid = subject.get("id", "?")
    d = registry.get(DECISION_ID)
    unit, miss = grid_schema.load_unit(subject)
    if miss is not None:                                   # [U-23] 격자를 못 읽은 것은 '할 일 아님' 이 아니다
        return units.envelope_for(miss, DECISION_ID, sid, as_of)
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", DECISION_ID, sid, as_of,
                        missing=[need_anchor("계획표의 날짜는 심은 날에서 센다")], result={"why": "기준점이 없다", "summary": "심은 날을 알면 계획표를 셉니다"})
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
    no_ship = not_shipping(subject)                                                # [W-48] 출하 또는 저장 판단과 같은 문
    ask = []
    prep = []
    # [경계일 촬영 2026-09-21 · B4 약속이 안 닿은 지점] 칸 창은 양끝 포함이라 **경계일은 두 칸에 걸린다**. 실측: 9/24 사진 한 장이
    # 칸 3(마감)과 칸 4(작업일)를 **둘 다 이행**으로 만들었다 — 한 번 찍었는데 두 단계가 기록된 것으로 센다(거짓 이행 · 되먹임 오염).
    # 약속은 이미 정해져 있었다: `grid.capture` 가 *"경계일은 **앞 칸**(첫 매치)"* 이라 적고, 그 주석이 **"판정기마다 따로 창을
    # 비교하면 그 약속이 갈린다"** 고까지 경고해 두었다. 단계 판정과 경보는 그 정본으로 왔는데 **촬영 대조만 제 창을 따로 비교**했다.
    # 그래서 여기서도 같은 약속을 지킨다 — 사진 한 장은 **가장 앞 칸 하나**에만 붙는다(쓰인 것은 다시 쓰지 않는다).
    used_media: set[str] = set()
    used_events: set[int] = set()           # [W-15] 사건도 같은 약속 — 한 기록은 앞 줄 하나에만(창이 칸 첫날까지 넓어져 겹칠 자리가 생겼다)
    for p in plan.from_unit(unit, anchor_d, subject.get("cert")):
        wd = date.fromisoformat(p["work_date"])
        dl = date.fromisoformat(p["deadline_date"]) if p.get("deadline_date") else wd + timedelta(days=tol)
        status, evidence, evidence_ref = None, None, None
        if p["kind"] == "plan.capture":
            hit = [v for v in videos
                   if p["work_date"] <= (v.get("observed_at") or "")[:10] <= p["deadline_date"] and v.get("id") not in used_media]
            if hit:
                used_media.add(hit[0].get("id"))
                what = "사진" if hit[0].get("kind") == media.KIND_IMAGE else "영상"      # 사진을 '영상' 이라 부르던 자리
                # [내부 값 전수 2026-10-04] 근거 칸이 `영상 vid_… (날짜)` 였다 — 기록 id 를 **사람이 읽는 문장 안에** 구워 넣으면 화면이 그것을
                # 떼어낼 수 없다. 문장과 id 를 나눠 둔다(id 는 `evidence_ref` 로 가고 화면은 그것을 `title` 에 내린다)
                status, evidence, evidence_ref = "이행", f"{what} ({hit[0].get('observed_at', '')[:10]})", hit[0].get("id")
        else:
            m = _matched_event(p, evts, tol, d.params, used_events)
            if m:
                used_events.add(id(m))
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
            # [W-14 2026-10-14] 못 한 이유(못 · 아직 · 미뤘다)는 마감까지 줄을 닫지 않는다 — 근거에만 싣는다(reason_closes 정본 · 웃거름 판단과 한 벌)
            said = f" · 못 한 이유({rec.get('observed_at', '')[:10]}): {sch.quote(rec['reason'], 80)}" if rec else ""
            if rec and reason_closes(rec, today, dl):
                # [발행자 2026-09-20 "웃거름 주지 않고 …"] 안 하기로 한 이유가 기록됐으면 마감 전이라도 '미이행'이 아니다 —
                # 전에는 마감 뒤에만 봐서, 마감 안에 말한 사유가 닷새 동안 '미이행'으로 보였다. 작목 무관(계획표 줄과 같은 키로 잇는다)
                status, evidence = "사유 기록됨", rec["reason"]
            elif today < wd:
                status = "예정"
                evidence = said.removeprefix(" · ") or None                    # 마감 전의 못 한 이유 — 줄은 그대로 · 근거에만
                pr = p.get("prep_date_rental")
                if pr and date.fromisoformat(pr) <= today:
                    prep.append({"task": p["task"], "work_date": p["work_date"], "prep_date": pr})
            elif today <= dl:
                status, evidence = "미이행", f"마감까지 {(dl - today).days}일 (재시도 {'가능' if p['retry_possible'] else '불가'}){said}"
            elif no_ship and p["kind"] != "plan.capture" and SHIP_TASK_KEY in p["task"]:
                # [W-48] 출하가 없는 작기 — 마감이 지나도 놓친 것이 아니다(창 안에서는 위 갈래 그대로 할 일 · 한 기록은 위에서 이행). 이유를 묻지 않는다
                status, evidence = "기록 없음", (f"{no_ship} 출하 판단이 없습니다 — 마감이 지나도 놓침으로 세지 않고 이유를 묻지 않습니다"
                                                 f"(마감 {dl.isoformat()} 안에 단기 저장을 하셨으면 그 날짜로 적어 주시면 한 일로 셉니다)")
            else:
                status, evidence = "놓침", f"마감 {p['deadline_date'] or p['work_date']} 지남 — 불이행 사유를 묻는다"
                ask.append({"task": p["task"], "work_date": p["work_date"], "stage": p["stage"]})
        counts[status] += 1
        rows.append({"stage": p["stage"], "task": p["task"], "work_date": p["work_date"], "deadline_date": p.get("deadline_date"),
                     "status": status, "evidence": evidence, "evidence_ref": evidence_ref, "materials": p.get("materials"), "kind": p["kind"],
                     "source_note": p.get("source_note", ""), "fixable_by": p.get("fixable_by"),   # [WO-ASK-01 §10 지점 2026-10-03] 할 일도 추론값 — 누가 고칠 수 있는가를 답까지
                     # [W-14] 그 줄이 한 일을 세기 시작하는 날 — 못 한 이유를 이을 때 같은 창을 본다(chat._plan_row_for · 창이 아직 안 열린 줄에 잇지 않는다)
                     "match_from": (p["work_date"] if p["kind"] == "plan.capture" else match_window(p, tol)[0].isoformat()),
                     "match_to": (p["deadline_date"] if p["kind"] == "plan.capture" else match_window(p, tol)[1].isoformat())})
    inputs = [AxisUse("anchor", anchor, subject.get("source", "farmer"), "cultivation_unit", "관측")]
    grades = ["관측", GRID_GRADE.get(unit["unit"].get("confidence", "하"), "추정")]
    return Envelope(
        "판단함", DECISION_ID, sid, as_of, inputs=inputs, grade=weakest(grades),
        revisit_at=(today + timedelta(days=d.revisit_days)).isoformat(),
        result={"days_since_anchor": (today - anchor_d).days, "counts": counts, "rows": rows,
                "ask_reason": ask, "prep_now": prep,
                "events_used": len(evts) - 1, "videos_used": len(videos), "reasons_used": len(reasons),
                # [앞날 걷기 2026-10-07] 용도를 넣으면 「다음 예정」 이 **조용히** 비워졌다(4 → 0 실측). 그 사실이 메모에만 있어 농가 답은 아무 말도 못 했다 —
                # 구조로도 싣는다(risk_alert 과 **같은 키** · 2층이 메모 문장을 파싱하면 어휘가 두 벌이 된다)
                "use_gap_stages": [f"{s.get('order')}. {s.get('name')}" for s in unit.get("stages", []) if plan.use_gapped(unit, s)],
                "use_gap_use": unit.get("_use") if any(plan.use_gapped(unit, s) for s in unit.get("stages", [])) else None},
        notes=[grid_schema.source_note(unit), f"작업↔사건 대응: {d.params['source']}",
               "사건 원장·영상 원장은 축이 아니라 기록 — inputs 에 축으로 싣지 않는다",
               # [종구 2026-10-03] 용도 기준이 없는 칸의 할 일은 계획표에 없다(plan.from_unit 이 걷는다) — 비어 있는 이유를 말한다(조용한 빈칸 금지)
               *[f"용도 '{unit.get('_use')}' — 칸 {s.get('order')}({s.get('name')})의 할 일은 그 용도의 기준이 재배 달력에 없어 계획표에 두지 않는다(발행자 정본 by_use 대기)"
                 for s in unit.get("stages", []) if plan.use_gapped(unit, s)]],
    )
