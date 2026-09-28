# -*- coding: utf-8 -*-
# FILE: scripts/prewalk_grid.py
# ROLE: [미리 걷기 도구 · 2026-09-27] 격자 한 칸에 값을 넣는 **발행자의 커밋**을 격리 워크트리에서 미리 해 보고 무엇이 깨지는지 센다.
#
#   전례 둘: d933afe — "격자 한 수정으로 끝난다" 고 적힌 답 넷을 실제로 넣어 보니 최대 6파일이 깨졌다.
#            25b9290 — D-18 규칙을 넣어 보니 상태 검사 다섯 · 형태 검사 0 · 문서 미반영. 그 걷기 스크립트가 스크래치패드에만 있었다(U-35 와 같은 형태 —
#            세션이 끝나면 사라진다). 여기 두어 다음 사람이 어느 격자 수정이든 같은 길로 미리 걷는다.
#
#   하는 일   ① git worktree(HEAD) 를 tmp 에 만들고 ② 작업 트리의 미커밋 수정을 얹고(없으면 그대로) ③ 격자 칸에 값을 넣고 ④ 검사를 돌리고
#            ⑤ 격자 문서를 재생성한 뒤 다시 돌려 **잔여**를 센다 ⑥ 워크트리를 지운다. 저장소 본체에는 아무것도 쓰지 않는다.
#   쓰는 법   python -m scripts.prewalk_grid jjokpa_autumn --stage 3 --key symptom_rules --value-file rules.json
#            python -m scripts.prewalk_grid jjokpa_autumn --stage 3 4 --key drought_rules --value-file rules.json --tests tests/test_grid.py tests/test_drought_slot.py
#            (--stage 는 여럿 가능 — 오늘 칸만 읽는 결정(가뭄)은 다른 칸에 넣으면 잔여 0 이라, 발행자가 두 칸에 넣는 커밋은 두 칸을 한 번에 건다)
#            (--tests 를 안 주면 전체 관문 — 약 10분. TZ 는 관문 규율대로 Asia/Seoul 로 고정한다)
#   규율     읽기 전용 측정 도구 — 격자 파일명은 data/grid 안의 것만 받고, 값은 JSON 파일에서만 받는다(셸에 긴 문면을 통과시키지 않는다 · HEREDOC-1).
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GRID_DIR = ROOT / "data" / "grid"
DOC_BUILDER = "scripts/build_grid_doc.py"
FAIL_RE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)


def set_in_unit(unit: dict[str, Any], stage_order: int, key: str, value: Any) -> dict[str, Any]:
    """칸(order)에 key=value 를 넣는다 — 그 칸이 없으면 ValueError(조용히 새 칸을 만들지 않는다)."""
    for s in unit.get("stages", []):
        if s.get("order") == stage_order:
            s[key] = value
            return unit
    raise ValueError(f"칸 {stage_order} 이 없다 — 있는 칸: {[s.get('order') for s in unit.get('stages', [])]}")


def parse_failures(pytest_output: str) -> list[str]:
    """pytest 출력에서 FAILED/ERROR 항목 id 만 — 마지막 요약 줄이 없어도(-q · 플러그인) 잡힌다."""
    seen: list[str] = []
    for m in FAIL_RE.findall(pytest_output):
        if m not in seen:
            seen.append(m)
    return seen


def _sh(cmd: list[str], cwd: Path) -> tuple[int, str]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "TZ": "Asia/Seoul", "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": os.environ.get("HOME", "/"), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode, r.stdout + r.stderr


