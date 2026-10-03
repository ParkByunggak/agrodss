# -*- coding: utf-8 -*-
# FILE: frontend/chat_pages.py
# ROLE: [M-13] Claude 형식 화면 — 왼쪽 채팅 목록(= 등록된 재배 단위) · 가운데 대화 · 오른쪽 패널(오늘 · 판단 · 영농일지).
#       4층이다: 원장은 ingest 를 통해서만, 판단은 judge.run 봉투만. 파일을 직접 열지 않는다(I-5 §5).
from __future__ import annotations

import html
from datetime import date
from typing import Any
from urllib.parse import quote

from frontend import config, render, words
from grid import capture as grid_capture
from ingest import asks, chat, events as ev, feedback as fb, media, parcels, profile, subjects
from judge import evolve, registry, run as judge_run

BRAND = "AGRODSS"
BRAND_HTML = f'<a class="brand" href="/" id="brand" title="홈 — 첫 채팅으로">{BRAND} <small>내부 화면</small></a>'
DECISION_LABEL = {"harvest_timing": "수확 시기", "risk_alert": "위험 경보", "material_citation": "자재 인용", "plan_vs_actual": "계획 대 실제"}
DECISION_LABEL.update({k: d.name for k, d in registry.all_decisions().items() if k not in DECISION_LABEL})   # M-10 등록분은 등록부 이름
# [발행자 2026-09-21 "이런 답변을 보여 주는 것을 이해할 사람이 얼마나 될까?"] 단추의 말은 **사람 말 정본**에서 온다 —
# 내부 이름(사건 · 관찰 · 불이행 사유)을 단추에 그대로 쓰면 고르는 사람이 무엇을 고르는지 모른다.
CHOOSABLE = tuple((k, chat.KIND_PLAIN[k]) for k in
                  ("event", "observation.note", "plan.farmer", "decision.noncompliance", "feedback.request", "subject.end"))


def _e(v: Any) -> str:
    return html.escape("" if v is None else str(v))


CSS = """
:root { --bg:#FAF9F5; --panel:#FFFFFF; --side:#F1EFE8; --fg:#1F1E1B; --muted:#6F6B62; --line:#E4E1D8; --accent:#C6613F;
  --accent-ink:#FFFFFF; --bubble:#EDE8DF; --sys:#FFFFFF; --ok:#DDF0E2; --ok-fg:#1F6B35; --warn:#FBEFD0; --warn-fg:#8A5A00;
  --err:#F6DEDE; --err-fg:#8C2B2B; --chip:#F1EFE8; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#1E1D1A; --panel:#26241F; --side:#181714; --fg:#ECE9E1; --muted:#A39E93; --line:#3A372F; --accent:#E0784F;
  --accent-ink:#1A120E; --bubble:#3A362D; --sys:#26241F; --ok:#16301C; --ok-fg:#7FD095; --warn:#3A2E12; --warn-fg:#F0C060;
  --err:#3A1A1A; --err-fg:#F09090; --chip:#2E2B25; } }
:root[data-theme="dark"] { --bg:#1E1D1A; --panel:#26241F; --side:#181714; --fg:#ECE9E1; --muted:#A39E93; --line:#3A372F;
  --accent:#E0784F; --accent-ink:#1A120E; --bubble:#3A362D; --sys:#26241F; --ok:#16301C; --ok-fg:#7FD095; --warn:#3A2E12;
  --warn-fg:#F0C060; --err:#3A1A1A; --err-fg:#F09090; --chip:#2E2B25; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font-family:"Noto Sans KR","Malgun Gothic","Apple SD Gothic Neo",-apple-system,sans-serif; font-size:14.5px; line-height:1.55; }
a { color:inherit; }
.app { display:grid; grid-template-columns:260px 1fr 340px; min-height:100vh; }
aside.side { background:var(--side); border-right:1px solid var(--line); padding:14px 12px; position:sticky; top:0; height:100vh; overflow:auto; }
.brand { font-weight:700; letter-spacing:.02em; font-size:16px; padding:4px 8px 10px; display:flex; justify-content:space-between; align-items:center; text-decoration:none; color:var(--fg); }
.brand:hover { color:var(--accent); }
.brand small { color:var(--muted); font-weight:400; font-size:11px; }
.newchat { display:block; width:100%; text-align:left; padding:8px 10px; border:1px solid var(--line); background:var(--panel); border-radius:8px; color:var(--fg); text-decoration:none; font-size:13.5px; margin-bottom:12px; }
.newchat:hover { border-color:var(--accent); }
.grp { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.08em; padding:8px 8px 4px; }
.chat { display:block; padding:8px 10px; border-radius:8px; text-decoration:none; color:var(--fg); margin-bottom:2px; }
.chat:hover { background:var(--panel); } .chat.on { background:var(--panel); border:1px solid var(--line); }
.chat b { display:block; font-weight:600; font-size:13.5px; } .chat span { color:var(--muted); font-size:12px; }
.pill { display:inline-block; font-size:11px; padding:0 7px; border-radius:9px; background:var(--chip); color:var(--muted); margin-left:4px; }
.pill.run { background:var(--ok); color:var(--ok-fg); } .pill.plan { background:var(--warn); color:var(--warn-fg); } .pill.end { background:var(--chip); color:var(--muted); }
.side .lnk { display:block; padding:5px 10px; font-size:13px; color:var(--muted); text-decoration:none; } .side .lnk:hover { color:var(--fg); }
aside.side { display:flex; flex-direction:column; }
""" + render.USER_MENU_CSS + """
main.thread { display:flex; flex-direction:column; min-height:100vh; min-width:0; }   /* [U-34] 그리드 항목의 min-width:auto 가 안쪽 폼 폭(size=60)에 밀려 화면을 넘겼다(390px 실측: 개선 화면 832 · 내 정보 475) */
.thead { position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line); padding:12px 24px; display:flex; justify-content:space-between; align-items:center; z-index:2; }
.thead h1 { font-size:16px; margin:0; font-weight:600; } .thead .meta { color:var(--muted); font-size:12px; }
.thead a { font-size:13px; color:var(--muted); margin-left:12px; }
.msgs { flex:1; padding:20px 24px 140px; max-width:820px; width:100%; margin:0 auto; }
.msg { margin:14px 0; display:flex; gap:10px; }
.msg.me { justify-content:flex-end; } .msg.me .bub { background:var(--bubble); border-radius:16px 16px 4px 16px; padding:10px 14px; max-width:78%; white-space:pre-wrap; }
.msg.sys .bub { max-width:88%; white-space:pre-wrap; padding:2px 0; }
.msg.sys .av { width:26px; height:26px; border-radius:50%; background:var(--accent); color:var(--accent-ink); font-size:12px; display:flex; align-items:center; justify-content:center; flex:none; margin-top:2px; }
.ts { color:var(--muted); font-size:11px; margin-top:4px; }
.acts { display:flex; gap:2px; margin-top:2px; opacity:.55; } .acts.right { justify-content:flex-end; } .msg:hover .acts { opacity:1; }
.acts .inline { display:inline; margin:0; }
/* [발행자 2026-09-22] '고쳐 달라기' 를 누르면 **적는 칸**이 열린다 — 자바스크립트 없이 <details> 로. */
.acts .ask { display:inline-block; }
.acts .ask > summary { list-style:none; cursor:pointer; display:inline-flex; align-items:center; gap:4px; }
.acts .ask > summary::-webkit-details-marker { display:none; }
.acts .ask[open] { display:block; width:100%; }
.acts .ask form { margin:6px 0 0; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px 12px; max-width:560px; }
.acts .ask .q { color:var(--muted); font-size:12px; margin-bottom:6px; }
.acts .ask textarea { width:100%; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--fg); font:inherit; font-size:13px; padding:6px 8px; resize:vertical; }
.acts .ask .btn { margin-top:6px; }
.act { display:inline-flex; align-items:center; gap:4px; border:0; background:transparent; color:var(--muted); font-size:11.5px; padding:3px 6px; border-radius:6px; cursor:pointer; }
.act:hover { background:var(--chip); color:var(--fg); }
.draft { margin:6px 0 0 36px; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px 12px; font-size:13px; }
.draft b { font-weight:600; } .draft form { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-top:6px; }
.draft input, .draft select { padding:4px 8px; border:1px solid var(--line); border-radius:6px; background:var(--bg); color:var(--fg); font-size:13px; }
.btn { padding:5px 12px; border-radius:7px; border:1px solid var(--line); background:var(--panel); color:var(--fg); cursor:pointer; font-size:13px; }
.btn.pri { background:var(--accent); color:var(--accent-ink); border-color:var(--accent); }
.done { color:var(--ok-fg); background:var(--ok); padding:2px 8px; border-radius:6px; font-size:12px; }
/* [발행자 2026-09-22] 꼬리는 **화면 가운데 아래**. 자리는 여기 한 곳이 정한다 — 본문에 박으면 다음 요청 때 여러 곳을 고친다.
   `pointer-events:none` 이 짝이다: 가운데로 오면 입력칸 위를 지나므로, 글자가 클릭을 먹으면 안 된다.
   입력칸 아래 여백(18px→28px)은 그 자리를 비워 두려고 함께 늘렸다 — 안 늘리면 글자와 상자가 겹친다. */
#footer { position:fixed; left:0; right:0; bottom:6px; text-align:center; pointer-events:none; z-index:3;
  color:var(--muted); font-size:10px; line-height:1.3; padding:0 12px; }
.composer { position:fixed; bottom:0; left:260px; right:340px; padding:14px 24px 28px; background:linear-gradient(transparent, var(--bg) 30%); }
.composer form { max-width:820px; margin:0 auto; background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:10px 12px; box-shadow:0 4px 18px rgba(0,0,0,.06); }
.composer textarea { width:100%; border:0; background:transparent; color:var(--fg); resize:none; font:inherit; min-height:52px; outline:none; }
.composer .row { display:flex; justify-content:space-between; align-items:center; margin-top:4px; }
.composer .hint { color:var(--muted); font-size:12px; }
.composer .files { font-size:12px; color:var(--muted); margin:4px 0; } .composer .files input { padding:3px 6px; border:1px solid var(--line); border-radius:6px; background:var(--bg); color:var(--fg); }
@media (max-width:720px) { .composer .row { flex-wrap:wrap; gap:6px; } .composer .hint { display:none; } .msg.me .bub { max-width:92%; } .thead { padding:10px 14px; } }
aside.panel { border-left:1px solid var(--line); background:var(--panel); padding:16px 16px 40px; position:sticky; top:0; height:100vh; overflow:auto; }
.panel h2 { font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); margin:14px 0 6px; }
.panel h2:first-child { margin-top:0; }
.card { border:1px solid var(--line); border-radius:10px; padding:10px 12px; margin-bottom:8px; font-size:13px; background:var(--bg); }
.card b { font-weight:600; } .card .k { display:inline-block; font-size:11px; padding:0 6px; border-radius:6px; background:var(--chip); color:var(--muted); margin-right:4px; }
.card.kind-판단함 { border-left:3px solid var(--ok-fg); } .card.kind-판단불가 { border-left:3px solid var(--warn-fg); }
.diary .day { font-weight:600; margin:12px 0 4px; font-size:13px; } .diary .it { padding:4px 0; border-bottom:1px dashed var(--line); font-size:13px; }
.diary .it .k { display:inline-block; min-width:52px; color:var(--muted); font-size:12px; }
.form { max-width:620px; margin:32px auto; background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:20px 22px; }
.form label { display:block; margin:10px 0 4px; font-size:13px; color:var(--muted); }
.form input, .form select { width:100%; padding:8px 10px; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--fg); font:inherit; }
.err { color:var(--err-fg); background:var(--err); padding:8px 12px; border-radius:8px; margin:10px 0; } .ok { color:var(--ok-fg); background:var(--ok); padding:8px 12px; border-radius:8px; margin:10px 0; }
.msgs code { overflow-wrap:anywhere; }   /* [U-34] 긴 code(경로 · 명령)가 줄을 안 바꿔 390px 에서 넘쳤다(내 정보 446 · 개선 화면 494 실측) — 주석에 화면 경로를 적지 않는다(검사 문자열과 겹친다 · §7.1 4번) */
table.tb { border-collapse:collapse; width:100%; font-size:13px; } .tb th, .tb td { border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; } .tb th { color:var(--muted); font-weight:500; }
@media (max-width:1100px) { .app { grid-template-columns:220px 1fr; } aside.panel { display:none; } .composer { right:0; left:220px; } }
@media (max-width:720px) { .app { grid-template-columns:1fr; } aside.side { position:static; height:auto; } .composer { left:0; } .msgs { padding-inline:16px; } }
/* [U-34 2026-09-26 · 실제 브라우저 390px 실측] 좁은 화면에서 넘치던 것 — 폼 입력칸(size=40·60) · 표 · 긴 머리글. 폭은 화면이 정하고 표는 제자리에서 옆으로 민다 */
.msgs { min-width:0; } .msgs input, .msgs select, .msgs textarea { max-width:100%; box-sizing:border-box; } .msgs form { max-width:100%; }   /* 폭 전부 — 768px 에서도 size=60 이 넘쳤다(실측 811) */
@media (max-width:720px) { table.tb { display:block; overflow-x:auto; } .thead { flex-wrap:wrap; gap:6px; } .thead h1 { overflow-wrap:anywhere; } }
"""


