# -*- coding: utf-8 -*-
# FILE: ingest/parcels.py
# ROLE: [M-6 · I-3 §1 · I-6] 필지 등록부 — 필지 고정 정보의 자리. 주소·PNU·좌표는 여기 있고 화면·봉투·몰에는 안 나간다(I-5 §1-2).
#       값이 없으면 키가 없다(대리값 금지). 3층에는 PARCEL_FIELDS_TO_LAYER3 만 붙여 준다.
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
PARCELS_PATH = ROOT / "data" / "parcels.json"


# [U-18 · 발행자 2026-09-20 "저장소 안 필지 주소는 오늘이다"] 원격이 **공개** 저장소(실측 visibility=public)인데 등록부 파일이 git 추적이라
# 지번 주소가 밖에 있었다. 그리고 런타임 기록(지오코딩 좌표 · PNU · 되물은 재배환경)이 그 추적 파일에 써져 발행자 PC 의 pull 이 충돌할 형태였다.
# 이제 등록부는 두 겹이다 — 추적 파일(data/parcels.json)은 PII 없는 **씨앗**, 이 PC 의 값(주소 · PNU · 좌표 · 런타임 기록 전부)은
# gitignore 된 **덮개**(data/parcels_local.json)에만. 읽을 때 덮개가 씨앗을 덮고, 쓸 때는 덮개에만 쓴다. 씨앗은 사람이 커밋으로만 고친다.
LOCAL_PATH = ROOT / "data" / "parcels_local.json"
SEED_PATH = ROOT / "data" / "parcels_seed.json"
PRIVATE_FIELDS = ("address", "pnu", "lat", "lon")     # 씨앗에 있으면 안 되는 필드 — ensure_local 이 덮개로 옮긴다
# 옛 추적 파일(data/parcels.json)은 여기서 **읽기만** 한다(덮개가 없을 때 이주 원천). 실측(2026-09-20): 로컬에서 수정된 추적 파일은
# upstream 이 지우거나 고치면 pull 이 "commit or stash" 로 멈춘다 — 발행자 PC 의 등록부는 2회차가 좌표를 써 넣어 수정돼 있을 수 있다.
# 그래서 이 파일은 코드가 갈아탄 뒤(덮개가 생긴 뒤) 별도 커밋으로 git 에서 뺀다. 그때까지 upstream 은 이 경로를 건드리지 않는다.


def parcels_path() -> Path:
    """씨앗(추적 파일 · PII 없음). [R-4 · 코드 평가 C4] 경로는 호출 시점에 env 로 푼다 — 기본 인자에 묶으면 conftest 격리가 안 닿는다."""
    return Path(os.environ.get("AGRODSS_PARCELS_PATH") or SEED_PATH)


def local_path() -> Path:
    return Path(os.environ.get("AGRODSS_PARCELS_LOCAL_PATH") or LOCAL_PATH)


def legacy_path() -> Path:
    return Path(os.environ.get("AGRODSS_PARCELS_LEGACY_PATH") or PARCELS_PATH)


def _read(p: Path) -> list[dict[str, Any]]:
    if not p.exists():
        return []
    return list(json.loads(p.read_text(encoding="utf-8")).get("parcels", []))


