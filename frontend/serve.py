# -*- coding: utf-8 -*-
# FILE: frontend/serve.py
# ROLE: [M-13] 내부 화면 — 별도 앱, localhost 전용, 브라우저 새 창. 매 요청마다 docs/ 를
#       다시 읽으므로 문서를 고치면 새로고침에 그대로 보인다(진행하는 대로 화면).
#
# 층 구조: 이 앱은 4층(전달)이다. 지금은 docs/ 만 읽는다. 앞으로 DSS 산출 봉투·몰 화면
# 데이터를 받되, 1·2층 원장을 직접 읽는 import 는 두지 않는다(I-5 §5 — 검사로 고정).
from __future__ import annotations

import email.policy
import html
import subprocess
import sys
import threading
import traceback
import webbrowser
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

if __package__ in (None, ""):
    # `python frontend/serve.py` 로 직접 실행될 때 저장소 루트를 경로에 넣는다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frontend import chat_pages, config, render  # noqa: E402
from ingest import chat, feedback as fb, profile, subjects  # noqa: E402  — [M-13] 채팅 원장 · 되먹임 · 재배 단위·사용자 등록부도 ingest 를 통해서만
from ingest import events as ev  # noqa: E402  — 사건 원장도 ingest 를 통해서만
from ingest import media  # noqa: E402  — 입력 화면은 ingest 를 통해서만 1층에 쓴다(원장 파일을 직접 열지 않는다)
from grid import capture as grid_capture  # noqa: E402  — 촬영 시점 알림(격자 지식, 원장 아님)
from judge import run as judge_run  # noqa: E402  — 4층은 3층 봉투만 받는다


