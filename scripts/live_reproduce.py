# -*- coding: utf-8 -*-
# FILE: scripts/live_reproduce.py
# ROLE: [M-10 관문 · CLAUDE.md "라이브 3/3"] 판단 산출을 **독립 프로세스 3회**로 재현하고 대조해 원장(verification.live)에 남긴다.
#
#   규율(CLAUDE.md · VELA N-152): 3회는 독립 세션이어야 한다 — 같은 프로세스 안의 재호출은 캐시 재판정(1회)이다.
#   그래서 회차마다 `python -m scripts.live_reproduce --one` 을 **새 프로세스**로 띄운다(모듈 캐시 · 메모리 상태가 없다).
#   응답 시간이 0에 가까우면 캐시 적중을 의심한다(외부 원천을 썼다고 하면서 CACHE_SUSPECT_MS 아래면 표지).
#   외부 원천(예보 · 예찰 · 처방 · PSIS)이 하나도 안 붙은 3/3 은 달력 재현이지 라이브가 아니다 — '미성립(외부 원천 0)'.
#
#   판정: 결정마다 (종류 · 등급 · 주장 payload) 가 3회 다 같으면 3/3. 하나라도 다르면 N/3 — 2/3 은 잔여(완료 아님).
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest import feedback as fb  # noqa: E402
from judge import evolve, run as judge_run  # noqa: E402
from schema import records as sch  # noqa: E402

RUNS = 3
CACHE_SUSPECT_MS = 200
EXTERNAL_PREFIX = "external:"


def _head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace").stdout.strip() or "?"
    except OSError:
        return "?"


def one_run(today: date | None = None) -> dict[str, Any]:
    """한 회차 — 이 프로세스에서 판정 전부를 한 번 내고 대조 가능한 형태로 줄인다."""
    t0 = time.perf_counter()
    today = today or date.today()
    out: dict[str, Any] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "head": _head(), "today": today.isoformat(), "subjects": {}}
    for s, envs, info in judge_run.all_judgments(today=today):
        decs: dict[str, Any] = {}
        for e in envs:
            sources = sorted({i.source for i in e.inputs if str(i.source).startswith(EXTERNAL_PREFIX)})
            payload = evolve.payload_of(e)
            decs[e.decision_id] = {"kind": e.kind, "grade": e.grade, "payload_hash": sch.payload_hash(payload) if payload else None,
                                   "payload": payload, "external_sources": sources}
        out["subjects"][s["id"]] = {"decisions": decs, "gather": info}
    out["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    out["external"] = any(d["external_sources"] for sub in out["subjects"].values() for d in sub["decisions"].values())
    return out


def compare(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """회차들을 결정 단위로 대조. 돌려주는 것: {verdict, live, agree, total, diffs, cache_suspect}"""
    if not runs:
        return {"verdict": "미성립(회차 0)", "live": False, "agree": 0, "total": 0, "diffs": [], "cache_suspect": []}
    base = runs[0]
    diffs: list[dict[str, Any]] = []
    total = agree = 0
    for sid, sub in base["subjects"].items():
        for did, d0 in sub["decisions"].items():
            total += 1
            same = True
            for k, r in enumerate(runs[1:], start=2):
                d = r["subjects"].get(sid, {}).get("decisions", {}).get(did)
                if d is None or (d["kind"], d["grade"], d["payload_hash"]) != (d0["kind"], d0["grade"], d0["payload_hash"]):
                    same = False
                    diffs.append({"subject": sid, "decision": did, "run": k, "first": (d0["kind"], d0["grade"], d0["payload_hash"]),
                                  "this": None if d is None else (d["kind"], d["grade"], d["payload_hash"])})
            agree += 1 if same else 0
    live = all(r.get("external") for r in runs)
    cache_suspect = [i + 1 for i, r in enumerate(runs) if r.get("external") and r.get("elapsed_ms", 0) < CACHE_SUSPECT_MS]
    n = len(runs)
    if not live:
        verdict = f"미성립(외부 원천 0) — 달력 재현 {agree}/{total} 결정 일치, {n}회"
    elif agree == total and not diffs:
        verdict = f"{n}/{n}"
    else:
        verdict = f"{n - len({d['run'] for d in diffs})}/{n} — 잔여(완료 아님)"
    return {"verdict": verdict, "live": live, "agree": agree, "total": total, "diffs": diffs, "cache_suspect": cache_suspect, "runs": n}


def record(runs: list[dict[str, Any]], cmp: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    ts = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    subjects = sorted({sid for r in runs for sid in r["subjects"]})
    rec = {"id": f"liv_{ts[:19].replace(':', '').replace('-', '')}", "kind": "verification.live", "subject": subjects[0] if len(subjects) == 1 else "*",
           "subjects": subjects, "code_head": runs[0]["head"] if runs else "?", "runs": [{"at": r["at"], "elapsed_ms": r["elapsed_ms"], "external": r["external"]} for r in runs],
           "verdict": cmp["verdict"], "live": cmp["live"], "agree": cmp["agree"], "total": cmp["total"], "diffs": cmp["diffs"],
           "cache_suspect": cmp["cache_suspect"], "observed_at": ts[:10], "recorded_at": ts, "source": "computed:verify", "resolution": "cultivation_unit"}
    return fb._append(rec)


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--one" in argv:
        print(json.dumps(one_run(), ensure_ascii=False))
        return 0
    runs: list[dict[str, Any]] = []
    for i in range(RUNS):
        r = subprocess.run([sys.executable, "-m", "scripts.live_reproduce", "--one"], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not r.stdout.strip():
            print(f"회차 {i + 1} 실패: {r.stderr.strip()[-400:]}")
            return 2
        runs.append(json.loads(r.stdout.strip().splitlines()[-1]))
        print(f"회차 {i + 1}: {runs[-1]['elapsed_ms']}ms · 외부 원천 {'있음' if runs[-1]['external'] else '없음'} · HEAD {runs[-1]['head']}")
    cmp = compare(runs)
    rec = record(runs, cmp)
    print(f"판정: {cmp['verdict']} · 결정 일치 {cmp['agree']}/{cmp['total']} · 캐시 의심 회차 {cmp['cache_suspect'] or '없음'} · 원장 {rec['id']}")
    for d in cmp["diffs"]:
        print(f"  다름 {d['subject']} {d['decision']} 회차{d['run']}: {d['first']} vs {d['this']}")
    return 0 if (cmp["live"] and cmp["verdict"].endswith(f"{RUNS}/{RUNS}")) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