def shell(title: str, side: str, main: str, panel: str | None, footer: str) -> str:
    """[발행자 화면 2026-09-21] 발행자가 붙여 주신 꼬리가 결함을 그대로 보여 주었다:

        HEAD 실행 중 225cf9f · 127.0.0.1:8765 · 외부 배포 없음(D-6) · 127.0.0.1:8765 · 외부 배포 없음(D-6)

    받은 것은 **꼬리 정본**(`serve.footer_text()` — 실행 중 커밋 · 호스트 · D-6 · AI 고지를 이미 담고 있다)인데,
    이 자리가 그것을 `head` 라고 부르며 **호스트·포트·D-6 을 한 번 더** 붙이고 앞에 낡은 `HEAD ` 까지 달았다.
    두 벌 진실의 표현 층 판이다 — 정본이 바뀌어도 이 사본은 안 바뀐다(실제로 '실행 중' 으로 고친 뒤에도
    `HEAD` 라는 말이 남아, 읽는 사람에게는 *저장소 HEAD* 로 보였다).

    받은 것을 **그대로** 싣는다. 이름도 `footer` 로 바꾼다 — `head` 라는 이름이 이 사본을 부른 원인이다.

    [발행자 2026-09-22] *"이 문장은 화면의 **중앙**에 위치하도록 한다."* — 오른쪽 구석에서 가운데로 옮겼다.
    자리(스타일)는 CSS 의 `#footer` 하나가 정한다: 본문에 박아 두면 다음 요청 때 여기저기를 고쳐야 하고,
    검사도 그 문자열을 물고 있어 **맞는 고침이 관문을 빨갛게 만든다**(오늘 네 번 겪은 그 형태).
    """
    # [①⑤a 걷기 실측 2026-09-29] 이 덮어쓰기가 CSS 뒤에 실려 720px 미디어 규칙(.app{1fr})을 이겼다 — 휴대폰(390px)에서 패널 없는 화면 전부
    # (/me · /me/outlook · /c/new · /diary · /selfcheck)가 사이드바 260px + 본문 130px 이었다(/me/outlook 은 400px 로 넘침). 데스크톱에서만 덮어쓴다.
    cols = "" if panel is not None else "<style>@media (min-width:721px){.app{grid-template-columns:260px 1fr}}.composer{right:0}</style>"
    title = title if title.startswith(BRAND) else f"{BRAND} — {title}"
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="icon" href="data:,">'
            f"<title>{_e(title)}</title><style>{CSS}</style>{cols}</head><body><div class=\"app\">"
            f'<aside class="side">{side}</aside><main class="thread">{main}</main>'
            + (f'<aside class="panel">{panel}</aside>' if panel is not None else "")
            + f'</div><div id="footer">{_e(footer)}</div></body></html>')


def sidebar(current: str, docs: list[str], today: date) -> str:
    # [발행자 2026-09-19] 좌측 상단 탭 = AGRODSS(대문자) · 홈(/) 링크 · 모든 화면에 있다
    # [§7.5 전수 2026-09-21] 이 이름들은 **모든 페이지**에 실린다 — 한 낱말이 152곳 중 열 몇 곳을 혼자 만들고 있었다.
    out = [BRAND_HTML, '<a class="newchat" href="/c/new">＋ 새 채팅 (작목 추가 · 계획)</a>',
           '<div class="grp">채팅 — 짓는 농사</div>']
    subs = subjects.load()
    if not subs:
        out.append('<div class="lnk">아직 목록이 없다 — 새 채팅으로 작목을 더한다</div>')
    for s in subs:
        st = s.get("status") or ("재배 중" if s.get("anchor") else "계획")
        meta = f"{_e(s.get('season'))}" + (f" · 심은 지 {(today - date.fromisoformat(s['anchor'])).days}일" if s.get("anchor") else " · 파종 전")
        cls = ' on' if current == f"/c/{s['id']}" else ""
        pill = {"재배 중": "run", "종료": "end"}.get(st, "plan")          # 종료(작기 종료 경로 2026-09-20)는 계획 색이 아니라 회색
        out.append(f'<a class="chat{cls}" href="/c/{quote(s["id"])}"><b>{_e(s.get("crop"))}<span class="pill {pill}">{_e(st)}</span></b><span>{meta}</span></a>')
    out.append('<div class="grp">화면</div>')
    first = subs[0]["id"] if subs else ""
    for href, label in (("/improve", "고쳐 달라는 말 · 스스로 개선"), ("/judge", "판단 전체"), ("/selfcheck", "자기 점검 — 화면이 스스로 확인"),   # [①⑤a 2026-09-29]
                        ("/me/decisions", "결정 — 한 화면에서 답하기"),   # [WO-PB-01 다음 한 수 2026-09-29] 검토지(파일)가 11일째 비어 있던 자리를 화면으로
                        ("/media", "영상 반입"), ("/events", "한 일 · 못 한 이유(표)"),
                        (f"/mall/{quote(first)}" if first else "/c/new", "몰 상세페이지 목업 (M-11)")):
        out.append(f'<a class="lnk" href="{href}">{label}</a>')
    out.append('<div class="grp">문서</div>')
    for name in docs:
        out.append(f'<a class="lnk" href="/doc/{_e(name)}">{_e(name.removesuffix(".md"))}</a>')
    out.append(user_tab_html(current))
    return "".join(out)


# [발행자 2026-09-20 화면 형식 — 계정 메뉴 스크린샷] 사용자 탭을 누르면 위로 열리는 메뉴. 그 형식에서 agrodss 에 **실재하는** 항목만 옮겼다:
#   설정 → /me · 도움 받기 → 채팅 화면 설명 · 모든 플랜 보기 → 모든 목록 · 앱/확장 → 휴대폰 동기화(D-16) · 변경 로그 → /changes · 자세히 → 대장.
#   언어 · 팀 참여 · 로그아웃은 넣지 않았다 — 언어 전환 · 팀 · 계정이 없다(D-6 이 PC 뿐). 없는 기능을 메뉴에 두면 눌러서 실망하는 항목이 된다.
USER_MENU: tuple[tuple[str, str, str] | None, ...] = (
    ("/me", "설정", "사용자 정보 · 필지 · 동기화"),
    ("/doc/m13_chat_screen.md", "도움 받기", "채팅 화면 설명"),
    None,
    ("/", "모든 목록 보기", "짓는 농사별 채팅"),
    ("/judge", "판단 보기", "수확 시기 · 위험 경보 · 계획 대 실제"),
    ("/events", "한 일 · 못 한 이유", "표로 직접 적기"),
    ("/media", "영상 · 사진 반입", "촬영 시각이 붙어야 등록"),
    ("/improve", "고쳐 달라는 말", "말씀하신 것 → 고칠 항목"),
    ("/me#sync", "휴대폰 동기화", "같은 Wi-Fi · 토큰"),
    None,
    ("/changes", "변경 로그 보기", "커밋 이력 · 실행 중 코드"),
    ("/doc/agrodss_backlog.md", "자세히 알아보기", "작업 기록 · 문서"),
)


