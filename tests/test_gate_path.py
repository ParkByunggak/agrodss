# -*- coding: utf-8 -*-
# [자기 도구 축 2026-10-06] 세션의 관문 명령이 **자기가 요구하는 수치를 못 내고 있었다**.
#   명령   python -B -m pytest -p no:cacheprovider **-q**        ← `pytest.ini` 에 이미 `addopts = -q` 가 있어 **-qq**
#   규율   CLAUDE.md 완료 보고 「관문 N passed · 직전 대비 증분 = 신규 검사 수」
# -qq 는 집계 줄을 **아예 안 찍는다**. 그래서 그 숫자는 손으로 점을 세어 메워졌고, 한 번은 **영원히 안 오는 줄**을 기다리는 폴링 루프가 20분을 썼다.
# 실측(2026-10-06 · 저장소 안 = ini 가 적용되는 곳):
#       -qq 통과   집계 줄 없음 · rc 0            -qq 실패   집계 줄 없음 · FAILED 있음 · rc 1
#       -qq 오류   집계 줄 없음 · ERROR 있음 · rc 2(failed 는 0)      -q(ini만)  집계 줄 있음
# 안전 신호(rc · FAILED/ERROR)는 -qq 에서도 산다 — 죽는 것은 **셈**뿐이다. R-1(집계 줄 부재)의 다섯 번째 판이다.
#
# 이 검사가 고정하는 것 여섯:
#   ① 집계 줄이 있으면 그것을 읽고, 없으면 **추정이라고 말한다**(조용히 0 을 돌려주지 않는다 — 0 은 「통과 0」 과 구별이 안 된다)
#   ② 수집 오류는 `failed` 0 · `error` 1 로 **갈라 센다**(§7.1 0번 — `failed` 만 읽으면 초록으로 오독한다)
#   ③ 초록의 조건은 셋(rc 0 · 실패·오류 0 · **집계 줄 있었음**) — 양방향으로 본다
#   ④ 증분은 **전체 관문에서만** 말한다(부분 스코프의 수를 직전과 견주면 거짓 회귀를 쫓는다)
#   ⑤ 직전 수는 **대장 페이지 정본에서** 읽는다(손으로 박으면 회차마다 어긋난다)
#   ⑥ 경로가 그 명령을 쥔다 — `-q` 를 더하지 않고 · TZ 를 세우고 · 셈을 세고 · rc 를 보존한다(파이프에 삼키지 않는다 · R-8)
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import gate_count as gc

ROOT = Path(gc.__file__).resolve().parent.parent
GATE_SH = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")

PASS_FULL = ".....\t\t[100%]\n1805 passed in 512.33s\n"
PASS_QQ = "........ [ 50%]\n........ [100%]\n"                       # -qq — 집계 줄이 없다
FAILED_ONE = "FAILED tests/x.py::test_a - assert 1 == 2\n1 failed, 1804 passed in 500.0s\n"
COLLECT_ERR = "ERROR tests/x.py - RuntimeError: 죽는다\n!!!! Interrupted: 1 error during collection !!!!\n1 error in 0.17s\n"
KILLED = "........ [ 50%]\n....\n"                                   # 중간에 죽은 출력 — 집계 줄도 [100%] 도 없다


def test_the_summary_line_is_read_when_it_is_there():
    c = gc.parse(PASS_FULL)
    assert (c["passed"], c["failed"], c["error"], c["counted"]) == (1805, 0, 0, True)
    c = gc.parse(FAILED_ONE)
    assert (c["passed"], c["failed"], c["counted"]) == (1804, 1, True)


def test_without_the_summary_line_it_says_the_count_is_an_estimate():
    """[①] -qq 거나 죽은 출력 — 센 수를 내되 **추정이라고 말한다**. 그 사실을 안 말하면 손으로 센 수가 보고로 그냥 나간다."""
    c = gc.parse(PASS_QQ)
    assert c["counted"] is False and c["passed"] == 16 and c["marks"] == 16      # 괄호·퍼센트는 세지 않는다(첫 판이 13 을 냈다)
    line, ok = gc.report(PASS_QQ, 0)
    assert "집계 줄 없음" in line and ok is False                                 # rc 0 이어도 초록이 아니다
    assert gc.parse(KILLED)["passed"] == 8 and gc.parse(KILLED)["counted"] is False


