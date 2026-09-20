# -*- coding: utf-8 -*-
# [M-6] 스키마 원본 = 마이그레이션 — 한 정의 · 허용 목록 파생 · 원장 쓰기 직전 검증(배선) · 필지 등록부 · PII · 마이그레이션 스크립트.
from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from ingest import events as ev
from ingest import media, parcels, soil_exam
from judge import boundary, plan
from judge import plan_vs_actual as PVA
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
SUBJ = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


# ── 한 정의 ──────────────────────────────────────────────────────────────────────
def test_no_kind_declares_a_forbidden_field():
    for k in sch.KINDS.values():
        assert not (k.fields & sch.FORBIDDEN_FIELDS), k.name


def test_boundary_allow_lists_are_derived_from_schema_not_copied():
    # 두 벌 금지 — 경계의 허용 목록은 스키마 객체 그 자체다(사본이면 어긋난다)
    assert boundary.ALLOWED_RECORD_KINDS is sch.LAYER3_INPUT_KINDS
    assert boundary.ALLOWED_SUBJECT_FIELDS is sch.LAYER3_SUBJECT_FIELDS
    assert boundary.FORBIDDEN_FIELDS is sch.FORBIDDEN_FIELDS
    assert boundary.ALLOWED_EVENT_SOURCES == sch.KINDS["event"].sources
    assert boundary.ALLOWED_PLAN_SOURCES == {"farmer"}
    src = (ROOT / "judge" / "boundary.py").read_text(encoding="utf-8")
    assert "frozenset({" not in src.split("RETURN_KIND_QUALITY")[0], "경계 파일에 허용 목록 리터럴이 다시 생겼다"


def test_every_layer3_kind_and_feedback_kind_declared():
    for k in ("observation.video", "event", "decision.noncompliance", "plan.task", "plan.capture", "plan.target_date",
              "observation.weather_daily", "forecast.weather_daily", "observation.pest_forecast", "reference.organic_material_notice",
              "observation.soil_exam", "parcel", "subject", "chat.message",
              "feedback.request", "feedback.prediction", "feedback.outcome", "improvement.item"):
        assert k in sch.KINDS
    assert "improvement.item" in sch.LAYER3_INPUT_KINDS and "feedback.prediction" not in sch.LAYER3_INPUT_KINDS


# ── 검증 규칙 ────────────────────────────────────────────────────────────────────
def _event(**over):
    r = {"id": "evt_x", "kind": "event", "type": "예찰", "subject": SUBJ["id"], "observed_at": "2026-09-10",
         "recorded_at": "2026-09-10T00:00:00+00:00", "source": "farmer", "resolution": "cultivation_unit"}
    r.update(over)
    return r


def test_validate_rejects_unknown_missing_extra_source_time_forbidden():
    with pytest.raises(sch.SchemaError, match="없는 레코드 종류"):
        sch.validate({**_event(), "kind": "event.secret"})
    with pytest.raises(sch.SchemaError, match="필수 필드"):
        sch.validate({k: v for k, v in _event().items() if k != "resolution"})
    with pytest.raises(sch.SchemaError, match="자리가 없는 필드"):
        sch.validate(_event(inventory_qty=3))
    with pytest.raises(sch.SchemaError, match="허용 출처"):
        sch.validate(_event(source="mall:demand"))
    with pytest.raises(sch.SchemaError, match="대상 시각"):
        sch.validate(_event(observed_at=""))
    with pytest.raises(sch.SchemaError, match="금지 필드"):
        sch.validate({"kind": "observation.weather_daily", "axis": ["temp"], "observed_at": "2026-09-10", "fetched_at": "x",
                      "station": 1, "source": "external:kma_sfcdd", "resolution": "station:1", "values": {"stock": 1}})
    assert sch.validate(_event()) is not None
    assert sch.stamp(_event())["schema_version"] == sch.SCHEMA_VERSION


def test_external_source_prefix_and_no_subject():
    r = {"kind": "observation.weather_daily", "axis": ["temp", "precip"], "observed_at": "2026-09-10", "fetched_at": "x",
         "source": "external:kma_sfcdd", "resolution": "station:127", "station": 127, "values": {"tmax": 20}}
    assert sch.validate(r)
    with pytest.raises(sch.SchemaError, match="허용 출처"):
        sch.validate({**r, "source": "farmer"})


def test_registries_and_plans_conform():
    assert media.load_subjects()                                            # subjects.json 이 스키마를 통과한다
    assert parcels.load() and parcels.by_id("p001")["use"] == "시험 재배(자가)"
    unit = PVA._load_unit(SUBJ)
    for p in plan.from_unit(unit, date(2026, 8, 25), "유기"):
        sch.validate(p)
    rec = soil_exam.SoilExamRecord(status="no_data", pnu="4376038025100500000", observed_at=None, fetched_at="x")
    sch.validate(rec.to_dict())
    for e in boundary.settlement_to_events({"subject": SUBJ["id"], "harvested_at": "2026-10-20", "quantity": "30kg", "amount": 100}):
        assert "schema_version" not in e and sch.validate(e)


