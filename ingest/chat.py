# -*- coding: utf-8 -*-
# FILE: ingest/chat.py
# ROLE: [M-13 · I-3 §3 "질의 자체가 관찰"] 채팅 원장 + 분류 + 확인 + 영농일지.
#
#   · 채팅 한 줄은 1층 사실(chat.message)로 원장에 남는다 — 농가 발화는 최종 심급의 재료다.
#   · 분류(classify)는 2층 파생이다. 규칙 기반(사전·어휘·날짜)이고 **제안(drafts)만** 만든다.
#     확인(confirm)해야 사건·관찰·계획·개선 요구 원장에 들어간다 — 시스템이 대신 적지 않는다(대리값 금지).
#   · 날짜가 없는 사건·관찰·계획은 확인 화면이 날짜를 묻는다. 없으면 안 들어간다.
#   · 질문은 3층 봉투로 답한다(judge.run). 등록된 결정이 없으면 '판단 불가(지식)' — 지어내지 않는다.
#   · 영농일지(diary)는 새 원장이 아니다 — 원장들을 날짜로 펼친 것.
#   · 원장 격리: AGRODSS_CHAT_DIR (테스트는 tmp — conftest).
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ingest import events as ev
from ingest import feedback as fb
from ingest import media, subjects
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
RESOLUTION = "cultivation_unit"

EVENT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "파종": ("파종", "심었", "심음", "씨 뿌", "씨뿌", "종구를"), "정식": ("정식", "옮겨 심", "옮겨심"),
    "방제": ("방제", "약 쳤", "약을 쳤", "약쳤", "살포", "뿌렸"), "시비": ("시비", "비료", "거름", "웃거름", "밑거름"),
    "관수": ("관수", "물 줬", "물을 줬", "물줬", "물 주었"), "제초": ("제초", "풀 뽑", "풀뽑", "김매", "풀을 뽑"),
    "예찰": ("예찰", "트랩", "살펴봤", "둘러봤", "살펴보았"), "보식": ("보식", "다시 심", "다시심"),
    "배수": ("배수", "물 빼", "물빼", "도랑"), "수확": ("수확", "캤", "뽑았", "거뒀", "거두었"),
    "납품": ("납품", "보냈", "출하했", "출하 했"), "저장": ("저장", "창고에"), "소독": ("소독",), "정리": ("정리했", "걷었"),
}
OBS_WORDS = ("보인다", "보여", "보임", "생겼", "누렇", "누래", "시들", "벌레", "병이", "병 ", "잎이", "잎에", "싹이", "발아", "꽃이",
             "썩", "마름", "진딧물", "굼벵이", "나방", "고랑에 물", "말랐")
PLAN_WORDS = ("예정", "할 것", "하려고", "하려 한다", "계획", "할까 한다", "할 생각", "하겠다", "할게", "해야겠")
_PLAN_RE = re.compile(r"(려고|려 한다|려한다|할 예정|예정|계획|할 것|겠다|할게|해야겠|할 생각)")
REQ_WORDS = ("틀렸", "잘못", "고쳐", "바꿔", "개선", "불편", "이상하", "너무 넓", "너무 좁", "안 맞", "맞지 않", "원한다", "해 줬으면", "해줬으면")
Q_WORDS = ("언제", "얼마나", "할까", "될까", "어떻게", "뭐 해야", "무엇을", "해야 하나", "해야 할까", "괜찮나", "괜찮을까", "되나")
TOPIC: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("harvest_timing", ("수확", "캐", "뽑을", "거둘")),
    ("risk_alert", ("서리", "추위", "얼", "비가", "장마", "위험", "경보", "병", "벌레", "습")),
    ("material_citation", ("약", "자재", "비료", "공시", "뿌려도", "써도", "쳐도")),
    ("plan_vs_actual", ("해야", "할 일", "계획", "뭐", "무엇", "다음")),
)
KIND_LABEL = {"event": "사건", "observation.note": "관찰", "plan.farmer": "계획", "plan.target_date": "납품 계획일",
              "feedback.request": "개선 요구", "decision.noncompliance": "불이행 사유", "observation.video": "영상",
              "question": "질문", "subject.new": "새 목록"}


class ChatError(ValueError):
    pass


def chat_dir() -> Path:
    return Path(os.environ.get("AGRODSS_CHAT_DIR") or (ROOT / "data" / "chat"))


