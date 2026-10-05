# -*- coding: utf-8 -*-
"""[검토표 ①⑤a 2026-09-29 · 발행자 승인 "제안 순서대로"] 자기 점검 화면 — 발행자가 손으로 하던 '확인 셋' 을 화면이 스스로 돌린다.

왜 — 핸드오버 §5 ⑧ 검토표: ① 확인 셋(㉠ 엔터 · ㉡ 증상 두 문장 · ㉢ /judge 카드)과 ⑤a "내일 날씨 어때" 는 사람이 매 판마다
채팅에 쳐 보고 세션에 붙이던 일이다. 셋 중 둘(㉡ · ㉢)과 ⑤a 는 서버가 같은 함수를 돌려 볼 수 있다 — `classify` 는 순수 함수이고
`answer` 는 `judgments_for(said=)` 로 **저장 없이** 판정한다. ㉠(엔터)은 브라우저 안의 동작이라 서버가 못 본다 — 그 사실을 화면이 말한다.

규율:
  읽기 전용   일지·원장에 아무것도 넣지 않는다(검사가 파일 수를 전후로 센다). 물음은 `answer` 로만 — `send` 는 원장에 쓴다.
  정직        "맞다" 는 기대와 실제를 대조해서만 나온다 — 대조 없이 맞다고 말하는 것은 update.bat 이 "돌고 있을 것" 이라 주장하던 형태.
  시점        걸린 시간을 줄마다 적는다(원천이 죽어 있으면 날씨 한 줄이 최대 60초 — §5 ⑦ 의 그 측정을 화면이 상시로 한다).
"""
from __future__ import annotations

import html
from datetime import date, datetime
from typing import Any

from ingest import probes as _probes      # 문장 목록은 ingest 가 읽는다 — 4층은 파일을 직접 열지 않는다

# 발행자 몫 ① 의 그 두 문장(대장 페이지 「① 확인 셋」 과 같은 문면) — 다른 말로 물어도 같은 답이어야 한다
SYMPTOM_QUESTIONS = ("잎 끝이 누렇게 되는데 왜 그런가요", "잎이 노래지는데 어떻게 해야 하나")
WEATHER_QUESTION = "내일 날씨 어때"
DROUGHT_QUESTION = "가뭄이 심한데 물 줘야 하나"      # [D-20 2026-09-29] 관측 원천(기상청 지난 일강수)이 붙었는지는 이 답의 괄호로 보인다
CARD_DECISION = "symptom_triage"
BROWSER_ONLY = "㉠ 엔터로 보내기(Shift+Enter 는 줄바꿈) — 브라우저 안의 동작이라 화면이 스스로 볼 수 없다. 세션의 걷기 도구가 본다"
NO_SUBJECT = "심은 날이 적힌 목록이 없어 점검할 재료가 없다 — 새 채팅에서 작목과 심은 날을 넣으면 여기가 채워진다"

# [발행자 2026-10-04 "단문도 해석하지 못하고 있는지 확인"] 문장 형태 점검 — 이미 틀린 여섯이 전부 단문이었고, 분류가 **명사**를 보는데 사람의 물음은 **동사·어미**가 뜻을 정한다
# ("관수했다" 는 한 일 · "관수를 알려줘" 는 조회 · "관수해야 하나" 는 판단). 같은 명사 × 다른 어미 · 같은 뜻 × 다른 표현을 저장 없는 길로 돌려 기대와 실제를 대조한다.
# 기대 종류는 **발행자가 붙인다** — 세션이 붙이면 채점자와 응시자가 같다. 기대가 없는 줄은 그렇다고 보인다(FILL_ME). 틀린 줄이 쌓이면 WO-LLM 비교 세트의 재료다 —
# 실사용 측정(/changes 「종류 고침」)과는 출처가 다르니 섞지 않고 여기서만 센다.
PROBES_PATH = str(_probes.PATH)
PROBES_TITLE = "문장 형태 점검 — 같은 명사 × 다른 어미 · 같은 뜻 × 다른 표현"
FILL_ME = "기대 종류 — 발행자가 붙일 것"
FILL_HOW = "줄 끝 빈칸에 종류 하나만 적어 세션에 보내시면 됩니다 — 줄을 지우거나 고치지 않으셔도 됩니다."
PROBES_BROKEN = "문장 목록 파일을 못 읽었다 — 다른 점검은 그대로 돈다"
NO_ROUTE = "어느 판단으로도 안 간다"


