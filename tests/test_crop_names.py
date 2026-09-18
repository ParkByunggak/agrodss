# -*- coding: utf-8 -*-
# [D-11] 이름 정규화 — 발행자 판정 5쌍은 고정, 모호는 되묻기, 모르면 모름(추측 금지).
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

from names import resolve as R

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_crop_axes_doc as b  # noqa: E402


# ── 발행자 판정 5쌍 (2026-09-18) ────────────────────────────────────────────────
@pytest.mark.parametrize("alias,canon", [
    ("길경", "도라지"), ("도라지(길경)", "도라지"),
    ("고려엉겅퀴", "곤드레"), ("곤드레(고려엉겅퀴)", "곤드레"),
    ("취나물", "참취"),
    ("긴강남차", "결명자"),
])
def test_publisher_identity_pairs(alias, canon):
    r = R.resolve(alias)
    assert r.status == "alias" and r.canonical == canon, r


def test_publisher_identity_pairs_source_is_publisher():
    assert R.resolve("길경").source == "발행자"
    assert R.resolve("취나물").source == "발행자"


def test_sorghum_is_not_merged():
    # 수수 ≠ 찰수수 — 같은 종이지만 용도가 달라 각자 정본
    assert R.resolve("찰수수").status == "canonical"
    assert R.resolve("수수").status == "canonical"


# ── 모호 · 모름 ──────────────────────────────────────────────────────────────────
def test_ambiguous_asks_back():
    r = R.resolve("깨")
    assert r.status == "ambiguous" and set(r.candidates) == {"참깨", "들깨"}
    r = R.resolve("파")
    assert r.status == "ambiguous" and "쪽파" in r.candidates


def test_unknown_is_unknown_not_guessed():
    assert R.resolve("없는작목이름").status == "unknown"
    assert R.resolve("").status == "unknown"


def test_dialect_alias_resolves_with_inferred_source():
    r = R.resolve("정구지")
    assert r.status == "alias" and r.canonical == "부추" and r.source == "추론"


def test_caution_pairs_are_flagged_both_ways():
    assert "초피나무" in R.resolve("산초나무").cautions
    assert "산초나무" in R.resolve("초피나무").cautions


def test_whitespace_normalized():
    assert R.resolve(" 도라지 ( 길경 ) ").canonical == "도라지"


# ── 정본 일관성 ──────────────────────────────────────────────────────────────────
def test_identity_aliases_are_not_canonical():
    d = R.load()
    for alias in d.alias:
        assert alias not in d.canonical, alias


def test_every_canonical_in_names_csv_exists_as_crop():
    d = R.load()
    with R.NAMES_CSV.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["관계"] in (R.AMBIGUOUS,):
                for c in r["정본명"].split("/"):
                    assert R._norm(c) in d.canonical, f"모호 후보 {c!r} 가 작목이 아니다"
            elif r["관계"] == R.IDENTITY:
                assert R._norm(r["정본명"]) in d.canonical, r["정본명"]


def test_vela_duplicate_rows_have_identical_axes():
    # 동일 관계인데 둘 다 VELA 키인 쌍은 축 값이 같아야 한다 — 합칠 때 정보가 안 사라지도록
    rows = {r["작목"]: r for r in b.load_rows()}
    pairs = [("도라지", "도라지(길경)"), ("곤드레(고려엉겅퀴)", "고려엉겅퀴"), ("참취", "취나물"),
             ("결명자", "긴강남차")]
    for a, c in pairs:
        ra, rc = rows[a], rows[c]
        for col in b.AXES[1:-1]:  # 범위·확신 제외
            assert ra[col] == rc[col], f"{a}/{c}.{col}: {ra[col]} != {rc[col]}"


def test_names_doc_in_sync():
    generated = b.build_names(b.load_names())
    assert generated == b.NAMES_DOC_PATH.read_text(encoding="utf-8"), "docs/crop_names.md 재생성 필요"
