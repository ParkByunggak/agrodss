# -*- coding: utf-8 -*-
# FILE: names/resolve.py
# ROLE: [D-11] 작목 이름 → 정본명. 격자 단위·입력·경계가 전부 같은 키를 잡게 하는 첫 관문.
#
# 원칙 (발행자 2026-09-18): 이름 혼동은 격자보다 먼저 정리한다. 현장은 사투리를 쓴다 —
#   사전은 열린 목록이고, 모르는 이름은 추측하지 않고 '모름'으로 돌려준다(대리값 금지).
#
# 상태:  canonical  정본명 그 자체
#        alias      동일 관계의 이명 → 정본명
#        ambiguous  통칭 — 후보 목록. 되묻기
#        unknown    사전에 없음 — 채집 대상(U-14)
from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES_CSV = ROOT / "data" / "crop_names.csv"
AXES_CSV = ROOT / "data" / "crop_axes.csv"


def names_csv_path() -> Path:
    """씨앗 CSV 경로(추적 · 읽기만) — 호출 시점에 env 로 푼다(테스트는 사본 — R-4 규율).
    [U-38 2026-09-27] 전에는 승인이 여기 줄을 붙였다 — 추적 파일에 런타임이 쓰면 다음 update.bat 이 되돌려 **승인한 이름이 사전에서
    사라진다**(재배 단위 등록부 U-24·U-37 과 같은 형태). 이제 승인은 덮개(`names_local_csv_path`)에만 쓴다."""
    return Path(os.environ.get("AGRODSS_NAMES_CSV") or NAMES_CSV)


NAMES_LOCAL_CSV = ROOT / "data" / "crop_names_local.csv"
NAMES_BACKUP_CSV = ROOT / "data" / "_local_backup" / "crop_names.csv"
HEADER = ("정본명", "이명", "관계", "이명종류", "출처", "비고")


def names_local_csv_path() -> Path:
    """덮개 CSV(git 밖) — 이 PC 의 승인이 쌓인다. 씨앗과 같은 열. 세션이 커밋으로 씨앗에 옮기면 그 줄은 중복이어도 무해하다(같은 키)."""
    return Path(os.environ.get("AGRODSS_NAMES_LOCAL_CSV") or NAMES_LOCAL_CSV)


def names_backup_csv_path() -> Path:
    """update.bat 이 수정된 추적 CSV 를 옮겨 두는 자리(읽기만) — 두 겹 이전 승인이 여기 남는다."""
    return Path(os.environ.get("AGRODSS_NAMES_BACKUP_CSV") or NAMES_BACKUP_CSV)


def append_local(row: dict[str, str]) -> None:
    """덮개에 한 줄 — 없으면 머리글부터. 쓴 뒤 사전을 다시 읽는다."""
    p = names_local_csv_path()
    new = not p.exists()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(HEADER)
        w.writerow([row.get(h, "") for h in HEADER])
    reload()


def ensure_local() -> int:
    """[U-38] update.bat 사본에 남은 승인 줄(두 겹 이전에 씨앗에 붙은 것)을 덮개로 — 씨앗에도 덮개에도 없는 (정본명, 이명)만.
    사본이 없으면 아무것도 안 만든다. 멱등. 돌려주는 값은 덧붙인 줄 수."""
    bp = names_backup_csv_path()
    if not bp.exists():
        return 0
    seen = {(r.get("정본명", ""), r.get("이명", "")) for r in _read(names_csv_path()) + _read(names_local_csv_path())}
    added = 0
    for r in _read(bp):
        key = (r.get("정본명", ""), r.get("이명", ""))
        if not key[0] or not key[1] or key in seen:
            continue
        append_local(r)
        seen.add(key)
        added += 1
    return added

IDENTITY = "동일"
AMBIGUOUS = "모호"
CAUTION = "다른종(혼동주의)"


@dataclass(frozen=True)
class Resolution:
    status: str                       # canonical | alias | ambiguous | unknown
    query: str
    canonical: str | None = None      # canonical · alias 일 때
    candidates: tuple[str, ...] = ()  # ambiguous 일 때
    cautions: tuple[str, ...] = ()    # 혼동 주의 상대 — 되묻기 문구 재료
    source: str | None = None         # 이명 판정 출처(발행자 / VELA / 추론)


def _norm(s: str) -> str:
    return "".join(s.split())


@dataclass
class Dictionary:
    canonical: set[str] = field(default_factory=set)
    alias: dict[str, tuple[str, str]] = field(default_factory=dict)        # 이명 → (정본명, 출처)
    ambiguous: dict[str, tuple[tuple[str, ...], str]] = field(default_factory=dict)
    caution: dict[str, set[str]] = field(default_factory=dict)             # 이름 → 혼동 상대들

    def resolve(self, name: str) -> Resolution:
        q = _norm(name)
        if not q:
            return Resolution("unknown", name)
        if q in self.ambiguous:
            cands, src = self.ambiguous[q]
            return Resolution("ambiguous", name, candidates=cands, source=src)
        if q in self.canonical:
            return Resolution("canonical", name, canonical=q, cautions=tuple(sorted(self.caution.get(q, ()))))
        if q in self.alias:
            canon, src = self.alias[q]
            return Resolution("alias", name, canonical=canon, source=src,
                              cautions=tuple(sorted(self.caution.get(canon, ()))))
        return Resolution("unknown", name)


def _read(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []                                  # 덮개·사본은 없을 수 있다 — 없으면 빈 것(지어내지 않는다)
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load(names_csv: Path | None = None, axes_csv: Path | None = None, local_csv: Path | None = None) -> Dictionary:
    """경로는 호출 시점에 푼다 — 기본 인자에 묶으면 승인(CSV 추가)·격리가 안 닿는다(R-4). 씨앗 + 덮개(U-38)."""
    return _load(Path(names_csv or names_csv_path()), Path(local_csv or names_local_csv_path()), Path(axes_csv or AXES_CSV))


def reload() -> None:
    """사전 재적재 — U-14 승인이 CSV 에 줄을 붙인 뒤, 테스트 격리 전후."""
    _load.cache_clear()


@lru_cache(maxsize=4)
def _load(names_csv: Path, local_csv: Path, axes_csv: Path) -> Dictionary:
    d = Dictionary()
    # 정본명의 첫 원천: 격자 대상 작목 전수(범위=작목)
    for r in _read(axes_csv):
        if r["범위"] == "작목":
            d.canonical.add(_norm(r["작목"]))
    for r in _read(names_csv) + _read(local_csv):     # 씨앗 뒤에 덮개 — 같은 키면 덮개가 나중에 쓴다
        canon, alias, rel, src = _norm(r["정본명"]), _norm(r["이명"]), r["관계"], r["출처"]
        if rel == AMBIGUOUS:
            d.ambiguous[alias] = (tuple(_norm(c) for c in canon.split("/")), src)
            continue
        if rel == CAUTION:
            d.caution.setdefault(canon, set()).add(alias)
            d.caution.setdefault(alias, set()).add(canon)
            continue
        if rel == IDENTITY:
            d.canonical.add(canon)
            d.alias[alias] = (canon, src)
        # 용도구분 · 품종군 · 부산물은 이명이 아니라 관련 항목 — 각자 정본명이다
    # 동일 관계의 이명이 정본 집합에도 있으면(VELA 중복 키) 정본에서 뺀다 — 키는 하나
    for alias in d.alias:
        d.canonical.discard(alias)
    return d


def resolve(name: str) -> Resolution:
    return load().resolve(name)
