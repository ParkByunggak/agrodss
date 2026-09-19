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
    "배수": ("배수", "물 빼", "물빼", "도랑", "고랑 정비", "고랑정비"), "수확": ("수확", "캤", "캐서", "캐냈", "뽑았", "뽑아서", "다듬었", "거뒀", "거두었"),
    "납품": ("납품", "보냈", "출하했", "출하 했"), "저장": ("저장", "창고에"), "소독": ("소독",), "정리": ("정리했", "정비했", "걷었"),
}
OBS_WORDS = ("보인다", "보여", "보임", "생겼", "누렇", "누래", "시들", "벌레", "병이", "병 ", "잎이", "잎에", "싹이", "발아", "꽃이",
             "썩", "마름", "진딧물", "굼벵이", "나방", "고랑에 물", "말랐",
             # [발행자 2026-09-19 첫 발화 "오늘 상황은 줄기가 매우 왕성한 모습이다" → 분류 안 됨] 생육 상태 서술 어휘
             "줄기", "뿌리", "잎 ", "잎은", "잎도", "싹", "꽃", "알이", "구가", "왕성", "모습", "상태", "자랐", "자라", "컸다", "크다",
             "작다", "웃자", "쓰러", "누웠", "빽빽", "성글", "고르", "듬성")
PLAN_WORDS = ("예정", "할 것", "하려고", "하려 한다", "계획", "할까 한다", "할 생각", "하겠다", "할게", "해야겠")
_PLAN_RE = re.compile(r"(려고|려 한다|려한다|할 예정|예정|계획|할 것|겠다|겠습니다|겠어요|겠음|할게|해야겠|할 생각|생각\s*(이다|입니다|이에요|임)?\s*$)")
REQ_WORDS = ("틀렸", "틀린", "틀려", "잘못", "고쳐", "바꿔", "개선", "불편", "너무 넓", "너무 좁", "안 맞", "맞지 않", "원한다", "해 줬으면", "해줬으면")
# '이상하' 는 뺐다 — "잎이 이상하다" 는 작물 상태 서술(관찰)이지 시스템 교정 요구가 아니다 (발행자 2026-09-19 "내부 로직으로 분류")
Q_WORDS = ("언제", "얼마나", "할까", "될까", "어떻게", "뭐 해야", "무엇을", "해야 하나", "해야 할까", "괜찮나", "괜찮을까", "되나",
           # [발행자 2026-09-19 라이브 "쪽파를 현재 관리해야 할 항목들을 알려줘요" → 분류 안 됨] 물음표 없는 요청형 — 알려/가르쳐 + 존대 어미
           "알려", "가르쳐", "궁금", "설명해", "나요", "까요", "할지", "해야 하는", "해야 할 항목", "해야 할 일", "할 일이",
           "왜 ", "어디", "어느", "인가", "는가", "은가", "을까", "줘요", "주세요", "줄래", "추천해", "제안해",
           # 전수 측정(2026-09-19 · 40문장)에서 나온 것: "지금 뭘 해야 하죠" · "오늘 상태 어때" · "뭐부터 챙겨야 해". '몇 ' 은 뺐다 — "벌레 먹은 잎이 몇 개" 가 질문으로 샜다
           "뭘 ", "뭘까", "뭐부터", "뭐가 ", "뭐를", "어때", "어떠", "하죠", "이죠", "인지 ")
TOPIC: tuple[tuple[str, tuple[str, ...]], ...] = (
    # [M-10 결정 등록] 구체 결정이 일반 결정보다 앞 — "웃거름 줘야 하나"가 자재 인용으로 새지 않게
    ("ship_or_store", ("출하", "저장할까", "납품할까", "저장")),
    ("top_dressing_1", ("웃거름", "추비")),
    ("base_fertilization", ("밑거름", "기비")),
    ("replant", ("보식", "결주", "안 난", "안 났", "듬성")),
    ("sowing_window", ("파종", "심을 때", "심어도", "언제 심")),
    ("drainage_alert", ("배수", "물 빠", "고랑", "물이 고")),
    ("harvest_timing", ("수확", "캐", "뽑을", "거둘")),
    ("pest_alert", ("벌레", "병", "나방", "파리", "진딧물")),
    ("risk_alert", ("서리", "추위", "얼", "비가", "장마", "위험", "경보", "습")),
    ("material_citation", ("약", "자재", "비료", "공시", "뿌려도", "써도", "쳐도")),
    ("plan_vs_actual", ("해야", "할 일", "계획", "뭐", "무엇", "다음", "관리", "항목", "챙겨", "신경", "지금")),   # "현재 관리해야 할 항목" → 계획 대 실제

)
# [U-16] 피해 어휘 — 갈래는 judge.evolve.RISK_FAMILIES 와 같은 이름(대조가 갈래로 잇는다)
DAMAGE_WORDS: dict[str, tuple[str, ...]] = {
    "서리": ("서리 맞", "서리에", "얼었", "얼어", "냉해", "동해", "서리 피해"),
    "부패": ("썩었", "썩어", "물러졌", "무름", "부패", "녹았"),
    "해충": ("벌레 먹", "벌레가 먹", "파리 유충", "구더기", "갉아", "유충이", "진딧물이", "나방이", "굼벵이가"),
    "병": ("병 걸", "병에 걸", "병이 났", "반점이", "곰팡이", "잎마름", "노균", "탄저"),
}
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
    """기록 시각은 발행자 PC 의 지역 시각(오프셋 포함) — 화면에 03:33 처럼 UTC 가 찍히면 사람이 시점을 오독한다."""
    return now or datetime.now(timezone.utc).astimezone()


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


