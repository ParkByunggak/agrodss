# -*- coding: utf-8 -*-
# [발행자 몫의 마찰 제거] CLI 도 .env 를 읽는다 · VELA .env 에서 키를 이름만 보고 옮긴다(있는 값은 안 건드린다 · 값은 안 찍는다) ·
#        수집 요약은 PII 없이 상태만.
from __future__ import annotations

import os
from pathlib import Path

from ingest import config as icfg, fertilizer as fz
from scripts import env_from_vela as ev

ROOT = Path(__file__).resolve().parent.parent


# ── [코드 평가 D2 · D11 · 2026-09-19] 발행자가 오늘 밟는 live_check 경로 ───────────────────────────────────────────
def test_dotenv_loader_is_one_and_lives_in_ingest_config():
    # 로더 두 벌이 빈 값을 다르게 다뤄 화면 프로세스에서 옮긴 키가 사라졌다 — frontend 는 자기 로더를 갖지 않는다
    src = (ROOT / "frontend" / "config.py").read_text(encoding="utf-8")
    assert "def _load_dotenv" not in src and "from ingest import config" in src
    assert "load_dotenv(ROOT / \".env\")" in (ROOT / "ingest" / "config.py").read_text(encoding="utf-8")


def test_merge_replaces_empty_key_line_instead_of_appending():
    # .env.example 을 복사한 파일에는 빈 KEY= 줄이 있다 — 덧붙이면 두 줄이 되고 로더(첫 줄 우선)는 빈 값을 본다
    cur = "# keys\nSOIL_API_KEY=\nVWORLD_API_KEY=\nAGRODSS_WATCH_DIRS=C:\\x\n"
    vela = "SOIL_API_KEY=vela-soil\nEXTERNAL_API__VWORLD_API_KEY=vela-vw\n"
    new, copied, missing = ev.merge(cur, vela, ["SOIL_API_KEY", "VWORLD_API_KEY", "PSIS_API_KEY"])
    assert copied == ["SOIL_API_KEY", "VWORLD_API_KEY"] and missing == ["PSIS_API_KEY"]
    assert new.count("SOIL_API_KEY=") == 1 and new.count("VWORLD_API_KEY=") == 1        # 교체 — 두 줄이 아니다
    assert ev.parse_env(new)["SOIL_API_KEY"] == "vela-soil" and new.index("SOIL_API_KEY=vela-soil") < new.index("AGRODSS_WATCH_DIRS")
    assert "[D-9 키 인용]" not in new                                                    # 덧붙인 것이 없으면 머리말도 없다
    new2, _, _ = ev.merge("AGRODSS_WATCH_DIRS=C:\\x\n", vela, ["SOIL_API_KEY"])          # 빈 줄이 없으면 덧붙인다
    assert "[D-9 키 인용]" in new2 and ev.parse_env(new2)["SOIL_API_KEY"] == "vela-soil"


def test_live_check_bat_is_ascii_uses_subject_and_delayed_expansion():
    raw = (ROOT / "scripts" / "live_check.bat").read_bytes()
    assert all(b < 128 for b in raw), "배치는 ASCII 만 — cmd 가 cp949 로 읽어 UTF-8 한글이 깨진다"
    text = raw.decode("ascii")
    assert "enabledelayedexpansion" in text and "!errorlevel!" in text and "%errorlevel%" not in text.split("REM inside")[-1].split("\n", 1)[1]
    assert "--subject=" in text and "--parcel=" not in text and "--crop=" not in text  # 작목·주소는 등록부에서 — 배치에 리터럴 없음


def test_resolve_subject_reads_registries_and_refuses_unknown():
    r = fz.resolve_subject("p001-jjokpa-2026f")
    assert r["parcel"] == "p001" and r["crop"] == "쪽파" and set(r) == {"parcel", "crop", "address", "environment"}
    import pytest
    with pytest.raises(fz.CodeError, match="없는 재배 단위"):
        fz.resolve_subject("nope")


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