def probes() -> dict[str, Any]:
    return _probes.load()


def route_of(text: str, subject: dict[str, Any] | None) -> str | None:
    """물음이 어느 판단으로 가는가 — `chat.answer_with_asks` 와 같은 순서(증상 어휘 → 조회 → 주제). 저장 없음."""
    from ingest import chat
    if chat.symptom_in(text, chat.grid_symptom_words(subject)):
        return "symptom_triage"
    return chat.topic_of(text)


def _route_said(route: str | None) -> str:
    from frontend import words
    from ingest import chat
    if route is None:
        return NO_ROUTE
    if route == chat.LOOKUP_ID:
        return "일지 조회"
    return words.decision(route)


def utterances(today: date, subject: dict[str, Any] | None) -> dict[str, Any]:
    """문장마다 실제 종류(classify — 순수 함수)와 경로. 기대가 있는 줄만 맞다/다르다 · 없는 줄은 None(발행자가 붙일 것)."""
    from ingest import chat, dropped
    try:
        doc = probes()
    except (OSError, ValueError) as ex:                       # 깨진 목록 — 화면이 죽지 않고 이유를 말한다(조용한 실패 금지 · 결정 답 파일과 같은 형태) · /changes 에도 남긴다
        why = f"{type(ex).__name__}: {ex}"
        dropped.note(_probes.DROP_WHERE, _probes.PATH.name, why)
        return {"groups": [], "with_expected": 0, "without_expected": 0, "ok": 0, "differ": 0, "error": why}
    groups, with_e, without_e, ok_n, differ = [], 0, 0, 0, 0
    for g in doc.get("groups", []):
        rows = []
        for r in g.get("rows", []):
            text = r["text"]
            drafts = chat.classify(text, today, subject=subject)
            actual = drafts[0]["kind"] if drafts else None
            route = route_of(text, subject) if actual == "question" else None
            exp, exp_route = r.get("expected"), r.get("expected_route")
            if exp is None:
                ok = None
                without_e += 1
            else:
                ok = actual == exp and (exp_route is None or route == exp_route)
                with_e += 1
                ok_n += 1 if ok else 0
                differ += 0 if ok else 1
            rows.append({"text": text, "actual": actual, "actual_said": chat.KIND_PLAIN.get(actual, actual or ""), "route": route,
                         "route_said": _route_said(route) if actual == "question" else "", "expected": exp,
                         "expected_said": chat.KIND_PLAIN.get(exp, exp) if exp else "", "expected_route": exp_route,
                         "expected_route_said": _route_said(exp_route) if exp_route else "", "expected_note": r.get("expected_note") or "", "ok": ok})
        groups.append({"name": g.get("name", ""), "rows": rows})
    return {"groups": groups, "with_expected": with_e, "without_expected": without_e, "ok": ok_n, "differ": differ}


def _mine(said: str) -> str:
    """사람이 쓴 글(물음 문장 · 발행자 메모 · 묶음 이름) — 낱말 표를 대지 않는다. 이 화면은 페이지를 통째로 표에 넣으므로 싸 두지 않으면 쓴 말이 바뀌어 돌아온다."""
    from frontend import words
    return words.mine(said)