def parse_day(text: str, today: date, past: bool = False) -> str | None:
    """텍스트의 날짜. past=True(사건 · 관찰 — 이미 일어난 것)면 연도 없는 월/일이 오늘보다 뒤일 때 **지난해**로 읽는다.
    [코드 평가 C6] 1월에 "12월 20일에 심었다"가 올해 12월(미래 사건)이 되던 경로. 계획은 past=False(앞날이 맞다)."""
    m = _ISO.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    m = _MD.search(text)
    if m:
        try:
            d = date(today.year, int(m.group(1)), int(m.group(2)))
            if past and d > today:
                d = date(today.year - 1, d.month, d.day)
            return d.isoformat()
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


def _damage_risk(text: str) -> str | None:
    for fam, words in DAMAGE_WORDS.items():
        if any(w in text for w in words):
            return fam
    return "피해" if "피해" in text else None


def classify(text: str, today: date) -> list[dict[str, Any]]:
    """발화 → 초안 목록. 하나도 못 나누면 [] (되묻는다). 초안은 확인 전까지 아무 원장에도 안 들어간다."""
    t = text.strip()
    if not t:
        return []
    day = parse_day(t, today)                      # 계획 — 앞날이 맞다
    day_past = parse_day(t, today, past=True)      # 사건 · 관찰 · 피해 — 이미 일어난 것(C6: 연도 없는 월/일이 오늘보다 뒤면 지난해)
    # [발행자 2026-09-19] "질문을 분석하고 그 성격을 분류해서 내부 로직으로" — 사람에게 종류를 고르라고 넘기지 않는다.
    # 순서: 교정 요구(시스템을 향한 동사) → 질문(물음표 · 의문 · 요청형) → 계획 → 피해 → 사건 → 관찰 어휘 → 서술문은 관찰 메모.
    # 종류는 규칙이 정하고 내용(날짜 · 사건 종류)은 지어내지 않는다 — 없으면 needs 로 남긴다. 확인에서 사람이 종류를 바꿀 수 있다.
    if any(w in t for w in REQ_WORDS):
        return [{"kind": "feedback.request", "text": t, "target": "other", "why": "교정·요구 어휘"}]
    if "?" in t or any(w in t for w in Q_WORDS):
        return [{"kind": "question", "why": "물음표·의문·요청형 어휘"}]
    et = _event_type(t)
    if any(w in t for w in PLAN_WORDS) or _PLAN_RE.search(t):
        if any(w in t for w in ("납품", "출하")):
            return [{"kind": "plan.target_date", "target_date": day, "note": t, "why": "납품·출하 + 계획 어휘",
                     "needs": [] if day else ["target_date"]}]
        return [{"kind": "plan.farmer", "task": et or t[:60], "planned_day": day, "note": t, "why": "계획 어휘",
                 "needs": [] if day else ["planned_day"]}]
    dmg = _damage_risk(t)
    if dmg:
        # [U-16] 피해는 사건이되 무엇의 피해인지(risk)가 있어야 경보와 대조된다. '피해'만 있고 갈래가 없으면 확인 화면이 묻는다
        risk = None if dmg == "피해" else dmg
        return [{"kind": "event", "type": ev.DAMAGE_TYPE, "observed_at": day_past or today.isoformat(), "risk": risk, "note": t,
                 "why": f"피해 어휘 → {risk or '갈래 미상'}", "needs": [] if risk else ["risk"]}]
    if et:
        return [{"kind": "event", "type": et, "observed_at": day_past, "note": t, "why": f"사건 어휘 → {et}",
                 "needs": [] if day_past else ["observed_at"]}]
    if any(w in t for w in OBS_WORDS):
        return [{"kind": "observation.note", "text": t, "observed_at": day_past or today.isoformat(),
                 "why": "관찰 어휘(날짜 없으면 오늘 본 것으로 제안 — 확인에서 고친다)", "needs": []}]
    # 아무 어휘도 안 걸린 서술문 — 농가가 밭에서 한 말은 관찰 메모(원문 그대로)로 제안한다. 내용을 지어내지 않고 종류만 정한다
    return [{"kind": "observation.note", "text": t, "observed_at": day_past or today.isoformat(),
             "why": "서술문 — 사건·계획·질문 어휘가 없어 관찰 메모로 제안(원문 그대로 · 종류는 확인에서 바꾼다)", "needs": []}]


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
    if r.get("summary") and e.decision_id not in ("harvest_timing", "risk_alert", "material_citation", "plan_vs_actual"):
        caps = " · ".join(f"상한: {c.get('name')}({c.get('basis')})" for c in (e.caps or []))
        return f"{head} {r['summary']} · 등급 {e.grade}" + (f" · {caps}" if caps else "")
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
        # [발행자 2026-09-19 "현재 관리해야 할 항목"] 지금 것이 먼저다 — 마감 안 미이행 → 다음 예정 → 놓침(사유). 옛 놓침 6건만 보이던 표현 층 결함
        rows = r.get("rows") or []
        by = {k: [x for x in rows if x.get("status") == k] for k in ("미이행", "예정", "놓침")}
        parts = []
        if by["미이행"]:
            parts.append(f"지금 할 것(마감 안) {len(by['미이행'])}: " + " · ".join(f"{x.get('task')}(~{(x.get('deadline_date') or '')[5:]})" for x in by["미이행"]))
        if by["예정"]:
            parts.append(f"다음 예정 {len(by['예정'])}: " + " · ".join(f"{x.get('task')}({(x.get('work_date') or '')[5:]})" for x in by["예정"][:3]))
        ask = r.get("ask_reason") or []
        if by["놓침"]:
            parts.append(f"놓침 {len(by['놓침'])}" + (f" — 사유를 묻는다: {', '.join(a.get('task', '') for a in ask)}" if ask else ""))
        return f"{head} " + (" / ".join(parts) or "밀린 것 없음 · 다음 예정 없음")
    return f"{head} {json.dumps(r, ensure_ascii=False)[:300]}"


