# -*- coding: utf-8 -*-
# [미리 걷기 도구 2026-09-27] 격자 한 칸 수정을 격리 워크트리에서 미리 걷는 도구 — 25b9290 의 걷기 스크립트가 스크래치패드에만 있었다(U-35 형태).
# 본다: 칸에 값 넣기(없는 칸은 거부) · 실패 목록 파싱(요약 줄이 없어도) · 실제로 워크트리에서 돌려 잔여를 내고 본체에는 아무것도 안 쓴다.
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from scripts import prewalk_grid as pw

ROOT = Path(__file__).resolve().parent.parent


def test_set_in_unit_sets_only_an_existing_stage():
    unit = {"stages": [{"order": 1}, {"order": 3}]}
    assert pw.set_in_unit(unit, 3, "k", [1])["stages"][1] == {"order": 3, "k": [1]}
    with pytest.raises(ValueError, match="칸 2"):
        pw.set_in_unit(unit, 2, "k", [1])                                          # 없는 칸을 조용히 만들지 않는다


def test_the_cli_takes_several_stages_at_once_for_decisions_that_read_only_todays_cell():
    """[D-20 미리 걷기 2026-09-28] 칸 3 에만 임계를 넣은 걷기가 잔여 0 이었다 — 그 결정은 오늘 칸(4)을 읽는다. 발행자가 칸 3·4 에 넣는 커밋은
    두 칸을 한 번에 걸어야 그 커밋의 잔여가 나온다. 걷기 자체는 위 e2e 검사가 보고, 여기서는 인자와 표기만."""
    import argparse
    src = (ROOT / "scripts" / "prewalk_grid.py").read_text(encoding="utf-8")
    assert 'nargs="+"' in src.split('add_argument("--stage"')[1].split("\n")[0]       # --stage 3 4
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, nargs="+", required=True)
    assert ap.parse_args(["--stage", "3", "4"]).stage == [3, 4]
    rep = pw.report({"grid": "data/grid/x.json", "stage": "3·4", "key": "drought_rules", "failures_before_doc": [], "doc_rebuilt": True,
                     "doc_mentions_value": True, "failures_after_doc": [], "worktree_removed": True, "worktree": "-"})
    assert "칸 3·4" in rep
    body = src[src.index("def walk("):]
    body = body[:body.index("\ndef ", 10)]
    assert "for o in orders:" in body and "set_in_unit(unit, o, key, value)" in body   # 칸마다 넣는다 · int 하나도 그대로 받는다


def test_parse_failures_reads_ids_without_a_summary_line():
    out = "....F..\nFAILED tests/a.py::test_x - AssertionError: assert 1\nERROR tests/b.py::test_y\nFAILED tests/a.py::test_x - again\n"
    assert pw.parse_failures(out) == ["tests/a.py::test_x", "tests/b.py::test_y"]
    assert pw.parse_failures("....\n") == []


def test_first_string_finds_a_marker_inside_nested_values():
    assert pw._first_string([{"symptoms": ["노랗"], "causes": []}]) == "노랗"
    assert pw._first_string({"a": [], "b": {"c": "x"}}) == "x" and pw._first_string([]) is None


def test_it_refuses_a_grid_outside_data_grid(tmp_path):
    with pytest.raises(ValueError, match="data/grid"):
        pw.walk("../parcels_seed", 3, "k", [])
    with pytest.raises(ValueError):
        pw.walk("no_such_grid", 3, "k", [])


def _tree_hash(paths):
    h = hashlib.sha1()
    for p in sorted(paths):
        h.update(p.read_bytes())
    return h.hexdigest()