def _utterance_html(u: dict[str, Any] | None, e) -> str:
    if not u:
        return ""
    if u.get("error"):
        return f'<h2 style="font-size:15px;margin-top:18px">{e(PROBES_TITLE)}</h2><p class="err">{e(PROBES_BROKEN)} — {e(u["error"])}</p>'
    out = [f'<h2 style="font-size:15px;margin-top:18px">{e(PROBES_TITLE)}</h2>',
           f'<p class="meta">기대 있는 줄 {u["with_expected"]} — 맞음 {u["ok"]} · 다름 {u["differ"]} · 기대 없는 줄 {u["without_expected"]}. 기대 종류는 발행자가 붙입니다(세션이 붙이면 채점자와 응시자가 같습니다) — 「문장 — 종류」 한 줄씩 세션에 보내시면 됩니다. 다른 줄은 규칙이 못 나눈 사례로 쌓입니다(비교 세트 재료).</p>']
    for g in u["groups"]:
        out.append(f'<h3 style="font-size:13px;margin:10px 0 4px">{_mine(e(g["name"]))}</h3>')     # 묶음 이름도 발행자가 쓴 말이다
        for r in g["rows"]:
            if r["ok"] is None:
                verdict = f'<span class="meta">{e(FILL_ME)}</span>'
            else:
                verdict = f'<span class="{"ok" if r["ok"] else "err"}"><b>{"맞다" if r["ok"] else "다르다"}</b></span>'
            route = f' · {e(r["route_said"])}' if r["route_said"] else ""
            # 물음 문장과 발행자 메모는 **쓴 그대로**(words.mine) · 종류·갈래 말은 시스템 말이라 표를 거친다
            expected = (f'<div class="meta">기대: {e(r["expected_said"])}' + (f' · {e(r["expected_route_said"])}' if r["expected_route_said"] else "")
                        + (f' ({_mine(e(r["expected_note"]))})' if r["expected_note"] else "") + "</div>") if r["expected"] else ""
            out.append(f'<div class="card utt"><b>{_mine(e(r["text"]))}</b> · {verdict}<div>실제: <span title="{e(r["actual"] or "")}">{e(r["actual_said"])}</span>{route}</div>{expected}</div>')
    out.append(_fill_block(u, e))
    return "".join(out)


def _fill_block(u: dict[str, Any], e) -> str:
    """기대가 없는 줄을 **그대로 복사해 쓸 수 있는** 묶음으로 낸다 — 발행자는 줄마다 종류만 채워 보낸다.

    [2026-10-05] 이 항목은 열흘 가까이 발행자 몫으로 막혀 있었고, 비용의 대부분이 **문장 열넷을 다시 치는 것**이었다(화면에는 흩어져 있고 보내는 꼴은 「문장 — 종류」 다).
    세션이 기대를 붙이면 채점자와 응시자가 같아지므로 **종류 자리는 비워 둔다** — 채우는 것은 사람이고, 여기서 주는 것은 종이뿐이다.
    쓸 수 있는 종류 말은 화면이 쓰는 그 말 그대로다(`chat.KIND_PLAIN` 정본 — 목록을 두 벌 두지 않는다).
    """
    rows = [r["text"] for g in u["groups"] for r in g["rows"] if r["expected"] is None]
    if not rows:
        return ""
    from ingest import chat
    # **이 틀이 받는 종류만** 보인다(`probes.KINDS`) — 사람 말은 화면 정본(`chat.KIND_PLAIN`)에서 가져온다.
    # 전부 보이면 틀이 거부하는 말(영상 · 새 목록)을 적게 되고, 그러면 목록 파일이 실리지 않는다(발행자가 왜 안 되는지 모른다)
    kinds = " · ".join(dict.fromkeys(chat.KIND_PLAIN[k] for k in _probes.KINDS if k in chat.KIND_PLAIN))
    lines = "\n".join(f"{t} — " for t in rows)
    from frontend import render, words
    # 묶음 꼴은 정본 하나(`render.paste_block` — 「붙이면」 이라고 말하는 자리가 셋인데 꼴이 하나뿐이었다) · 안의 문장은 **발행자가 쓴 물음**이라 낱말 표를 대지 않는다.
    # 오늘 스무 줄 중 바뀌는 것은 0 이지만(측정 2026-10-05) 「원장을 보여줘」 같은 조회 물음이 들어오면 묶음이 「일지를 보여줘」 를 돌려준다 — 그 줄로 답하면 목록과 안 맞는다.
    return ('<h3 style="font-size:13px;margin:14px 0 4px">그대로 복사해 쓰실 줄</h3>'
            f'<p class="meta">{e(FILL_HOW)} 쓸 수 있는 말: {e(kinds)}</p>'
            + words.mine(render.paste_block(lines)))