def test_a_collection_error_is_counted_apart_from_failures():
    """[②] 모듈 단언·SyntaxError 는 `failed` 0 으로 뜬다 — 그래서 `error` 를 따로 센다.

    [주입 B 2026-10-06] 복수형(`2 errors`)을 세는 가드에 **아무 검사도 닿지 않았다**(단수만 고정해 둬서 지워도 안 터졌다 — §7.1 3번).
    pytest 는 둘 이상이면 복수로 찍으므로, 그 자리가 바로 수집 오류가 여럿일 때다."""
    c = gc.parse(COLLECT_ERR)
    assert (c["failed"], c["error"], c["counted"]) == (0, 1, True)
    line, ok = gc.report(COLLECT_ERR, 2)
    assert ok is False and "1 error" in line
    plural = gc.parse("ERROR a.py\nERROR b.py\n2 errors in 0.3s\n")
    assert (plural["error"], plural["failed"], plural["counted"]) == (2, 0, True), plural
    assert gc.report("2 errors in 0.3s\n", 2)[1] is False
    mixed = gc.parse("= 1 failed, 1803 passed, 3 errors in 500.0s =")
    assert (mixed["failed"], mixed["passed"], mixed["error"]) == (1, 1803, 3), mixed


def test_green_needs_all_three_and_nothing_less():
    """[③ 양방향] 막는 것만 보면 「열어놓고 깨진」 상태를 못 본다 — 통과 쪽도 본다."""
    assert gc.report(PASS_FULL, 0)[1] is True                       # 셋 다 맞으면 초록
    assert gc.report(PASS_FULL, 1)[1] is False                      # rc 가 아니라고 하면 초록이 아니다(출력이 초록이어도)
    assert gc.report(FAILED_ONE, 1)[1] is False
    assert gc.report(COLLECT_ERR, 2)[1] is False
    assert gc.report(PASS_QQ, 0)[1] is False                        # 셈 추정으로는 초록을 말하지 않는다
    line, _ = gc.report("ERROR tests/x.py - boom\n12 passed in 1s\n", 0)
    assert "셈에는 없다" in line                                      # FAILED/ERROR 줄이 있는데 셈이 0 이면 그 어긋남을 말한다


def test_only_the_whole_gate_talks_about_the_increment():
    """[④] 부분 스코프에 증분을 붙이면 「−1800」 이 보고로 나가고, 더 나쁘게는 그 수로 회귀를 찾는다."""
    whole, _ = gc.report(PASS_FULL, 0, last=1800)
    part, _ = gc.report(PASS_FULL, 0, last=1800, full=False)
    assert "증분 +5" in whole and "부분 스코프" not in whole
    assert "직전" not in part and "전체 관문이 아니다" in part        # 「증분 대조 대상 아님」 이라는 말에 '증분' 이 들어 있다 — 수가 붙는 자리로 본다(§7.1 4번)


def test_the_previous_number_comes_from_the_ledger_page_canon(tmp_path, monkeypatch):
    """[⑤] 발행자가 읽는 그 숫자와 한 자리 — 검사도 손으로 박지 않고 정본에서 읽어 대조한다.

    그리고 **정본을 움직여** 따라오는지 본다: 오늘 맞는 수를 박아 두면 그 검사는 공허하다(앞 회차 주입 D 가 그 형태였다 — 값이 같아 통과했다)."""
    from scripts import build_ledger_page as blp
    m = re.search(r"^\s*(\d+)\s*→\s*(\d+)", blp.BEST["gate"])
    assert m, blp.BEST["gate"]
    assert gc.last_gate() == int(m.group(2))
    assert gc.last_gate() > 1000                                    # 자리를 잘못 잡으면(시작 수 1277 를 읽으면) 증분이 늘 +500 대가 된다
    fake = tmp_path / "scripts"
    fake.mkdir()
    (fake / "build_ledger_page.py").write_text('BEST = {"gate": "1277 → 4242 · 주입 1/1"}\n', encoding="utf-8")
    monkeypatch.setattr(gc, "ROOT", tmp_path)
    assert gc.last_gate() == 4242, "정본을 움직였는데 안 따라온다 — 수를 읽는 것이 아니라 박아 둔 것이다"


def test_the_path_holds_the_command():
    """[⑥] 명령을 문서에 적어 두면 세 번째에 또 난다 — 경로가 쥔다(HEREDOC-1 과 같은 길)."""
    body = GATE_SH
    assert "pytest.ini" in body and "-qq" in body                                # 왜 -q 를 안 더하는지 그 자리에 적혀 있다
    cmd = next(l for l in body.splitlines() if "-m pytest" in l and not l.lstrip().startswith("#"))
    assert "-q" not in cmd.replace("no:cacheprovider", ""), cmd                  # ini 의 -q 하나로 집계 줄이 남는다
    assert "> \"$OUT\" 2>&1" in cmd and "rc=$?" in body                          # 파이프에 rc 를 삼키지 않는다(R-8)
    assert re.search(r'export TZ="\$\{TZ:-Asia/Seoul\}"', body) and "NODE_PATH" in body   # 잊을 자리를 없앤다(시각 결함은 TZ 없이 재현되지 않는다)
    assert "python -m scripts.gate_count" in body and "--partial" in body
    assert "소스를 고치지 않는다" in body


