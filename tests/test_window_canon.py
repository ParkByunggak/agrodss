# -*- coding: utf-8 -*-
# [§7.5 처방 직후 전수 2026-09-21] 경계일 촬영을 고친 그 자리에서 **같은 형태**를 코드 전체에서 셌다.
#
# 격자 창은 양끝 포함이라 경계일(10 · 30 · 50 · 70일)은 **두 칸에 걸린다**. 어느 칸이 맞는지는 격자 지식이고(검토지 ⓓ B4),
# 답이 오기 전까지의 약속은 `grid.capture` 하나에 있다 — *"경계일은 **앞 칸**(첫 매치)"*. 그 주석은 이렇게까지 적어 두었다:
#
#     "판정기마다 따로 창을 비교하면 그 약속이 갈린다"
#
# 그런데 **세 번 갈렸다**: `stage_for_day` 와 `risk_alert` (전례 · 이미 정본으로 왔다), 그리고 이번 촬영 대조.
# 경고가 주석으로 두 번 적혀 있었는데도 세 번째가 났다 — **경고는 장치가 아니다.** 그래서 형태로 고정한다.
#
# 전수 결과(2026-09-21, 이 커밋 시점): 날짜로 칸을 **고르는** 자리는 정본을 쓰거나(`risk_alert._stages_in_scope`)
# 결정 id 로 고른다(`harvest_timing._harvest_stage` · `stage_decisions._stage`). 나머지 `from_day`/`to_day` 사용은
# **특정 칸의 창을 날짜로 바꾸는 읽기**라 약속과 무관하다 — 그 둘을 섞어 세면 잡음이 신호를 덮는다(급을 가른다).
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path("/home/user/agrodss") if Path("/home/user/agrodss").exists() else Path(__file__).resolve().parent.parent
CANON = ROOT / "grid" / "capture.py"
SKIP_DIRS = {"tests", "venv", ".git", "__pycache__", "scripts", "docs"}


def _subscript_keys(node: ast.AST) -> set[str]:
    """그 식 안에서 읽는 문자열 첨자 전부 — `w["from_day"]` 의 'from_day'."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
            out.add(n.slice.value)
    return out


def _membership_tests(path: Path) -> list[int]:
    """창 **양끝을 함께** 보면서 **바깥 값(날짜)을 끼워 넣는** 비교 = '오늘이 이 칸 안인가'.
    그 판단은 정본 하나에만 있어야 한다.

    급을 가른다(§7.5 — 같은 형태라고 같은 급이 아니다). 첫 판은 두 열쇠가 한 식에 있으면 다 걸었고, 그래서
    `grid/schema.py` 의 `w["from_day"] > w["to_day"]` 가 잡혔다 — 그것은 **창 자체가 말이 되는가**를 보는 스키마
    검증이지 칸을 고르는 것이 아니다. 두 끝을 **서로** 견주는 것은 약속과 무관하고, 거기에 **제3의 값**이 끼면
    비로소 '어느 칸인가'가 된다. 한쪽만 보는 것(`day > w["to_day"]` — 창을 넘겼는가)도 고르는 것이 아니라 제외한다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        # **비교 노드만** 본다. 첫 판은 BoolOp 의 비교 아닌 가지(`not isinstance(...)`)까지 부품으로 세어
        # 스키마 검증 줄을 또 걸었다 — 도구가 아니라 도구의 범위가 문제였다(자기 도구 오류 계열).
        cmps = ([node] if isinstance(node, ast.Compare)
                else [v for v in node.values if isinstance(v, ast.Compare)] if isinstance(node, ast.BoolOp) else [])
        if not cmps:
            continue
        keys = set().union(*(_subscript_keys(c) for c in cmps))
        if not {"from_day", "to_day"} <= keys:
            continue
        parts = [p for c in cmps for p in (c.left, *c.comparators)]
        if any(not _subscript_keys(p) for p in parts):                # 두 끝 말고 **끼어든 값**(날짜)이 있는가
            bad.append(node.lineno)
    return bad


def test_only_the_canon_decides_whether_a_day_is_inside_a_stage_window():
    """약속을 지키는 자리는 하나다 — 여기 걸리면 `grid.capture.is_open` / `stage_for_day` 를 쓰라는 뜻이다."""
    offenders = []
    for p in sorted(ROOT.rglob("*.py")):
        if any(s in p.parts for s in SKIP_DIRS) or p == CANON:
            continue
        for ln in _membership_tests(p):
            offenders.append(f"{p.relative_to(ROOT)}:{ln}")
    assert not offenders, ("창 양끝을 직접 비교하는 자리가 생겼다 — 경계일 약속이 갈린다. "
                          f"`grid.capture.is_open`(열림) · `stage_for_day`(오늘 칸 하나)를 쓴다: {offenders}")


def test_the_canon_itself_still_holds_the_promise():
    """[게이트는 양방향] 정본이 사라지거나 약속이 바뀌면 위 검사는 **아무것도 지키지 않는 상태**가 된다."""
    src = CANON.read_text(encoding="utf-8")
    assert _membership_tests(CANON), "정본이 창 비교를 더는 하지 않는다 — 약속이 어디로 갔는가"
    assert "def is_open" in src and "def stage_for_day" in src
    from grid import capture as gc
    w = {"from_day": 10, "to_day": 30}
    assert gc.is_open(w, 10) and gc.is_open(w, 30) and not gc.is_open(w, 9) and not gc.is_open(w, 31)   # 양끝 포함
    unit = {"stages": [{"order": 1, "window": {"from_day": 0, "to_day": 10}},
                       {"order": 2, "window": {"from_day": 10, "to_day": 30}}]}
    assert [s["order"] for s in gc.stages_open(unit, 10)] == [1, 2]              # 경계일은 둘 다 열려 있고
    assert gc.stage_for_day(unit, 10)["order"] == 1                              # 오늘 칸은 **앞 칸**이다


def test_the_capture_matching_goes_through_the_promise_not_its_own_comparison():
    """이번에 고친 그 자리 — 촬영 대조가 다시 제 창을 비교하면 여기서 깨진다(배선 래칫)."""
    src = (ROOT / "judge" / "plan_vs_actual.py").read_text(encoding="utf-8")
    body = src[src.index("def judge("):]
    body = body[:body.index("\n    inputs = [AxisUse(")]
    # [주입이 드러낸 허점 2026-09-21] 첫 판은 `"used_media" in body` 만 봤다 — **거르는 줄에서만** 빼는 주입(N2)은
    # 선언과 `.add(` 가 남아 있어 그대로 통과했다. 낱말이 아니라 **거르는 그 조건**을 본다(있음을 세는 검사는 뚫린다).
    assert "v.get(\"id\") not in used_media" in body, "사진 한 장이 여러 칸에 붙는 상태로 돌아갔다(거르는 조건이 없다)"
    i_add, i_hit = body.index("used_media.add("), body.index("hit = [v for v in videos")
    assert i_hit < i_add, "쓴 사진을 표시하기 전에 골라야 한다"
    assert "from_day" not in body and "to_day" not in body, "계획 대 실제가 창 양끝을 다시 직접 보고 있다"
