# -*- coding: utf-8 -*-
# [검토표 ② 2026-09-29 · 발행자 승인 "제안 순서대로"] 격자 값 한 명령 — 미리 걷기 → 격자 → 문서 → 검사 → 잔여 보고. 계약: 잔여가 상태 검사 하나를 넘으면
# 아무것도 쓰지 않는다 · 형태가 틀리면 쓰지 않는다 · 넣으면 문서까지 · 커밋은 하지 않는다 · 본체 저장소가 아니라 임시 클론에서 검사한다.
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import apply_grid_value as ag
from scripts import prewalk_grid as pw

ROOT = Path(__file__).resolve().parent.parent
VALUE = {"dry_days": 7, "source": "검사용 출처 2026"}


@pytest.fixture
def clone(tmp_path):
    """본체의 임시 클론 — 이 도구는 본체에 쓰는 것이 일이라(격자 = 커밋 정본) 검사는 클론에서 한다."""
    c = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--shared", str(ROOT), str(c)], check=True, capture_output=True)
    # [§10 2026-10-03 실측] 클론은 HEAD 다 — 격자와 검증기가 **같은 회차에** 바뀌면(fixable_by) 이 프로세스의 새 검증기가 HEAD 격자를 거부해 도구가 아무것도
    # 안 쓴다. 도구의 검사는 커밋 상태가 아니라 **지금 격자**에 대한 것이라 격자 파일만 작업 트리 것으로 덮는다(검증기 · 문서 생성기도 이 프로세스 것이다).
    for p in (ROOT / "data" / "grid").glob("*.json"):
        (c / "data" / "grid" / p.name).write_bytes(p.read_bytes())
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-a", "--allow-empty", "-m", "working grid"], cwd=c, check=True, capture_output=True)
    return c


def _pre(residual, doc_rebuilt=True):
    return {"worktree": "x", "grid": "data/grid/jjokpa_autumn.json", "stage": "3·4", "key": "drought_rules", "failures_before_doc": residual,
            "doc_rebuilt": doc_rebuilt, "doc_mentions_value": True, "failures_after_doc": residual, "worktree_removed": True}


def test_decide_lets_only_one_state_test_remain():
    assert ag.decide(_pre([])) == (True, "")
    assert ag.decide(_pre(["tests/test_drought_slot.py::test_with_the_real_grid"])) == (True, "")
    go, why = ag.decide(_pre(["a::t1", "b::t2"]))
    assert not go and "잔여 2" in why and "처방이 먼저다" in why
    go, why = ag.decide(_pre([], doc_rebuilt=False))
    assert not go and "문서 재생성" in why


def test_it_writes_nothing_when_the_prewalk_leaves_more_than_one(clone, monkeypatch):
    monkeypatch.setattr(pw, "walk", lambda *a, **k: _pre(["a::t1", "b::t2"]))
    grid = clone / "data" / "grid" / "jjokpa_autumn.json"
    before = grid.read_bytes()
    r = ag.apply("jjokpa_autumn", [3, 4], "drought_rules", VALUE, tests=[], root=clone)
    assert not r["applied"] and "처방이 먼저다" in r["why"] and grid.read_bytes() == before
    assert "넣지 않았다" in ag.report(r)
    st = subprocess.run(["git", "status", "--short"], cwd=clone, capture_output=True, text=True).stdout
    assert st.strip() == ""                                                              # 클론에 아무것도 안 바뀌었다


def test_it_writes_the_grid_and_the_doc_and_reports_what_is_left(clone, monkeypatch):
    monkeypatch.setattr(pw, "walk", lambda *a, **k: _pre(["tests/test_drought_slot.py::test_with_the_real_grid_it_says_which_cell_is_empty_and_what_the_water_values_are"]))
    head = subprocess.run(["git", "log", "--oneline", "-1"], cwd=clone, capture_output=True, text=True).stdout     # 클론의 HEAD(작업 트리 격자를 덮은 커밋)
    r = ag.apply("jjokpa_autumn", [3, 4], "drought_rules", VALUE, tests=[], root=clone)
    assert r["applied"] and r["doc_mentions_value"]
    unit = json.loads((clone / "data" / "grid" / "jjokpa_autumn.json").read_text(encoding="utf-8"))
    cells = {s["order"]: s.get("drought_rules") for s in unit["stages"]}
    assert cells[3] == VALUE and cells[4] == VALUE and cells.get(2) is None                # 두 칸에 · 다른 칸엔 없다
    assert "무강수 7일 · 검사용 출처 2026" in (clone / "docs" / "grid_jjokpa_autumn.md").read_text(encoding="utf-8")
    assert sorted(r["changed"]) == ["M data/grid/jjokpa_autumn.json", "M docs/grid_jjokpa_autumn.md"]      # 격자와 문서, 그 둘뿐
    assert r["residual_here"] and all("test_with_the_real_grid" in f for f in r["residual_here"])   # 임계가 서면 상태 검사 하나가 새 상태를 말한다
    rep = ag.report(r)
    assert "넣었다" in rep and "남은 것 1" in rep and "커밋은 이 명령이 하지 않는다" in rep
    log = subprocess.run(["git", "log", "--oneline", "-1"], cwd=clone, capture_output=True, text=True).stdout
    assert log == head                                                                    # 커밋하지 않았다
    assert not (ROOT / "data" / "grid" / "jjokpa_autumn.json").read_text(encoding="utf-8").count("검사용 출처")   # 본체는 그대로


def test_a_wrong_shape_is_refused_and_nothing_changes(clone, monkeypatch):
    monkeypatch.setattr(pw, "walk", lambda *a, **k: _pre([]))
    grid = clone / "data" / "grid" / "jjokpa_autumn.json"
    before = grid.read_bytes()
    r = ag.apply("jjokpa_autumn", [3], "drought_rules", {"dry_days": "일곱", "source": "x"}, tests=[], root=clone)
    assert not r["applied"] and "형태 검증 실패" in r["why"] and "정수" in r["why"] and grid.read_bytes() == before


def test_it_refuses_a_grid_outside_data_grid_and_a_missing_cell(clone, monkeypatch):
    with pytest.raises(ValueError):
        ag.apply("../subjects", [3], "drought_rules", VALUE, tests=[], root=clone)
    monkeypatch.setattr(pw, "walk", lambda *a, **k: _pre([]))
    with pytest.raises(ValueError):
        ag.apply("jjokpa_autumn", [99], "drought_rules", VALUE, tests=[], root=clone)     # 없는 칸을 만들지 않는다


def test_the_cli_reads_the_value_from_a_file_only_and_never_commits():
    src = (ROOT / "scripts" / "apply_grid_value.py").read_text(encoding="utf-8")
    assert "--value-file" in src and "json.loads(Path(a.value_file)" in src
    body = src[src.index("def apply("):]
    body = body[:body.index("\ndef ", 10)]
    assert '"commit"' not in body and "git\", \"add" not in body                          # 커밋·스테이징은 사람 몫
    assert "pw.walk(" in body and "schema.validate(unit)" in body and "pw.DOC_BUILDER" in body   # 세 줄이 한 자리에
