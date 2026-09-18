# -*- coding: utf-8 -*-
# [M-7 · 트리 C] 작목 축 마킹 정본(CSV)의 형식 래칫 + 문서 동기 래칫.
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_crop_axes_doc as b  # noqa: E402

ENUMS = {
    "범위": {"작목", "버섯", "채취·부산물", "관상"},
    "생애주기": {"일년생", "다년생초본", "목본", "해당없음"},
    "수확형태": {"일시", "연속", "혼합", "해당없음"},
    "재배환경": {"노지", "시설", "양쪽"},
    "품종의존": {"시간축", "성질까지", "미상"},
    "수확단위": {"필지", "품종", "해당없음"},
    "품종불명": {"영향미미", "범위제시", "판단불가", "미상"},
    "저장성": {"낮음", "중간", "높음", "해당없음"},
    "수분구조": {"자가", "타가", "부분자가", "해당없음"},
    "품종다양성": {"낮음", "중간", "높음", "해당없음"},
    "확신": {"상", "중", "하"},
}
PROPAGATION = {"직파", "육묘정식", "영양번식", "해당없음"}


@pytest.fixture(scope="module")
def rows():
    return b.load_rows()


def test_row_count_matches_vela_species(rows):
    assert len(rows) == 202, "VELA crop_master_list species_index 202 (2026-09-18 실측)"


def test_names_unique(rows):
    names = [r["작목"] for r in rows]
    assert len(names) == len(set(names))


def test_enums(rows):
    for r in rows:
        for col, allowed in ENUMS.items():
            assert r[col] in allowed, f"{r['작목']}.{col}={r[col]!r}"
        for p in r["번식방식"].split("+"):
            assert p in PROPAGATION, f"{r['작목']}.번식방식={r['번식방식']!r}"


def test_non_crop_scope_has_no_variety_dependence(rows):
    # 격자 대상이 아닌 것(채취·부산물·관상)과 버섯은 품종 축이 '미상'이어야 한다 — 마킹한 척하지 않는다
    for r in rows:
        if r["범위"] != "작목":
            assert r["품종의존"] == "미상", r["작목"]


def test_crop_scope_is_fully_marked(rows):
    # 작목은 품종 축이 '미상'이면 안 된다 — 빈칸 3종 중 '아직 안 채움'을 '값 있음'으로 위장하지 않는다
    for r in rows:
        if r["범위"] == "작목":
            assert r["품종의존"] != "미상" and r["품종불명"] != "미상", r["작목"]


def test_vegetative_harvest_pollination_is_na(rows):
    # 잎·뿌리 수확 작물 표본: 수분구조 해당없음
    by = {r["작목"]: r for r in rows}
    for n in ("배추", "감자", "쪽파", "당근", "부추"):
        assert by[n]["수분구조"] == "해당없음", n


def test_tree_examples_agree(rows):
    # 트리 C 의 예시와 어긋나지 않는다
    by = {r["작목"]: r for r in rows}
    assert by["배추"]["생애주기"] == "일년생" and by["사과"]["생애주기"] == "목본"
    assert by["부추"]["생애주기"] == "다년생초본"
    assert by["오이"]["수확형태"] == "연속" and by["벼"]["수확형태"] == "일시"
    assert by["사과"]["수분구조"] == "타가" and by["배"]["수분구조"] == "타가"
    assert "영양번식" in by["감자"]["번식방식"] and "영양번식" in by["포도"]["번식방식"]
    assert by["벼"]["품종불명"] == "판단불가"       # 품종이 작형 결정
    assert by["쪽파"]["범위"] == "작목"              # D-1 첫 작목


def test_doc_is_in_sync_with_csv(rows):
    generated = b.build(rows)
    on_disk = b.DOC_PATH.read_text(encoding="utf-8")
    assert generated == on_disk, "docs/crop_axes.md 가 정본(CSV)과 다르다 — build_crop_axes_doc.py 를 돌려라"