def test_the_path_runs_and_judges(tmp_path):
    """살아 있는지 — 통과 하나와 실패 하나를 실제로 돌려 rc 를 본다(검사의 검사)."""
    probe = ROOT / "probe_gate_tmp"
    probe.mkdir(exist_ok=True)
    try:
        (probe / "test_ok.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
        env = {"PATH": "/usr/bin:/bin", "GATE_OUT": str(tmp_path / "ok.txt"), "HOME": str(tmp_path)}
        r = subprocess.run(["bash", str(ROOT / "scripts" / "gate.sh"), "probe_gate_tmp/test_ok.py"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "1 passed" in r.stdout and "부분 스코프" in r.stdout
        (probe / "test_ok.py").write_text("def test_ok():\n    assert 1 == 2\n", encoding="utf-8")
        env["GATE_OUT"] = str(tmp_path / "bad.txt")
        r = subprocess.run(["bash", str(ROOT / "scripts" / "gate.sh"), "probe_gate_tmp/test_ok.py"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        assert r.returncode == 1 and "초록이 아니다" in r.stdout and "1 failed" in r.stdout
        # rc 는 **조용한 실패**에서도 산다 — 출력에 실패 줄이 하나도 없는 꼴(인자 오류 · 죽은 실행)이 그 자리다(파이프가 rc 를 삼키면 여기서 0 이 된다 · R-8)
        env["GATE_OUT"] = str(tmp_path / "usage.txt")
        r = subprocess.run(["bash", str(ROOT / "scripts" / "gate.sh"), "--그런-인자-없다"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        assert r.returncode == 1 and "0 failed" in r.stdout, r.stdout
    finally:
        for p in probe.glob("*"):
            p.unlink()
        probe.rmdir()


def test_the_other_pytest_callers_are_accounted_for():
    """**안 하기로 한 것**과 **빠뜨린 것**을 가른다 — `-q` 를 더하는 자리가 또 있는데, 그쪽은 셈을 안 내고 rc·FAILED 줄만 본다(그 사유를 여기 적어 둔다)."""
    known = {
        "scripts/finish_round.sh": "문서 검사 — 셈을 보고하지 않고 rc 로만 판정한다(R-8). 집계 줄이 없어도 판정이 안 흔들린다",
        "scripts/prewalk_grid.py": "미리 걷기 — FAILED/ERROR 줄을 파싱한다(그 줄은 -qq 에서도 찍힌다 · 2026-10-06 실측)",
        "scripts/apply_grid_value.py": "잔여 재실행 — 같은 파서를 쓴다",
    }
    adds_q = []
    for p in sorted((ROOT / "scripts").glob("*")):
        if p.suffix not in (".py", ".sh") or p.name in ("gate.sh", "gate_count.py"):
            continue
        src = p.read_text(encoding="utf-8")
        for line in src.splitlines():
            if "pytest" in line and re.search(r'["\s]-q["\s]|"-q"', line) and not line.lstrip().startswith("#"):
                adds_q.append(p.relative_to(ROOT).as_posix())
                break
    assert set(adds_q) == set(known), (sorted(adds_q), sorted(known))     # 새 자리가 생기면 셈을 내는지 묻게 된다
    for rel, why in known.items():
        assert "pytest" in (ROOT / rel).read_text(encoding="utf-8"), (rel, why)


def test_the_completion_rule_points_at_the_path():
    """규율과 도구가 어긋나 있던 것이 이 묶음의 결함이다 — 완료 보고 규율이 그 경로를 이름으로 가리킨다(다음 사람이 손으로 점을 세지 않게)."""
    md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "scripts/gate.sh" in md
    i = md.index("## 완료 보고")
    assert "scripts/gate.sh" in md[i:i + 1200], "완료 보고 칸에서 가리켜야 한다 — 다른 곳에만 적히면 그 자리에서 안 읽힌다"


@pytest.mark.parametrize("text,expect", [("1805 passed in 1s", 1805), ("1 failed, 2 passed, 3 errors in 1s", 2),
                                         ("3 passed, 1 skipped in 0.5s", 3), ("= 2 passed, 1 warning in 1s =", 2)])
def test_the_summary_shapes_pytest_actually_prints(text, expect):
    """pytest 의 집계 줄은 모양이 여럿이다(= 로 둘리거나 · 건너뜀·경고가 섞이거나 · errors 복수형) — 하나만 보면 다른 모양에서 0 이 된다."""
    assert gc.parse(text)["passed"] == expect and gc.parse(text)["counted"] is True