def git_head_short() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT,
            capture_output=True, encoding="utf-8", errors="replace", timeout=5,
        )
        return r.stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def git_log_lines(n: int = 20) -> list[tuple[str, str, str]]:
    """(짧은 해시, 날짜, 제목) 최근 n건 — 변경 로그 화면. 제목만 싣는다(본문은 싣지 않는다 — 문서 인용 · 경로가 길다)."""
    try:
        r = subprocess.run(
            ["git", "log", f"-{int(n)}", "--date=short", "--format=%h%x1f%ad%x1f%s"], cwd=config.ROOT,
            capture_output=True, encoding="utf-8", errors="replace", timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    out = []
    for line in r.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            out.append((parts[0], parts[1], parts[2]))
    return out


RUNNING_HEAD = git_head_short()   # 프로세스가 기동한 코드. 저장소 HEAD 가 앞서가면 watch_head 가 재기동한다(RELOAD_ON_HEAD_CHANGE) — 이 둘의 차이가 '반영 여부'다


def changes_page() -> tuple[int, str]:
    """[발행자 2026-09-20 메뉴 '변경 로그 보기'] 커밋 이력 + **실행 중 코드가 저장소와 같은가**. CLAUDE.md 라이브 반영 규율의 화면판."""
    head = git_head_short()
    if head == RUNNING_HEAD:
        state = f'<span class="st st-완료">반영됨</span> 실행 중 {html.escape(RUNNING_HEAD)} = 저장소 HEAD'
    elif config.RELOAD_ON_HEAD_CHANGE:
        state = f'<span class="st st-진행">뒤처짐</span> 실행 중 {html.escape(RUNNING_HEAD)} · 저장소 {html.escape(head)} — 자동 재기동 대기({config.RELOAD_POLL_SEC}초 감시), 새로고침하면 새 코드'
    else:
        state = f'<span class="st st-대기">뒤처짐</span> 실행 중 {html.escape(RUNNING_HEAD)} · 저장소 {html.escape(head)} — AGRODSS_RELOAD=0 이라 수동 재시작'
    if config.today_frozen():
        state += f' · <span class="st st-대기">오늘 고정 {html.escape(config.today_frozen())}</span> ({config.TODAY_ENV} — 검사·재현용, 운영이면 지운다)'
    rows = "".join(f"<tr><td><code>{html.escape(h)}</code></td><td>{html.escape(d)}</td><td>{html.escape(s)}</td></tr>" for h, d, s in git_log_lines(20))
    body = (f"<h1>변경 로그</h1><p>{state}</p>"
            f"<table><thead><tr><th>커밋</th><th>날짜</th><th>제목</th></tr></thead><tbody>{rows or '<tr><td colspan=3>git 이력을 읽지 못했다</td></tr>'}</tbody></table>"
            "<p style='color:var(--muted)'>저장소 정본 <code>git log</code> 의 제목 20건 — 무엇이 언제 바뀌었는지. 반영 상태는 위 한 줄이다(커밋 완료 ≠ 반영 완료).</p>")
    meta = "실행 중 코드와 저장소 HEAD 를 대조한다 — 뒤처지면 자동 재기동(run_frontend.bat) 뒤 새로고침"
    footer = f"HEAD {head} · {config.HOST}:{config.PORT} · 외부 배포 없음(D-6)"
    return 200, render.page("AGRODSS —변경 로그", nav_html("/changes"), body, meta, footer)


def doc_list() -> list[str]:
    present = sorted(p.name for p in config.DOCS_DIR.glob("*.md"))
    ordered = [n for n in config.NAV_ORDER if n in present]
    return ordered + [n for n in present if n not in ordered]


def nav_html(current: str) -> str:
    parts = [chat_pages.BRAND_HTML, '<div class="grp">판단</div>']     # [발행자 2026-09-19] AGRODSS 홈 탭은 표 화면에도 있다
    cls = ' class="on"' if current == "/judge" else ""
    parts.append(f'<a href="/judge"{cls}>수확 시기 · 위험 경보 (M-10)</a>')
    parts.append('<div class="grp">입력</div>')
    cls = ' class="on"' if current == "/media" else ""
    parts.append(f'<a href="/media"{cls}>영상 반입 (I-7)</a>')
    cls = ' class="on"' if current == "/events" else ""
    parts.append(f'<a href="/events"{cls}>사건 · 불이행 사유 (I-3)</a>')
    parts.append('<div class="grp">문서</div>')
    for name in doc_list():
        cls = ' class="on"' if name == current else ""
        label = html.escape(name.removesuffix(".md"))
        parts.append(f'<a href="/doc/{html.escape(name)}"{cls}>{label}</a>')
    parts.append(chat_pages.user_tab_html(current))                       # [발행자 2026-09-19] 사용자 정보 탭은 표 화면에도 — 매 페이지
    return "".join(parts)


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


KIND_CLASS = {"판단함": "완료", "선택지+대가": "진행", "사실 인용": "진행",
              "판단 불가(데이터)": "대기", "판단 불가(지식)": "보류", "해당 없음": "보류",
              "예측 불가": "폐기", "답하지 않음": "폐기"}


LEVEL_CLASS = {"경보": "폐기", "주의": "진행", "예고": "대기"}


def _render_env(out: list[str], e: dict, title: str) -> None:
    badge = f'<span class="st st-{KIND_CLASS.get(e["kind"], "대기")}">{_e(e["kind"])}</span>'
    out.append(f"<h2>{_e(title)} {badge}</h2>")
    r = e["result"]
    if e["kind"] == "판단함" and e["decision_id"] == "risk_alert":
        out.append(f"<p>기준점 후 {r['days_since_anchor']}일 · 보는 칸: {_e(' / '.join(r['stages']))} · {r['horizon_days']}일 앞까지 · "
                   f"신뢰 등급 <b>{_e(e['grade'])}</b> · 재판정 {_e(e['revisit_at'])}</p>")
        if r["alerts"]:
            out.append("<table><tr><th>수준</th><th>위험</th><th>칸</th><th>회복</th><th>근거</th></tr>" + "".join(
                f'<tr><td><span class="st st-{LEVEL_CLASS.get(a["level"], "대기")}">{_e(a["level"])}</span></td><td><b>{_e(a["risk"])}</b></td>'
                f'<td>{_e(a["stage"])}</td><td>{"가능" if a["recoverable"] else "불가"}</td><td>{_e(a["basis"])}</td></tr>' for a in r["alerts"]) + "</table>")
        else:
            out.append("<p>지금 낼 경보가 없다.</p>")
        out.append(f"<p class=\"meta\">회복 가능 위험 {r['watched_recoverable']}건은 신호가 임계를 넘을 때만 나온다(확률 충분할 때만).</p>")
    elif e["kind"] == "판단함" and e["decision_id"] == "harvest_timing":
        out.append(f"<p><b>수확 창 {_e(r['window_start'])} ~ {_e(r['window_end'])}</b> (중심 {_e(r['center'])}, ±{r['error_days']}일) · "
                   f"신뢰 등급 <b>{_e(e['grade'])}</b> · 기준점 후 {r['days_since_anchor']}일 · {_e(r['position'])} · 재판정 {_e(e['revisit_at'])}</p>")
        out.append(f"<p class=\"meta\">근거: {_e(r['basis'])} · {_e(r['final_say'])}</p>")
        if e["caps"]:
            out.append("<ul>" + "".join(f"<li><b>상한 제약</b> {_e(c['name'])} — {_e(c['basis'])}</li>" for c in e["caps"]) + "</ul>")
    elif e["kind"] == "판단함" and e["decision_id"] == "plan_vs_actual":
        c = r["counts"]
        out.append(f"<p>기준점 후 {r['days_since_anchor']}일 · " + " · ".join(f"{k} <b>{v}</b>" for k, v in c.items()) +
                   f" · 사건 {r['events_used']} · 영상 {r['videos_used']} · 재판정 {_e(e['revisit_at'])}</p>")
        if r["prep_now"]:
            out.append("<p><b>지금 준비 착수</b>(임대 리드타임 기준): " + " · ".join(f"{_e(p['task'])}(작업 {_e(p['work_date'])})" for p in r["prep_now"]) + "</p>")
        if r["ask_reason"]:
            out.append("<p class=\"err\"><b>창을 넘긴 작업</b> — 안 한 이유가 조언보다 값지다. <a href=\"/events\">사건 화면</a>에서 사유를 적는다: " +
                       " · ".join(f"{_e(a['task'])}({_e(a['work_date'])})" for a in r["ask_reason"]) + "</p>")
        st_cls = {"이행": "완료", "예정": "대기", "미이행": "진행", "놓침": "폐기", "사유 기록됨": "보류"}
        out.append("<table><tr><th>상태</th><th>칸</th><th>작업</th><th>작업일</th><th>마감</th><th>근거</th></tr>" + "".join(
            f'<tr><td><span class="st st-{st_cls.get(x["status"], "대기")}">{_e(x["status"])}</span></td><td>{_e(x["stage"])}</td><td>{_e(x["task"])}</td>'
            f'<td>{_e(x["work_date"])}</td><td>{_e(x.get("deadline_date") or "")}</td><td>{_e(x.get("evidence") or "")}</td></tr>' for x in r["rows"]) + "</table>")
    elif e["kind"] == "사실 인용":
        c = r["citation"]
        out.append(f"<p>칸 {_e(r['stage'])} · 인용 계열 {r['cited_families']}/{len(r['groups'])} · 출처 {_e(c['source'])} · 목록 시점 {_e(c['observed_at'])} · 재판정 {_e(e['revisit_at'])}</p>")
        if c.get("proxy_notice"):
            out.append(f'<p class="meta"><b>⚠ {_e(c["proxy_notice"])}</b></p>')
        for g in r["groups"]:
            head = g.get("family") or f"{g.get('risk', '')} · {g.get('pest', '')}"       # 유기(계열) · 관행(위험 · 병해충) 두 모양
            proxy = f' <span class="st st-보류">{_e(g["proxy_label"])}</span>' if g.get("proxy_label") else ""
            if g["status"] == "success" and "family" in g:
                out.append(f"<p><b>{_e(head)}</b> <span class=\"meta\">(검색어 '{_e(g['keyword'])}' · 유효 {g['total']}건 중 {len(g['items'])})</span></p><ul>" + "".join(
                    # [코드 평가 C1] 공시 가격은 싣지 않는다(스키마 금지 필드 price) — 화면이 그 값의 마지막 소비자였다
            f"<li><b>{_e(i['product'])}</b>({_e(i['material'])}) · {_e(i['company'])} · 공시 {_e(i['notice_no'])} (~{_e(i['valid_until'])})</li>" for i in g["items"]) + "</ul>")
            elif g["status"] == "success":
                # 관행 갈래(PSIS) — 항목 필드는 원천 표기(FIELD_KO)를 그대로. [C3 표기] 대체 조회면 그 사실을 항목 위에 단다
                out.append(f"<p><b>{_e(head)}</b>{proxy} <span class=\"meta\">(등록 {g['total']}건 중 {len(g['items'])})</span></p><ul>" + "".join(
                    f"<li>{_e(' · '.join(f'{k} {v}' for k, v in i.items() if v))}</li>" for i in g["items"]) + "</ul>")
            else:
                out.append(f"<p><b>{_e(head)}</b>{proxy} — <span class=\"st st-보류\">{_e(g['status'])}</span> {_e(g.get('note') or '')}</p>")
        out.append(f"<p class=\"meta\">{_e(c['note'])}</p>")
    elif e["kind"] == "판단 불가(데이터)":
        out.append("<ul>" + "".join(f"<li>없는 축 <code>{_e(m['axis'])}</code> — 채울 수 있는 자: {_e(m['who_can_fill'])}</li>" for m in e["missing"]) + "</ul>")
    elif e["kind"] == "판단함" and r.get("summary"):
        # [2026-09-20 실측 — 표현 층 왜곡] M-10 단계 결정(웃거름 · 병해충 · 배수)의 '판단함' 봉투가 이 화면에서 배지와 입력 축 표만 보였다 —
        # 요약(상태 · 작업일 · 양 · 사유 · 경보)이 result 에 있는데 화면이 안 실었다. 발행자에게 "/judge 에서 양을 보라"고 해 놓고 화면엔 없었다
        out.append(f"<p><b>{_e(r['summary'])}</b> · 신뢰 등급 <b>{_e(e['grade'])}</b> · 재판정 {_e(e['revisit_at'])}</p>")
        if r.get("alerts"):
            out.append("<table><tr><th>수준</th><th>위험</th><th>칸</th><th>회복</th><th>근거</th></tr>" + "".join(
                f'<tr><td><span class="st st-{LEVEL_CLASS.get(a["level"], "대기")}">{_e(a["level"])}</span></td><td><b>{_e(a["risk"])}</b></td>'
                f'<td>{_e(a["stage"])}</td><td>{"가능" if a.get("recoverable") else "불가"}</td><td>{_e(a["basis"])}</td></tr>' for a in r["alerts"]) + "</table>")
    else:
        out.append(f"<p>{_e(r.get('why', ''))} {_e(r.get('who', ''))}</p>")
    if e["inputs"]:
        out.append("<table><tr><th>쓴 축</th><th>관측 시각</th><th>출처</th><th>해상도</th><th>등급</th></tr>" +
                   "".join(f"<tr><td>{_e(i['axis'])}</td><td>{_e(i['observed_at'])}</td><td>{_e(i['source'])}</td><td>{_e(i['resolution'])}</td><td>{_e(i['grade'])}</td></tr>" for i in e["inputs"]) + "</table>")
    if e["notes"]:
        out.append("<ul>" + "".join(f"<li class=\"meta\">{_e(n)}</li>" for n in e["notes"]) + "</ul>")


def judge_page() -> tuple[int, str]:
    out = ["<h1>판단 — 3층 산출 봉투</h1>",
           "<p class=\"meta\">화면은 봉투만 받는다(4층). 종류(kind)가 먼저 보이고, 값은 그 다음이다. 소비자 노출은 D-2 전까지 전부 아니오.</p>"]
    if config.today_frozen():
        out.append(f'<p class="err"><b>오늘이 {_e(config.today_frozen())} 로 고정돼 있다</b> ({config.TODAY_ENV} — 검사·재현용. 운영이면 .env 에서 지운다)</p>')
    for s, envs, info in judge_run.all_judgments(config.today()):
        out.append(f"<h1 style=\"font-size:17px;margin-top:24px\">{_e(s['label'])}</h1>")
        for env in envs:
            e = env.to_dict()
            # [칸 3 재측정 2026-09-20 · A13/D13] 여기 인라인 사전이 정본(`chat_pages.DECISION_LABEL`)을 **가리고** 있었다 —
            # 사본이 먼저 걸리니 정본을 고쳐도 이 화면만 안 바뀐다(정본 역전). 그리고 실제로 어긋나 있었다: 사본의
            # "자재 인용(유기 공시)" 는 PSIS(관행 등록약제)가 붙기 전 이름이라, 관행 인용까지 싣는 지금은 틀린 말이다.
            _render_env(out, e, chat_pages.DECISION_LABEL.get(e["decision_id"], e["decision_id"]))
        out.append(f"<p class=\"meta\">예보: {_e(info['forecast'])} · 예찰: {_e(info.get('pest', ''))}</p>")
    footer = f"HEAD {git_head_short()} · {config.HOST}:{config.PORT} · 외부 배포 없음(D-6)"
    return 200, render.page("AGRODSS —판단", nav_html("/judge"), "".join(out), "3층 산출 — I-1 봉투 8종 중 하나", footer)


def events_page(message: str = "", error: str = "") -> tuple[int, str]:
    subjects = media.load_subjects()
    out = ["<h1>사건 · 불이행 사유 — 1층 기록</h1>"]
    if error:
        out.append(f'<p class="err"><b>기록 안 됨</b> — {_e(error)}</p>')
    if message:
        out.append(f'<p class="ok">{_e(message)}</p>')
    sel = "".join(f'<option value="{_e(s["id"])}">{_e(s["label"])}</option>' for s in subjects)
    types = "".join(f'<option value="{_e(t)}">{_e(t)}</option>' for t in ev.EVENT_TYPES)
    out.append('<h2>사건 추가</h2><form method="post" action="/events/add" class="reg">')
    out.append(f'<label>재배 단위 <select name="subject">{sel}</select></label>')
    out.append(f'<label>종류 <select name="type">{types}</select></label>')
    out.append('<label>일어난 날 <input name="observed_at" placeholder="2026-09-19" size="14"> <span class="meta">없으면 기록되지 않는다</span></label>')
    out.append('<label>자재(쉼표) <input name="materials" size="40" placeholder="예: 비티박사, 님오일"></label>')
    out.append('<label>메모 <input name="note" size="40"></label><button type="submit">기록</button></form>')
    out.append('<h2>불이행 사유 (계획을 안 따른 이유)</h2><form method="post" action="/events/reason" class="reg">')
    out.append(f'<label>재배 단위 <select name="subject">{sel}</select></label>')
    out.append('<label>계획 작업명 <input name="planned_task" size="30" placeholder="예: 예찰(트랩 · 육안)"></label>')
    out.append('<label>계획 작업일 <input name="planned_day" size="14" placeholder="2026-09-08"></label>')
    out.append('<label>사유 <input name="reason" size="50" placeholder="예: 트랩을 못 구했다 / 비가 계속 왔다 / 필요 없다고 봤다"></label>')
    out.append('<button type="submit">기록</button></form>')
    recs = ev.list_records()
    out.append(f"<h2>기록 ({len(recs)})</h2>")
    if recs:
        out.append("<table><tr><th>종류</th><th>재배 단위</th><th>대상 시각</th><th>내용</th><th>기록 시각</th></tr>" + "".join(
            f"<tr><td>{_e(r.get('type') or r.get('kind'))}</td><td>{_e(r.get('subject'))}</td><td>{_e(r.get('observed_at'))}</td>"
            f"<td>{_e(r.get('reason') or r.get('note') or '')} {_e(', '.join(r.get('materials') or []))}</td><td>{_e(render.local_time(r.get('recorded_at')))}</td></tr>"
            for r in reversed(recs)) + "</table>")
    else:
        out.append("<p>아직 없다. 파종은 기준점(재배 단위 등록부)이 사건을 대신한다.</p>")
    style = ("<style>.reg{border:1px solid var(--line);border-radius:6px;padding:10px;margin:8px 0;display:grid;gap:6px}"
             ".reg label{display:block}.err{color:var(--drop-fg);background:var(--drop);padding:6px 10px;border-radius:4px}"
             ".ok{color:var(--done-fg);background:var(--done);padding:6px 10px;border-radius:4px}</style>")
    footer = f"HEAD {git_head_short()} · {config.HOST}:{config.PORT} · 외부 배포 없음(D-6)"
    return (400 if error else 200), render.page("AGRODSS —사건", nav_html("/events"), style + "".join(out),
                                                "사건(I-3 §2) · 결정(§5 불이행 사유) — 대상 시각 없이는 기록되지 않는다", footer)


def media_page(message: str = "", error: str = "") -> tuple[int, str]:
    subjects = media.load_subjects()
    items = media.list_inbox()
    records = [media.public_view(r) for r in media.list_records()]
    watch = media.watch_dirs()
    out = ["<h1>영상 반입 — 관찰(영상) 1층 등록</h1>"]
    if error:
        out.append(f'<p class="err"><b>등록 안 됨</b> — {_e(error)}</p>')
    if message:
        out.append(f'<p class="ok">{_e(message)}</p>')
    out.append("<h2>지금 찍을 장면 (격자 촬영 칸)</h2><ul>")
    for s in subjects:
        h = grid_capture.hint_for(s, config.today())
        if h is None:
            out.append(f"<li><b>{_e(s['label'])}</b> — 격자 또는 기준점 없음</li>")
        elif h["stage"] is None:
            out.append(f"<li><b>{_e(s['label'])}</b> — 기준점 후 {h['day']}일: 격자 창 밖(단계 없음)</li>")
        else:
            what = f"<b>찍는다</b> — {_e(h['scene'])}" if h["shoot"] else "이 단계는 촬영 칸이 아니다"
            out.append(f"<li><b>{_e(s['label'])}</b> — 기준점 후 <b>{h['day']}일</b> · 단계 {_e(h['stage'])} "
                       f"({h['window'][0]}~{h['window'][1]}일) · {what}</li>")
    out.append("</ul>")
    out.append("<h2>어디서 들어오나</h2><ul>")
    out.append(f"<li>기본 inbox: <code>{_e(media.inbox_dir())}</code> — 여기 넣은 파일은 등록 시 <b>옮겨진다</b></li>")
    if watch:
        for w in watch:
            state = "" if w.is_dir() else " <b>(폴더 없음)</b>"
            out.append(f"<li>동기화 폴더(감시): <code>{_e(w)}</code>{state} — 읽기만, 등록 시 <b>복사</b>. 원본은 그대로</li>")
    else:
        out.append("<li>동기화 폴더: <b>미설정</b> — <code>.env</code> 에 <code>AGRODSS_WATCH_DIRS=…</code> "
                   "(휴대폰 카메라가 PC 로 동기화되는 폴더. OneDrive · 구글 드라이브 · iCloud 사진 · Syncthing)</li>")
    out.append("</ul>")
    out.append(f"<h2>등록 대기 ({len(items)})</h2>")
    if not items:
        out.append("<p>대기 중인 영상이 없다. 폴더에 영상이 들어오면 새로고침.</p>")
    for it in items:
        pr = it["probe"]
        auto = pr.get("creation_time")
        out.append('<form method="post" action="/media/register" class="reg">')
        out.append(f'<input type="hidden" name="key" value="{_e(it["key"])}">')
        out.append(f'<div><b>{_e(it["name"])}</b> <span class="meta">{it["bytes"] // (1 << 20)} MB · '
                   f'{_e(it["origin"])} · {_e(pr.get("width"))}×{_e(pr.get("height"))} · '
                   f'{_e(pr.get("duration_sec"))}s · 위치 {"있음" if pr.get("gps") else "없음"}</span></div>')
        if pr.get("error"):
            out.append(f'<div class="meta">메타 판독: {_e(pr["error"])}</div>')
        out.append('<label>재배 단위 <select name="subject">')
        for s in subjects:
            out.append(f'<option value="{_e(s["id"])}">{_e(s["label"])}</option>')
        out.append("</select></label>")
        if auto:
            out.append(f'<label>촬영 시각(메타, UTC) <input name="observed_at" value="{_e(auto)}" size="28"></label>')
        else:
            out.append('<label>촬영 시각 <input name="observed_at" placeholder="2026-09-18T15:30:00+09:00" size="28"> '
                       '<span class="meta">메타에 없음 — 직접 입력. 없으면 등록 안 됨</span></label>')
        out.append('<label>메모 <input name="note" size="40" placeholder="예: 파종 24일차, 잎 길이 15cm"></label>')
        out.append('<button type="submit">등록</button></form>')
    out.append(f"<h2>등록된 영상 ({len(records)})</h2>")
    if records:
        out.append("<table><tr><th>관측 시각</th><th>재배 단위</th><th>파일</th><th>해상도</th><th>길이</th>"
                   "<th>위치</th><th>시각 출처</th><th>메모</th></tr>")
        for r in sorted(records, key=lambda r: r["observed_at"], reverse=True):
            out.append(f'<tr><td>{_e(r["observed_at"])}</td><td>{_e(r["subject"])}</td><td><code>{_e(r["file"])}</code></td>'
                       f'<td>{_e(r.get("width"))}×{_e(r.get("height"))}</td><td>{_e(r.get("duration_sec"))}s</td>'
                       f'<td>{_e(r["gps"])}</td><td>{_e(r.get("observed_at_source"))}</td><td>{_e(r.get("note"))}</td></tr>')
        out.append("</table>")
    else:
        out.append("<p>아직 없다.</p>")
    style = ("<style>.reg{border:1px solid var(--line);border-radius:6px;padding:10px;margin:8px 0;display:grid;gap:6px}"
             ".reg label{display:block}.err{color:var(--drop-fg);background:var(--drop);padding:6px 10px;border-radius:4px}"
             ".ok{color:var(--done-fg);background:var(--done);padding:6px 10px;border-radius:4px}</style>")
    meta = "1층 관찰(영상) — 촬영 시각 · 출처 · 해상도가 붙어야 등록된다. 좌표는 화면에 내지 않는다"
    footer = f"HEAD {git_head_short()} · {config.HOST}:{config.PORT} · 외부 배포 없음(D-6)"
    return (400 if error else 200), render.page("AGRODSS —영상 반입", nav_html("/media"), style + "".join(out), meta, footer)


def render_page(name: str) -> tuple[int, str]:
    path = config.DOCS_DIR / name
    if not name.endswith(".md") or "/" in name or "\\" in name or not path.is_file():
        return 404, render.page("없음", nav_html(""), "<h1>없는 문서</h1>", "", "")
    text = path.read_text(encoding="utf-8")
    body = render.md_to_html(text)
    meta = f"정본 <code>docs/{html.escape(name)}</code> · 화면은 렌더 사본 — 갱신은 파일에서"
    if name == config.LEDGER_DOC:
        counts = render.ledger_counts(text)
        meta += ' · <span class="counts">' + "".join(
            f'<span class="st st-{s}">{s} {n}</span>' for s, n in counts.items()
        ) + "</span>"
    footer = f"HEAD {git_head_short()} · {config.HOST}:{config.PORT} · 외부 배포 없음(D-6)"
    return 200, render.page(f"AGRODSS —{name}", nav_html(name), body, meta, footer)


# ── [M-13] Claude 형식 채팅 화면 ─────────────────────────────────────────────────────
def _shell(current: str, main_html: str, panel_html: str | None, title: str) -> str:
    return chat_pages.shell(title, chat_pages.sidebar(current, doc_list(), config.today()), main_html, panel_html, git_head_short())


def chat_home() -> tuple[int, str, str | None]:
    subs = subjects.load()
    if subs:
        return 302, "", f"/c/{quote(subs[0]['id'])}"
    return 302, "", "/c/new"


def chat_page(sid: str, message: str = "", error: str = "") -> tuple[int, str]:
    s = subjects.by_id(sid)
    if not s:
        return 404, _shell("", '<div class="msgs"><h1>없는 목록</h1></div>', None, "없음")
    today = config.today()
    body = chat_pages.thread_main(s, today, message=message, error=error)
    return (400 if error else 200), _shell(f"/c/{sid}", body, chat_pages.thread_panel(s, today), f"AGRODSS —{s.get('label')}")


def diary_page(sid: str) -> tuple[int, str]:
    s = subjects.by_id(sid)
    if not s:
        return 404, _shell("", '<div class="msgs"><h1>없는 목록</h1></div>', None, "없음")
    return 200, _shell(f"/c/{sid}", chat_pages.diary_main(s, config.today()), None, f"영농일지 — {s.get('label')}")


def new_page(error: str = "", form: dict[str, str] | None = None) -> tuple[int, str]:
    return (400 if error else 200), _shell("/c/new", chat_pages.new_main(error, form), None, "새 채팅")


def mall_page(sid: str) -> tuple[int, str]:
    """[M-11] 몰 상세페이지 목업 — mall.product 가 몰-H 게이트를 지난 뷰만 준다."""
    from mall import product as mall_product
    try:
        view = mall_product.product_view(sid, today=config.today())
    except mall_product.MallBoundaryError as e:
        return 404, _shell("", f'<div class="msgs"><h1>없는 상품</h1><p>{html.escape(str(e))}</p></div>', None, "없음")
    return 200, _shell(f"/mall/{sid}", chat_pages.mall_main(view), None, f"몰 목업 — {view['title']}")


def me_page(message: str = "", error: str = "", form: dict[str, str] | None = None) -> tuple[int, str]:
    return (400 if error else 200), _shell("/me", chat_pages.me_main(message, error, form), None, "사용자 정보")


def improve_page(message: str = "", error: str = "", cycle=None) -> tuple[int, str]:
    return (400 if error else 200), _shell("/improve", chat_pages.improve_main(config.today(), message, error, cycle), None, "개선 · 자율진화")


def parse_body(content_type: str, raw: bytes) -> tuple[dict[str, str], list[tuple[str, bytes]]]:
    """urlencoded 또는 multipart/form-data → (필드, [(파일명, 바이트)]). 표준 라이브러리 email 파서로 multipart 를 읽는다."""
    ct = content_type or ""
    if ct.startswith("multipart/form-data"):
        msg = BytesParser(policy=email.policy.HTTP).parsebytes(b"Content-Type: " + ct.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + raw)
        fields: dict[str, str] = {}
        files: list[tuple[str, bytes]] = []
        if msg.is_multipart():
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                fn = part.get_filename()
                payload = part.get_payload(decode=True) or b""
                if fn:
                    files.append((fn, payload))
                elif name:
                    fields[name] = payload.decode("utf-8", errors="replace").strip()
        return fields, files
    return {k: v[0] for k, v in parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True).items()}, []