def ensure_local() -> Path:
    """씨앗(추적 파일)에 PII 필드가 남아 있고 덮개가 없으면 덮개를 만들어 옮겨 둔다 — 발행자 PC 에서 pull 뒤 첫 기동에 자동으로 일어난다.
    씨앗은 여기서 건드리지 않는다(추적 파일 쓰기 금지 — 씨앗에서 PII 를 빼는 것은 커밋으로)."""
    lp = local_path()
    if lp.exists():
        return lp
    seed = {r.get("id"): r for r in _read(parcels_path())}
    legacy = {r.get("id"): r for r in _read(legacy_path())}       # 옛 추적 파일 — 발행자 PC 에는 런타임이 써 넣은 좌표·PNU 도 여기 있다
    moved: list[dict[str, Any]] = []
    for pid in list(seed) + [k for k in legacy if k not in seed]:
        s, lg = seed.get(pid, {}), legacy.get(pid, {})
        priv = {k: lg[k] for k in PRIVATE_FIELDS if k in lg}
        priv.update({k: s[k] for k in PRIVATE_FIELDS if k in s})
        extra = {k: v for k, v in lg.items() if k not in s and k not in PRIVATE_FIELDS and k != "id"}   # 옛 파일에만 있는 런타임 기록
        if priv or extra:
            moved.append({"id": pid, **priv, **extra})
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text(json.dumps({"_note": "이 PC 의 필지 값(PII · 런타임 기록) — git 밖. 씨앗은 data/parcels.json", "parcels": moved},
                             ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return lp


def load(path: Path | None = None) -> list[dict[str, Any]]:
    """씨앗 + 덮개(같은 id 는 덮개 값이 이긴다). path 를 주면 그 파일 하나만(옛 호출 호환)."""
    if path is not None:
        return [sch.validate(r, kind="parcel") for r in _read(path)]
    rows = _read(parcels_path())
    over = {r.get("id"): r for r in _read(local_path())}
    out = []
    for r in rows:
        merged = {**r, **{k: v for k, v in over.get(r.get("id"), {}).items() if k != "id"}}
        merged = {k: v for k, v in merged.items() if v is not None}   # 덮개의 None = 그 키 없음(대리값 금지 — 키를 두지 않는다)
        out.append(sch.validate(merged, kind="parcel"))
    return out


def by_id(pid: str, path: Path | None = None) -> dict[str, Any] | None:
    for r in load(path):
        if r.get("id") == pid:
            return r
    return None


def public_view(rec: dict[str, Any]) -> dict[str, Any]:
    """화면용 — PII 를 뺀다(정본 sch.strip_pii · kind 가 선언한 pii). 있음/없음만 남긴다."""
    out = sch.strip_pii({**rec, "kind": rec.get("kind") or "parcel"})
    out["location"] = "있음" if any(rec.get(k) is not None for k in ("address", "pnu", "lat", "lon")) else "없음"
    return out


def enrich_subject(subject: dict[str, Any], parcel: dict[str, Any] | None) -> dict[str, Any]:
    """재배 단위에 필지의 3층 허용 필드만 붙인다. 주소·PNU 는 붙지 않는다. 없는 값은 안 붙는다."""
    s = dict(subject)
    if not parcel:
        return s
    for k in sch.PARCEL_FIELDS_TO_LAYER3:
        if k in parcel and k not in s:
            s[k] = parcel[k]
    return s


def missing_inputs(parcel: dict[str, Any] | None) -> list[str]:
    """I-6 입력 대기 — 필지 레코드에 아직 없는 키(화면에 '입력 대기'로)."""
    want = ("lat", "lon", "area_m2", "use", "environment", "soil_texture", "slope", "drainage", "irrigation",
            "microclimate", "night_light", "cert_legal", "seed_source", "soil_exam_ref")
    have = set(parcel or {})
    return [k for k in want if k not in have]


class ParcelError(ValueError):
    pass


def set_fields(pid: str, **fields: Any) -> dict[str, Any]:
    """[I-6 · 발행자 라이브 2026-09-19 21:34] 필지 등록부에 값을 넣는다 — 지오코딩이 얻은 좌표·PNU, 되물은 재배환경.
    스키마(kind=parcel)가 허용하는 필드만, 값이 None 이면 키를 지운다(대리값 금지). 이미 있는 값은 덮지 않는다(overwrite=True 로만)."""
    overwrite = bool(fields.pop("overwrite", False))
    rec = by_id(pid)                                          # 씨앗 + 덮개가 합쳐진 현재 값
    if rec is None:
        raise ParcelError(f"없는 필지: {pid}")
    allowed = sch.KINDS["parcel"].fields
    lp = ensure_local()
    data = json.loads(lp.read_text(encoding="utf-8"))
    rows = data.setdefault("parcels", [])
    over = next((r for r in rows if r.get("id") == pid), None)
    if over is None:
        over = {"id": pid}
        rows.append(over)
    for k, v in fields.items():
        if k not in allowed:
            raise ParcelError(f"필지 등록부에 없는 필드: {k}")
        if v is None:
            over[k] = None                                    # 덮개의 None = 씨앗 값도 가린다(키 삭제와 같은 뜻)
        elif k not in rec or rec.get(k) is None or overwrite:
            over[k] = v
    merged = {**rec, **{k: v for k, v in over.items() if k != "id"}}
    merged = {k: v for k, v in merged.items() if v is not None}
    sch.validate(merged, kind="parcel")
    lp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")   # 추적 파일(씨앗)에는 쓰지 않는다
    return merged
