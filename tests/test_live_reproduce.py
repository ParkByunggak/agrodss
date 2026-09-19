# -*- coding: utf-8 -*-
# [M-10 라이브 3/3 채비] 독립 프로세스 회차 · 결정 단위 대조(종류·등급·주장) · 외부 원천 0 이면 미성립 · 캐시 의심 · 원장 기록.
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from ingest import feedback as fb
from schema import records as sch
from scripts import live_reproduce as LR

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"


def _run(kind="판단함", grade="추정", h="abc", external=True, elapsed=900, head="h1"):
    return {"at": "2026-09-19T10:00:00+00:00", "head": head, "today": "2026-09-19", "elapsed_ms": elapsed, "external": external,
            "subjects": {SID: {"decisions": {"harvest_timing": {"kind": kind, "grade": grade, "payload_hash": h, "payload": {"w": 1},
                                                                 "external_sources": ["external:kma_vilagefcst"] if external else []}},
                               "gather": {}}}}


def test_compare_three_identical_external_runs_is_3_of_3():
    c = LR.compare([_run(), _run(), _run()])
    assert c["verdict"] == "3/3" and c["live"] and c["agree"] == 1 and c["diffs"] == [] and c["cache_suspect"] == []


def test_compare_one_differing_run_is_residual_not_done():
    c = LR.compare([_run(), _run(h="zzz"), _run()])
    assert c["verdict"].startswith("2/3") and "잔여" in c["verdict"] and c["diffs"][0]["run"] == 2 and c["agree"] == 0
    c = LR.compare([_run(), _run(), _run(grade="관측")])
    assert c["verdict"].startswith("2/3")


def test_compare_without_external_sources_is_not_live_even_if_identical():
    c = LR.compare([_run(external=False), _run(external=False), _run(external=False)])
    assert not c["live"] and c["verdict"].startswith("미성립(외부 원천 0)") and c["agree"] == 1


def test_cache_suspicion_flags_fast_external_runs():
    c = LR.compare([_run(elapsed=50), _run(), _run(elapsed=10)])
    assert c["cache_suspect"] == [1, 3]


def test_record_writes_schema_valid_ledger_line():
    runs = [_run(), _run(), _run()]
    rec = LR.record(runs, LR.compare(runs))
    assert rec["kind"] == "verification.live" and rec["verdict"] == "3/3" and rec["subject"] == SID and rec["schema_version"] == sch.SCHEMA_VERSION
    assert fb.list_records("verification.live")[0]["id"] == rec["id"]


def test_one_run_in_this_repo_has_twelve_decisions_and_reports_external_honestly():
    r = LR.one_run(today=date(2026, 9, 19))
    decs = r["subjects"][SID]["decisions"]
    assert len(decs) == 12 and decs["harvest_timing"]["kind"] == "판단함" and decs["harvest_timing"]["payload_hash"]
    assert r["external"] is False                                            # 키 없는 환경 — 외부 원천 0 을 정직하게


def test_subprocess_one_is_a_fresh_process_and_full_run_records_not_live(tmp_path):
    env = dict(os.environ)
    r = subprocess.run([sys.executable, "-m", "scripts.live_reproduce", "--one"], cwd=ROOT, env=env, capture_output=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert SID in out["subjects"] and out["elapsed_ms"] >= 0
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "live_reproduce.py")], cwd=ROOT, env=env, capture_output=True, encoding="utf-8", errors="replace")
    assert r.returncode == 1 and "미성립(외부 원천 0)" in r.stdout and "회차 3" in r.stdout
    lives = fb.list_records("verification.live")
    assert lives and lives[-1]["live"] is False and lives[-1]["runs"][0]["external"] is False and len(lives[-1]["runs"]) == 3
