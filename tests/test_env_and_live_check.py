# -*- coding: utf-8 -*-
# [발행자 몫의 마찰 제거] CLI 도 .env 를 읽는다 · VELA .env 에서 키를 이름만 보고 옮긴다(있는 값은 안 건드린다 · 값은 안 찍는다) ·
#        수집 요약은 PII 없이 상태만.
from __future__ import annotations

import os
from pathlib import Path

from ingest import config as icfg, fertilizer as fz
from scripts import env_from_vela as ev


def test_ingest_config_loads_dotenv_without_overriding(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("# 주석\nAGRODSS_T_ONE=abc\nAGRODSS_T_TWO=\"q\"\nAGRODSS_T_EMPTY=\n", encoding="utf-8")
    monkeypatch.setenv("AGRODSS_T_ONE", "already")
    monkeypatch.delenv("AGRODSS_T_TWO", raising=False)
    monkeypatch.delenv("AGRODSS_T_EMPTY", raising=False)
    loaded = icfg.load_dotenv(p)
    assert loaded == ["AGRODSS_T_TWO"] and os.environ["AGRODSS_T_ONE"] == "already" and os.environ["AGRODSS_T_TWO"] == "q"
    assert "AGRODSS_T_EMPTY" not in os.environ and icfg.load_dotenv(tmp_path / "none") == []
    monkeypatch.delenv("AGRODSS_T_TWO", raising=False)


def test_merge_copies_only_missing_keys_by_name_with_prefix_fallback():
    names = ["SOIL_API_KEY", "VWORLD_API_KEY", "PSIS_API_KEY", "NCPMS_API_KEY"]
    cur = "AGRODSS_WATCH_DIRS=C:\\x\nSOIL_API_KEY=keep-me\n"
    vela = "SOIL_API_KEY=vela-soil\nEXTERNAL_API__VWORLD_API_KEY=vela-vw\nPSIS_API_KEY=vela-psis\nOTHER=1\n"
    new, copied, missing = ev.merge(cur, vela, names)
    assert copied == ["VWORLD_API_KEY", "PSIS_API_KEY"] and missing == ["NCPMS_API_KEY"]
    got = ev.parse_env(new)
    assert got["SOIL_API_KEY"] == "keep-me" and got["VWORLD_API_KEY"] == "vela-vw" and got["PSIS_API_KEY"] == "vela-psis"
    assert "OTHER" not in got and new.startswith("AGRODSS_WATCH_DIRS=") and "[D-9 키 인용]" in new
    new2, copied2, _ = ev.merge(new, vela, names)
    assert copied2 == [] and new2 == new                                       # 두 번 돌려도 같다


def test_wanted_names_come_from_env_example():
    names = ev.wanted_names((Path(ev.ROOT) / ".env.example").read_text(encoding="utf-8"))
    assert {"SOIL_API_KEY", "VWORLD_API_KEY", "FERTILIZER_API_KEY", "PSIS_API_KEY", "NCPMS_API_KEY"} <= set(names)


def test_fertilizer_summary_has_statuses_only():
    res = {"parcel": "p001", "crop": "쪽파", "pnu": "4376038025100500000", "soil": {"status": "success", "values": {"ph": 6.1}},
           "prescription": {"status": "no_data", "message": "301 NODATA", "values": {}}, "standard": None, "saved": ["a"]}
    s = fz.summary(res)
    assert s["pnu"] == "있음" and s["soil"] == "success" and s["prescription"] == "no_data" and s["standard"] == "없음" and s["saved"] == 1
    assert "4376" not in str(s) and "6.1" not in str(s) and s["notes"] == ["prescription: 301 NODATA"]