# ── 배선: 원장에 쓰는 직전 한 번 ─────────────────────────────────────────────────────
def test_events_ledger_writes_go_through_schema_stamp():
    with pytest.raises(sch.SchemaError, match="자리가 없는 필드"):
        ev._append(_event(stock=3))
    r = ev.add_event(SUBJ["id"], "예찰", "2026-09-10", now=NOW)
    assert r["schema_version"] == sch.SCHEMA_VERSION and ev.list_records(SUBJ["id"])[0]["schema_version"] == sch.SCHEMA_VERSION
    r2 = ev.add_noncompliance(SUBJ["id"], "예찰(트랩 · 육안)", "비가 왔다", "2026-09-08", now=NOW)
    assert r2["schema_version"] == sch.SCHEMA_VERSION


def _block_containing(src: str, needle: str) -> str:
    """그 문장을 품은 최상위 함수 본문. [2026-09-20] 전에는 `def register(` 로 잘랐는데, 그 함수가 잠금 겉껍질이 되고
    본문이 옮겨가자 **배선은 멀쩡한데 래칫만** 깨졌다 — 이름이 아니라 **검사 대상 문장**으로 구역을 찾는다(형태 독립)."""
    i = src.index(needle)
    start = src.rindex("\ndef ", 0, i)
    end = src.find("\ndef ", i)
    return src[start:end if end != -1 else len(src)]


def test_media_register_stamps_before_write():
    # 구역(함수 본문)을 잘라 본다 — stamp 호출이 index 쓰기보다 앞
    src = (ROOT / "ingest" / "media.py").read_text(encoding="utf-8")
    body = _block_containing(src, 'index_path().open("a"')
    assert body.index("sch.stamp(") < body.index('index_path().open("a"')
    src_e = (ROOT / "ingest" / "events.py").read_text(encoding="utf-8")
    body_e = src_e[src_e.index("def _append("):]
    body_e = body_e[:body_e.index("\ndef ", 10)]
    assert body_e.index("sch.stamp(") < body_e.index('index_path().open("a"')


# ── 필지 등록부 · PII ─────────────────────────────────────────────────────────────
def test_parcel_public_view_strips_pii_and_enrich_carries_only_layer3_fields():
    p = parcels.by_id("p001")
    v = parcels.public_view(p)
    assert "address" not in v and v["location"] == "있음" and v["use"] == p["use"]
    fake = {**p, "lat": 36.9, "lon": 128.0, "pnu": "123", "drainage": "양호"}
    s = parcels.enrich_subject(SUBJ, fake)
    assert s["lat"] == 36.9 and s["drainage"] == "양호"
    assert "address" not in s and "pnu" not in s
    boundary.gate_subject(s)                                                 # 붙은 결과가 경계 허용 목록 안이다
    assert "slope" in parcels.missing_inputs(p) and "use" not in parcels.missing_inputs(p)   # environment 는 발행자 답(노지)으로 채워졌다(2026-09-19)


def test_parcel_record_with_undeclared_field_rejected(tmp_path):
    bad = tmp_path / "parcels.json"
    bad.write_text(json.dumps({"parcels": [{**parcels.by_id("p001"), "stock": 5}]}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(sch.SchemaError):
        parcels.load(bad)


def test_run_enriches_subject_before_gate():
    src = (ROOT / "judge" / "run.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "all_judgments")
    loop = next(n for n in fn.body if isinstance(n, ast.For))
    names = []
    for st in loop.body:
        for c in ast.walk(st):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute):
                names.append(c.func.attr)
    assert names.index("enrich_subject") < names.index("gate") < names.index("apply_caps")


# ── 마이그레이션 스크립트 ──────────────────────────────────────────────────────────
def _run_migrate(env, *args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "migrate_ledgers.py"), *args], cwd=ROOT, env=env,
                          capture_output=True, encoding="utf-8", errors="replace")


def test_migrate_reports_and_refuses_apply_when_rejected(tmp_path, monkeypatch):
    import os
    env = dict(os.environ)
    edir = tmp_path / "events"
    edir.mkdir()
    good = _event()
    bad = _event(id="evt_b", stock=1)
    (edir / "index.jsonl").write_text(json.dumps(good, ensure_ascii=False) + "\n" + json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")
    r = _run_migrate(env)
    assert r.returncode == 1 and "거부 1" in r.stdout and "stock" in r.stdout
    r = _run_migrate(env, "--apply")
    assert r.returncode == 1 and "적용 안 함" in r.stdout
    (edir / "index.jsonl").write_text(json.dumps(good, ensure_ascii=False) + "\n", encoding="utf-8")
    r = _run_migrate(env, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    rows = [json.loads(x) for x in (edir / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["schema_version"] == sch.SCHEMA_VERSION and list(edir.glob("index.jsonl.bak-*"))


# ── 문서 동기 ─────────────────────────────────────────────────────────────────────
def test_schema_doc_in_sync():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_schema_doc.py"), "--check"], cwd=ROOT,
                       capture_output=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
