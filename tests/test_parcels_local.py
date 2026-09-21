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


def test_ensure_local_moves_pii_to_overlay_without_touching_seed(monkeypatch, tmp_path):
    """씨앗에 PII 가 남아 있는 옛 형태(1단계 이전 사본)를 검사용으로 만들어 둔다 — 실제 씨앗에는 없다(아래 별도 검사)."""
    seed_path = tmp_path / "seed_with_pii.json"
    seed_path.write_text(json.dumps({"parcels": [{"id": "p001", "source": "publisher", "recorded_at": "2026-09-19T00:00:00+00:00",
                                                   "observed_at": "2026-09-18", "resolution": "parcel", "address": "검사용 지번 2", "environment": "노지"}]},
                                    ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(seed_path))
    monkeypatch.setenv("AGRODSS_PARCELS_LOCAL_PATH", str(tmp_path / "no_overlay_yet.json"))
    seed_before = _seed_bytes()
    seed = json.loads(seed_before.decode("utf-8"))["parcels"][0]
    assert "address" in seed
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


def test_no_tracked_file_carries_a_pii_key_whatever_its_name():
    """[§7.5 지점 축 · 2026-09-21] 앞의 래칫은 **파일 이름 둘**을 박아 두었다 — 이름이 다른 새 파일이 주소를 담으면 안 닿는다.
    형태로 고정한다: git 이 추적하는 어떤 텍스트 파일도 PII 키를 갖지 않는다(값은 여기서도 읽지 않는다 — 키만 본다).

    이 검사를 만든 계기: 발행자가 *"저장소가 공개인지"* 를 두 번 물었고, 2026-09-21 에 재니 **공개**였다. 추적 파일은 깨끗했지만
    **이력의 커밋 둘에 주소가 남아 있다** — 그쪽은 검사가 못 막는다(force-push 는 발행자 몫). 검사가 막을 수 있는 것은 **다음 한 건**이다.
    """
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=60).stdout.split()
    bad = []
    for rel in tracked:
        p = ROOT / rel
        if p.suffix.lower() not in (".json", ".csv", ".md", ".txt") or not p.exists():
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # 주소·PNU 는 언제나 PII. 좌표는 **그것이 가리키는 것**에 달렸다 — 관측소 좌표(data/kma/stations.json)는 공개 참조값이고
        # 필지 좌표는 PII 다. 그래서 파일 이름이 아니라 **내용**으로 가른다: 그 파일이 필지 레코드를 담고 있는가.
        # (첫 판은 좌표만 보고 관측소 목록을 걸었다 — 과잉 차단은 다음 사람이 가드를 통째로 끄게 만든다.)
        always = [k for k in ("address", "pnu") if f'"{k}"' in t]
        coords = [k for k in ("lat", "lon") if f'"{k}"' in t] if ('"parcel"' in t or '"parcels"' in t) else []
        if always or coords:
            bad.append((rel, always + coords))
    assert not bad, f"추적 파일이 PII 키를 담았다: {bad} — 값은 덮개(git 밖)에만"


def test_overlay_is_ignored_by_git_and_created_at_server_start():
    assert "data/parcels_local.json" in (ROOT / ".gitignore").read_text(encoding="utf-8").split()
    tracked = subprocess.run(["git", "ls-files", "data"], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=30).stdout.split()
    assert "data/parcels_local.json" not in tracked and "data/parcels.json" not in tracked     # [U-18 2단계] 옛 추적 파일도 git 밖(발행자 덮개 확인 2026-09-20)
    assert "data/parcels_seed.json" in tracked
    src = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")
    body = src[src.index("def make_server"):src.index("def watch_head")]
    assert ".ensure_local()" in body                                                # 발행자 PC 는 pull 뒤 첫 기동에서 덮개를 얻는다
    src_p = (ROOT / "ingest" / "parcels.py").read_text(encoding="utf-8")
    sf = src_p[src_p.index("def set_fields"):]
    assert "parcels_path()" not in sf and "lp.write_text(" in sf                     # 쓰기는 덮개에만


# ── 복구 절차의 순서 함정(미리 걷기 2026-09-21) ────────────────────────────────────
def _write(p: Path, rows: list[dict]) -> None:
    p.write_text(json.dumps({"parcels": rows}, ensure_ascii=False), encoding="utf-8")


