# -*- coding: utf-8 -*-
# FILE: scripts/apply_grid_value.py
# ROLE: [검토표 ② 2026-09-29 · 발행자 승인 "제안 순서대로"] 격자 값이 오면 세 줄(미리 걷기 → 격자 → 문서 재생성 → 검사)을 **한 명령**으로.
#
#   왜      D-18 규칙 · D-20 임계처럼 발행자가 값과 출처를 한 줄로 주면, 세션이 그 세 줄을 손으로 돌렸다(핸드오버 §5 ② · ⑤).
#           한 줄이 빠지면(문서 재생성) "정본이 있는데 문서가 안 싣는" G1 형태가 된다 — 2026-09-27 D-18 미리 걷기가 그것을 잡았다.
#   하는 일  ① prewalk_grid 로 격리 워크트리에서 미리 걷는다(전체 관문 또는 --tests) ② 잔여가 상태 검사 하나 이하일 때만 본체 격자에 넣는다
#           ③ 형태 검증(grid.schema) — 틀리면 되돌리고 이유 ④ 격자 문서 재생성 ⑤ 잔여 검사를 본체에서 다시 돌려 **무엇이 남았는지** 보고
#           ⑥ 커밋은 하지 않는다 — 남은 상태 검사의 기대를 새 상태로 고치는 것과 커밋은 사람(세션) 몫이다(값은 지식이라 코드가 정하지 않는다).
#   쓰는 법  python -m scripts.apply_grid_value jjokpa_autumn --stage 3 4 --key drought_rules --value-file v.json [--tests …] [--dry-run]
#   규율     격자는 data/grid 안의 것만 · 값은 JSON 파일에서만(HEREDOC-1) · 잔여가 둘 이상이면 아무것도 쓰지 않는다(처방이 먼저다)
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from grid import schema  # noqa: E402
from scripts import prewalk_grid as pw  # noqa: E402

MAX_RESIDUAL = 1        # 「격자 수정 + 문서 재생성 + 상태 검사 하나」 — 그 이상이면 처방이 먼저다(prewalk 보고문의 그 규칙)


def decide(pre: dict[str, Any], max_residual: int = MAX_RESIDUAL) -> tuple[bool, str]:
    """미리 걷기 결과로 넣을지 정한다 — 잔여가 상한 이하이고 문서가 재생성됐을 때만."""
    if not pre.get("doc_rebuilt"):
        return False, "미리 걷기에서 격자 문서 재생성이 실패했다 — 값의 형태가 문서 생성기와 안 맞는다"
    res = pre.get("failures_after_doc") or []
    if len(res) > max_residual:
        return False, f"미리 걷기 잔여 {len(res)}(상한 {max_residual}) — 처방이 먼저다: " + " · ".join(res)
    return True, ""


def apply(grid_stem: str, orders: list[int], key: str, value: Any, tests: list[str] | None = None,
          root: Path = ROOT, dry_run: bool = False) -> dict[str, Any]:
    target = root / "data" / "grid" / f"{grid_stem}.json"
    if not target.exists() or target.parent != root / "data" / "grid":
        raise ValueError(f"data/grid 안의 격자만 받는다: {grid_stem}")
    out: dict[str, Any] = {"grid": target.relative_to(root).as_posix(), "stage": "·".join(str(o) for o in orders), "key": key, "applied": False}
    pre = pw.walk(grid_stem, orders, key, value, tests=tests, root=root)
    out["prewalk"] = pre
    go, why = decide(pre)
    out["why"] = why
    if not go or dry_run:
        out["why"] = why or "dry-run — 미리 걷기만 했다"
        return out
    before = target.read_text(encoding="utf-8")
    unit = json.loads(before)
    for o in orders:
        pw.set_in_unit(unit, o, key, value)
    rep = schema.validate(unit)
    if not rep.ok:
        out["why"] = "형태 검증 실패 — 격자에 쓰지 않았다: " + " · ".join(rep.errors)
        return out
    target.write_text(json.dumps(unit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rc, log = pw._sh([sys.executable, "-B", pw.DOC_BUILDER], root)
    if rc != 0:
        target.write_text(before, encoding="utf-8")                          # 문서를 못 만들면 격자도 되돌린다 — 반쪽 커밋을 남기지 않는다
        tail = log.strip().splitlines()[-1] if log.strip() else ""
        out["why"] = f"격자 문서 재생성 실패 — 격자를 되돌렸다: {tail}"
        return out
    out["applied"] = True
    doc = root / "docs" / f"grid_{grid_stem}.md"
    marker = pw._first_string(value)
    out["doc_mentions_value"] = doc.exists() and marker is not None and marker in doc.read_text(encoding="utf-8")
    residual = pre.get("failures_after_doc") or []
    if residual:
        py = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "-q", "--no-header", *[f.split(" - ")[0] for f in residual]]
        rc, log = pw._sh(py, root)
        out["residual_here"] = pw.parse_failures(log)
    else:
        out["residual_here"] = []
    rc, log = pw._sh(["git", "status", "--short", "--", "data/grid", "docs"], root)
    out["changed"] = [ln.strip() for ln in log.splitlines() if ln.strip()]
    return out


def report(r: dict[str, Any]) -> str:
    lines = [pw.report(r["prewalk"]), ""]
    if not r["applied"]:
        lines.append(f"넣지 않았다 — {r['why']}")
        return "\n".join(lines)
    lines += [f"넣었다 — {r['grid']} 칸 {r['stage']} · {r['key']} · 격자 문서 재생성됨 · 값이 문서에 {'실림' if r.get('doc_mentions_value') else '안 실림'}",
              "  바뀐 파일:"] + [f"    {c}" for c in r.get("changed", [])]
    res = r.get("residual_here") or []
    if res:
        lines += [f"  남은 것 {len(res)} — 이 검사의 기대를 새 상태로 고친 뒤 커밋한다(값은 사람이 정한 지식이라 검사도 사람이 고친다):"] + [f"    {f}" for f in res]
    else:
        lines.append("  남은 것 0 — 바로 커밋한다")
    lines.append("커밋은 이 명령이 하지 않는다. 격자·문서·상태 검사를 한 커밋으로.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="격자 값을 한 명령으로 — 미리 걷기 → 격자 → 문서 → 검사 → 잔여 보고(커밋은 사람)")
    ap.add_argument("grid", help="격자 파일 이름(확장자 없이 · data/grid 안)")
    ap.add_argument("--stage", type=int, nargs="+", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--value-file", required=True, help="넣을 값(JSON 파일) — 셸에 긴 문면을 통과시키지 않는다")
    ap.add_argument("--tests", nargs="*", default=None, help="미리 걷기에서 돌릴 검사(없으면 전체 관문 · 약 10분)")
    ap.add_argument("--dry-run", action="store_true", help="미리 걷기만 하고 넣지 않는다")
    a = ap.parse_args(argv)
    value = json.loads(Path(a.value_file).read_text(encoding="utf-8"))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    r = apply(a.grid, a.stage, a.key, value, tests=a.tests, dry_run=a.dry_run)
    print(report(r))
    return 0 if r["applied"] or a.dry_run else 1


if __name__ == "__main__":
    sys.exit(main())
