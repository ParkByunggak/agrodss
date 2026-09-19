# -*- coding: utf-8 -*-
# [코드 평가 칸 2 · 관절 정합 묶음 · 2026-09-19] 같은 결함(정본은 있는데 관절이 안 본다)에 같은 처방.
#   A4 격자 "N/A" 문자열을 축 집합으로 읽지 않는다 · A5 recoverable 은 bool · A7 gdd basis 는 소비자가 생길 때까지 거부 ·
#   C4 필지 등록부도 R-4(호출 시점 env) · C11 원천 모듈 셋이 ingest.config 하나(.env 적재 · 타임아웃)를 쓴다.
#   A3(게이트 필드 허용 목록)은 tests/test_boundary.py 에.
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from grid import schema as gs
from ingest import config as icfg, kma, ncpms, organic_materials as om, parcels
from judge import registry as R

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "data" / "grid" / "jjokpa_autumn.json"


def _unit():
    return json.loads(GRID.read_text(encoding="utf-8"))


def test_na_axes_are_empty_set_not_letters():
    d = R.get("harvest_timing")
    errs = R.check_against_grid(d, {"name": "x", "required_axes": "N/A", "forbidden_axes": "N/A"})
    assert not any("'N'" in e or "'/'" in e or "'A'" in e for e in errs), errs
    assert any("anchor" in e for e in errs)                                   # 진짜 사유(필요 축 없음)는 남는다


def test_grid_recoverable_must_be_bool_and_basis_anchor_only():
    u = _unit()
    assert gs.validate(u).ok
    bad = _unit()
    for s in bad["stages"]:
        for r in (s.get("risks") or []) if s.get("risks") != gs.NA else []:
            r["recoverable"] = "false"
            r["alert"] = "confident_only"
    rep = gs.validate(bad)
    assert not rep.ok and any("recoverable(bool)" in e for e in rep.errors)
    bad2 = _unit()
    w = next(s for s in bad2["stages"] if isinstance(s.get("window"), dict))["window"]
    w["basis"] = "gdd"
    rep2 = gs.validate(bad2)
    assert not rep2.ok and any("basis" in e and "gdd" in e for e in rep2.errors)


def test_parcels_registry_resolves_path_at_call_time_and_is_isolated(tmp_path, monkeypatch):
    assert parcels.parcels_path().resolve() != parcels.PARCELS_PATH.resolve()   # conftest 격리가 닿는다
    assert parcels.by_id("p001")                                                  # 사본은 운영 등록부와 같다
    other = tmp_path / "p.json"
    other.write_text(json.dumps({"parcels": []}), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(other))
    assert parcels.load() == [] and parcels.by_id("p001") is None               # 호출 시점 env — 기본 인자에 묶이지 않았다
    import inspect
    for fn in (parcels.load, parcels.by_id):
        assert all(p.default is None or p.default is inspect._empty for p in inspect.signature(fn).parameters.values()
                   if p.name == "path")


# ── [코드 평가 §1-1 · 고아 4 · 중복 진실] ──────────────────────────────────────────────────────────────────────────────
def test_pii_stripping_has_one_truth_and_kind_pii_is_honoured():
    from ingest import media
    from schema import records as sch
    # kind 가 선언한 pii 가 곧 제거 목록이다 — 세 벌(전역 목록 · parcels 손코딩 · media 손코딩)이 하나로
    p = {"kind": "parcel", "id": "x", "address": "a", "pnu": "1", "lat": 1.0, "lon": 2.0, "use": "텃밭", "source": "farmer",
         "recorded_at": "t", "observed_at": "2026-09-19", "resolution": "parcel"}
    assert set(sch.strip_pii(p)) == set(p) - set(sch.KINDS["parcel"].pii)
    assert set(parcels.public_view(p)) == (set(p) - set(sch.KINDS["parcel"].pii)) | {"location"}
    v = media.public_view({"kind": "observation.video", "id": "v", "gps": [1.0, 2.0], "file": "f"})
    assert v["gps"] == "없음" or v["gps"] == "있음"                       # 좌표는 있음/없음으로만
    assert sch.strip_pii({"kind": "observation.video", "gps": [1.0, 2.0], "id": "v"}) == {"kind": "observation.video", "id": "v"}
    for mod in ("ingest/parcels.py", "ingest/media.py"):
        src = (ROOT / mod).read_text(encoding="utf-8")
        blk = src[src.index("def public_view("):]
        nxt = blk.find("\ndef ", 10)
        blk = blk[:nxt] if nxt > 0 else blk                                     # 파일 마지막 함수면 끝까지
        blk = re.sub(r'"""[\s\S]*?"""', "", blk)                                # 독스트링을 걷는다 — 거기 적힌 이름이 검사에 걸렸다(§7.1 4번)
        assert re.search(r"=\s*sch\.strip_pii\(", blk), mod                    # 호출형: 정본 호출 결과를 쓴다
    assert not hasattr(sch, "public_fields")                                    # 사문 삭제


def test_dead_entry_points_are_gone():
    from judge import run
    from frontend import render
    assert not hasattr(run, "all_harvest") and not hasattr(run, "harvest_for_subject")   # 게이트 우회 경로
    assert not hasattr(render, "render_doc")


def test_climate_normal_collector_is_deliberately_unwired():
    # "안 하기로 한 것"과 "빠뜨린 것"을 가른다 — 참조 0 만 보면 구분이 안 된다(검사 규율). 결정을 문서와 검사로 고정
    src_files = [p for p in ROOT.rglob("*.py") if "tests" not in p.parts and "__pycache__" not in p.parts and p.name != "kma.py"]
    callers = [str(p) for p in src_files if "fetch_normals" in p.read_text(encoding="utf-8")]
    assert callers == [], callers
    doc = (ROOT / "docs" / "i4_axes_minimal.md").read_text(encoding="utf-8")
    assert "fetch_normals" in doc and "호출자를 두지 않는다" in doc


def test_source_modules_share_one_config_for_env_and_timeout():
    assert kma.TIMEOUT == ncpms.TIMEOUT == icfg.TIMEOUT_SEC
    for mod in (kma, ncpms, om):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "from ingest import config" in src, mod.__name__
        assert 'os.environ.get("AGRODSS_INGEST_TIMEOUT_SEC"' not in src, mod.__name__   # 타임아웃 정본은 config 하나
