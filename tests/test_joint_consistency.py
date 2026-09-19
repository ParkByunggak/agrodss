# -*- coding: utf-8 -*-
# [코드 평가 칸 2 · 관절 정합 묶음 · 2026-09-19] 같은 결함(정본은 있는데 관절이 안 본다)에 같은 처방.
#   A4 격자 "N/A" 문자열을 축 집합으로 읽지 않는다 · A5 recoverable 은 bool · A7 gdd basis 는 소비자가 생길 때까지 거부 ·
#   C4 필지 등록부도 R-4(호출 시점 env) · C11 원천 모듈 셋이 ingest.config 하나(.env 적재 · 타임아웃)를 쓴다.
#   A3(게이트 필드 허용 목록)은 tests/test_boundary.py 에.
from __future__ import annotations

import json
import os
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


def test_source_modules_share_one_config_for_env_and_timeout():
    assert kma.TIMEOUT == ncpms.TIMEOUT == icfg.TIMEOUT_SEC
    for mod in (kma, ncpms, om):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "from ingest import config" in src, mod.__name__
        assert 'os.environ.get("AGRODSS_INGEST_TIMEOUT_SEC"' not in src, mod.__name__   # 타임아웃 정본은 config 하나
