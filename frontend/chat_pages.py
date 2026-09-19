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
from ingest import chat, events as ev, feedback as fb, parcels, subjects
from judge import evolve, run as judge_run

DECISION_LABEL = {"harvest_timing": "수확 시기", "risk_alert": "위험 경보", "material_citation": "자재 인용", "plan_vs_actual": "계획 대 실제"}
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
.brand { font-weight:700; letter-spacing:-.01em; font-size:16px; padding:4px 8px 10px; display:flex; justify-content:space-between; align-items:center; }
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
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{_e(title)}</title><style>{CSS}</style>{cols}</head><body><div class=\"app\">"
            f'<aside class="side">{side}</aside><main class="thread">{main}</main>'
            + (f'<aside class="panel">{panel}</aside>' if panel is not None else "")
            + f'</div><div style="position:fixed;bottom:4px;right:8px;color:var(--muted);font-size:10px">HEAD {_e(head)} · {config.HOST}:{config.PORT} · 외부 배포 없음(D-6)</div></body></html>')


def sidebar(current: str, docs: list[str], today: date) -> str:
    out = [f'<div class="brand">agrodss <small>내부 화면</small></div>', '<a class="newchat" href="/c/new">＋ 새 채팅 (작목 추가 · 계획)</a>',
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
    for href, label in (("/improve", "개선 · 자율진화"), ("/judge", "판단 봉투 전체"), ("/media", "영상 반입"), ("/events", "사건 · 사유(표)")):
        out.append(f'<a class="lnk" href="{href}">{label}</a>')
    out.append('<div class="grp">문서</div>')
    for name in docs:
        out.append(f'<a class="lnk" href="/doc/{_e(name)}">{_e(name.removesuffix(".md"))}</a>')
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
            out.append(f'<div class="msg sys"><div class="av">a</div><div><div class="bub">{_e(m["text"])}</div><div class="ts">{_e(m.get("recorded_at", "")[:16])}</div></div></div>')
        else:
            out.append(f'<div class="msg me"><div><div class="bub">{_e(m["text"])}</div><div class="ts" style="text-align:right">{_e(m.get("recorded_at", "")[:16])}</div></div></div>')
            drafts = m.get("drafts") or []
            if drafts:
                for i, d in enumerate(drafts):
                    out.append(_draft_html(m, i, d))
            elif not m.get("confirmed_refs"):
                out.append(_choose_html(m))
    out.append("</div>")
    out.append(f'<div class="composer"><form method="post" action="/c/{quote(s["id"])}/send"><textarea name="text" placeholder="예) 오늘 물 줬다 / 잎 끝이 누렇다 / 9월 25일에 웃거름 주려고 한다 / 수확 창이 너무 넓다 / 언제 캐면 되나?" required></textarea>'
               f'<div class="row"><span class="hint">사건 · 관찰 · 계획 · 개선 요구 · 질문 — 날짜는 "9월 20일" · "어제" · "2026-09-20"</span><button class="btn pri" type="submit">보내기</button></div></form></div>')
    return "".join(out)


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
    preds = fb.list_records("feedback.prediction")
    out.append(f'<p style="color:var(--muted);font-size:12px">예측 원장 {len(preds)} 줄(바뀔 때만 한 줄) · 오늘 {today}</p></div>')
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
