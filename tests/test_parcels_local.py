# -*- coding: utf-8 -*-
# [U-18 · 발행자 2026-09-20 "저장소 안 필지 주소는 오늘이다"] 등록부 두 겹 — 추적 파일(씨앗)에는 PII 가 없고, 이 PC 의 값(주소 · PNU · 좌표 ·
# 런타임 기록)은 gitignore 된 덮개에만. 읽기는 덮개가 씨앗을 덮고, 쓰기는 덮개에만(추적 파일에 런타임이 쓰면 발행자 PC 의 pull 이 충돌한다).
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ingest import parcels

ROOT = Path(__file__).resolve().parent.parent


def _seed_bytes() -> bytes:
    return Path(parcels.parcels_path()).read_bytes()


def test_ensure_local_moves_pii_to_overlay_without_touching_seed():
    seed_before = _seed_bytes()
    seed = json.loads(seed_before.decode("utf-8"))["parcels"][0]
    assert "address" in seed                                                        # 격리 사본의 씨앗에는 아직 주소가 있다(2단계에서 뺀다)
    lp = parcels.ensure_local()
    assert lp == Path(parcels.local_path()) and lp.exists() and lp != Path(parcels.parcels_path())
    over = json.loads(lp.read_text(encoding="utf-8"))["parcels"]
    assert over and over[0]["id"] == "p001" and over[0]["address"] == seed["address"]
    assert set(over[0]) <= {"id", *parcels.PRIVATE_FIELDS}                            # 덮개로 옮기는 것은 PII 필드뿐
    assert _seed_bytes() == seed_before                                             # 씨앗(추적 파일)은 안 건드린다
    assert parcels.ensure_local() == lp and json.loads(lp.read_text(encoding="utf-8"))["parcels"] == over   # 두 번째는 그대로


def test_set_fields_writes_overlay_only_and_load_merges_with_none_as_absent():
    seed_before = _seed_bytes()
    rec = parcels.set_fields("p001", lat=36.7, lon=127.9, slope="평지")
    assert rec["lat"] == 36.7 and rec["slope"] == "평지" and rec["address"]           # 합쳐진 현재 값
    assert _seed_bytes() == seed_before                                             # 런타임 기록은 추적 파일에 쓰지 않는다
    over = json.loads(Path(parcels.local_path()).read_text(encoding="utf-8"))["parcels"]
    assert next(r for r in over if r["id"] == "p001")["slope"] == "평지"
    assert parcels.by_id("p001")["lat"] == 36.7 and parcels.by_id("p001")["environment"] == "노지"   # 씨앗 값 + 덮개 값
    assert parcels.set_fields("p001", slope="완경사")["slope"] == "평지"               # 있는 값은 덮지 않는다
    assert "slope" not in parcels.set_fields("p001", slope=None)                     # None = 키 없음
    assert "slope" not in parcels.by_id("p001")
    assert "environment" not in parcels.set_fields("p001", environment=None)         # 덮개의 None 이 씨앗 값도 가린다(대리값 금지)
    assert parcels.set_fields("p001", environment="시설", overwrite=True)["environment"] == "시설"


def test_legacy_tracked_file_is_migration_source_only_and_real_seed_has_no_pii(monkeypatch, tmp_path):
    """발행자 PC: 씨앗(새 추적 파일)에는 PII 가 없고 옛 추적 파일(data/parcels.json)에 주소 + 런타임이 써 넣은 좌표가 있다 → 첫 기동이 덮개로 옮긴다."""
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"parcels": [{"id": "p001", "source": "publisher", "recorded_at": "2026-09-19T00:00:00+00:00",
                                              "observed_at": "2026-09-18", "resolution": "parcel", "environment": "노지"}]}, ensure_ascii=False), encoding="utf-8")
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({"parcels": [{"id": "p001", "source": "publisher", "recorded_at": "2026-09-19T00:00:00+00:00",
                                                "observed_at": "2026-09-18", "resolution": "parcel", "address": "어느 지번", "lat": 36.7, "lon": 127.9,
                                                "pnu": "1234567890123456789", "slope": "평지"}]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(seed))
    monkeypatch.setenv("AGRODSS_PARCELS_LEGACY_PATH", str(legacy))
    monkeypatch.setenv("AGRODSS_PARCELS_LOCAL_PATH", str(tmp_path / "local.json"))
    parcels.ensure_local()
    rec = parcels.by_id("p001")
    assert rec["address"] == "어느 지번" and rec["lat"] == 36.7 and rec["pnu"].endswith("789") and rec["slope"] == "평지" and rec["environment"] == "노지"
    assert legacy.read_text(encoding="utf-8") and seed.read_text(encoding="utf-8")                       # 둘 다 안 건드린다
    assert "address" not in json.loads(seed.read_text(encoding="utf-8"))["parcels"][0]
    # 저장소의 실제 씨앗 — PII 필드 없음. 옛 추적 파일은 이 커밋에서 건드리지 않는다(발행자 PC 의 pull 이 멈추지 않게) — 뺄 때는 별도 커밋
    real_seed = json.loads((ROOT / "data" / "parcels_seed.json").read_text(encoding="utf-8"))["parcels"]
    assert real_seed and all(not any(k in r for k in parcels.PRIVATE_FIELDS) for r in real_seed)
    assert "data/parcels.json" in (ROOT / ".gitignore").read_text(encoding="utf-8").split()


def test_overlay_is_ignored_by_git_and_created_at_server_start():
    assert "data/parcels_local.json" in (ROOT / ".gitignore").read_text(encoding="utf-8").split()
    tracked = subprocess.run(["git", "ls-files", "data"], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=30).stdout
    assert "parcels_local" not in tracked
    src = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")
    body = src[src.index("def make_server"):src.index("def watch_head")]
    assert ".ensure_local()" in body                                                # 발행자 PC 는 pull 뒤 첫 기동에서 덮개를 얻는다
    src_p = (ROOT / "ingest" / "parcels.py").read_text(encoding="utf-8")
    sf = src_p[src_p.index("def set_fields"):]
    assert "parcels_path()" not in sf and "lp.write_text(" in sf                     # 쓰기는 덮개에만