def user_tab_html(current: str) -> str:
    """[발행자 2026-09-19] 채팅 목록 최하단 — 사용자 정보 탭. **매 페이지**에 있다(채팅 셸 · 표 화면 · 404 까지) — 정본은 이 함수 하나.
    [2026-09-20] 탭이 메뉴(USER_MENU)를 연다. 이름 · 역할만 보인다 — 이메일 · 연락처는 등록부에 없다(PII)."""
    u = profile.load()
    name, role = u.get("name") or "사용자 정보", u.get("role") or ""
    cls = ' on' if current == "/me" else ""
    items = []
    for it in USER_MENU:
        if it is None:
            items.append("<hr>")
            continue
        href, label, sub = it
        on = ' class="on"' if href == current else ""
        items.append(f'<a href="{href}"{on}>{_e(label)}' + (f"<small>{_e(sub)}</small>" if sub else "") + "</a>")
    return (f'<details class="umenu" id="user-tab"><summary class="user{cls}"><b>{_e(name)}<span class="pill">{_e(role)}</span></b>'
            f'<span>필지 {len(u.get("parcels") or [])} · 메뉴 ▴</span></summary>'
            f'<div class="ulist"><div class="uhead">{_e(name)} · {_e(role)}</div>{"".join(items)}</div></details>')


# [발행자 2026-09-21 "필지 3문항과 토성·경사가 비어 있어서 병해충 필지 보정과 과습 판정이 막혀 있다"]
# 실측 ①: `missing_inputs` 는 **보여 주기만** 했고 쓰는 길은 CLI 뿐이었다 — 밭에서 답을 받아 와도 JSON 을 손으로 고쳐야 했다.
#         그래서 답이 들어갈 자리를 만든다. 규율 셋: **PII 는 폼에도 없다**(주소 · PNU · 좌표 — D-1 · U-18) ·
#         빈 칸은 빈 채로 둔다(대리값 금지) · 쓰기는 덮개에만(`parcels.set_fields`).
# 실측 ②: 그 값을 **읽는 쪽**을 같은 자리에서 셌더니 use · environment 둘뿐이었다(parcels.FIELDS_READ_BY_JUDGMENT 의 G1 전수).
#         [2026-10-03] 배수(drainage)가 셋째가 됐다 — 과습 위험의 근거가 읽는다(WO-ASK-01 결정 ① 「가」). 표지는 등록부 분할에서 자동으로 바뀐다.
#         미기상은 격자 칸 3 축에 이름만 있고 값을 읽는 코드가 없다 — 채워도 오늘은 병해충 판정이 달라지지 않는다.
#         그래서 화면이 그렇게 **말한다**. 열리지 않을 판정을 열린다고 하면 밭에 헛걸음을 시킨다.
# 어휘 목록은 여기 두지 않는다 — 등록부(ingest.parcels.FIELD_CHOICES)가 정본이고 CLI 도 같은 것을 본다.
READS_LABEL = "판정이 읽는 값"
STORED_ONLY_LABEL = "지금은 등록부에만 쌓인다(읽는 판정 없음)"


def _parcel_note(key: str) -> str:
    tag = READS_LABEL if key in parcels.FIELDS_READ_BY_JUDGMENT else STORED_ONLY_LABEL
    return f' <span style="color:var(--muted)">— {tag}</span>'


def parcel_form(p: dict[str, Any]) -> str:
    """밭에서 받아 온 답이 들어갈 자리. 주소·PNU·좌표는 **폼에도 없다**(PII)."""
    rows = ['<form method="post" action="/me/parcel" style="margin-top:8px">'
            f'<input type="hidden" name="id" value="{_e(p["id"])}">']
    for key, opts in parcels.FIELD_CHOICES.items():
        cur = p.get(key)
        sel = "".join(f'<option value="{_e(o)}"{" selected" if cur == o else ""}>{_e(o)}</option>' for o in opts)
        rows.append(f'<label>{_e(key)}{_parcel_note(key)}</label>'
                    f'<select name="{key}"><option value="">— 모름(비워 둔다)</option>{sel}</select>')
    for key, label in parcels.FIELD_LABELS:
        rows.append(f'<label>{_e(label)}{_parcel_note(key)}</label><input name="{key}" value="{_e(p.get(key) or "")}">')
    rows.append('<div style="margin-top:8px"><button class="btn pri" type="submit">필지 저장</button>'
                '<span style="color:var(--muted)"> — 빈 칸은 건드리지 않는다(모르는 것을 지어내지도, 있는 값을 지우지도 않는다). '
                '주소·좌표는 이 화면에 없다(PII)</span></div></form>')
    return '<div class="form">' + "".join(rows) + "</div>"


OUTLOOK_FIELDS: tuple[tuple[str, str, str], ...] = (
    # (폼 이름, 라벨, 입력 종류) — 값은 발표문 그대로. 파일 climate_outlook_local.json 의 열과 같다(두 벌 진실이 아니라 같은 열의 두 입구)
    ("issued_on", "발표일 (YYYY-MM-DD)", "date"),
    ("target_from", "대상 시작 (YYYY-MM-DD)", "date"),
    ("target_to", "대상 끝 (YYYY-MM-DD)", "date"),
    ("region", "지역 (발표문 표기 그대로 · 예: 충북)", "text"),
    ("source_title", "출처 제목 (예: 기상청 1개월 전망 2026.10.5.~11.1.)", "text"),
    ("source_url", "출처 주소 (발표문 URL · 필수)", "url"),
    ("note", "비고 (선택)", "text"),
)
TERCILE_LABELS = {"temp": ("기온", ("높음", "비슷", "낮음")), "precip": ("강수", ("많음", "비슷", "적음"))}


def outlook_form_entry(form: dict[str, str]) -> dict[str, Any]:
    """폼 → 등재 항목(검증은 ingest.outlook 이 한다 — 여기서는 모양만 옮긴다 · 3분위 셋이 다 비면 그 축은 없음)."""
    e: dict[str, Any] = {"period_type": (form.get("period_type") or "").strip()}
    for k, _, _ in OUTLOOK_FIELDS:
        v = (form.get(k) or "").strip()
        if v:
            e[k] = v
    for axis in ("temp", "precip"):
        vals = {k: (form.get(f"{axis}_{k}") or "").strip() for k in ("above", "normal", "below")}
        if any(vals.values()):
            e[axis] = {k: (float(v) if v.replace(".", "", 1).isdigit() else v) for k, v in vals.items()}   # 숫자 아닌 것은 그대로 넘겨 검증이 이유를 말하게
    return e


def outlook_main(message: str = "", error: str = "", form: dict[str, str] | None = None) -> str:
    """[⑤b 2026-09-28 · 발행자 승인 "제안 순서대로"] 1·3개월 전망 입력 폼 — JSON 손 편집의 오류를 없앤다. 덮개(git 밖)에만 쓴다 · 저장 전에 합≈100 · URL 을 말한다."""
    from ingest import outlook as _ol
    f = form or {}
    out = ['<div class="thead"><div><h1>장기 전망 등재</h1><div class="meta">기상청 1·3개월 전망 발표문의 수치를 출처와 함께 — 시스템은 여기 적힌 것만 낸다(값을 지어내지 않는다). '
           '덮개 파일(git 밖)에 저장되어 update.bat 이 건드리지 않는다.</div></div></div><div class="msgs">']
    if error:
        out.append(f'<p class="err">{_e(error)}</p>')
    if message:
        out.append(f'<p class="ok">{_e(message)}</p>')
    pt = f.get("period_type") or "1개월"
    rows = ['<div class="form" style="margin-top:8px"><form method="post" action="/me/outlook">',
            '<label>전망 종류</label><select name="period_type">' + "".join(f'<option value="{p}"{" selected" if pt == p else ""}>{p} 전망</option>' for p in _ol.PERIOD_TYPES) + '</select>']
    for k, label, kind in OUTLOOK_FIELDS:
        rows.append(f'<label>{_e(label)}</label><input name="{k}" type="{kind}" value="{_e(f.get(k) or "")}"{" required" if k in ("issued_on", "target_from", "target_to", "region", "source_title", "source_url") else ""}>')
    for axis, (name, words) in TERCILE_LABELS.items():
        cells = "".join(f'<label style="display:inline-block;width:30%">{w} %<input name="{axis}_{k}" type="number" min="0" max="100" step="1" value="{_e(f.get(f"{axis}_{k}") or "")}"></label> '
                        for w, k in zip(words, ("above", "normal", "below")))
        rows.append(f'<div style="margin-top:6px"><b>{name}</b> 확률 3분위 — 합 100(±5)<br>{cells}</div>')
    rows.append('<div style="margin-top:12px"><button class="btn pri" type="submit">등재</button>'
                '<span style="color:var(--muted)"> — 틀린 것(합 100 아님 · URL 없음 · 날짜 꼴)은 저장하지 않고 이유를 말한다. 같은 항목을 두 번 눌러도 한 번만 남는다</span></div></form></div>')
    out.extend(rows)
    out.append('<h2 style="font-size:14px">등재된 것</h2>')
    recs, bad = _ol.load()
    today = config.today().isoformat()                                                  # 화면의 오늘은 정본 하나(AGRODSS_TODAY 고정을 따른다 — today 래칫)
    if not recs and not bad:
        out.append('<p class="meta">아직 없다 — 지금 날씨 물음은 「장기 — 없음: 등재된 장기 전망 없음」 이라고 답한다.</p>')
    for i, e in enumerate(_ol.local_entries()):
        try:
            r = _ol.entry_to_record(e)
            t, p = r["values"].get("temp"), r["values"].get("precip")
            fmt = lambda d, ws: "" if not d else " / ".join(f"{w} {d[k]:g}%" for w, k in zip(ws, ("above", "normal", "below")))
            live = "" if r["period_to"] >= today else ' <span class="st st-보류">지난 기간</span>'
            out.append(f'<div class="card"><b>{_e(r["period_type"])} 전망 · {_e(r["period_from"])} ~ {_e(r["period_to"])} · {_e(r["region"])}</b>{live}'
                       f'<div>기온 {_e(fmt(t, ("높음", "비슷", "낮음")))} · 강수 {_e(fmt(p, ("많음", "비슷", "적음")))}</div>'
                       f'<div class="meta">발표 {_e(r["observed_at"])} · <a href="{_e(r["citation"]["url"])}">{_e(r["citation"]["title"])}</a></div>'
                       f'<form method="post" action="/me/outlook/delete" style="margin-top:4px"><input type="hidden" name="index" value="{i}"><button class="btn" type="submit">이 항목 지우기</button></form></div>')
        except ValueError as err:
            out.append(f'<div class="card kind-판단불가"><b>못 읽음 — 덮개 {i + 1}번째</b><div class="meta">{_e(str(err))}</div>'
                       f'<form method="post" action="/me/outlook/delete" style="margin-top:4px"><input type="hidden" name="index" value="{i}"><button class="btn" type="submit">이 항목 지우기</button></form></div>')
    n_seed = len(recs) - sum(1 for e in _ol.local_entries() if _safe_entry(e))          # 읽힌 전체 − 덮개의 읽힌 것 = 씨앗의 것
    if n_seed > 0:
        out.append(f'<p class="meta">씨앗(저장소 · 세션 커밋)에도 {n_seed}건 — 화면에서는 못 지운다.</p>')
    for why in bad:
        if not why.startswith(_ol.local_path().name):
            out.append(f'<p class="err">씨앗 못 읽음 — {_e(why)}</p>')
    out.append('<p class="meta">파일로 넣어도 된다: <code>data/kma/climate_outlook_local.json</code> — 같은 열이다. 지난 기간은 두어도 된다(오늘 뒤만 낸다).</p></div>')
    return "".join(out)