def index_path() -> Path:
    return chat_dir() / "index.jsonl"


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _append(rec: dict[str, Any]) -> dict[str, Any]:
    rec = sch.stamp(rec)
    index_path().parent.mkdir(parents=True, exist_ok=True)
    with index_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def list_messages(subject: str) -> list[dict[str, Any]]:
    """같은 id 의 마지막 줄이 현재 상태(확인이 붙으면 한 줄 더). 순서는 첫 등장 순."""
    p = index_path()
    if not p.exists():
        return []
    order: list[str] = []
    latest: dict[str, dict[str, Any]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("subject") != subject:
            continue
        if r["id"] not in latest:
            order.append(r["id"])
        latest[r["id"]] = r
    return [latest[i] for i in order]


def get_message(msg_id: str) -> dict[str, Any] | None:
    p = index_path()
    if not p.exists():
        return None
    cur = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["id"] == msg_id:
                cur = r
    return cur


# ── 날짜 ─────────────────────────────────────────────────────────────────────────
_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_MD = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_AGO = re.compile(r"(\d+)\s*일\s*전")
_REL = {"오늘": 0, "어제": -1, "그저께": -2, "엊그제": -2, "내일": 1, "모레": 2, "글피": 3}


def parse_day(text: str, today: date) -> str | None:
    m = _ISO.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    m = _MD.search(text)
    if m:
        try:
            return date(today.year, int(m.group(1)), int(m.group(2))).isoformat()
        except ValueError:
            return None
    m = _AGO.search(text)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    for w, d in _REL.items():
        if w in text:
            return (today + timedelta(days=d)).isoformat()
    return None


# ── 분류(2층 — 제안만) ─────────────────────────────────────────────────────────────
def _event_type(text: str) -> str | None:
    for t, words in EVENT_SYNONYMS.items():
        if any(w in text for w in words):
            return t
    return None


def classify(text: str, today: date) -> list[dict[str, Any]]:
    """발화 → 초안 목록. 하나도 못 나누면 [] (되묻는다). 초안은 확인 전까지 아무 원장에도 안 들어간다."""
    t = text.strip()
    if not t:
        return []
    day = parse_day(t, today)
    if "?" in t or any(w in t for w in Q_WORDS):
        return [{"kind": "question", "why": "물음표·의문 어휘"}]
    if any(w in t for w in REQ_WORDS):
        return [{"kind": "feedback.request", "text": t, "target": "other", "why": "교정·요구 어휘"}]
    et = _event_type(t)
    if any(w in t for w in PLAN_WORDS) or _PLAN_RE.search(t):
        if any(w in t for w in ("납품", "출하")):
            return [{"kind": "plan.target_date", "target_date": day, "note": t, "why": "납품·출하 + 계획 어휘",
                     "needs": [] if day else ["target_date"]}]
        return [{"kind": "plan.farmer", "task": et or t[:60], "planned_day": day, "note": t, "why": "계획 어휘",
                 "needs": [] if day else ["planned_day"]}]
    if et:
        return [{"kind": "event", "type": et, "observed_at": day, "note": t, "why": f"사건 어휘 → {et}",
                 "needs": [] if day else ["observed_at"]}]
    if any(w in t for w in OBS_WORDS):
        return [{"kind": "observation.note", "text": t, "observed_at": day or today.isoformat(),
                 "why": "관찰 어휘(날짜 없으면 오늘 본 것으로 제안 — 확인에서 고친다)", "needs": []}]
    return []


# ── 질문 → 3층 봉투 ─────────────────────────────────────────────────────────────────
def topic_of(text: str) -> str | None:
    for did, words in TOPIC:
        if any(w in text for w in words):
            return did
    return None


def answer(subject: dict[str, Any], text: str, today: date) -> str:
    from judge import run as judge_run   # 4층 화면과 같은 규율 — 3층 봉투만 받는다
    did = topic_of(text)
    if not did:
        return "판단 불가(지식) — 이 질문에 대응하는 결정이 등록돼 있지 않다. 지어내지 않는다. (수확 시기 · 위험 경보 · 자재 · 계획 대 실제 는 답한다)"
    envs = judge_run.judgments_for(subject["id"], today=today)
    e = next((x for x in envs if x.decision_id == did), None)
    if e is None:
        return "판단 불가(데이터) — 이 목록은 아직 판정을 낼 재료(기준점·격자)가 없다"
    return summarize_envelope(e)


def summarize_envelope(e: Any) -> str:
    r = e.result or {}
    head = f"[{e.kind}]"
    if e.kind != "판단함" and e.kind != "사실 인용":
        why = r.get("why") or ""
        miss = " · ".join(f"{m.get('axis')}: {m.get('who_can_fill')}" for m in (e.missing or []))
        return f"{head} {why}" + (f" — 채울 사람: {miss}" if miss else "")
    if e.decision_id == "harvest_timing":
        return (f"{head} 수확 창 {r.get('window_start')} ~ {r.get('window_end')} (±{r.get('error_days')}일) · 등급 {e.grade} · "
                f"{r.get('basis', '')} · {r.get('final_say', '')}")
    if e.decision_id == "risk_alert":
        al = r.get("alerts") or []
        body = " / ".join(f"{a.get('level')} {a.get('risk')}({a.get('stage')})" for a in al) or "지금 창에 경보 없음"
        return f"{head} {body} · 등급 {e.grade} · 재판정 {e.revisit_at}"
    if e.decision_id == "material_citation":
        fams = r.get("cited_families")
        n = fams if isinstance(fams, int) else len(fams or [])
        return f"{head} {r.get('stage', '')} · 공시 자재 계열 {n}건 인용 — 효능 보증 아님. 화면 /judge 에 목록"
    if e.decision_id == "plan_vs_actual":
        rows = r.get("rows") or []
        todo = [x for x in rows if x.get("status") in ("예정", "미이행", "놓침")]
        body = " / ".join(f"{x.get('status')} {x.get('task')}({x.get('work_date')})" for x in todo[:6]) or "밀린 것 없음"
        ask = r.get("ask_reason") or []
        return f"{head} {body}" + (f" · 사유를 묻는다: {', '.join(a.get('task', '') for a in ask)}" if ask else "")
    return f"{head} {json.dumps(r, ensure_ascii=False)[:300]}"


# ── 보내기 · 확인 ───────────────────────────────────────────────────────────────────
def send(subject_id: str, text: str, today: date | None = None, now: datetime | None = None,
         role: str = "farmer") -> tuple[dict[str, Any], dict[str, Any] | None]:
    """발화 1건 → (내 메시지, 시스템 답) . 분류 초안은 메시지에 붙고 답은 별도 메시지."""
    s = subjects.by_id(subject_id)
    if not s:
        raise ChatError(f"없는 목록: {subject_id}")
    text = (text or "").strip()
    if not text:
        raise ChatError("빈 발화")
    today = today or date.today()
    ts = _now(now).isoformat(timespec="seconds")
    drafts = classify(text, today)
    msg = _append({"id": f"msg_{uuid.uuid4().hex[:12]}", "kind": "chat.message", "subject": subject_id, "role": role, "text": text[:2000],
                   "observed_at": today.isoformat(), "recorded_at": ts, "source": role, "resolution": RESOLUTION,
                   "drafts": drafts, "confirmed_refs": []})
    if drafts and drafts[0]["kind"] == "question":
        reply_text = answer(s, text, today)
    elif drafts:
        d = drafts[0]
        need = d.get("needs") or []
        reply_text = f"{KIND_LABEL[d['kind']]}(으)로 읽었다 — {d['why']}. " + ("날짜를 넣고 " if need else "") + "확인하면 원장에 들어간다. 아니면 다른 종류를 고른다."
    else:
        reply_text = "분류 안 됨 — 사건 · 관찰 · 계획 · 개선 요구 중 골라 주면 그 종류로 초안을 만든다. (추측으로 적지 않는다)"
    reply = _append({"id": f"msg_{uuid.uuid4().hex[:12]}", "kind": "chat.message", "subject": subject_id, "role": "system", "text": reply_text,
                     "observed_at": today.isoformat(), "recorded_at": ts, "source": "computed:chat", "resolution": RESOLUTION,
                     "drafts": [], "confirmed_refs": [], "reply_ref": msg["id"]})
    return msg, reply


def choose_kind(msg_id: str, kind: str, today: date | None = None) -> dict[str, Any]:
    """분류 안 된 발화에 사람이 종류를 고른다 → 초안 생성(확인은 별도)."""
    m = get_message(msg_id)
    if not m:
        raise ChatError("없는 메시지")
    today = today or date.today()
    t = m["text"]
    day = parse_day(t, today)
    if kind == "event":
        d = {"kind": "event", "type": _event_type(t) or "기타", "observed_at": day, "note": t, "why": "사람이 고름", "needs": [] if day else ["observed_at"]}
    elif kind == "observation.note":
        d = {"kind": "observation.note", "text": t, "observed_at": day or today.isoformat(), "why": "사람이 고름", "needs": []}
    elif kind == "plan.farmer":
        d = {"kind": "plan.farmer", "task": t[:60], "planned_day": day, "note": t, "why": "사람이 고름", "needs": [] if day else ["planned_day"]}
    elif kind == "feedback.request":
        d = {"kind": "feedback.request", "text": t, "target": "other", "why": "사람이 고름"}
    else:
        raise ChatError(f"고를 수 없는 종류: {kind}")
    rec = dict(m)
    rec["drafts"] = [d]
    rec.pop("schema_version", None)
    return _append(rec)


def confirm(msg_id: str, draft_index: int = 0, day: str | None = None, event_type: str | None = None,
            now: datetime | None = None) -> dict[str, Any]:
    """초안 → 원장. 날짜가 없으면 여기서 받은 day 가 필요하다. 확인된 레코드 id 가 메시지에 붙는다."""
    m = get_message(msg_id)
    if not m:
        raise ChatError("없는 메시지")
    drafts = m.get("drafts") or []
    if draft_index >= len(drafts):
        raise ChatError("없는 초안")
    d = dict(drafts[draft_index])
    sid, ref = m["subject"], m["id"]
    k = d["kind"]
    try:
        if k == "event":
            et = event_type or d.get("type")
            rec = ev.add_event(sid, et, day or d.get("observed_at") or "", note=d.get("note", ""), chat_ref=ref, now=now)
            if et in ("파종", "정식"):
                s = subjects.by_id(sid)
                if s and not s.get("anchor"):
                    subjects.set_anchor(sid, rec["observed_at"], f"{et}(채팅 확인)")
        elif k == "observation.note":
            rec = ev.add_observation(sid, d["text"], day or d.get("observed_at") or "", chat_ref=ref, now=now)
        elif k == "plan.farmer":
            rec = ev.add_farmer_plan(sid, d["task"], day or d.get("planned_day") or "", note=d.get("note", ""), chat_ref=ref, now=now)
        elif k == "plan.target_date":
            rec = ev.add_target_date(sid, day or d.get("target_date") or "", note=d.get("note", ""), chat_ref=ref, now=now)
        elif k == "feedback.request":
            rec = fb.add_request(d["text"], target=d.get("target", "other"), subject=sid, source=m.get("source", "farmer"), now=now)
        else:
            raise ChatError(f"확인할 수 없는 종류: {k}")
    except (ev.EventError, fb.FeedbackError) as e:
        raise ChatError(str(e))
    upd = dict(m)
    upd["confirmed_refs"] = list(m.get("confirmed_refs", [])) + [rec["id"]]
    upd.pop("schema_version", None)
    _append(upd)
    return rec


def pending_drafts(subject_id: str) -> list[tuple[dict[str, Any], int, dict[str, Any]]]:
    out = []
    for m in list_messages(subject_id):
        if m.get("role") != "farmer" and m.get("source") != "publisher":
            continue
        if m.get("confirmed_refs"):
            continue
        for i, d in enumerate(m.get("drafts") or []):
            if d["kind"] != "question":
                out.append((m, i, d))
    return out


# ── 영농일지 — 원장을 날짜로 펼친다 ─────────────────────────────────────────────────
def diary(subject_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for r in ev.list_records(subject_id):
        k = r.get("kind")
        if k == "event":
            txt = f"{r.get('type')} — {r.get('note') or ''} {', '.join(r.get('materials') or [])}".strip(" —")
        elif k == "observation.note":
            txt = r.get("text", "")
        elif k == "plan.farmer":
            txt = f"할 일: {r.get('task')} — {r.get('note') or ''}".strip(" —")
        elif k == "plan.target_date":
            txt = f"납품 계획일 {r.get('target_date')} — {r.get('note') or ''}".strip(" —")
        elif k == "decision.noncompliance":
            txt = f"{r.get('planned_task')} 안 한 이유: {r.get('reason')}"
        else:
            txt = json.dumps(r, ensure_ascii=False)[:120]
        items.append({"day": (r.get("observed_at") or "")[:10], "kind": k, "label": KIND_LABEL.get(k, k), "text": txt,
                      "id": r.get("id"), "source": r.get("source"), "from_chat": bool(r.get("chat_ref"))})
    for v in media.list_records(subject_id):
        items.append({"day": (v.get("observed_at") or "")[:10], "kind": "observation.video", "label": "영상",
                      "text": f"{v.get('file')} · {v.get('note') or ''}".strip(" ·"), "id": v.get("id"), "source": v.get("source"), "from_chat": False})
    items.sort(key=lambda x: (x["day"], x["id"] or ""), reverse=True)
    return items
