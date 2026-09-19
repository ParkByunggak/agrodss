# -*- coding: utf-8 -*-
# FILE: frontend/chat_pages.py
# ROLE: [M-13] Claude 형식 화면 — 왼쪽 채팅 목록(= 등록된 재배 단위) · 가운데 대화 · 오른쪽 패널(오늘 · 판단 · 영농일지).
#       4층이다: 원장은 ingest 를 통해서만, 판단은 judge.run 봉투만. 파일을 직접 열지 않는다(I-5 §5).
from __future__ import annotations

import html
from datetime import date
from typing import Any
from urllib.parse import quote

from frontend import config
from grid import capture as grid_capture
from ingest import chat, events as ev, feedback as fb, media, parcels, profile, subjects
from judge import evolve, registry, run as judge_run

BRAND = "AGRODSS"
BRAND_HTML = f'<a class="brand" href="/" id="brand" title="홈 — 첫 채팅으로">{BRAND} <small>내부 화면</small></a>'
DECISION_LABEL = {"harvest_timing": "수확 시기", "risk_alert": "위험 경보", "material_citation": "자재 인용", "plan_vs_actual": "계획 대 실제"}
DECISION_LABEL.update({k: d.name for k, d in registry.all_decisions().items() if k not in DECISION_LABEL})   # M-10 등록분은 등록부 이름
CHOOSABLE = (("event", "사건"), ("observation.note", "관찰"), ("plan.farmer", "계획"), ("feedback.request", "개선 요구"))


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
.pill.run { background:var(--ok); color:var(--ok-fg); } .pill.plan { background:var(--warn); color:var(--warn-fg); }
.side .lnk { display:block; padding:5px 10px; font-size:13px; color:var(--muted); text-decoration:none; } .side .lnk:hover { color:var(--fg); }
aside.side { display:flex; flex-direction:column; } .chat.user { margin-top:auto; border-top:1px solid var(--line); border-radius:0; padding-top:12px; }
main.thread { display:flex; flex-direction:column; min-height:100vh; }
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
.act { display:inline-flex; align-items:center; gap:4px; border:0; background:transparent; color:var(--muted); font-size:11.5px; padding:3px 6px; border-radius:6px; cursor:pointer; }
.act:hover { background:var(--chip); color:var(--fg); }
.draft { margin:6px 0 0 36px; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px 12px; font-size:13px; }
.draft b { font-weight:600; } .draft form { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-top:6px; }
.draft input, .draft select { padding:4px 8px; border:1px solid var(--line); border-radius:6px; background:var(--bg); color:var(--fg); font-size:13px; }
.btn { padding:5px 12px; border-radius:7px; border:1px solid var(--line); background:var(--panel); color:var(--fg); cursor:pointer; font-size:13px; }
.btn.pri { background:var(--accent); color:var(--accent-ink); border-color:var(--accent); }
.done { color:var(--ok-fg); background:var(--ok); padding:2px 8px; border-radius:6px; font-size:12px; }
.composer { position:fixed; bottom:0; left:260px; right:340px; padding:14px 24px 18px; background:linear-gradient(transparent, var(--bg) 30%); }
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
table.tb { border-collapse:collapse; width:100%; font-size:13px; } .tb th, .tb td { border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; } .tb th { color:var(--muted); font-weight:500; }
@media (max-width:1100px) { .app { grid-template-columns:220px 1fr; } aside.panel { display:none; } .composer { right:0; left:220px; } }
@media (max-width:720px) { .app { grid-template-columns:1fr; } aside.side { position:static; height:auto; } .composer { left:0; } .msgs { padding-inline:16px; } }
"""


def shell(title: str, side: str, main: str, panel: str | None, head: str) -> str:
    cols = "" if panel is not None else "<style>.app{grid-template-columns:260px 1fr}.composer{right:0}</style>"
    title = title if title.startswith(BRAND) else f"{BRAND} — {title}"
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{_e(title)}</title><style>{CSS}</style>{cols}</head><body><div class=\"app\">"
            f'<aside class="side">{side}</aside><main class="thread">{main}</main>'
            + (f'<aside class="panel">{panel}</aside>' if panel is not None else "")
            + f'</div><div style="position:fixed;bottom:4px;right:8px;color:var(--muted);font-size:10px">HEAD {_e(head)} · {config.HOST}:{config.PORT} · 외부 배포 없음(D-6)</div></body></html>')


def sidebar(current: str, docs: list[str], today: date) -> str:
    # [발행자 2026-09-19] 좌측 상단 탭 = AGRODSS(대문자) · 홈(/) 링크 · 모든 화면에 있다
    out = [BRAND_HTML, '<a class="newchat" href="/c/new">＋ 새 채팅 (작목 추가 · 계획)</a>',
           '<div class="grp">채팅 — 재배 단위</div>']
    subs = subjects.load()
    if not subs:
        out.append('<div class="lnk">아직 목록이 없다 — 새 채팅으로 작목을 더한다</div>')
    for s in subs:
        st = s.get("status") or ("재배 중" if s.get("anchor") else "계획")
        meta = f"{_e(s.get('season'))}" + (f" · 기준점 후 {(today - date.fromisoformat(s['anchor'])).days}일" if s.get("anchor") else " · 파종 전")
        cls = ' on' if current == f"/c/{s['id']}" else ""
        out.append(f'<a class="chat{cls}" href="/c/{quote(s["id"])}"><b>{_e(s.get("crop"))}<span class="pill {"run" if st == "재배 중" else "plan"}">{_e(st)}</span></b><span>{meta}</span></a>')
    out.append('<div class="grp">화면</div>')
    first = subs[0]["id"] if subs else ""
    for href, label in (("/improve", "개선 · 자율진화"), ("/judge", "판단 봉투 전체"), ("/media", "영상 반입"), ("/events", "사건 · 사유(표)"),
                        (f"/mall/{quote(first)}" if first else "/c/new", "몰 상세페이지 목업 (M-11)")):
        out.append(f'<a class="lnk" href="{href}">{label}</a>')
    out.append('<div class="grp">문서</div>')
    for name in docs:
        out.append(f'<a class="lnk" href="/doc/{_e(name)}">{_e(name.removesuffix(".md"))}</a>')
    out.append(user_tab_html(current))
    return "".join(out)


def user_tab_html(current: str) -> str:
    """[발행자 2026-09-19] 채팅 목록 최하단 — 사용자 정보 탭. **매 페이지**에 있다(채팅 셸 · 표 화면 · 404 까지) — 정본은 이 함수 하나."""
    u = profile.load()
    cls = ' on' if current == "/me" else ""
    return (f'<a class="chat user{cls}" href="/me" id="user-tab"><b>{_e(u.get("name") or "사용자 정보")}<span class="pill">{_e(u.get("role"))}</span></b>'
            f'<span>필지 {len(u.get("parcels") or [])} · 설정 · 동기화</span></a>')


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
    out.append('<h2 style="font-size:14px">필지</h2>')
    for p in parcels.load():
        v = parcels.public_view(p)
        miss = parcels.missing_inputs(p)
        out.append(f'<div class="card"><b>{_e(p["id"])}</b> · 용도 {_e(v.get("use") or "미기재")} · 위치 {_e(v["location"])} · 인증 주장 {_e(v.get("cert_claimed") or "없음")}'
                   f'<div style="color:var(--muted)">입력 대기 {len(miss)}: {_e(", ".join(miss))}</div></div>')
    out.append('<h2 style="font-size:14px">설정 · 동기화</h2>')
    lan = "켜짐(같은 Wi-Fi, 토큰 필요)" if config.BIND == config.LAN_BIND and config.LAN_TOKEN else "꺼짐(이 PC 에서만 — D-6)"
    out.append(f'<div class="card"><b>휴대폰 동기화(D-16)</b> {_e(lan)}<div style="color:var(--muted)">켜려면 <code>.env</code> 에 <code>AGRODSS_BIND=0.0.0.0</code> 과 <code>AGRODSS_LAN_TOKEN=(16자 이상)</code> 을 넣고 재시작, 휴대폰은 같은 Wi-Fi 에서 <code>http://&lt;PC IP&gt;:{config.PORT}/?t=&lt;토큰&gt;</code>. '
               '휴대폰 마이크·음성은 https 또는 localhost 에서만 열린다(브라우저 보안 규칙) — 휴대폰에서는 글·사진·영상 입력이 먼저다</div></div>')
    out.append(f'<div class="card"><b>음성 질문(D-15)</b> 크롬 내장 인식(구글 서버 경유) · 무신호 {config.VOICE_SILENCE_MS // 1000}초면 종료 · 최대 {config.VOICE_MAX_MS // 1000}초</div>')
    out.append(f'<div class="card"><b>반입</b> 사진(EXIF 시각) · 영상(mvhd 시각) · 한 번에 {config.MAX_UPLOAD_MB}MB 까지 · 시각 없으면 촬영일 입력</div>')
    out.append(f'<div class="card"><b>원장</b> 영상·사진 {len(media.list_records())} · 반입 대기 {len(media.list_inbox())} · 개선 요구 {len(fb.latest_by_id("feedback.request"))} · 개선 항목 {len(fb.latest_by_id("improvement.item"))}</div>')
    out.append("</div>")
    return "".join(out)


def _draft_html(m: dict[str, Any], i: int, d: dict[str, Any]) -> str:
    k = d["kind"]
    if k == "question":
        return ""
    if m.get("confirmed_refs"):
        return f'<div class="draft"><span class="done">원장에 들어감</span> {_e(chat.KIND_LABEL.get(k, k))} · {_e(", ".join(m["confirmed_refs"]))}</div>'
    need = d.get("needs") or []
    parts = [f'<div class="draft"><b>{_e(chat.KIND_LABEL.get(k, k))}</b> 초안 — {_e(d.get("why", ""))}']
    parts.append(f'<form method="post" action="/c/{quote(m["subject"])}/confirm"><input type="hidden" name="msg" value="{_e(m["id"])}"><input type="hidden" name="i" value="{i}">')
    if k == "event":
        opts = "".join(f'<option value="{_e(t)}"{" selected" if t == d.get("type") else ""}>{_e(t)}</option>' for t in ev.EVENT_TYPES)
        parts.append(f'<select name="type">{opts}</select>')
        if d.get("type") == ev.DAMAGE_TYPE:
            parts.append(f'<input name="risk" value="{_e(d.get("risk") or "")}" placeholder="무엇의 피해(서리 · 부패 · 해충 · 병){" (필요)" if "risk" in need else ""}" size="16">')
    day = d.get("observed_at") or d.get("planned_day") or d.get("target_date") or ""
    if k != "feedback.request":
        parts.append(f'<input name="day" value="{_e(day)}" placeholder="YYYY-MM-DD{" (필요)" if need else ""}" size="12">')
    parts.append('<button class="btn pri" type="submit">확인 → 원장</button></form>')
    parts.append('<form method="post" action="/c/' + quote(m["subject"]) + '/choose" style="margin-top:4px"><input type="hidden" name="msg" value="' + _e(m["id"]) + '"><span style="color:var(--muted)">다른 종류:</span>'
                 + "".join(f'<button class="btn" name="kind" value="{kk}">{lab}</button>' for kk, lab in CHOOSABLE if kk != k) + '</form></div>')
    return "".join(parts)


def _choose_html(m: dict[str, Any]) -> str:
    return ('<div class="draft"><b>분류 안 됨</b> — 종류를 고른다 <form method="post" action="/c/' + quote(m["subject"]) + '/choose"><input type="hidden" name="msg" value="' + _e(m["id"]) + '">'
            + "".join(f'<button class="btn" name="kind" value="{kk}">{lab}</button>' for kk, lab in CHOOSABLE) + '</form></div>')


def thread_main(s: dict[str, Any], today: date, message: str = "", error: str = "") -> str:
    st = s.get("status") or ("재배 중" if s.get("anchor") else "계획")
    out = [f'<div class="thead"><div><h1>{_e(s.get("label"))}</h1><div class="meta">{_e(st)} · 격자 {_e(s.get("grid_unit") or "없음")} · 인증 {_e(s.get("cert") or "미기재")}</div></div>'
           f'<div><a href="/diary/{quote(s["id"])}">영농일지</a><a href="/judge">판단</a></div></div><div class="msgs">']
    if error:
        out.append(f'<p class="err">{_e(error)}</p>')
    if message:
        out.append(f'<p class="ok">{_e(message)}</p>')
    msgs = chat.list_messages(s["id"])
    if not msgs:
        out.append('<div class="msg sys"><div class="av">a</div><div class="bub">이 목록의 첫 대화다. 무엇을 했는지(사건) · 무엇이 보이는지(관찰) · 무엇을 할지(계획) · 고칠 것(개선 요구) · 물음(질문)을 적으면 분류해 초안을 만든다. 확인해야 원장에 들어간다 — 시스템이 대신 적지 않는다.</div></div>')
    for m in msgs:
        if m.get("role") == "system":
            out.append(f'<div class="msg sys"><div class="av">a</div><div><div class="bub" id="t-{_e(m["id"])}">{_e(m["text"])}</div>'
                       f'<div class="ts">{_e(m.get("recorded_at", "")[:16])}{" · 개선 요구 " + _e(m["request_ref"]) if m.get("request_ref") else ""}</div>'
                       f'{_answer_actions(m)}</div></div>')
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
                       f'<div class="ts" style="text-align:right">{_e(m.get("recorded_at", "")[:16])}{_e(tag)}</div>{_question_actions(m)}</div></div>')
            drafts = m.get("drafts") or []
            if drafts:
                for i, d in enumerate(drafts):
                    out.append(_draft_html(m, i, d))
            elif not m.get("confirmed_refs"):
                out.append(_choose_html(m))
    out.append("</div>")
    out.append(f'<div class="composer"><form method="post" action="/c/{quote(s["id"])}/send" id="composer" enctype="multipart/form-data">'
               '<input type="hidden" name="input_mode" id="input_mode" value="text"><input type="hidden" name="edit_of" id="edit_of" value="">'
               '<textarea name="text" id="text" placeholder="예) 오늘 물 줬다 / 잎 끝이 누렇다 / 9월 25일에 웃거름 주려고 한다 / 수확 창이 너무 넓다 / 언제 캐면 되나?"></textarea>'
               '<div class="files" id="files" hidden><span id="filenames"></span> <label>촬영일 <input name="observed_at" id="observed_at" placeholder="메타에 없으면 필요 (2026-09-19)" size="24"></label></div>'
               '<div class="row"><span class="hint" id="hint">사건 · 관찰 · 계획 · 개선 요구 · 질문 — 날짜는 "9월 20일" · "어제" · "2026-09-20"</span>'
               '<span><input type="file" name="file" id="file" accept="image/*,video/*" multiple hidden>'
               '<button class="btn" type="button" id="attach" title="사진 · 영상 올리기 — 촬영 시각은 메타(EXIF · mvhd)에서 읽고 없으면 촬영일을 묻는다">📎 사진·영상</button> '
               '<button class="btn" type="button" id="mic" title="음성으로 질문 — 말이 끝나거나 5초 조용하면 글로 바꿔 보낸다(D-15: 크롬 내장 인식, 구글 서버 경유)">🎤 음성</button> '
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
    mid = _e(m["id"])
    return (f'<div class="acts" data-msg="{mid}">'
            f'<button type="button" class="act" data-act="copy" data-target="t-{mid}" title="복사">{ICONS["copy"]}<span>복사</span></button>'
            f'<form method="post" action="/c/{quote(m["subject"])}/request" class="inline"><input type="hidden" name="reply" value="{mid}">'
            f'<button type="submit" class="act" data-act="request" title="개선 요구 — 이 답이 틀리거나 부족하다고 접수한다">{ICONS["request"]}<span>개선 요구</span></button></form>'
            f'<button type="button" class="act" data-act="speak" data-target="t-{mid}" title="소리 내어 읽기">{ICONS["speak"]}<span>소리 내어 읽기</span></button></div>')


ACTION_JS = """<script>
(function(){
  const $ = (s, r) => (r || document).querySelector(s);
  const text = (id) => { const el = document.getElementById(id); return el ? el.textContent : ""; };
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
    return f'<div class="card {cls}"><span class="k">{_e(DECISION_LABEL.get(e.decision_id, e.decision_id))}</span><b>{_e(e.kind)}</b><div>{_e(chat.summarize_envelope(e))}</div></div>'


def thread_panel(s: dict[str, Any], today: date) -> str:
    out = ["<h2>오늘</h2>"]
    hint = grid_capture.hint_for(s, today)
    if hint:
        out.append(f'<div class="card"><b>찍을 장면</b> · {_e(hint.get("stage"))}<div>{_e(hint.get("scene") or hint.get("shoot"))}</div></div>')
    else:
        out.append('<div class="card">격자·기준점이 없어 촬영 시점을 못 낸다 — 파종 사건을 확인하면 기준점이 생긴다</div>')
    pend = chat.pending_drafts(s["id"])
    if pend:
        out.append(f'<div class="card"><b>미확인 초안 {len(pend)}</b> — 대화에서 확인하면 원장에 들어간다</div>')
    inbox = media.list_inbox()
    if inbox:
        out.append(f'<div class="card"><b>반입 대기 파일 {len(inbox)}</b> — 촬영 시각이 없어 등록되지 않았다. <a href="/media">/media</a> 에서 날짜를 넣어 등록</div>')
    miss = parcels.missing_inputs(parcels.by_id(s.get("parcel", "")))
    if miss:
        out.append(f'<div class="card"><b>필지 입력 대기 {len(miss)}</b> <span style="color:var(--muted)">{_e(", ".join(miss[:6]))}{" …" if len(miss) > 6 else ""}</span></div>')
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
    out = [f'<div class="thead"><div><h1>영농일지 — {_e(s.get("label"))}</h1><div class="meta">원장(사건 · 관찰 · 계획 · 사유 · 영상)을 날짜로 펼친 것. 새 원장이 아니다.</div></div><div><a href="/c/{quote(s["id"])}">대화로</a></div></div><div class="msgs diary">']
    pend = chat.pending_drafts(s["id"])
    if pend:
        out.append(f'<p class="err">미확인 초안 {len(pend)} — 대화에서 확인해야 일지에 들어간다</p>')
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
            f'<label>필지</label><input name="parcel" value="{_e(f.get("parcel", subjects.DEFAULT_PARCEL))}">'
            '<div style="margin-top:14px"><button class="btn pri" type="submit">목록 만들기</button></div></form></div>')


def improve_main(today: date, message: str = "", error: str = "", cycle: dict[str, Any] | None = None) -> str:
    out = ['<div class="thead"><div><h1>개선 · 자율진화 (J · D-14)</h1><div class="meta">보이게까지 자동 — 보수(등급 하향)는 자동 반영, 확장(임계·규칙·칸)은 제안까지. 채택은 사람.</div></div></div><div class="msgs">']
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
    out.append(f'<h2 style="font-size:14px">개선 요구 (사용자)</h2><form method="post" action="/improve/request" class="draft" style="margin-left:0"><input name="text" size="60" placeholder="무엇이 틀렸거나 불편한가" required> <select name="target">{tg}</select> <select name="subject"><option value="">(목록 없음)</option>{sel}</select> <button class="btn pri">접수</button></form>')
    reqs = list(fb.latest_by_id("feedback.request").values())
    if reqs:
        out.append('<table class="tb"><tr><th>상태</th><th>요구</th><th>대상</th><th>목록</th><th>개선 항목</th></tr>')
        for r in reversed(reqs):
            out.append(f'<tr><td>{_e(r["status"])}</td><td>{_e(r["text"])}</td><td>{_e(r["target"])}</td><td>{_e(r.get("subject") or "")}</td><td>{_e(r.get("item_ref") or "")}</td></tr>')
        out.append("</table>")
    out.append('<h2 style="font-size:14px">개선 항목</h2>')
    items = list(fb.latest_by_id("improvement.item").values())
    if not items:
        out.append("<p>아직 없다 — 빗나감 · 불이행 사유 · 개선 요구가 생기면 제안이 만들어진다.</p>")
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
    out.append('<h2 style="font-size:14px">작목 이름 후보 (U-14 — 사투리 · 이명)</h2>')
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
    out.append('<h2 style="font-size:14px">라이브 3/3 재현 (M-10 관문)</h2>')
    if not lives:
        out.append('<p style="color:var(--muted)">아직 없다 — <code>python scripts\\live_reproduce.py</code> 가 독립 프로세스 3회로 재현해 여기 적는다. 외부 원천(키)이 없으면 미성립으로 적힌다.</p>')
    else:
        out.append('<table class="tb"><tr><th>날짜</th><th>HEAD</th><th>판정</th><th>일치</th><th>캐시 의심</th></tr>')
        for v in reversed(lives[-5:]):
            out.append(f'<tr><td>{_e(v["observed_at"])}</td><td>{_e(v["code_head"])}</td><td>{_e(v["verdict"])}</td><td>{v["agree"]}/{v["total"]}</td><td>{_e(v["cache_suspect"] or "없음")}</td></tr>')
        out.append("</table>")
    preds = fb.list_records("feedback.prediction")
    out.append(f'<p style="color:var(--muted);font-size:12px">예측 원장 {len(preds)} 줄(바뀔 때만 한 줄) · 오늘 {today}</p></div>')
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
            out.append(f'<div style="margin:4px 0 0 8px">▶ {_e(c["kind"])} {_e(str(c["observed_at"])[:16])}{_e(dur)}{_e(size)} {_e(c.get("note") or "")}</div>')
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


def run_cycle(today: date, head: str) -> dict[str, Any]:
    return evolve.cycle(today=today, code_head=head)