def ingest_uploads(sid: str, fields: dict[str, str], files: list[tuple[str, bytes]]) -> tuple[list[dict], list[str]]:
    """[M-13 채팅 반입] 파일마다 inbox 저장 → 등록. 시각 없는 파일은 등록되지 않고 inbox 에 남는다(/media 에서 날짜를 넣어 등록)."""
    ok, errs = [], []
    for fn, data in files:
        try:
            key = media.save_upload(fn, data)
            ok.append(media.register(key, sid, fields.get("observed_at") or None, note=fields.get("text", "")))
        except media.RegisterError as e:
            errs.append(f"{fn}: {e}")
    return ok, errs


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: str, location: str | None = None, set_cookie: str | None = None) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        if location:
            self.send_header("Location", location)
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> tuple[bool, str | None]:
        """[D-16] LAN 토큰이 설정돼 있으면 ?t=<token> 또는 쿠키가 있어야 한다. 루프백 기본 설정(토큰 없음)에서는 항상 통과."""
        tok = config.LAN_TOKEN
        if not tok:
            return True, None
        q = parse_qs(urlparse(self.path).query).get("t", [""])[0]
        if q == tok:
            return True, f"{config.COOKIE_NAME}={tok}; Path=/; HttpOnly; SameSite=Lax"
        cookie = self.headers.get("Cookie") or ""
        return (f"{config.COOKIE_NAME}={tok}" in cookie), None

    def _same_origin(self) -> bool:
        """[코드 평가 D6] Host 가 이 서버(루프백이면 127.0.0.1|localhost:PORT, LAN 옵트인이면 아무 호스트:PORT)이고,
        Origin 이 있으면 그 Host 와 같고, Sec-Fetch-Site 가 있으면 same-origin 이어야 한다. 헤더가 없는 도구(curl · 검사)는 Host 만 본다."""
        host = (self.headers.get("Host") or "").strip().lower()
        port = self.server.server_address[1]                          # 실제 리슨 포트(검사는 0 → 임의 포트)
        if config.BIND == config.HOST:                                # 루프백 기본 — 두 이름만
            if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                return False
        elif not host or "," in host or not host.endswith(f":{port}"):   # LAN 옵트인 — 이 포트로 온 것만(호스트명은 폰이 정한다)
            return False
        origin = (self.headers.get("Origin") or "").strip().lower()
        if origin and origin not in (f"http://{host}", f"https://{host}"):
            return False
        sfs = (self.headers.get("Sec-Fetch-Site") or "").strip().lower()
        return sfs in ("", "same-origin", "none")

    # [코드 평가 D4 · 2026-09-19] 총괄 예외 — BaseHTTPRequestHandler 는 do_* 의 예외를 잡지 않아 응답 없이 연결이 끊겼다(브라우저 "연결 끊김",
    # 원인 안 보임). 여기서 500 페이지로 바꾼다. 메시지는 이스케이프하고 traceback 은 콘솔에만.
    def _guarded(self, fn) -> None:
        try:
            fn()
        except Exception as e:  # noqa: BLE001 — 마지막 방어선. 여기서 삼키는 것이 아니라 보이게 만든다
            traceback.print_exc()
            msg = f"{type(e).__name__}: {e}"
            try:
                self._send(500, render.page("AGRODSS —오류", nav_html(""),
                                            f"<h1>화면 오류</h1><p>이 화면을 만들다 실패했다. 아래 한 줄을 세션에 붙이면 고친다.</p><pre>{html.escape(msg)}</pre>", "", ""))
            except Exception:  # noqa: BLE001 — 응답 도중 끊긴 소켓
                pass

    def do_GET(self) -> None:  # noqa: N802
        self._guarded(self._get)

    def _get(self) -> None:
        p = urlparse(self.path).path
        ok, cookie = self._authorized()
        if not ok:
            self._send(401, render.page("접근 불가", "", "<h1>토큰이 필요하다</h1><p>같은 Wi-Fi 동기화(D-16)는 첫 접속을 <code>?t=&lt;토큰&gt;</code> 으로 한다.</p>", "", ""))
            return
        loc = None
        if p == "/":
            status, body, loc = chat_home()
        elif p == "/c/new":
            status, body = new_page()
        elif p.startswith("/c/"):
            status, body = chat_page(unquote(p[len("/c/"):]))
        elif p.startswith("/diary/"):
            status, body = diary_page(unquote(p[len("/diary/"):]))
        elif p == "/improve":
            status, body = improve_page()
        elif p == "/me":
            status, body = me_page()
        elif p.startswith("/mall/"):
            status, body = mall_page(unquote(p[len("/mall/"):]))
        elif p == "/media":
            status, body = media_page()
        elif p == "/judge":
            status, body = judge_page()
        elif p == "/events":
            status, body = events_page()
        elif p == "/changes":
            status, body = changes_page()
        elif p.startswith("/doc/"):
            status, body = render_page(unquote(p[len("/doc/"):]))
        else:
            status, body = 404, render.page("없음", nav_html(""), "<h1>없는 경로</h1>", "", "")
        self._send(status, body, loc, set_cookie=cookie)

    def do_POST(self) -> None:  # noqa: N802
        self._guarded(self._post)

    def _post(self) -> None:
        p = urlparse(self.path).path
        ok, _ = self._authorized()
        if not ok:
            self._send(401, render.page("접근 불가", "", "<h1>토큰이 필요하다</h1>", "", ""))
            return
        # [코드 평가 D6] POST 는 같은 출처에서만 — 루프백 기본은 토큰도 쿠키도 없어 브라우저에 열린 아무 사이트가 폼 POST 로 원장을
        # 쓸 수 있었다(CSRF · DNS 리바인딩). Host 가 이 서버이고, Origin/Sec-Fetch-Site 가 있으면 같은 출처여야 한다.
        if not self._same_origin():
            self._send(403, render.page("AGRODSS —거부", nav_html(""), "<h1>다른 출처의 요청</h1><p>이 화면에서 보낸 폼만 받는다.</p>", "", ""))
            return
        length = int(self.headers.get("Content-Length") or 0)
        limit = config.MAX_UPLOAD_MB << 20
        if length > limit:
            # [코드 평가 D5] 상한 초과는 413 — 전에는 잘라 읽고 잘린 multipart 를 그대로 등록했다(불완전 파일이 1층 관찰로)
            # 본문은 읽어 버린다(메모리에 안 남김) — 안 읽고 닫으면 브라우저/클라이언트가 보내는 도중 연결이 끊겨 413 을 못 본다
            # (관문 간헐 실패 2026-09-19 22:1x: 3회 중 1회 ConnectionReset — 근본 원인이 이것).
            left = length
            while left > 0:
                chunk = self.rfile.read(min(left, 1 << 20))
                if not chunk:
                    break
                left -= len(chunk)
            self._send(413, render.page("AGRODSS —너무 큼", nav_html(""),
                                        f"<h1>본문이 너무 크다</h1><p>한 번에 {config.MAX_UPLOAD_MB}MB 까지. 파일을 나눠 올린다.</p>", "", ""))
            return
        raw = self.rfile.read(length)
        form, files = parse_body(self.headers.get("Content-Type") or "", raw)
        if p == "/c/new":
            try:
                s = subjects.add(form.get("crop", ""), form.get("season", ""), status=form.get("status") or "계획",
                                 parcel=form.get("parcel") or None, anchor=form.get("anchor") or None,   # 비면 등록부가 하나일 때만 그것(subjects.default_parcel)
                                 cert=form.get("cert") or None)
                self._send(302, "", f"/c/{quote(s['id'])}")
                return
            except (subjects.SubjectError, ValueError) as e:
                status, body = new_page(error=str(e), form=form)
        elif p.startswith("/c/") and p.endswith("/send"):
            sid = unquote(p[len("/c/"):-len("/send")])
            try:
                recs, errs = ingest_uploads(sid, form, files) if files else ([], [])
                if not files and not (form.get("text") or "").strip():
                    raise chat.ChatError("빈 발화 — 글이나 파일이 있어야 보낸다")
                if recs or (form.get("text") or "").strip():
                    chat.send(sid, form.get("text", ""), today=config.today(), retry_of=form.get("retry_of") or None, edit_of=form.get("edit_of") or None,
                              input_mode=form.get("input_mode") or "text", media_refs=recs)   # 오늘은 화면 정본 하나(§7.5 관문의 입력 — 고정이 여기 안 닿았다)
                if errs:
                    status, body = chat_page(sid, error="; ".join(errs) + " — 파일은 반입 대기함(inbox)에 남았다. 촬영일을 넣어 다시 올리거나 /media 에서 등록한다")
                else:
                    self._send(302, "", f"/c/{quote(sid)}")
                    return
            except chat.ChatError as e:
                status, body = chat_page(sid, error=str(e))
        elif p.startswith("/c/") and p.endswith("/request"):
            sid = unquote(p[len("/c/"):-len("/request")])
            try:
                req, _ = chat.request_improvement(form.get("reply", ""), form.get("text", ""))
                status, body = chat_page(sid, message=f"개선 요구 접수 {req['id']} — /improve 에서 개선 항목으로 이어진다")
            except (chat.ChatError, fb.FeedbackError) as e:
                status, body = chat_page(sid, error=str(e))
        elif p.startswith("/c/") and p.endswith("/confirm"):
            sid = unquote(p[len("/c/"):-len("/confirm")])
            try:
                rec = chat.confirm(form.get("msg", ""), int(form.get("i") or 0), day=form.get("day") or None, event_type=form.get("type") or None,
                                   risk=form.get("risk") or None, planned_task=form.get("planned_task") or None)
                status, body = chat_page(sid, message=f"원장에 들어감 {rec['id']} · {chat.KIND_LABEL.get(rec['kind'], rec['kind'])} {rec.get('observed_at', '')}")
            except (chat.ChatError, ValueError) as e:
                status, body = chat_page(sid, error=str(e))
        elif p.startswith("/c/") and p.endswith("/choose"):
            sid = unquote(p[len("/c/"):-len("/choose")])
            try:
                chat.choose_kind(form.get("msg", ""), form.get("kind", ""), today=config.today())
                self._send(302, "", f"/c/{quote(sid)}")
                return
            except chat.ChatError as e:
                status, body = chat_page(sid, error=str(e))
        elif p == "/me":
            try:
                u = profile.save(form.get("name", ""), form.get("role", "farmer"), note=form.get("note", ""))
                status, body = me_page(message=f"저장됨 — {u['name']} ({u['role']})")
            except profile.ProfileError as e:
                status, body = me_page(error=str(e), form=form)
        elif p == "/improve/request":
            try:
                r = fb.add_request(form.get("text", ""), target=form.get("target") or "other", subject=form.get("subject") or None, source="publisher")
                status, body = improve_page(message=f"접수 {r['id']}")
            except fb.FeedbackError as e:
                status, body = improve_page(error=str(e))
        elif p == "/improve/status":
            try:
                status, body = improve_page(message=chat_pages.handle_improve_status(form))
            except fb.FeedbackError as e:
                status, body = improve_page(error=str(e))
        elif p == "/improve/name":
            from names import candidates as nc
            try:
                if form.get("act") == "approve":
                    r = nc.approve(form.get("id", ""), form.get("canonical", ""), alias_kind=form.get("kind") or "사투리", by="publisher")
                    status, body = improve_page(message=f"사전 등재 — '{r['query']}' → {r['canonical']} ({r['alias_kind']}). 서버 재시작 없이 다음 새 채팅부터 통한다")
                else:
                    r = nc.reject(form.get("id", ""), why=form.get("why", ""), by="publisher")
                    status, body = improve_page(message=f"거부 — '{r['query']}'")
            except nc.CandidateError as e:
                status, body = improve_page(error=str(e))
        elif p == "/improve/cycle":
            status, body = improve_page(cycle=chat_pages.run_cycle(config.today(), git_head_short()))
        elif p == "/media/register":
            try:
                rec = media.register(form.get("key", ""), form.get("subject", ""),
                                     form.get("observed_at") or None, form.get("note", ""))
                status, body = media_page(message=f"등록됨 {rec['id']} · 관측 {rec['observed_at']} · {rec['file']}")
            except media.RegisterError as e:
                status, body = media_page(error=str(e))
        elif p == "/events/add":
            try:
                mats = [m.strip() for m in (form.get("materials") or "").split(",") if m.strip()]
                rec = ev.add_event(form.get("subject", ""), form.get("type", ""), form.get("observed_at", ""),
                                   note=form.get("note", ""), materials=mats)
                status, body = events_page(message=f"기록됨 {rec['id']} · {rec['type']} {rec['observed_at']}")
            except ev.EventError as e:
                status, body = events_page(error=str(e))
        elif p == "/events/reason":
            try:
                rec = ev.add_noncompliance(form.get("subject", ""), form.get("planned_task", ""), form.get("reason", ""), form.get("planned_day", ""))
                status, body = events_page(message=f"사유 기록됨 {rec['id']} · {rec['planned_task']}")
            except ev.EventError as e:
                status, body = events_page(error=str(e))
        else:
            status, body = 404, render.page("없음", nav_html(""), "<h1>없는 경로</h1>", "", "")
        self._send(status, body)

    def log_message(self, fmt: str, *args) -> None:  # 조용히
        pass