def _base(**extra) -> dict:
    return {"id": "p001", "source": "publisher", "recorded_at": "2026-09-19T00:00:00+00:00",
            "observed_at": "2026-09-18", "resolution": "parcel", **extra}


def test_overlay_backfills_values_that_only_the_legacy_file_has(monkeypatch, tmp_path):
    """발행자 PC 복구의 실제 순서 — pull 과 사본 되돌리기 **사이에** 서버가 뜨면 덮개가 좌표 없이 만들어진다
    (HEAD 가 바뀌면 스스로 다시 뜨므로 사람이 순서를 지키기 어렵다). 실측: 좌표·PNU 는 커밋된 적 없는 런타임 값이라
    그대로 사라졌다. 덮개가 있어도 **옛 파일에만 있는 값은 채운다** — 그래야 순서와 무관하게 값을 안 잃는다."""
    seed, legacy, local = tmp_path / "seed.json", tmp_path / "legacy.json", tmp_path / "local.json"
    _write(seed, [_base(environment="노지")])
    _write(legacy, [_base()])                                     # 되돌린 커밋본 — 좌표·PNU 가 없다
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(seed))
    monkeypatch.setenv("AGRODSS_PARCELS_LEGACY_PATH", str(legacy))
    monkeypatch.setenv("AGRODSS_PARCELS_LOCAL_PATH", str(local))
    parcels.ensure_local()                                        # ① 서버가 먼저 떴다
    assert parcels.by_id("p001").get("lat") is None
    _write(legacy, [_base(address="어느 지번", lat=36.7, lon=127.9, pnu="1234567890123456789")])   # ② 사본을 되돌렸다
    parcels.ensure_local()
    rec = parcels.by_id("p001")
    assert rec["lat"] == 36.7 and rec["pnu"].endswith("789") and rec["address"] == "어느 지번", rec
    assert rec["environment"] == "노지"                            # 씨앗 값도 그대로


def test_backfill_never_overwrites_a_value_the_overlay_already_has(monkeypatch, tmp_path):
    """경계 — 채우기는 **덧붙이기만** 한다. 덮개가 이긴다(사람이 화면에서 고친 값을 옛 파일이 되돌리면 안 된다)."""
    seed, legacy, local = tmp_path / "seed.json", tmp_path / "legacy.json", tmp_path / "local.json"
    _write(seed, [_base()])
    _write(legacy, [_base(lat=36.7, lon=127.9)])
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(seed))
    monkeypatch.setenv("AGRODSS_PARCELS_LEGACY_PATH", str(legacy))
    monkeypatch.setenv("AGRODSS_PARCELS_LOCAL_PATH", str(local))
    parcels.ensure_local()
    parcels.set_fields("p001", lat=35.0, overwrite=True)           # 사람이 고쳤다
    parcels.ensure_local()                                        # 다시 떠도
    assert parcels.by_id("p001")["lat"] == 35.0                   # 옛 파일이 되돌리지 않는다
    assert parcels.by_id("p001")["lon"] == 127.9                  # 빠진 값은 그대로 채워진다


def test_backfill_does_not_rewrite_the_overlay_when_there_is_nothing_to_add(monkeypatch, tmp_path):
    """기동마다 덮개를 다시 쓰지 않는다 — 채울 것이 없으면 바이트가 그대로다(쓰기는 잃을 기회다)."""
    seed, legacy, local = tmp_path / "seed.json", tmp_path / "legacy.json", tmp_path / "local.json"
    _write(seed, [_base()])
    _write(legacy, [_base(lat=36.7)])
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(seed))
    monkeypatch.setenv("AGRODSS_PARCELS_LEGACY_PATH", str(legacy))
    monkeypatch.setenv("AGRODSS_PARCELS_LOCAL_PATH", str(local))
    parcels.ensure_local()
    before = local.read_bytes()
    writes = []
    real = Path.write_text
    monkeypatch.setattr(Path, "write_text",
                        lambda self, *a, **k: (writes.append(str(self)), real(self, *a, **k))[1])
    for _ in range(3):                       # 여러 번 떠도
        parcels.ensure_local()
    assert not [w for w in writes if w == str(local)], "채울 것이 없는데 덮개를 다시 썼다(내용이 같아도 쓰기는 잃을 기회다)"
    legacy.unlink()                          # 옛 파일이 아예 없어도 마찬가지
    parcels.ensure_local()
    assert not [w for w in writes if w == str(local)]
    assert local.read_bytes() == before