def _safe_entry(e: dict[str, Any]) -> bool:
    from ingest import outlook as _ol
    try:
        _ol.entry_to_record(e)
        return True
    except ValueError:
        return False


def decisions_main(message: str = "", error: str = "", form: dict[str, str] | None = None) -> str:
    """[WO-PB-01 다음 한 수 · 발행자 승인 2026-09-29] 일괄 결정 — 발행자만 답할 수 있는 것(P1)을 제안값과 함께 한 화면에. 답은 덮개(git 밖)에만.
    발행자 셋: 「모르겠다」 1급 선택지(쌓이면 P4 신호) · 제안값의 출처 표시(추론은 맞다를 눌러도 남는다) · 맨 위 D-2."""
    from ingest import decisions as dc
    f = form or {}
    answers, unreadable = dc.read_for_screen()          # 못 읽으면 (빈 답, 이유) — 화면은 500 이 아니라 이유를 말한다(U-21)
    sm = dc.summary(answers)
    c = sm["counts"]
    out = ['<div class="thead"><div><h1>결정 — 한 화면에서 답하기</h1><div class="meta">발행자만 답할 수 있는 것을 제안값과 함께 놓았다. 줄마다 맞다 / 다르다(→ 무엇) / 모르겠다 중 하나. '
           '답은 이 PC 의 덮개 파일(git 밖)에 남고, 아래 「세션에 보낼 것」 을 붙이면 세션이 작업 기록에 옮긴다 — 이 화면은 항목을 닫지 않는다.</div></div></div><div class="msgs">']
    if error:
        out.append(f'<p class="err">{_e(error)}</p>')
    if message:
        out.append(f'<p class="ok">{_e(message)}</p>')
    if unreadable:
        out.append(f'<p class="err">답 파일을 못 읽었다 — {_e(unreadable)}. 고치기 전까지 답은 저장되지 않는다(파일은 그대로 둔다 · 변경 로그 「읽다 버린 것」 에도 뜬다).</p>')
    out.append(f'<p class="meta">답 {sm["answered"]}/{sm["total"]} · 맞다 {c["맞다"]} · 다르다 {c["다르다"]} · 모르겠다 {c["모르겠다"]}</p>')
    if sm["unknown_ids"]:
        out.append(f'<p class="meta">모르겠다 {len(sm["unknown_ids"])}건({_e(" · ".join(sm["unknown_ids"]))}) — 모르겠다가 쌓이면 그 항목은 발행자만 답할 수 있는 것이 아니라 '
                   '아직 어디에도 없는 값이었다는 신호다(첫 시즌 실측을 기다린다). 세션이 그 갈래를 고친다.</p>')
    # [발행자 2026-10-03 "상한에 닿은 항목이 '모르겠다'로 떨어지는 것과 같은 자리에 가도록"] 묻기 원장에서 반복 상한에 닿아 멈춘 물음 — 같은 신호, 같은 자리
    if sm.get("stopped_asks_why"):
        out.append(f'<p class="err">물은 것 기록을 못 읽었다 — {_e(sm["stopped_asks_why"])}</p>')
    elif sm.get("stopped_asks"):
        rows = " · ".join(f'<span title="{_e(r.get("axis"))}">{_e(words.axis(r.get("axis")))}</span> {int(r.get("count", 0))}번' for r in sm["stopped_asks"])
        out.append(f'<p class="meta">더 묻지 않는 것 {len(sm["stopped_asks"])}건({rows}) — 같은 것을 상한만큼 물었는데 답이 안 왔다. 모르겠다와 같은 신호다: '
                   '농가 몫이 아니라 아직 어디에도 없는 값일 수 있다(상한 값은 발행자 추론 · 밭 정보 화면에 적으면 풀린다).</p>')
    for it in dc.ITEMS:
        a = answers.get(it["id"])
        out.append(f'<div class="card dec"><b>{_e(it["id"])} · {_e(it["ask"])}</b>'
                   f'<div style="margin-top:4px">제안: {_e(it["default"])} <span class="st">{_e(it["basis"])}</span></div>'
                   f'<div class="meta">{_e(dc.BASIS_SAID[it["basis"]])}</div>'
                   f'<div class="meta">풀리는 것: {_e(it["unblocks"])}</div>')
        if it["id"] in dc.DECIDED:
            out.append(f'<div class="ok">결정됨: {_e(dc.DECIDED[it["id"]])}</div>')     # 답한 카드로 남는다 — 지우기는 발행자 몫(세션 커밋)
        elif a:
            out.append(f'<div class="ok">답: {_e(a.get("verdict", ""))}{(" — " + _e(a["note"])) if a.get("note") else ""} <span class="meta">{_e(render.local_time(a.get("at")))}</span></div>'     # 시각은 local_time 으로만(C16 — [:10] 은 UTC 날짜를 잘라 저녁 답이 어제로 뜬다)
                       f'<form method="post" action="/me/decisions/delete" style="margin-top:4px"><input type="hidden" name="id" value="{_e(it["id"])}"><button class="btn" type="submit">이 답 지우기</button></form>')
        else:
            mine = f.get("id") == it["id"]
            picked = (f.get("verdict") or "") if mine else ""
            radios = " ".join(f'<label style="display:inline-block;margin-right:10px"><input type="radio" name="verdict" value="{v}"{" checked" if picked == v else ""} required> {v}</label>' for v in dc.VERDICTS)
            out.append(f'<form method="post" action="/me/decisions" style="margin-top:6px"><input type="hidden" name="id" value="{_e(it["id"])}">{radios}'
                       f'<input name="note" placeholder="다르다면 → 무엇" value="{_e((f.get("note") or "") if mine else "")}" style="width:60%;max-width:420px">'
                       f' <button class="btn pri" type="submit">저장</button></form>')
        out.append('</div>')
    text = dc.to_session_text(answers)
    out.append('<h2 style="font-size:14px">세션에 보낼 것</h2><p class="meta">답한 것만 · 항목 순서 · 한 줄씩. 이 글을 세션에 붙이면 세션이 작업 기록에 옮기고 항목을 닫는다.</p>')
    out.append(f'<pre class="send" style="white-space:pre-wrap">{_e(text) if text else "아직 답이 없다"}</pre></div>')
    return words.plain("".join(out))


def me_main(message: str = "", error: str = "", form: dict[str, str] | None = None) -> str:
    u = profile.load()
    f = form or {}
    out = ['<div class="thead"><div><h1>사용자 정보</h1><div class="meta">이름·역할·필지·설정. 연락처와 주소는 두지 않는다(PII).</div></div></div><div class="msgs">']
    if error:
        out.append(f'<p class="err">{_e(error)}</p>')
    if message:
        out.append(f'<p class="ok">{_e(message)}</p>')
    roles = "".join(f'<option value="{r}"{" selected" if (f.get("role") or u.get("role")) == r else ""}>{r}</option>' for r in profile.ROLES)
    out.append('<div class="form" style="margin-top:8px"><form method="post" action="/me">'
               f'<label>표시명</label><input name="name" value="{_e(f.get("name") or u.get("name") or "")}" required>'
               f'<label>역할</label><select name="role">{roles}</select>'
               f'<label>메모(연락처 금지)</label><input name="note" value="{_e(f.get("note") or u.get("note") or "")}">'
               '<div style="margin-top:12px"><button class="btn pri" type="submit">저장</button></div></form></div>')
    out.append('<h2 style="font-size:14px">장기 전망</h2><p class="meta"><a href="/me/outlook">장기 전망 등재 →</a> 기상청 1·3개월 전망 발표문 수치를 출처와 함께(덮개 · git 밖). 날씨 물음의 「장기」 줄이 이것을 낸다.</p>')
    out.append('<h2 style="font-size:14px">결정</h2><p class="meta"><a href="/me/decisions">결정 — 한 화면에서 답하기 →</a> 발행자만 답할 수 있는 것을 제안값과 함께. 줄마다 맞다 / 다르다 / 모르겠다.</p>')
    out.append('<h2 style="font-size:14px">필지</h2>')
    for p in parcels.load():
        v = parcels.public_view(p)
        miss = parcels.missing_inputs(p)
        out.append(f'<div class="card"><b>{_e(p["id"])}</b> · 용도 {_e(v.get("use") or "미기재")} · 위치 {_e(v["location"])} · 인증 주장 {_e(v.get("cert_claimed") or "없음")}'
                   f'<div style="color:var(--muted)">입력 대기 {len(miss)}: {_e(", ".join(miss))}</div>'
                   + parcel_form(p) + "</div>")
    out.append('<h2 id="sync" style="font-size:14px">설정 · 동기화</h2>')
    lan = "켜짐(같은 Wi-Fi, 토큰 필요)" if config.BIND == config.LAN_BIND and config.LAN_TOKEN else "꺼짐(이 PC 에서만 — D-6)"
    out.append(f'<div class="card"><b>휴대폰 동기화(D-16)</b> {_e(lan)}<div style="color:var(--muted)">켜려면 <code>.env</code> 에 <code>AGRODSS_BIND=0.0.0.0</code> 과 <code>AGRODSS_LAN_TOKEN=(16자 이상)</code> 을 넣고 재시작, 휴대폰은 같은 Wi-Fi 에서 <code>http://&lt;PC IP&gt;:{config.PORT}/?t=&lt;토큰&gt;</code>. '
               '휴대폰 마이크·음성은 https 또는 localhost 에서만 열린다(브라우저 보안 규칙) — 휴대폰에서는 글·사진·영상 입력이 먼저다</div></div>')
    out.append(f'<div class="card"><b>음성 질문(D-15)</b> 크롬 내장 인식(구글 서버 경유) · 무신호 {config.VOICE_SILENCE_MS // 1000}초면 종료 · 최대 {config.VOICE_MAX_MS // 1000}초</div>')
    out.append(f'<div class="card"><b>반입</b> 사진(EXIF 시각) · 영상(mvhd 시각) · 한 번에 {config.MAX_UPLOAD_MB}MB 까지 · 시각 없으면 촬영일 입력</div>')
    out.append(f'<div class="card"><b>쌓인 것</b> 영상·사진 {len(media.list_records())} · 반입 대기 {len(media.list_inbox())} · 고쳐 달라는 말 {len(fb.latest_by_id("feedback.request"))} · 고칠 항목 {len(fb.latest_by_id("improvement.item"))}</div>')
    out.append("</div>")
    return "".join(out)