def walk(grid_stem: str, stage_order: int | list[int], key: str, value: Any, tests: list[str] | None = None,
         root: Path = ROOT) -> dict[str, Any]:
    """격리 워크트리에서 미리 걷는다. 돌려주는 것: 넣기 전/문서 재생성 뒤 실패 목록 · 문서에 값이 실렸는지 · 워크트리 제거 여부.

    `stage_order` 는 칸 하나 또는 여럿 — [D-20 미리 걷기 2026-09-28] 오늘 칸만 읽는 결정은 다른 칸의 값을 넣어도 잔여 0 이라, 발행자가 칸 3·4 에
    같은 값을 넣는 커밋은 두 칸을 **한 번에** 걸어야 그 커밋의 잔여가 나온다.
    """
    orders = [stage_order] if isinstance(stage_order, int) else list(stage_order)
    target = (root / "data" / "grid" / f"{grid_stem}.json")
    if not target.exists() or target.parent != root / "data" / "grid":
        raise ValueError(f"data/grid 안의 격자만 받는다: {grid_stem}")
    wt = Path(tempfile.mkdtemp(prefix="agrodss_prewalk_"))
    wt.rmdir()                                   # git 이 만들게 한다(비어 있어야 한다)
    out: dict[str, Any] = {"worktree": str(wt), "grid": target.relative_to(root).as_posix(), "stage": "·".join(str(o) for o in orders), "key": key}
    rc, log = _sh(["git", "worktree", "add", "--detach", str(wt), "HEAD"], root)
    if rc != 0:
        raise RuntimeError(f"워크트리를 못 만들었다: {log}")
    try:
        rc, patch = _sh(["git", "diff", "HEAD"], root)
        out["uncommitted_applied"] = bool(patch.strip())
        if patch.strip():
            (wt / "_prewalk.patch").write_text(patch, encoding="utf-8")
            rc, log = _sh(["git", "apply", "_prewalk.patch"], wt)
            (wt / "_prewalk.patch").unlink()
            if rc != 0:
                raise RuntimeError(f"미커밋 수정을 못 얹었다: {log}")
        g = wt / target.relative_to(root)
        unit = json.loads(g.read_text(encoding="utf-8"))
        for o in orders:
            set_in_unit(unit, o, key, value)
        g.write_text(json.dumps(unit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        py = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "-q", "--no-header", *(tests or [])]
        rc, log = _sh(py, wt)
        out["failures_before_doc"] = parse_failures(log)
        rc, log = _sh([sys.executable, "-B", DOC_BUILDER], wt)
        out["doc_rebuilt"] = rc == 0
        doc = wt / "docs" / f"grid_{grid_stem}.md"
        out["doc_mentions_value"] = doc.exists() and _first_string(value) is not None and _first_string(value) in doc.read_text(encoding="utf-8")
        rerun = out["failures_before_doc"] or []
        if rerun:
            rc, log = _sh([*py[:7], *[f.split(" - ")[0] for f in rerun]], wt)
            out["failures_after_doc"] = parse_failures(log)
        else:
            out["failures_after_doc"] = []
    finally:
        rc, log = _sh(["git", "worktree", "remove", "--force", str(wt)], root)
        out["worktree_removed"] = rc == 0 and not wt.exists()
    return out


def _first_string(value: Any) -> str | None:
    """값 안의 첫 문자열 — 문서에 실렸는지 볼 표지(값 전체를 대조하지 않는다 · 형식은 생성기 몫)."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for v in value.values():
            s = _first_string(v)
            if s:
                return s
    if isinstance(value, list):
        for v in value:
            s = _first_string(v)
            if s:
                return s
    return None


def report(r: dict[str, Any]) -> str:
    lines = [f"미리 걷기 — {r['grid']} 칸 {r['stage']} · {r['key']}" + (" · 미커밋 수정 얹음" if r.get("uncommitted_applied") else ""),
             f"  넣고 돌린 검사 실패           {len(r['failures_before_doc'])}"]
    lines += [f"    {f}" for f in r["failures_before_doc"]]
    lines += [f"  격자 문서 재생성              {'됨' if r.get('doc_rebuilt') else '실패'} · 값이 문서에 {'실림' if r.get('doc_mentions_value') else '안 실림'}",
              f"  문서 재생성 뒤 잔여           {len(r['failures_after_doc'])}"]
    lines += [f"    {f}" for f in r["failures_after_doc"]]
    lines += [f"  워크트리                      {'제거됨' if r.get('worktree_removed') else '남아 있다 — ' + r['worktree']}",
              "잔여가 상태 검사 하나뿐이면 그 커밋은 「격자 수정 + 문서 재생성 + 상태 검사 하나」 다. 그 이상이면 처방이 먼저다."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="격자 한 칸 수정을 격리 워크트리에서 미리 걷는다(읽기 전용)")
    ap.add_argument("grid", help="격자 파일 이름(확장자 없이 · data/grid 안)")
    ap.add_argument("--stage", type=int, nargs="+", required=True, help="칸 번호 하나 또는 여럿(예: --stage 3 4 — 오늘 칸만 읽는 결정은 여럿을 한 번에)")
    ap.add_argument("--key", required=True)
    ap.add_argument("--value-file", required=True, help="넣을 값(JSON 파일) — 셸에 긴 문면을 통과시키지 않는다")
    ap.add_argument("--tests", nargs="*", default=None, help="돌릴 검사 파일들(없으면 전체 관문)")
    a = ap.parse_args(argv)
    value = json.loads(Path(a.value_file).read_text(encoding="utf-8"))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(report(walk(a.grid, a.stage, a.key, value, tests=a.tests)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
