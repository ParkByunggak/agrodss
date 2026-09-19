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
    """정본 CSV 경로 — 호출 시점에 env 로 푼다(U-14 승인이 여기에 쓴다 · 테스트는 사본 — R-4 규율)."""
    return Path(os.environ.get("AGRODSS_NAMES_CSV") or NAMES_CSV)

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
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load(names_csv: Path | None = None, axes_csv: Path | None = None) -> Dictionary:
    """경로는 호출 시점에 푼다 — 기본 인자에 묶으면 승인(CSV 추가)·격리가 안 닿는다(R-4)."""
    return _load(Path(names_csv or names_csv_path()), Path(axes_csv or AXES_CSV))


def reload() -> None:
    """사전 재적재 — U-14 승인이 CSV 에 줄을 붙인 뒤, 테스트 격리 전후."""
    _load.cache_clear()


@lru_cache(maxsize=4)
def _load(names_csv: Path, axes_csv: Path) -> Dictionary:
    d = Dictionary()
    # 정본명의 첫 원천: 격자 대상 작목 전수(범위=작목)
    for r in _read(axes_csv):
        if r["범위"] == "작목":
            d.canonical.add(_norm(r["작목"]))
    for r in _read(names_csv):
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