def chosen_reply(farmer: dict[str, Any] | None) -> str | None:
    """[발행자 실사용 2026-10-04 "고르신 종류 … 이미 있는데 왜 되묻는가?"] 종류를 고른 뒤에도 처음 답("… 본 것으로 적었습니다 · 아니면 아래에서 다르게 고르시면 됩니다")이
    그대로 보여 **되묻는 것**으로 읽혔다 — 고르는 동작이 아무것도 안 바꾸는 것처럼 보이면 사람이 고르기를 멈춘다. 기록(답 메시지)은 보낸 때의 것이라 고쳐 쓰지 않고,
    **화면**이 그 자리에 선택 확인을 낸다(원문은 title 에). 고른 초안이 없으면 None."""
    if not farmer:
        return None
    for i, d in enumerate(farmer.get("drafts") or []):
        if d.get("why") != chat.CHOSEN_WHY:
            continue
        k = chat.KIND_PLAIN.get(d["kind"], d["kind"])
        if chat.confirmed_ref(farmer, i):
            return f"고르신 종류({k})로 넣었습니다 — 처음 제안은 지웠습니다."
        return f"종류를 고르셨습니다 — {k}. 처음 제안은 지웠습니다. '{chat.CONFIRM_LABEL}' 를 누르면 영농일지에 들어갑니다."
    return None


def _draft_html(m: dict[str, Any], i: int, d: dict[str, Any]) -> str:
    k = d["kind"]
    if k == "question":
        return ""
    done = chat.confirmed_ref(m, i)
    if done:
        # [발행자 화면 2026-09-29 06:18] 제안(본 것)을 손으로 바꿔(할 일) 넣으면 위 답변은 "본 것으로 적었습니다" 인 채 남아 카드와 어긋나 보였다 —
        # 카드가 "고르신 종류" 라고 말해 두 줄이 서로를 설명하게 한다(답변은 보낸 때의 기록이라 고쳐 쓰지 않는다)
        chosen = " · 고르신 종류(처음 제안과 다릅니다)" if d.get("why") == chat.CHOSEN_WHY else ""
        return f'<div class="draft"><span class="done">{_e(chat.SAVED_LABEL)}</span> {_e(chat.KIND_PLAIN.get(k, k))}{_e(chosen)} · {_e(done)}</div>'
    need = d.get("needs") or []
    # [발행자 2026-09-21] 앞에 서는 것은 **사람 말**이고, 개발자 사유(`why`)는 버리지 않고 `title` 로 내린다 —
    # 정확함을 잃지 않으면서 읽는 사람을 막지 않는다. 옛 판은 `why` 를 그대로 카드 첫 줄에 냈다.
    why_line = "고르신 종류입니다 — 처음 제안은 지웠습니다" if d.get("why") == chat.CHOSEN_WHY else chat.plain_why(d)   # [2026-10-04] 고른 뒤엔 선택 확인
    parts = [f'<div class="draft" title="{_e(d.get("why", ""))}"><b>{_e(chat.KIND_PLAIN.get(k, k))}</b> — {_e(why_line)}']
    parts.append(f'<form method="post" action="/c/{quote(m["subject"])}/confirm"><input type="hidden" name="msg" value="{_e(m["id"])}"><input type="hidden" name="i" value="{i}">')
    if k == "event":
        opts = "".join(f'<option value="{_e(t)}"{" selected" if t == d.get("type") else ""}>{_e(t)}</option>' for t in ev.EVENT_TYPES)
        parts.append(f'<select name="type">{opts}</select>')
        if d.get("type") == ev.DAMAGE_TYPE:
            parts.append(f'<input name="risk" value="{_e(d.get("risk") or "")}" placeholder="무엇의 피해(서리 · 부패 · 해충 · 병){" (필요)" if "risk" in need else ""}" size="16">')
    if k == "decision.noncompliance":
        # 계획 작업명은 계획표에서 이은 값(작목 무관 — 그 재배 단위의 격자 줄). 사람이 고칠 수 있고, 계획일은 아래 날짜 칸이다
        parts.append(f'<input name="planned_task" value="{_e(d.get("planned_task") or "")}" placeholder="계획 작업명" size="18">')
    day = d.get("observed_at") or d.get("planned_day") or d.get("target_date") or ""
    if k in ("parcel.field", "subject.field"):     # [§9] 밭 정보 값 · [2026-10-04] 농사 값(인증) — 날짜가 아니라 값이 보인다(고르는 말 그대로)
        word = parcels.FIELD_WORDS.get(d.get("field")) or subjects.SUBJECT_FIELD_WORDS.get(d.get("field"), d.get("field"))
        parts.append(f'<span style="color:var(--muted)" title="{_e(d.get("field"))}">{_e(word)} → <b>{_e(d.get("value"))}</b></span> ')
    if k not in ("feedback.request", "parcel.field", "subject.field"):
        parts.append(f'<input name="day" value="{_e(day)}" placeholder="YYYY-MM-DD{" (필요)" if need else ""}" size="12">')
    parts.append(f'<button class="btn pri" type="submit">{_e(chat.CONFIRM_LABEL)}</button></form>')
    parts.append('<form method="post" action="/c/' + quote(m["subject"]) + '/choose" style="margin-top:4px"><input type="hidden" name="msg" value="' + _e(m["id"]) + f'"><span style="color:var(--muted)">{_e(chat.OTHER_KIND_LABEL)}</span>'
                 + "".join(f'<button class="btn" name="kind" value="{kk}">{lab}</button>' for kk, lab in CHOOSABLE if kk != k) + '</form></div>')
    return "".join(parts)


# [발행자 2026-09-21] "분류 안 됨 — 종류를 고른다 … 이는 사용자에게 묻는 것은 옳지 않다. 질문의 내용을 분석하고
# 시스템에서 어떻게 분류할 것인지를 확정해야 한다." 2026-09-19 에 같은 말을 듣고 **서술문은 관찰 메모로 제안**하게
# 고쳤는데, 사람에게 되묻는 **화면**은 그대로 남아 있었다(규칙은 고치고 물음은 안 치웠다). 여기서 없앤다 —
# 종류는 언제나 시스템이 정하고, 사람은 제안된 초안의 **'다른 종류'** 로 고친다(그것은 묻는 것이 아니라 고치는 것이다).


def thread_main(s: dict[str, Any], today: date, message: str = "", error: str = "") -> str:
    st = s.get("status") or ("재배 중" if s.get("anchor") else "계획")
    out = [f'<div class="thead"><div><h1>{_e(s.get("label"))}</h1><div class="meta">{_e(st)} · 재배 달력 {"있음" if s.get("grid_unit") else "없음"} · 인증 {_e(s.get("cert") or "미기재")}</div></div>'
           f'<div><a href="/diary/{quote(s["id"])}">영농일지</a><a href="/judge">판단</a></div></div><div class="msgs">']
    if error:
        out.append(f'<p class="err">{_e(error)}</p>')
    if message:
        out.append(f'<p class="ok">{_e(message)}</p>')
    msgs = chat.list_messages(s["id"])
    if not msgs:
        out.append('<div class="msg sys"><div class="av">a</div><div class="bub">여기에 그날 밭에서 있었던 일을 그냥 적으시면 됩니다 — <b>한 일</b>(오늘 물 줬다) · <b>본 것</b>(잎이 누렇다) · <b>할 일</b>(내일 웃거름) · 못 한 이유 · 고쳐 달라는 말 · 물음. 읽어서 어디에 적을지 <b>먼저 골라 보여 드립니다</b>. <b>넣기를 누르셔야</b> 영농일지에 들어갑니다 — 저절로 적히지 않습니다.</div></div>')
    by_id = {m["id"]: m for m in msgs}
    for m in msgs:
        if m.get("role") == "system":
            alt = chosen_reply(by_id.get(m.get("reply_ref") or ""))       # [2026-10-04] 종류를 고른 발화의 답은 선택 확인으로 — 원문은 title 에
            shown = alt or m["text"]
            title = f' title="{_e(m["text"])}"' if alt else ""
            out.append(f'<div class="msg sys"><div class="av">a</div><div><div class="bub" id="t-{_e(m["id"])}"{title}>{_e(shown)}</div>'
                       f'<div class="ts">{_e(render.local_time(m.get("recorded_at")))}{" · 고쳐 달라는 말 " + _e(m["request_ref"]) if m.get("request_ref") else ""}</div>'
                       f'{_answer_actions(dict(m, text=shown))}</div></div>')          # 고쳐 달라는 말 칸의 인용도 보이는 글(원장은 그대로)
        else:
            tags = []
            if m.get("input_mode") == "voice":
                tags.append("음성")
            if m.get("retry_of"):
                tags.append("다시 시도")
            if m.get("edit_of"):
                tags.append("편집")
            tag = (" · " + " · ".join(tags)) if tags else ""
            out.append(f'<div class="msg me"><div><div class="bub" id="t-{_e(m["id"])}">{_e(m["text"])}</div>'
                       f'<div class="ts" style="text-align:right">{_e(render.local_time(m.get("recorded_at")))}{_e(tag)}</div>{_question_actions(m)}</div></div>')
            drafts = m.get("drafts") or []
            for i, d in enumerate(drafts):
                out.append(_draft_html(m, i, d))
    out.append("</div>")
    out.append(f'<div class="composer"><form method="post" action="/c/{quote(s["id"])}/send" id="composer" enctype="multipart/form-data">'
               '<input type="hidden" name="input_mode" id="input_mode" value="text"><input type="hidden" name="edit_of" id="edit_of" value="">'
               '<textarea name="text" id="text" title="엔터로 보냅니다 — 줄바꿈은 Shift+Enter" placeholder="예) 오늘 물 줬다 / 잎 끝이 누렇다 / 9월 25일에 웃거름 주려고 한다 / 수확 창이 너무 넓다 / 언제 캐면 되나?"></textarea>'
               '<div class="files" id="files" hidden><span id="filenames"></span> <label>찍은 날 <input name="observed_at" id="observed_at" placeholder="적으시면 이 날짜로 (2026-09-19) — 비우셔도 됩니다" size="30"></label></div>'
               '<div class="row"><span class="hint" id="hint">한 일 · 본 것 · 할 일 · 고쳐 달라는 말 · 물음 — 날짜는 "9월 20일" · "어제" · "2026-09-20"</span>'
               '<span><input type="file" name="file" id="file" accept="image/*,video/*" multiple hidden>'
               '<button class="btn" type="button" id="attach" title="사진 · 영상 올리기 — 찍은 때는 적어 주신 날짜 → 사진 속 시각 → 파일 이름 → 올리신 때 순으로 정합니다">📎 사진·영상</button> '
               # [칸 3 재측정 2026-09-20 · D15] 툴팁만 '5초' 가 박혀 있었다 — 설정(AGRODSS_VOICE_SILENCE_MS)을 바꾸면 화면이 거짓말을 한다
               f'<button class="btn" type="button" id="mic" title="음성으로 질문 — 말이 끝나거나 {config.VOICE_SILENCE_MS // 1000}초 조용하면 글로 바꿔 보낸다(D-15: 크롬 내장 인식, 구글 서버 경유)">🎤 음성</button> '
               '<button class="btn pri" type="submit">보내기</button></span></div></form></div>')
    out.append(ACTION_JS.replace("__SILENCE_MS__", str(config.VOICE_SILENCE_MS)).replace("__MAX_MS__", str(config.VOICE_MAX_MS)))
    return "".join(out)


