# -*- coding: utf-8 -*-
# FILE: ingest/probes.py
# ROLE: [발행자 2026-10-04 "단문도 해석하지 못하고 있는지 확인"] 문장 형태 점검의 문장 목록(data/utterance_probes.json)을 **읽기만** 한다 — 4층(frontend)은 파일을 직접 열지 않는다(I-5 §5).
#   목록은 저장소 데이터(격자와 같은 자리) · 기대 종류는 발행자가 붙인다(세션이 붙이면 채점자와 응시자가 같다) · 여기서는 쓰지 않는다.
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PATH = Path(__file__).resolve().parent.parent / "data" / "utterance_probes.json"
DROP_WHERE = "문장 목록"          # /changes 「읽다 버린 것」 의 '어디' 열 — 목록 파일이 깨졌을 때
KINDS = ("question", "event", "observation.note", "plan.farmer", "plan.target_date", "feedback.request", "decision.noncompliance", "subject.end", "parcel.field", "subject.field")


def load(path: Path | None = None) -> dict[str, Any]:
    doc = json.loads((path or PATH).read_text(encoding="utf-8"))
    for g in doc.get("groups", []):
        for r in g.get("rows", []):
            if r.get("expected") is not None and r["expected"] not in KINDS:
                raise ValueError(f"문장 형태 점검 — 기대 종류가 어휘 밖이다: {r['expected']!r} ({r.get('text')})")
    return doc