# ── 보내기 · 확인 ───────────────────────────────────────────────────────────────────
INPUT_MODES = ("text", "voice", "file")


def send(subject_id: str, text: str, today: date | None = None, now: datetime | None = None,
         role: str = "farmer", retry_of: str | None = None, edit_of: str | None = None,
         input_mode: str = "text", media_refs: list[dict[str, Any]] | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """발화 1건 → (내 메시지, 시스템 답) . 분류 초안은 메시지에 붙고 답은 별도 메시지.
    retry_of / edit_of 는 '다시 시도' · '편집' 의 출처 메시지 — 원문은 지우지 않고 새 줄로 잇는다(원장은 append-only).
    input_mode=voice 는 브라우저 음성 인식에서 온 텍스트(D-15) — 오인식 교정은 '편집'으로."""
    s = subjects.by_id(subject_id)
    if not s:
        raise ChatError(f"없는 목록: {subject_id}")
    text = (text or "").strip()
    media_refs = media_refs or []
    if not text and media_refs:
        text = "[반입] " + " · ".join(f"{r.get('id')} {r.get('file', '')}" for r in media_refs)
        input_mode = "file"
    if not text:
        raise ChatError("빈 발화")
    if input_mode not in INPUT_MODES:
        raise ChatError(f"입력 방식은 {' · '.join(INPUT_MODES)} 중 하나")
    for ref in (retry_of, edit_of):
        if ref and not get_message(ref):
            raise ChatError(f"없는 메시지를 잇는다: {ref}")
    today = today or date.today()
    ts = _now(now).isoformat(timespec="seconds")
    drafts = classify(text, today)
    rec: dict[str, Any] = {"id": f"msg_{uuid.uuid4().hex[:12]}", "kind": "chat.message", "subject": subject_id, "role": role, "text": text[:2000],
                           "observed_at": today.isoformat(), "recorded_at": ts, "source": role, "resolution": RESOLUTION,
                           "drafts": drafts, "confirmed_refs": [], "input_mode": input_mode}
    if retry_of:
        rec["retry_of"] = retry_of
    if edit_of:
        rec["edit_of"] = edit_of
    if media_refs:
        rec["media_refs"] = [r.get("id") for r in media_refs]
    msg = _append(rec)
    media_line = ""
    if media_refs:
        media_line = "반입됨 " + " · ".join(f"{r.get('id')}(관측 {str(r.get('observed_at', ''))[:16]})" for r in media_refs) + " — 영상·사진 원장에 들어갔다. "
    if media_refs and not drafts:
        reply_text = media_line + "설명을 함께 적으면 사건·관찰로도 분류한다."
    elif drafts and drafts[0]["kind"] == "question":
        reply_text = answer(s, text, today)
    elif drafts:
        d = drafts[0]
        need = d.get("needs") or []
        reply_text = f"{KIND_LABEL[d['kind']]}(으)로 읽었다 — {d['why']}. " + ("날짜를 넣고 " if need else "") + "확인하면 원장에 들어간다. 아니면 다른 종류를 고른다."
    else:
        reply_text = "분류 안 됨(빈 발화) — 사건 · 관찰 · 계획 · 개선 요구 중 골라 주면 그 종류로 초안을 만든다."   # 서술문은 관찰 메모로 제안되므로 여기 오는 것은 빈 발화뿐
    if media_refs and drafts:
        reply_text = media_line + reply_text
    reply = _append({"id": f"msg_{uuid.uuid4().hex[:12]}", "kind": "chat.message", "subject": subject_id, "role": "system", "text": reply_text,
                     "observed_at": today.isoformat(), "recorded_at": ts, "source": "computed:chat", "resolution": RESOLUTION,
                     "drafts": [], "confirmed_refs": [], "reply_ref": msg["id"]})
    return msg, reply


def request_improvement(reply_id: str, text: str = "", now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """답변 아래 '개선 요구' — 그 답(시스템 메시지)을 겨냥한 feedback.request 를 바로 접수하고, 접수 사실을 대화에 남긴다.
    사람이 버튼을 눌러 낸 요구라 초안·확인 단계가 없다(다리 B: 사용자가 직접 말한 교정은 오탐일 수 없다)."""
    m = get_message(reply_id)
    if not m or m.get("role") != "system":
        raise ChatError("개선 요구는 시스템 답변에 대해 낸다")
    body = (text or "").strip() or f"이 답변이 틀리거나 부족하다: {m['text'][:200]}"
    req = fb.add_request(body, target="decision", target_ref=reply_id, subject=m.get("subject"), source="farmer", now=now)
    ts = _now(now).isoformat(timespec="seconds")
    note = _append({"id": f"msg_{uuid.uuid4().hex[:12]}", "kind": "chat.message", "subject": m["subject"], "role": "system",
                    "text": f"개선 요구 접수 {req['id']} — 개선 항목이 되면 /improve 에 보인다. 채택은 사람이 한다(D-14).",
                    "observed_at": ts[:10], "recorded_at": ts, "source": "computed:chat", "resolution": RESOLUTION,
                    "drafts": [], "confirmed_refs": [], "reply_ref": reply_id, "request_ref": req["id"]})
    return req, note


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
        d = {"kind": "observation.note", "text": t, "observed_at": day_past or today.isoformat(), "why": "사람이 고름", "needs": []}
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
            now: datetime | None = None, risk: str | None = None) -> dict[str, Any]:
    """초안 → 원장. 날짜가 없으면 여기서 받은 day 가 필요하다. 확인된 레코드 id 가 메시지에 붙는다."""
    m = get_message(msg_id)
    if not m:
        raise ChatError("없는 메시지")
    drafts = m.get("drafts") or []
    if draft_index >= len(drafts):
        raise ChatError("없는 초안")
    if m.get("confirmed_refs"):
        # [코드 평가 C7] 재확인 방지 — 브라우저 POST 재전송이 같은 사건을 두 번 원장에 썼다. 확인은 발화당 한 번
        raise ChatError(f"이미 확인된 발화 — 원장 {', '.join(m['confirmed_refs'])}")
    d = dict(drafts[draft_index])
    sid, ref = m["subject"], m["id"]
    k = d["kind"]
    try:
        if k == "event":
            et = event_type or d.get("type")
            rec = ev.add_event(sid, et, day or d.get("observed_at") or "", note=d.get("note", ""), chat_ref=ref, now=now,
                               risk=(risk or d.get("risk")) if et == ev.DAMAGE_TYPE else None)
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
            head = f"{r.get('type')}({r.get('risk')})" if r.get("risk") else str(r.get("type"))
            txt = f"{head} — {r.get('note') or ''} {', '.join(r.get('materials') or [])}".strip(" —")
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