ICONS = {
    "copy": '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
    "edit": '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
    "retry": '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 3v6h-6"/></svg>',
    "request": '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-6 0v4"/><path d="M4 9h16l-1.5 11H5.5Z"/></svg>',
    "speak": '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a9 9 0 0 1 0 14"/></svg>',
}


def _question_actions(m: dict[str, Any]) -> str:
    mid = _e(m["id"])
    return (f'<div class="acts right" data-msg="{mid}">'
            f'<button type="button" class="act" data-act="copy" data-target="t-{mid}" title="복사">{ICONS["copy"]}<span>복사</span></button>'
            f'<button type="button" class="act" data-act="edit" data-target="t-{mid}" title="편집 — 입력창에 올려 고쳐 보낸다">{ICONS["edit"]}<span>편집</span></button>'
            f'<form method="post" action="/c/{quote(m["subject"])}/send" class="inline"><input type="hidden" name="text" value="{_e(m["text"])}">'
            f'<input type="hidden" name="retry_of" value="{mid}"><button type="submit" class="act" data-act="retry" title="다시 시도 — 같은 질문을 다시 보낸다">{ICONS["retry"]}<span>다시 시도</span></button></form></div>')


def _answer_actions(m: dict[str, Any]) -> str:
    """[발행자 2026-09-22] *"사용자가 직접 입력해서 개선 사항을 전하는 입력창이 필요하다."*

    받는 쪽(`chat.request_improvement`)은 **처음부터 `text` 를 받고 있었다** — 보내는 쪽에 칸이 없었을 뿐이다.
    그래서 단추 하나가 *"이 답변이 틀리거나 부족하다"* 라는 **시스템이 지어낸 문장**만 접수시켰고, 정작
    무엇이 틀렸는지는 아무 데도 안 남았다(G1 의 거울 — 받는 자리는 있는데 **입구**가 없었다).

    칸은 `<details>` 로 연다 — 자바스크립트 없이 열리고, 휴대폰에서도 그냥 글상자다.
    """
    mid = _e(m["id"])
    raw = (m.get("text") or "").strip()
    quoted = _e(raw[:80]) + ("…" if len(raw) > 80 else "")
    return (f'<div class="acts" data-msg="{mid}">'
            f'<button type="button" class="act" data-act="copy" data-target="t-{mid}" title="복사">{ICONS["copy"]}<span>복사</span></button>'
            f'<details class="ask"><summary class="act" title="이 답이 틀리거나 부족합니다 — 무엇이 잘못됐는지 적어 보내 주세요">'
            f'{ICONS["request"]}<span>고쳐 달라기</span></summary>'
            f'<form method="post" action="/c/{quote(m["subject"])}/request">'
            f'<input type="hidden" name="reply" value="{mid}">'
            f'<div class="q">이 답에 대해 — “{quoted}”</div>'
            f'<textarea name="text" rows="2" required placeholder="무엇이 틀렸는지 · 어떻게 나오면 좋겠는지 적어 주세요"></textarea>'
            f'<button class="btn pri" type="submit">보내기</button></form></details>'
            f'<button type="button" class="act" data-act="speak" data-target="t-{mid}" title="소리 내어 읽기">{ICONS["speak"]}<span>소리 내어 읽기</span></button></div>')


ACTION_JS = """<script>
(function(){
  const $ = (s, r) => (r || document).querySelector(s);
  const text = (id) => { const el = document.getElementById(id); return el ? el.textContent : ""; };
  // [발행자 2026-09-26] "다시 시도하거나 새로운 질문을 하면 커서의 위치가 첫 질문의 위치로 가지 않고, 현재의 커서 위치에 있어야 한다."
  // 보내기·다시 시도·넣기는 전부 화면을 다시 그린다 — 브라우저는 새 문서를 맨 위(첫 질문)에서 연다. 새로 뜬 답은 맨 아래에 있으니
  // 거기로 가고, 커서는 입력칸 끝에 둔다(사람이 다음 말을 바로 이어 적는 자리).
  const ta = $("#text");
  window.scrollTo(0, document.documentElement.scrollHeight);
  if (ta) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }
  // [발행자 2026-09-26] "엔터키를 치면 보내기를 하지 않아도 문자가 전송이 되야 한다." 엔터 = 보내기, 줄바꿈은 Shift+Enter.
  // 한글은 조합 중(isComposing)에 엔터가 먼저 오므로 그때는 보내지 않는다 — 마지막 글자가 잘리거나 두 번 보내진다.
  if (ta) ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("#composer").requestSubmit(); } });
  document.addEventListener("click", async (ev) => {
    const b = ev.target.closest("button.act"); if (!b) return;
    const act = b.dataset.act, t = text(b.dataset.target || "");
    if (act === "copy") { try { await navigator.clipboard.writeText(t); flash(b, "복사됨"); } catch (e) { flash(b, "복사 실패"); } }
    else if (act === "edit") { const ta = $("#text"); ta.value = t; $("#edit_of").value = b.closest(".acts").dataset.msg; $("#input_mode").value = "text"; ta.focus(); $("#hint").textContent = "편집 중 — 고쳐서 보내면 새 발화로 이어진다(원문은 남는다)"; }
    else if (act === "speak") { if (!("speechSynthesis" in window)) { flash(b, "이 브라우저는 읽기를 지원하지 않는다"); return; }
      window.speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(t); u.lang = "ko-KR"; window.speechSynthesis.speak(u); flash(b, "읽는 중"); }
  });
  function flash(b, msg) { const s = b.querySelector("span"); if (!s) return; const o = s.textContent; s.textContent = msg; setTimeout(() => { s.textContent = o; }, 1500); }
  // 사진·영상 반입 — 파일을 고르면 이름과 촬영일 칸이 보인다. 촬영 시각은 서버가 메타에서 읽고, 없으면 여기 넣은 날짜를 쓴다.
  const attach = $("#attach"), file = $("#file");
  if (attach && file) {
    attach.addEventListener("click", () => file.click());
    file.addEventListener("change", () => { const n = Array.from(file.files).map(f => f.name + " (" + Math.round(f.size / 1048576) + "MB)").join(", ");
      $("#files").hidden = !n; $("#filenames").textContent = n; $("#hint").textContent = n ? "보내기를 누르면 반입된다 — 설명을 함께 적으면 사건·관찰로도 분류한다" : ""; });
  }
  $("#composer").addEventListener("submit", (e) => { if (!$("#text").value.trim() && !(file && file.files.length)) { e.preventDefault(); $("#hint").textContent = "글이나 파일이 있어야 보낸다"; } });
  // 음성 질문 — 브라우저 내장 인식(D-15). 입력 신호가 SILENCE_MS 동안 없으면 질문이 끝난 것으로 보고 글로 바꿔 보낸다. 오인식은 '편집'으로.
  const SILENCE_MS = __SILENCE_MS__, MAX_MS = __MAX_MS__;
  const mic = $("#mic"); if (!mic) return;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { mic.disabled = true; mic.title = "이 브라우저는 음성 인식을 지원하지 않는다(크롬 · 엣지에서 된다)"; return; }
  let rec = null, finalText = "", listening = false, silence = null, hardStop = null;
  const armSilence = () => { clearTimeout(silence); silence = setTimeout(() => { $("#hint").textContent = "입력 신호가 " + (SILENCE_MS / 1000) + "초 없어 질문을 끝낸다"; rec && rec.stop(); }, SILENCE_MS); };
  mic.addEventListener("click", () => {
    if (listening) { rec && rec.stop(); return; }
    rec = new SR(); rec.lang = "ko-KR"; rec.interimResults = true; rec.continuous = true; finalText = "";
    rec.onstart = () => { listening = true; mic.textContent = "⏹ 듣는 중…"; $("#hint").textContent = "말하세요 — " + (SILENCE_MS / 1000) + "초 조용하면 끝난 것으로 본다"; armSilence();
      hardStop = setTimeout(() => rec && rec.stop(), MAX_MS); };
    rec.onaudiostart = armSilence; rec.onsoundstart = armSilence; rec.onspeechstart = armSilence;
    rec.onresult = (e) => { let interim = ""; for (let i = e.resultIndex; i < e.results.length; i++) { const r = e.results[i]; if (r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript; }
      $("#text").value = (finalText + interim).trim(); armSilence(); };
    rec.onerror = (e) => { $("#hint").textContent = "음성 인식 오류: " + e.error + " — 마이크 권한 · 네트워크 · 보안 컨텍스트(https 또는 localhost)"; };
    rec.onend = () => { listening = false; clearTimeout(silence); clearTimeout(hardStop); mic.textContent = "🎤 음성"; const v = $("#text").value.trim();
      if (v) { $("#input_mode").value = "voice"; $("#composer").submit(); } else { $("#hint").textContent = "인식된 말이 없다 — 다시 눌러 말한다"; } };
    rec.start();
  });
})();
</script>"""