def make_server() -> ThreadingHTTPServer:
    host = config.assert_local(config.BIND)  # [D-6] 루프백 검증이 서버 생성보다 앞에 있다 (D-16 옵트인만 0.0.0.0 + 토큰)
    config.check_today()                     # [검토 ⑤] 잘못된 AGRODSS_TODAY 는 기동에서 막는다 — 요청마다 500 이 나고 원인이 숨던 형태
    from ingest import parcels as _parcels   # [U-18] 첫 기동에 씨앗의 PII 를 덮개(git 밖)로 옮긴다 — 발행자 PC 에서 pull 뒤 자동
    _parcels.ensure_local()
    return ThreadingHTTPServer((host, config.PORT), Handler)


def watch_head(srv, start_head: str, poll_sec: float, stop: threading.Event, head_fn=git_head_short) -> bool:
    """[발행자 2026-09-19 21:40 "수정된 것들은 리프레시하면 반영이 되어야 한다"] git HEAD 가 바뀌면(= git pull 이 내려앉으면) 서버를 내린다 —
    run_frontend.bat 가 새 코드로 다시 띄운다. True 면 HEAD 변화로 내렸다(종료 코드 3), False 면 stop 으로 끝났다(Ctrl+C).
    데이터(검정값 · 좌표 · 채팅)는 원래 요청마다 새로 읽으니 새로고침으로 충분했다 — 재시작이 필요했던 것은 코드뿐이다."""
    while not stop.wait(poll_sec):
        now = head_fn()
        if now not in ("?", "", start_head):
            print(f"[agrodss] 코드가 바뀌었다 {start_head} → {now} — 새 코드로 다시 뜬다(브라우저는 새로고침만)")
            srv.shutdown()
            return True
    return False


def main(open_browser: bool = True) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    srv = make_server()
    url = f"http://{config.HOST}:{config.PORT}/"
    head = git_head_short()
    print(f"[agrodss 내부 화면] {url}  HEAD {head}  (Ctrl+C 로 종료 · git pull 이 오면 스스로 다시 뜬다)")
    if open_browser:
        webbrowser.open(url)
    stop = threading.Event()
    restarted = {"v": False}
    if config.RELOAD_ON_HEAD_CHANGE:
        def _w() -> None:
            restarted["v"] = watch_head(srv, head, config.RELOAD_POLL_SEC, stop)
        threading.Thread(target=_w, daemon=True, name="agrodss-head-watch").start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        srv.server_close()
    return config.RESTART_EXIT_CODE if restarted["v"] else 0


if __name__ == "__main__":
    sys.exit(main(open_browser="--no-browser" not in sys.argv))
