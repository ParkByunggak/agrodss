# -*- coding: utf-8 -*-
# FILE: ingest/asks.py
# ROLE: [WO-ASK-01 §8 · §9 · 검토 §2-④ · 2026-10-03] **묻기 원장** — 시스템이 농가에게 무엇을(어느 축) 언제 몇 번 물었는지, 그리고
#   **직전 질문이 겨냥한 축**(pending). 지시서 §8: "같은 것 두 번 안 묻는다 · 반복 상한 · 유효기간" — 상한과 유효기간은 값이라
#   발행자 몫이고(지식), 여기는 세는 자리다. §9: 답이 올 때 그 축의 초안을 만들려면 **어느 물음에 대한 답인지**가 남아 있어야 한다 —
#   pending 이 그것이다(답을 묶는 것은 다음 단계 · 여기서는 "물은 뒤 처음 온 말" 만 잇는다).
#
#   규율(검토 §2-④): 이 원장은 **send(저장 길)에서만** 쓴다. answer(저장 없는 길)에 붙이면 자기 점검 화면(열 때마다 네 문장을
#   answer 로 돌린다)이 원장을 더럽힌다 — 검사가 그것을 양방향으로 본다. 그리고 기록 실패는 답을 막지 않되 **보이게**
#   (dropped.note — 변경 로그 「읽다 버린 것」) 남긴다(§13-3 ↔ fail-open 금지의 화해).
#
#   파일은 채팅 원장 폴더 안(data/chat/asks.json — gitignore · AGRODSS_CHAT_DIR 격리가 그대로 닿는다 · 런타임 분류는 WRITE_ACCESSORS).
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schema import records as sch

DROP_WHERE = "묻기 기록"        # /changes 「읽다 버린 것」 의 '어디' 열


def path() -> Path:
    """[R-4] 경로는 호출 시점에 env 로 푼다 — 기본은 채팅 폴더 안(그 폴더도 env 로 풀린다). conftest · walk.sh 가 같은 이름을 격리한다."""
    from ingest import chat          # 함수 안에서 — chat 이 이 모듈을 들므로(send 가 쓴다) 모듈 수준이면 순환
    return Path(os.environ.get("AGRODSS_ASKS_PATH") or (chat.chat_dir() / "asks.json"))


def _empty() -> dict[str, Any]:
    return {"asks": {}, "pending": {}}


def _read(p: Path | None = None) -> dict[str, Any]:
    p = p or path()
    if not p.exists():
        return _empty()
    doc = json.loads(p.read_text(encoding="utf-8"))          # 깨졌으면 ValueError — 호출부(send)가 dropped 로 보이게 한다
    if not isinstance(doc, dict) or not isinstance(doc.get("asks"), dict) or not isinstance(doc.get("pending"), dict):
        raise ValueError(f"{p.name} 의 모양이 다르다 — {{\"asks\": {{…}}, \"pending\": {{…}}}} 여야 한다")
    return doc


def _write(p: Path, doc: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ts(now: datetime | None) -> str:
    return (now or datetime.now(timezone.utc).astimezone()).isoformat(timespec="seconds")


def _key(subject_id: str, axis: str) -> str:
    return f"{subject_id}|{axis}"


def record(subject_id: str, asks: list[dict[str, Any]], msg_id: str, now: datetime | None = None) -> list[dict[str, Any]]:
    """답에 실린 요구 항목(판단 불가(데이터)의 missing)을 원장에 센다 — (재배 단위, 축)마다 횟수 · 처음 · 마지막 · 어느 판정이 물었나.
    같은 답 안의 같은 축은 한 번으로 센다. pending 은 **이 답이 겨냥한 축들**로 바뀐다(직전 것은 덮인다 — 마지막 물음이 답을 받는다)."""
    axes = list(dict.fromkeys(str(a.get("axis") or "") for a in asks if a.get("axis")))
    if not axes:
        return []
    ts = _ts(now)
    with sch.ledger_lock:
        p = path()
        doc = _read(p)
        rows = []
        for a in asks:
            ax = str(a.get("axis") or "")
            if not ax:
                continue
            k = _key(subject_id, ax)
            row = doc["asks"].get(k) or {"subject": subject_id, "axis": ax, "count": 0, "first_at": ts, "replies": 0}
            if row.get("last_msg") == msg_id:
                continue                                   # 같은 답 안의 같은 축 — 한 번
            row["count"] = int(row.get("count", 0)) + 1
            row["last_at"], row["last_msg"] = ts, msg_id
            row["decision"] = str(a.get("decision") or row.get("decision") or "")
            row["who_can_fill"] = str(a.get("who_can_fill") or "")
            doc["asks"][k] = row
            rows.append(dict(row))
        doc["pending"][subject_id] = {"axes": axes, "msg": msg_id, "at": ts}
        _write(p, doc)
    return rows


def pending(subject_id: str) -> dict[str, Any] | None:
    """직전 질문이 겨냥한 축 — 없으면 None. 읽기만."""
    return _read().get("pending", {}).get(subject_id)


def mark_replied(subject_id: str, msg_id: str, now: datetime | None = None) -> dict[str, Any] | None:
    """물은 뒤 처음 온 농가 말 — pending 을 걷고 그 축들에 '답이 왔다(어느 말)' 를 적는다. **답이 맞았는지는 모른다** — 그 판정은
    §9(답이 올 때 그 축의 초안)의 몫이라 이름을 replied 로 둔다(answered 가 아니다)."""
    with sch.ledger_lock:
        p = path()
        doc = _read(p)
        pend = doc["pending"].pop(subject_id, None)
        if not pend:
            return None
        ts = _ts(now)
        for ax in pend.get("axes") or []:
            row = doc["asks"].get(_key(subject_id, ax))
            if row is not None:
                row["replies"] = int(row.get("replies", 0)) + 1
                row["replied_at"], row["replied_msg"], row["replied_to"] = ts, msg_id, pend.get("msg")
        _write(p, doc)
        return pend


def mark_stopped(subject_id: str, axis: str, why: str, now: datetime | None = None) -> None:
    """[§8 반복 상한] 질문 생성이 어느 축을 더 묻지 않기로 했으면 그 사실을 원장에 적는다 — 조용히 사라지는 질문은 없다. 행이 없으면 만들지 않는다."""
    with sch.ledger_lock:
        p = path()
        doc = _read(p)
        row = doc["asks"].get(_key(subject_id, axis))
        if row is None:
            return
        row["stopped"] = {"at": _ts(now), "why": why}
        _write(p, doc)


def for_subject(subject_id: str) -> list[dict[str, Any]]:
    """그 재배 단위에 물은 것 — 마지막 물은 때 순(최근 먼저). 파일이 없으면 []. 깨졌으면 ValueError(화면이 이유를 말한다)."""
    rows = [r for r in _read()["asks"].values() if r.get("subject") == subject_id]
    return sorted(rows, key=lambda r: r.get("last_at", ""), reverse=True)


def summary_rows(subject_id: str) -> tuple[list[dict[str, Any]], str | None]:
    """화면용(U-21 형태) — (행, 못 읽은 이유). 못 읽으면 (빈 행, 이유) · dropped 에 남긴다."""
    from ingest import dropped
    try:
        return for_subject(subject_id), None
    except (OSError, ValueError) as e:
        why = f"{type(e).__name__}: {e}"
        dropped.note(DROP_WHERE, path().name, why)
        return [], why