def _env_card(e: Any) -> str:
    cls = "kind-판단함" if e.kind == "판단함" else ("kind-판단불가" if e.kind.startswith("판단 불가") else "")
    # [§7.5 전수 2026-09-21] 이름표가 `해당 없음` 이었다 — 안쪽 이름이다. 정확한 종류는 `title` 에 남긴다(잃지 않는다).
    return (f'<div class="card {cls}" title="{_e(e.kind)} · {_e((e.result or {}).get("why", ""))}">'
            f'<span class="k">{_e(DECISION_LABEL.get(e.decision_id, e.decision_id))}</span>'
            f'<b>{_e(words.said(e.kind))}</b><div>{_e(chat.summarize_envelope(e))}</div></div>')


def thread_panel(s: dict[str, Any], today: date) -> str:
    out = ["<h2>오늘</h2>"]
    hint = grid_capture.hint_for(s, today)
    if hint:
        out.append(f'<div class="card"><b>찍을 장면</b> · {_e(hint.get("stage"))}<div>{_e(hint.get("scene") or hint.get("shoot"))}</div></div>')
    else:
        out.append('<div class="card">심은 날이 아직 없어 촬영 시기를 못 냅니다 — 파종을 적고 넣으시면 그날부터 셉니다</div>')
    pend = chat.pending_drafts(s["id"])
    if pend:
        out.append(f'<div class="card"><b>{_e(chat.PENDING_LABEL)} {len(pend)}</b> — 대화에서 넣기를 누르시면 영농일지에 들어갑니다</div>')
    inbox = media.list_inbox()
    if inbox:
        out.append(f'<div class="card"><b>반입 대기 파일 {len(inbox)}</b> — 촬영 시각이 없어 등록되지 않았다. <a href="/media">/media</a> 에서 날짜를 넣어 등록</div>')
    miss = parcels.missing_inputs(parcels.by_id(s.get("parcel", "")))
    if miss:
        out.append(f'<div class="card"><b>필지 입력 대기 {len(miss)}</b> <span style="color:var(--muted)">{_e(", ".join(miss[:6]))}{" …" if len(miss) > 6 else ""}</span></div>')
    # [WO-ASK-01 §8 2026-10-03] 물은 것 — 묻기 원장(ingest.asks)을 그대로 보인다(축은 사람 말 · 정확한 축 이름은 title). 못 읽으면 이유 한 줄(U-21)
    asked, asked_why = asks.summary_rows(s["id"])
    if asked_why:
        out.append(f'<div class="card err">물은 것을 못 읽었다 — {_e(asked_why)}</div>')
    elif asked:
        rows = " · ".join(f'<span title="{_e(r.get("axis"))}">{_e(words.axis(r.get("axis")))}</span> {int(r.get("count", 0))}번'
                          f'{"(답 " + str(int(r.get("replies", 0))) + ")" if r.get("replies") else ""}' for r in asked[:6])
        out.append(f'<div class="card"><b>물은 것 {len(asked)}</b> <span style="color:var(--muted)">{rows}{" …" if len(asked) > 6 else ""}</span></div>')
    out.append("<h2>판단 (종류가 먼저)</h2>")
    for e in judge_run.judgments_for(s["id"], today=today):
        out.append(_env_card(e))
    out.append(f'<h2>영농일지 <a href="/diary/{quote(s["id"])}" style="font-weight:400;text-transform:none;letter-spacing:0">전체</a></h2><div class="diary">')
    items = chat.diary(s["id"])
    if not items:
        out.append('<div class="it">아직 없다 — 대화에서 확인한 것이 여기 쌓인다</div>')
    for it in items[:8]:
        out.append(f'<div class="it"><span class="k">{_e(it["day"])}</span> <span class="k">{_e(it["label"])}</span> {_e(it["text"])}</div>')
    out.append("</div>")
    return "".join(out)


def diary_main(s: dict[str, Any], today: date) -> str:
    out = [f'<div class="thead"><div><h1>영농일지 — {_e(s.get("label"))}</h1><div class="meta">넣으신 것(한 일 · 본 것 · 할 일 · 못 한 이유 · 영상)을 날짜순으로 펼친 것입니다. 따로 적는 곳이 아닙니다.</div></div><div><a href="/c/{quote(s["id"])}">대화로</a></div></div><div class="msgs diary">']
    pend = chat.pending_drafts(s["id"])
    if pend:
        out.append(f'<p class="err">{_e(chat.PENDING_LABEL)} {len(pend)} — 대화에서 넣기를 누르셔야 일지에 들어갑니다</p>')
    items = chat.diary(s["id"])
    if not items:
        out.append("<p>아직 기록이 없다.</p>")
    cur = None
    for it in items:
        if it["day"] != cur:
            cur = it["day"]
            out.append(f'<div class="day">{_e(cur or "날짜 없음")}</div>')
        src = "채팅" if it["from_chat"] else _e(it["source"])
        out.append(f'<div class="it"><span class="k">{_e(it["label"])}</span> {_e(it["text"])} <span style="color:var(--muted);font-size:11px">· {src}</span></div>')
    out.append("</div>")
    return "".join(out)


def new_main(error: str = "", form: dict[str, str] | None = None) -> str:
    f = form or {}
    st_opts = "".join(f'<option value="{s}"{" selected" if f.get("status", "계획") == s else ""}>{s}</option>' for s in ("계획", "재배 중"))
    return (f'<div class="form"><h1 style="font-size:17px;margin:0 0 4px">새 채팅 — 작목 추가 · 계획</h1><div style="color:var(--muted);font-size:13px">채팅 목록의 단위는 작목 × 작기(재배 단위)다. 작목 이름은 사전을 거친다 — 모호하면 되묻고, 없으면 등재를 청한다.</div>'
            + (f'<p class="err">{_e(error)}</p>' if error else "")
            + '<form method="post" action="/c/new">'
            f'<label>작목 (예: 쪽파 · 배추 · 도라지)</label><input name="crop" value="{_e(f.get("crop", ""))}" required>'
            f'<label>작기 (예: 2026 가을 · 2027 봄)</label><input name="season" value="{_e(f.get("season", ""))}" required>'
            f'<label>상태</label><select name="status">{st_opts}</select>'
            f'<label>기준점 — 파종·정식일 (재배 중일 때, YYYY-MM-DD)</label><input name="anchor" value="{_e(f.get("anchor", ""))}" placeholder="비우면 계획">'
            f'<label>인증 (유기 · 무농약 · 관행 — 없으면 비움)</label><input name="cert" value="{_e(f.get("cert", ""))}">'
            f'<label>필지</label><input name="parcel" value="{_e(f.get("parcel") or subjects.default_parcel() or "")}" placeholder="필지 id(등록부)">'
            '<div style="margin-top:14px"><button class="btn pri" type="submit">목록 만들기</button></div></form></div>')


