# -*- coding: utf-8 -*-
# FILE: ingest/probes.py
# ROLE: [발행자 2026-10-04 "단문도 해석하지 못하고 있는지 확인"] 문장 형태 점검의 문장 목록(data/utterance_probes.json) — 4층(frontend)은 파일을 직접 열지 않는다(I-5 §5).
#   문장은 저장소 데이터(격자와 같은 자리) · **기대 종류는 발행자가 붙인다**(세션이 붙이면 채점자와 응시자가 같다).
#
# [손 노릇 2026-10-07] 그 기대를 붙이는 길이 **채팅뿐**이었다 — 화면이 「그대로 복사해 쓰실 줄」 묶음을 주고, 발행자가 거기에 종류를 적어 세션에 보내고,
#   세션이 이 파일을 커밋으로 고친다. 왕복이 한 번 더 붙고, 그 사이 이 항목은 **열흘 넘게** 막혀 있었다.
#   그래서 **덮개**를 둔다(결정 답 · 장기 전망과 같은 자리 · git 밖): 화면이 덮개에 쓰고 **정본은 세션 커밋으로만** 바뀐다.
#   덮개가 있으면 그 줄은 바로 맞다/다르다로 셈이 돌고(머리의 「다름 N」 — WO-LLM 문턱의 재료), 세션에 보낼 묶음은 **답한 줄만** 낸다.
#   세션은 덮개를 쓰지 않는다(쓰면 채점자와 응시자가 같아진다) — 검사가 그 분할을 지킨다.
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PATH = Path(__file__).resolve().parent.parent / "data" / "utterance_probes.json"
LOCAL_PATH = Path(__file__).resolve().parent.parent / "data" / "utterance_probes_local.json"
DROP_WHERE = "문장 목록"          # /changes 「읽다 버린 것」 의 '어디' 열 — 목록 파일이 깨졌을 때
KINDS = ("question", "event", "observation.note", "plan.farmer", "plan.target_date", "feedback.request", "decision.noncompliance", "subject.end", "parcel.field", "subject.field")
BY_PUBLISHER = "발행자"           # 덮개 레코드의 출처 — 누가 붙였는지가 레코드에 남는다(원장 출처 3칙)


def local_path() -> Path:
    """발행자가 화면에서 붙인 기대가 쌓이는 덮개(git 밖). 추적 파일에 쓰면 update.bat 이 _local_backup 으로 치우고 되돌린다 — 값이 화면에서 사라진다."""
    return Path(os.environ.get("AGRODSS_PROBES_LOCAL_PATH") or LOCAL_PATH)


def _check_kind(kind: str, text: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"문장 형태 점검 — 기대 종류가 어휘 밖이다: {kind!r} ({text})")
    return kind


def load_local(p: Path | None = None) -> dict[str, dict[str, Any]]:
    """덮개 — **문장 그대로**가 키다(목록이 바뀌어도 그 줄에만 붙는다). 깨졌으면 ValueError(조용히 비우지 않는다 · 결정 답 파일과 같은 형태)."""
    p = p or local_path()
    if not p.exists():
        return {}
    doc = json.loads(p.read_text(encoding="utf-8"))
    rows = doc.get("expected") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        raise ValueError(f"덮개 꼴이 아니다(expected 가 표여야 한다): {p}")
    for t, r in rows.items():
        _check_kind((r or {}).get("expected", ""), t)
    return rows


def load(path: Path | None = None, local: Path | None = None) -> dict[str, Any]:
    """정본 + 덮개. **덮개가 이긴다** — 발행자가 나중에 붙인 것이고, 세션이 정본으로 옮기면 같아진다(그때까지 화면은 발행자 답으로 센다)."""
    doc = json.loads((path or PATH).read_text(encoding="utf-8"))
    over = load_local(local)
    for g in doc.get("groups", []):
        for r in g.get("rows", []):
            if r.get("expected") is not None:
                _check_kind(r["expected"], r.get("text", ""))
            o = over.get(r.get("text", ""))
            if o:
                r["expected"] = o["expected"]
                if o.get("expected_route"):
                    r["expected_route"] = o["expected_route"]
                r["by"] = o.get("by") or BY_PUBLISHER
                r["from_local"] = True          # 화면이 「발행자가 붙임 — 아직 정본 아님」 을 말할 수 있게
    return doc


def texts(path: Path | None = None) -> list[str]:
    """정본의 문장 전부 — 덮개는 **기대만** 담으므로 문장은 여기서만 온다."""
    doc = json.loads((path or PATH).read_text(encoding="utf-8"))
    return [r["text"] for g in doc.get("groups", []) for r in g.get("rows", [])]


def set_expected_all(pairs: list[tuple[str, str]], p: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """여러 줄을 **한 번에** — 전부 검증한 뒤에 쓴다(한 줄이 틀리면 아무것도 안 쓴다 · 결정 답과 같은 규율).

    고르지 않은 줄(빈 값)은 건너뛴다 · 목록에 없는 문장은 거부한다(문장은 정본의 것이다) · 같은 값이면 그대로 다시 쓴다(시각만 새로).
    """
    known = set(texts())
    rows = [(t, (k or "").strip()) for t, k in pairs if (k or "").strip()]
    if not rows:
        raise ValueError("고른 줄이 없다 — 하나 이상 고르고 저장한다(빈 저장은 아무것도 안 쓴다)")
    seen: set[str] = set()
    for t, k in rows:
        if t not in known:
            raise ValueError(f"목록에 없는 문장이다(문장은 정본의 것이다): {t!r}")
        if t in seen:
            raise ValueError(f"같은 줄이 두 번 왔다: {t!r}")
        seen.add(t)
        _check_kind(k, t)
    p = p or local_path()
    doc = {"expected": load_local(p)}
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    for t, k in rows:
        doc["expected"][t] = {"expected": k, "by": BY_PUBLISHER, "at": stamp}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"written": [t for t, _ in rows]}


def to_session_text(doc: dict[str, Any]) -> str:
    """세션에 붙일 한 덩어리 — **발행자가 붙인 줄만**(덮개에서 온 것) · 한 줄이 한 기대. 세션이 이것으로 정본을 커밋한다."""
    return "\n".join(f"{r['text']} — {r['expected']}"
                     for g in doc.get("groups", []) for r in g.get("rows", []) if r.get("from_local"))