def subject() -> dict[str, Any] | None:
    """재배 중(심은 날 있음)인 첫 목록 — 판정 재료가 있는 것만 점검한다."""
    from ingest import media
    subs = [s for s in media.load_subjects() if s.get("anchor")]
    return subs[0] if subs else None


def _first_line(text: str) -> str:
    return (text or "").split("\n", 1)[0].strip()


def _since(t0: datetime) -> float:
    return (datetime.now() - t0).total_seconds()        # 4층은 stdlib 중 datetime 만 쓴다(`time` 은 허용 목록 밖 — test_frontend_local_only)


def run(today: date, judge_html: str | None) -> dict[str, Any]:
    """점검을 돌려 줄 목록을 준다. `judge_html` 은 /judge 화면 그대로(카드 존재는 **화면**에서 본다 — 판정 목록만 보면 배선이 빠진다)."""
    from frontend import chat_pages, words
    from ingest import chat

    s = subject()
    checks: list[dict[str, Any]] = []
    utt = utterances(today, s)                                        # 문장 형태 점검 — 목록이 없어도 돈다(순수 함수)
    if s is None:
        return {"subject": None, "checks": checks, "ok": 0, "total": 0, "utterances": utt}
    judged = words.said("판단함")
    for q in SYMPTOM_QUESTIONS:
        t0 = datetime.now()
        a = chat.answer(s, q, today)                                  # 저장 없음 — said 관찰로 한 번 판정하고 버린다
        drafts = chat.classify(q, today, subject=s)                   # 순수 함수
        draft_ok = any(d.get("kind") == "observation.note" for d in drafts)
        ok = a.startswith(f"[{judged}]") and "원인 후보" in a and draft_ok
        checks.append({"id": "㉡", "name": f"증상 물음 「{q}」", "expect": f"「{judged} · 원인 후보 …」 와 '본 것' 카드",
                       "actual": _first_line(a) + ("" if draft_ok else " · '본 것' 카드 없음"), "ok": ok, "sec": _since(t0)})
    label = chat_pages.DECISION_LABEL.get(CARD_DECISION, CARD_DECISION)
    present = judge_html is not None and f"<h2>{html.escape(label)} " in judge_html
    checks.append({"id": "㉢", "name": f"판단 화면의 「{label}」 카드", "expect": "카드가 있다",
                   "actual": "있다" if present else "없다 — 판단 화면에 그 카드가 안 보인다", "ok": present, "sec": 0.0})
    t0 = datetime.now()
    a = chat.answer(s, WEATHER_QUESTION, today)
    cited = words.said("사실 인용")
    ok = a.startswith(f"[{cited}]")
    checks.append({"id": "⑤a", "name": f"날씨 물음 「{WEATHER_QUESTION}」", "expect": f"「{cited}」 와 단기·중기 줄",
                   "actual": _first_line(a), "ok": ok, "sec": _since(t0)})
    # [D-20 2026-09-29] 가뭄 물음 — 임계가 서면 판단함(마지막 비 온 날의 원천이 괄호에), 임계가 없으면 「기준이 없습니다」(아는 상태). 「마지막으로 비 온 날 …」 이면
    # 비 온 날의 원천(기상청 관측 · 농가 기록)이 하나도 안 닿은 것 — 관측 키·좌표를 본다. 걸린 시간이 관측 호출(임계 날수만 · 임계 없으면 0번 — 2026-09-30)의 값이다
    t0 = datetime.now()
    a = chat.answer(s, DROUGHT_QUESTION, today)
    no_knowledge = words.said("판단 불가(지식)")
    ok = a.startswith(f"[{judged}]") or a.startswith(f"[{no_knowledge}]")
    checks.append({"id": "⑤b", "name": f"가뭄 물음 「{DROUGHT_QUESTION}」", "expect": f"「{judged} · 마지막 비·관수 …(원천) 뒤 무강수 N일」 또는 임계가 없으면 「{no_knowledge}」",
                   "actual": _first_line(a) + ("" if ok else " · 비 온 날의 원천이 하나도 안 닿았다(관측 키 · 좌표)"), "ok": ok, "sec": _since(t0)})
    return {"subject": s, "checks": checks, "ok": sum(1 for c in checks if c["ok"]), "total": len(checks), "utterances": utt}