def improve_main(today: date, message: str = "", error: str = "", cycle: dict[str, Any] | None = None) -> str:
    # [U-26 잔여 2026-09-26] 이 화면도 사람 말로 — 발행자가 '고쳐 달라는 말' 을 넣고 확인하러 오는 곳이다. 대장 번호(J · D-14 · U-14 · M-10)는 뺀다.
    out = ['<div class="thead"><div><h1>개선 · 자율진화</h1><div class="meta">보이게까지는 자동입니다 — 보수(근거를 낮추는 쪽)는 자동 반영, 넓히는 쪽(임계·규칙·단계)은 제안까지. 채택은 사람이 합니다.</div></div></div><div class="msgs">']
    if error:
        out.append(f'<p class="err">{_e(error)}</p>')
    if message:
        out.append(f'<p class="ok">{_e(message)}</p>')
    if cycle is not None:
        out.append(f'<p class="ok">한 바퀴: 예측 {cycle["predictions"]} 줄 · 대조 {len(cycle["outcomes"])} · 제안 {len(cycle["proposals"])}</p>')
    out.append('<form method="post" action="/improve/cycle" style="margin:8px 0"><button class="btn pri">자율진화 한 바퀴 (측정 → 제안)</button> <span style="color:var(--muted);font-size:12px">몇 번 돌려도 같은 것을 두 번 적지 않는다</span></form>')
    subs = subjects.load()
    sel = "".join(f'<option value="{_e(s["id"])}">{_e(s["label"])}</option>' for s in subs)
    tg = "".join(f'<option value="{t}">{t}</option>' for t in ("other", "grid", "decision", "dictionary", "screen", "schema", "input"))
    out.append(f'<h2 style="font-size:14px">고쳐 달라는 말 (사용자)</h2><form method="post" action="/improve/request" class="draft" style="margin-left:0"><input name="text" size="60" placeholder="무엇이 틀렸거나 불편한가" required> <select name="target">{tg}</select> <select name="subject"><option value="">(목록 없음)</option>{sel}</select> <button class="btn pri">접수</button></form>')
    reqs = list(fb.latest_by_id("feedback.request").values())
    if reqs:
        out.append('<table class="tb"><tr><th>상태</th><th>요구</th><th>대상</th><th>목록</th><th>개선 항목</th></tr>')
        for r in reversed(reqs):
            out.append(f'<tr><td>{_e(r["status"])}</td><td>{_e(r["text"])}</td><td>{_e(r["target"])}</td><td>{_e(r.get("subject") or "")}</td><td>{_e(r.get("item_ref") or "")}</td></tr>')
        out.append("</table>")
    out.append('<h2 style="font-size:14px">개선 항목</h2>')
    items = list(fb.latest_by_id("improvement.item").values())
    if not items:
        out.append("<p>아직 없다 — 빗나감 · 못 한 이유 · 고쳐 달라는 말이 생기면 제안이 만들어진다.</p>")
    else:
        out.append('<table class="tb"><tr><th>상태</th><th>방향</th><th>제안</th><th>출처</th><th>검증</th><th>처리</th></tr>')
        for it in reversed(items):
            v = it.get("verify") or {}
            vtxt = f'{v.get("ok", 0)}/{v.get("required", fb.VERIFY_REQUIRED)}' + (f' · 실패 {v["fail"]}' if v.get("fail") else "") if v else "—"
            acts = []
            for st_ in ("채택", "반영", "거부", "보류"):
                if st_ != it["status"]:
                    acts.append(f'<button class="btn" name="status" value="{st_}">{st_}</button>')
            if it["status"] in ("반영", "검증"):
                acts.append(f'<button class="btn" name="status" value="verify_ok">라이브 확인 +1</button>')
            form = (f'<form method="post" action="/improve/status"><input type="hidden" name="item" value="{_e(it["id"])}"><input name="session_ref" size="8" placeholder="세션 id"> {"".join(acts)}</form>')
            out.append(f'<tr><td>{_e(it["status"])}{" · 자동" if it["auto_applied"] else ""}</td><td>{_e(it["direction"])}</td><td>{_e(it["proposal"])}<div style="color:var(--muted);font-size:11px">{_e(it.get("subject") or "")} · {_e(it["target"])}:{_e(it.get("target_ref") or "")}</div></td>'
                       f'<td style="font-size:11px">{_e(it["origin"]["kind"])}<br>{_e(it["origin"]["ref"])}</td><td>{vtxt}</td><td>{form}</td></tr>')
        out.append("</table>")
    outs = fb.list_records("feedback.outcome")
    if outs:
        out.append('<h2 style="font-size:14px">대조 결과</h2><table class="tb"><tr><th>날짜</th><th>목록</th><th>결정</th><th>판정</th><th>내용</th></tr>')
        for o in reversed(outs[-30:]):
            out.append(f'<tr><td>{_e(o["observed_at"])}</td><td>{_e(o["subject"])}</td><td>{_e(DECISION_LABEL.get(o["decision_id"], o["decision_id"]))}</td><td>{_e(o["verdict"])}</td><td>{_e(o["detail"])}</td></tr>')
        out.append("</table>")
    # [U-14] 사전에 없는 작목 이름 후보 — 승인(정본명에 잇기)은 사람
    from names import candidates as nc
    cands = nc.open_candidates()
    out.append('<h2 style="font-size:14px">작목 이름 후보 (사투리 · 이명)</h2>')
    if not cands:
        out.append('<p style="color:var(--muted)">열린 후보 없음 — 새 채팅에서 사전에 없는 이름을 적으면 여기 쌓인다.</p>')
    else:
        kinds = "".join(f'<option value="{k}">{k}</option>' for k in nc.KINDS)
        out.append('<table class="tb"><tr><th>이름</th><th>맥락</th><th>날짜</th><th>처리</th></tr>')
        for c in cands:
            out.append(f'<tr><td><b>{_e(c["query"])}</b></td><td>{_e(c["context"])}</td><td>{_e(c["observed_at"])}</td>'
                       f'<td><form method="post" action="/improve/name" class="inline"><input type="hidden" name="id" value="{_e(c["id"])}">'
                       f'<input name="canonical" size="10" placeholder="정본명"> <select name="kind">{kinds}</select> '
                       f'<button class="btn pri" name="act" value="approve">승인 → 사전</button> <button class="btn" name="act" value="reject">거부</button></form></td></tr>')
        out.append("</table>")
    lives = fb.list_records("verification.live")
    out.append('<h2 style="font-size:14px">라이브 3/3 재현</h2>')
    if not lives:
        out.append('<p style="color:var(--muted)">아직 없다 — <code>python scripts\\live_reproduce.py</code> 가 독립 프로세스 3회로 재현해 여기 적는다. 외부 원천(키)이 없으면 미성립으로 적힌다.</p>')
    else:
        out.append('<table class="tb"><tr><th>날짜</th><th>HEAD</th><th>판정</th><th>일치</th><th>캐시 의심</th></tr>')
        for v in reversed(lives[-5:]):
            out.append(f'<tr><td>{_e(v["observed_at"])}</td><td>{_e(v["code_head"])}</td><td>{_e(v["verdict"])}</td><td>{v["agree"]}/{v["total"]}</td><td>{_e(v["cache_suspect"] or "없음")}</td></tr>')
        out.append("</table>")
    preds = fb.list_records("feedback.prediction")
    out.append(f'<p style="color:var(--muted);font-size:12px">예측 일지 {len(preds)} 줄(바뀔 때만 한 줄) · 오늘 {today}</p></div>')
    return "".join(out)


def mall_main(view: dict[str, Any]) -> str:
    """[M-11] 소비자가 볼 상세페이지의 목업 — 영상 시계열이 본문이다. 내부 화면 안에서만 렌더된다(D-6)."""
    out = [f'<div class="thead"><div><h1>{_e(view["title"])} <span class="pill plan">목업 · 내부</span></h1>'
           f'<div class="meta">상품 = 재배 단위 {_e(view["product_id"])} · {_e(view["status"])} · 기준점({_e(view.get("anchor_kind") or "")}) 후 {_e(view.get("days_since_anchor"))}일 · {_e(view["as_of"])}</div></div>'
           f'<div><a href="/c/{quote(view["product_id"])}">대화로</a></div></div><div class="msgs">']
    out.append(f'<div class="card"><b>인증 표기</b> {_e(view["cert_label"])}</div>')
    out.append(f'<div class="card"><b>현장 영상 {view["clips_total"]}건</b> — {_e(view["editing_rule"])}</div>')
    out.append('<h2 style="font-size:14px">촬영 시계열 (격자 촬영 칸 — 연속성이 상품)</h2>')
    for t in view["timeline"]:
        cls = {"촬영됨": "kind-판단함", "촬영 창 열림": "kind-판단불가"}.get(t["state"], "")
        out.append(f'<div class="card {cls}"><span class="k">{_e(t["stage"])}</span><b>{_e(t["state"])}</b><div>{_e(t["scene"])}</div><div style="color:var(--muted);font-size:12px">창 {_e(t["window"])}</div>')
        for c in t["clips"]:
            dur = f' · {c["duration_sec"]}초' if c.get("duration_sec") else ""
            size = f' · {c["width"]}×{c["height"]}' if c.get("width") else ""
            out.append(f'<div style="margin:4px 0 0 8px">▶ {_e(c["kind"])} {_e(render.local_time(c.get("observed_at")))}{_e(dur)}{_e(size)} {_e(c.get("note") or "")}</div>')   # [C16 전수 2026-09-28] 영상 시각은 UTC 저장 — 자르면 아홉 시간 어긋난다
        out.append("</div>")
    out.append('<h2 style="font-size:14px">판정 노출 (몰-G)</h2>')
    if view["judgments"]:
        for j in view["judgments"]:
            out.append(f'<div class="card kind-판단함"><span class="k">{_e(j["decision"])}</span><b>{_e(j["kind"])}</b> {_e(j["summary"])}<div style="color:var(--muted);font-size:12px">관측일 {_e(j["as_of"])} · 등급 {_e(j["grade"])} · 기준: {_e(j["basis"])}</div></div>')
    else:
        out.append('<p style="color:var(--muted)">노출 없음 — 첫 시즌 비노출 권고(D-2 대기). 판정은 내부 화면에서만 본다.</p>')
    out.append(f'<h2 style="font-size:14px">구매</h2><div class="card">{_e(view["reservation"])}<br>{_e(view["quantity"])}</div>')
    out.append('<p style="color:var(--muted);font-size:12px">이 페이지는 내부 목업이다 — 외부 배포 없음(D-6). 몰 MVP 는 봄 작기 납품 검토(D-8) 뒤. 주소·검정값·좌표는 어떤 경로로도 실리지 않는다(몰-H 게이트).</p></div>')
    return "".join(out)


def handle_improve_status(form: dict[str, str]) -> str:
    st = form.get("status", "")
    item = form.get("item", "")
    if st == "verify_ok":
        ref = (form.get("session_ref") or "").strip()
        if not ref:
            raise fb.FeedbackError("라이브 확인에는 세션 id 가 필요하다(독립 세션 규율)")
        fb.record_verification(item, True, ref)
        return f"라이브 확인 기록 {item}"
    fb.set_item_status(item, st, by="publisher", note=form.get("note", ""))
    return f"{item} → {st}"


def handle_parcel_form(form: dict[str, str]) -> str:
    """필지 폼 처리 — 채운 것만 쓴다. 빈 칸은 **보내지 않는다**(지우지도, 메우지도 않는다).

    발행자가 고쳐 적은 값은 덮는다(overwrite=True) — 안 그러면 화면이 새 값을 받아 놓고 조용히 버린다
    (전례: `set_environment` 도 사람 답은 덮는다). 값이 안 바뀐 칸은 같은 값이 다시 써질 뿐이라 해가 없다.
    """
    pid = (form.get("id") or "").strip()
    if not pid:
        raise parcels.ParcelError("필지 id 가 없다")
    keys = tuple(parcels.FIELD_CHOICES) + tuple(k for k, _ in parcels.FIELD_LABELS)
    vals = {k: (form.get(k) or "").strip() for k in keys}
    filled = {k: v for k, v in vals.items() if v}
    if not filled:
        raise parcels.ParcelError("채운 칸이 없다 — 빈 폼은 아무것도 바꾸지 않는다")
    rec = parcels.set_fields(pid, overwrite=True, **filled)
    left = parcels.missing_inputs(rec)
    # [WO-ASK-01 §12 · §7.5 지점 2026-10-03] 답을 넣는 자리 셋 가운데 이 폼만 「판정이 읽는 값 drainage」 라고 키 이름을 냈고 **무엇이 열렸는지** 는 말하지 않았다 —
    # 발행자가 10-14 전에 여기서 「종구 생산」 을 넣는다. 문장은 words.opened 하나(채팅 초안 줄 · 확인 줄과 같은 자리) · 칸 이름은 농가 말(FIELD_WORDS).
    opened = [words.opened(k, v) for k, v in filled.items() if words.opened(k, v)]
    tail = " · " + " ".join(opened) if opened else " · 지금 판단이 읽는 값은 없습니다(밭 정보에 남습니다)"
    names = ", ".join(parcels.FIELD_WORDS.get(k, k) for k in sorted(filled))
    return f"필지 {pid} 저장 — {names}{tail} · 입력 대기 {len(left)}"


def run_cycle(today: date, head: str) -> dict[str, Any]:
    return evolve.cycle(today=today, code_head=head)
