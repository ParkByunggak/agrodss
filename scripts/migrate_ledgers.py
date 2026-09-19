# -*- coding: utf-8 -*-
# FILE: scripts/migrate_ledgers.py
# ROLE: [M-6] 스키마 원본 = 마이그레이션 — 원장(영상·사건·되먹임·채팅)의 모든 줄을 스키마로 검증하고 schema_version 을 찍는다.
#   기본은 보고만(dry-run). --apply 는 거부 0 일 때만 쓰며, 원본을 index.jsonl.bak-<시각> 으로 남긴다.
#   거부된 줄을 지우거나 고치지 않는다 — 1층 원장은 사람이 본다(대리값 금지 · 걷어 내지 않는다).
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest import events, media  # noqa: E402
from ingest import feedback  # noqa: E402
from schema import records as sch  # noqa: E402


def ledgers() -> list[tuple[str, Path]]:
    out = [("영상", media.index_path()), ("사건", events.index_path()), ("되먹임", feedback.index_path())]
    try:
        from ingest import chat  # noqa: WPS433 — M-13 이후에만 있다
        out.append(("채팅", chat.index_path()))
    except ImportError:
        pass
    return out


def check(path: Path) -> tuple[list[dict], list[tuple[int, str, str]]]:
    ok, bad = [], []
    if not path.exists():
        return ok, bad
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            bad.append((i, "?", f"JSON 아님: {e}"))
            continue
        try:
            sch.validate(rec)
            ok.append(rec)
        except sch.SchemaError as e:
            bad.append((i, str(rec.get("kind")), str(e)))
    return ok, bad


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    apply = "--apply" in argv
    total_bad = 0
    plan: list[tuple[Path, list[dict]]] = []
    print(f"스키마 v{sch.SCHEMA_VERSION} · 종류 {len(sch.KINDS)} · {'적용' if apply else '보고만(dry-run)'}")
    for name, p in ledgers():
        ok, bad = check(p)
        stale = sum(1 for r in ok if r.get("schema_version") != sch.SCHEMA_VERSION)
        print(f"[{name}] {p}  줄 {len(ok) + len(bad)} · 통과 {len(ok)} · 거부 {len(bad)} · 버전 미기재 {stale}")
        for i, kind, why in bad:
            print(f"    거부 L{i} {kind}: {why}")
        total_bad += len(bad)
        if ok and stale:
            plan.append((p, ok))
    if total_bad:
        print(f"거부 {total_bad}건 — 적용 안 함. 거부된 줄은 사람이 본다(지우거나 고치지 않는다).")
        return 1
    if not apply:
        print("거부 0. --apply 로 schema_version 을 찍을 수 있다.")
        return 0
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for p, ok in plan:
        bak = p.with_name(p.name + f".bak-{ts}")
        bak.write_bytes(p.read_bytes())
        with p.open("w", encoding="utf-8") as f:
            for r in ok:
                f.write(json.dumps(sch.stamp(r), ensure_ascii=False) + "\n")
        print(f"적용 {p} ({len(ok)}줄) · 원본 {bak.name}")
    if not plan:
        print("찍을 것이 없다(전부 현재 버전).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