def main_html(report: dict[str, Any], today: date) -> str:
    """채팅 셸의 본문. **시스템 문장만** 낱말 표를 거친다(plain_outside) — 물음 문장·발행자 메모·묶음 이름은 목록 파일에서 온 **사람이 쓴 글**이라
    `_mine` 으로 싸 둔다. 전에 이 자리가 *"물음 문장은 이 파일의 것"* 이라 적고 페이지를 통째로 표에 넣었는데, 문장은 이 파일의 것이 아니다."""
    from frontend import words
    e = html.escape
    from schema import labels
    out = [f'<div class="thead"><div><h1>{e(labels.label("/selfcheck"))}한 것</h1><div class="meta">'     # 머리 = 왼쪽 메뉴 이름 + 한 것(이름은 계약 하나에서)
           '발행자가 손으로 치던 확인을 화면이 같은 길로 돌려 본 결과입니다. 일지에는 아무것도 넣지 않습니다. 이 화면을 열 때마다 다시 돕니다.'
           '</div></div><div><a href="/judge">판단</a></div></div><div class="msgs">']
    s = report["subject"]
    if s is None:
        out.append(f'<p class="err">{e(NO_SUBJECT)}</p>' + _utterance_html(report.get("utterances"), e) + '</div>')
        return words.plain_outside("".join(out))     # 사람이 쓴 조각(물음 문장 · 메모 · 복사 묶음)은 빼고 — 둘 다 같은 길이다(목록 없는 꼴에서도 문장은 실린다)
    n, total = report["ok"], report["total"]
    if n == total:
        out.append(f'<p class="ok"><b>전부 맞다</b> ({n}/{total}) · 목록 {e(str(s.get("label") or s.get("id")))} · 오늘 {today.isoformat()}</p>')
    else:
        out.append(f'<p class="err"><b>다른 것 {total - n}</b> ({n}/{total} 맞음) · 목록 {e(str(s.get("label") or s.get("id")))} · 오늘 {today.isoformat()} — 다른 줄을 그대로 세션에 붙이면 된다</p>')
    for c in report["checks"]:                                    # 표가 아니라 카드 — 여섯 열 표는 휴대폰(390px)에서 옆으로 넘쳤다(걷기 실측 2026-09-29)
        cls = "ok" if c["ok"] else "err"
        out.append(f'<div class="card chk"><b>{e(c["id"])} {e(c["name"])}</b> · <span class="{cls}"><b>{"맞다" if c["ok"] else "다르다"}</b></span> · {c["sec"]:.1f}초'
                   f'<div class="meta">기대: {e(c["expect"])}</div><div>실제: {e(c["actual"])}</div></div>')
    out.append(_utterance_html(report.get("utterances"), e))
    out.append(f'<p class="meta">{e(BROWSER_ONLY)}</p>')
    out.append('<p class="meta">날씨 줄이 오래 걸리면 원천(기상청)이 늦거나 죽어 있는 것입니다 — 걸린 시간이 그 증거입니다. 못 받은 이유는 실제 칸에 그대로 나옵니다.</p></div>')
    return words.plain_outside("".join(out))
