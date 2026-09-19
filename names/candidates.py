# -*- coding: utf-8 -*-
# FILE: names/candidates.py
# ROLE: [U-14 사투리·이명 채집 통로] 사전에 없는 작목 이름을 **후보**로 쌓고, 발행자가 정본명에 잇는다(승인) 또는 거부한다.
#       보이게까지 자동 · 등재는 사람(다리 B · D-14). 승인은 정본 CSV(data/crop_names.csv)에 한 줄을 붙이고 사전을 다시 읽는다.
#       후보 원장: data/names/candidates.jsonl (AGRODSS_NAMES_DIR 격리). 정본 CSV 경로도 호출 시점에 푼다(R-4).
from __future__ import annotations

import csv
import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from names import resolve as names
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
STATUS = ("후보", "승인", "거부")
KINDS = ("사투리", "이명", "오기", "통칭")
CONTEXTS = ("new_chat", "chat", "publisher")


class CandidateError(ValueError):
    pass


def names_dir() -> Path:
    return Path(os.environ.get("AGRODSS_NAMES_DIR") or (ROOT / "data" / "names"))


def index_path() -> Path:
    return names_dir() / "candidates.jsonl"


def _now(now: datetime | None) -> str:
    return (now or datetime.now(timezone.utc).astimezone()).isoformat(timespec="seconds")


def _append(rec: dict[str, Any]) -> dict[str, Any]:
    rec = sch.stamp(rec)
    index_path().parent.mkdir(parents=True, exist_ok=True)
    with index_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def latest_by_id() -> dict[str, dict[str, Any]]:
    p = index_path()
    out: dict[str, dict[str, Any]] = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["id"]] = r
    return out


def open_candidates() -> list[dict[str, Any]]:
    return [r for r in latest_by_id().values() if r["status"] == "후보"]


def add(query: str, context: str = "chat", subject: str | None = None, source: str = "farmer", note: str = "",
        now: datetime | None = None) -> dict[str, Any] | None:
    """사전에 없는 이름 1건을 후보로. 이미 사전에 있는 이름(정본·이명·모호)은 후보가 아니다. 같은 이름의 열린 후보가 있으면 안 만든다."""
    q = (query or "").strip()
    if not q:
        raise CandidateError("빈 이름")
    if context not in CONTEXTS:
        raise CandidateError(f"출처 맥락은 {' · '.join(CONTEXTS)} 중 하나")
    if names.resolve(q).status != "unknown":
        return None
    norm = names._norm(q)
    for r in open_candidates():
        if r["normalized"] == norm:
            return None
    ts = _now(now)
    rec: dict[str, Any] = {"id": f"nm_{uuid.uuid4().hex[:12]}", "kind": "names.candidate", "query": q[:60], "normalized": norm,
                           "context": context, "status": "후보", "observed_at": ts[:10], "recorded_at": ts, "source": source,
                           "resolution": "national"}
    if subject:
        rec["subject"] = subject
    if note:
        rec["note"] = note[:300]
    return _append(rec)


def approve(cand_id: str, canonical: str, alias_kind: str = "사투리", by: str = "publisher", note: str = "",
            now: datetime | None = None, regenerate_doc: bool | None = None) -> dict[str, Any]:
    """발행자 승인 — 후보를 정본명에 잇는다. 정본명은 사전에 있어야 한다(이명이면 그 정본으로). CSV 에 한 줄 붙이고 사전을 다시 읽는다."""
    if by not in sch.HUMAN_SOURCES:
        raise CandidateError("승인은 사람만(farmer · publisher) — 자동 등재 금지(D-14)")
    cur = latest_by_id().get(cand_id)
    if not cur or cur["status"] != "후보":
        raise CandidateError("열린 후보가 아니다")
    if alias_kind not in KINDS:
        raise CandidateError(f"이명 종류는 {' · '.join(KINDS)} 중 하나")
    r = names.resolve(canonical)
    if r.status not in ("canonical", "alias"):
        raise CandidateError(f"정본명이 사전에 없다: {canonical!r} — 격자 대상 작목이어야 한다(먼저 crop_axes 에 등재)")
    canon = r.canonical
    if names._norm(cur["query"]) == canon:
        raise CandidateError("후보와 정본명이 같다")
    csv_path = names.names_csv_path()
    day = (now or datetime.now(timezone.utc).astimezone()).date().isoformat()
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([canon, cur["query"], names.IDENTITY, alias_kind, f"발행자 승인 {day}", (note or f"채집 {cur['context']} · 후보 {cand_id}")[:200]])
    names.reload()
    if regenerate_doc is None:
        regenerate_doc = csv_path.resolve() == names.NAMES_CSV.resolve()
    if regenerate_doc:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_crop_axes_doc as b  # noqa: WPS433
        b.NAMES_DOC_PATH.write_text(b.build_names(b.load_names(csv_path)), encoding="utf-8")
    ts = _now(now)
    rec = dict(cur)
    rec.update({"status": "승인", "canonical": canon, "alias_kind": alias_kind, "recorded_at": ts, "source": by})
    if note:
        rec["note"] = note[:300]
    rec.pop("schema_version", None)
    return _append(rec)


def reject(cand_id: str, why: str = "", by: str = "publisher", now: datetime | None = None) -> dict[str, Any]:
    if by not in sch.HUMAN_SOURCES:
        raise CandidateError("거부도 사람만")
    cur = latest_by_id().get(cand_id)
    if not cur or cur["status"] != "후보":
        raise CandidateError("열린 후보가 아니다")
    rec = dict(cur)
    rec.update({"status": "거부", "recorded_at": _now(now), "source": by})
    if why:
        rec["note"] = why[:300]
    rec.pop("schema_version", None)
    return _append(rec)