def test_walk_runs_in_a_worktree_reports_residual_and_writes_nothing_here():
    """실제로 걷는다(좁은 검사 둘 · 수 초). D-18 형식 규칙을 칸 3 에 넣으면: 문서 동기 검사가 붉고 → 문서 재생성 뒤 상태 검사 하나만 남는다(25b9290 실측과 같아야 한다).
    본체의 격자·문서는 바이트 그대로이고 워크트리는 지워진다."""
    from tests.test_symptom_triage import RULES
    watched = [ROOT / "data" / "grid" / "jjokpa_autumn.json", ROOT / "docs" / "grid_jjokpa_autumn.md"]
    before = _tree_hash(watched)
    r = pw.walk("jjokpa_autumn", 3, "symptom_rules", RULES, tests=["tests/test_grid.py", "tests/test_symptom_triage.py"])
    assert _tree_hash(watched) == before                                             # 본체에 아무것도 안 썼다
    assert r["worktree_removed"] and not Path(r["worktree"]).exists()
    assert r["doc_rebuilt"] and r["doc_mentions_value"]
    assert any(f.endswith("::test_doc_in_sync") for f in r["failures_before_doc"])   # 넣기만 하면 문서 동기가 붉다
    assert not any(f.endswith("::test_doc_in_sync") for f in r["failures_after_doc"])   # 재생성하면 사라진다
    assert all("test_with_the_real_grid" in f for f in r["failures_after_doc"]) and len(r["failures_after_doc"]) == 1   # 잔여 = 상태 검사 하나
    rep = pw.report(r)
    assert "잔여" in rep and "제거됨" in rep and "상태 검사 하나" in rep
    wl = subprocess.run(["git", "worktree", "list"], cwd=ROOT, capture_output=True, text=True).stdout
    assert "agrodss_prewalk_" not in wl                                               # git 쪽에도 안 남는다


def test_the_tool_never_writes_into_the_repo_root():
    src = (ROOT / "scripts" / "prewalk_grid.py").read_text(encoding="utf-8")
    body = src[src.index("def walk("):]
    body = body[:body.index("\ndef ", 10)]
    assert "git" in body and "worktree" in body and '"remove"' in body and "finally:" in body   # 워크트리 안에서만 · 반드시 지운다
    assert "overlay_uncommitted(root, wt)" in body                                           # 미커밋 상태를 얹는 자리는 하나(diff + 새 파일)
    writes = [ln for ln in body.splitlines() if "write_text(" in ln]
    assert writes and all("wt /" in ln or "g.write_text" in ln for ln in writes), writes  # 쓰는 곳은 워크트리 경로뿐
    ov = src[src.index("def overlay_uncommitted("):]
    ov = ov[:ov.index("\ndef ", 10)]
    writes = [ln for ln in ov.splitlines() if "write_text(" in ln or "write_bytes(" in ln]
    assert writes and all("wt /" in ln or "dst.write_bytes" in ln for ln in writes) and "dst = " in ov and "wt / rel" in ov, writes


def test_overlay_copies_untracked_new_files_not_only_tracked_diffs(tmp_path):
    """[자기 도구 오류 2026-09-28] `git diff HEAD` 만 얹으면 추적 안 된 새 모듈이 빠져, 그것을 import 하는 추적 파일 때문에 워크트리의 검사가
    수집 단계에서 전부 죽고 걷기가 '잔여 0' 을 말했다. 새 파일도 얹는다 — gitignore 된 것은 빼고."""
    root = tmp_path / "repo"
    root.mkdir()

    def git(*a, cwd=root):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "a.py")
    git("commit", "-qm", "init")
    (root / "a.py").write_text("from b import y\n", encoding="utf-8")            # 추적 파일 수정(diff)
    (root / "pkg").mkdir()
    (root / "pkg" / "b.py").write_text("y = 2\n", encoding="utf-8")               # 추적 안 된 새 모듈(하위 디렉터리)
    (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (root / "ignored.txt").write_text("no\n", encoding="utf-8")                  # gitignore — 얹지 않는다
    wt = tmp_path / "wt"
    git("worktree", "add", "--detach", str(wt), "HEAD")
    try:
        r = pw.overlay_uncommitted(root, wt)
        assert (wt / "a.py").read_text(encoding="utf-8") == "from b import y\n"
        assert (wt / "pkg" / "b.py").read_text(encoding="utf-8") == "y = 2\n" and not (wt / "ignored.txt").exists()
        assert r["uncommitted_applied"] and set(r["untracked_copied"]) == {".gitignore", "pkg/b.py"}
        assert (root / "a.py").read_text(encoding="utf-8") == "from b import y\n"   # 본체는 그대로
        git("add", "-A")
        git("commit", "-qm", "all")                                                   # 전부 커밋하면 얹을 것이 없다
        assert pw.overlay_uncommitted(root, wt) == {"uncommitted_applied": False, "untracked_copied": []}   # 없으면 없다
        empty = tmp_path / "empty"
        empty.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=empty, check=True)
        with pytest.raises(RuntimeError, match="git diff HEAD"):                     # 커밋 없는 저장소 — 오류 문장을 패치로 오독하지 않는다
            pw.overlay_uncommitted(empty, wt)
    finally:
        git("worktree", "remove", "--force", str(wt))
