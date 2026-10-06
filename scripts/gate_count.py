# -*- coding: utf-8 -*-
# FILE: scripts/gate_count.py
# ROLE: 관문 출력의 **셈을 읽는다** — 집계 줄이 있으면 그것을, 없으면 진행 표시를 세고 "셈 추정"이라고 말한다.
#
# [자기 도구 축 2026-10-06 실측] 세션이 쓰던 관문 명령은 `python -B -m pytest -p no:cacheprovider -q` 인데, `pytest.ini` 에 이미 `addopts = -q` 가 있어
# **-qq** 가 된다. 그러면 집계 줄(「N passed」)이 **아예 안 찍힌다**. 그런데 CLAUDE.md 완료 보고는 그 줄의 숫자(「관문 N passed · 직전 대비 증분」)를 요구한다 —
# **도구가 못 내는 수치를 보고 규율이 요구**하고 있었고, 그 자리는 손으로 세거나 기억으로 메우게 된다(R-1 계열: 「집계 줄 부재」 가 네 번째였고 이것이 다섯 번째다).
#
# 같은 날 실측(저장소 안 · ini 가 적용되는 곳):
#     -qq 전부 통과   집계 줄 **없음**            rc 0
#     -qq 실패 1      집계 줄 없음 · FAILED 있음   rc 1
#     -qq 수집 오류   집계 줄 없음 · ERROR 있음    rc 2 (failed 는 0 — `failed` 만 읽으면 초록으로 오독한다 · §7.1 0번)
#     -q(ini 만)      집계 줄 **있음**
# 그래서 안전 신호(rc · FAILED/ERROR 줄)는 -qq 에서도 살아 있다 — 죽는 것은 **셈**뿐이다. 이 파일이 고치는 것은 그 셈이고, rc 를 1차 신호로 둔다.
#
# 측정 한계(도구 축 자기 기록): 처음 이 트랩을 /tmp 의 임시 검사로 재니 집계 줄이 **찍혔다** — rootdir 가 달라 `pytest.ini` 가 안 읽힌 것이다.
# **ini 가 적용되는 곳에서 재야 한다**(측정 조건 축). 그 오측정을 믿고 "트랩이 없다"고 닫을 수 있었다.
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 집계 줄: "1805 passed in 512.33s" · "1 failed, 1 passed in 0.02s" · "2 failed, 3 passed, 1 error in 1.2s"
_SUMMARY = re.compile(r"^=*\s*(?P<body>(?:\d+ \w+(?:, )?)+)\s*(?:\(.*?\)\s*)?in [\d.]+s", re.M)
_ITEM = re.compile(r"(\d+) (passed|failed|errors|error|skipped|xfailed|xpassed|deselected|warnings|warning)")
# 교체 순서가 함정이다 — 「error」 가 앞이면 「2 errors」 에서 **단수만** 집히고(남은 s 는 버려진다) 복수 정규화 분기는 **닿을 수 없는 코드**가 된다.
# 주입 B 가 그 분기를 지워도 안 터져서 드러났다(§7.1 3번으로 보였는데 재니 미검사 가드가 아니라 사문이었다 — 낱말 표의 「짧은 말이 앞」 순서 함정과 같은 축).
_PROGRESS = re.compile(r"^([.FEsxX]+)\s+\[\s*\d+%\]$", re.M)      # 표시만 — 괄호까지 세면 「점 13개」 같은 거짓 수가 나온다(첫 판이 그랬다)
_FAILED_LINE = re.compile(r"^(FAILED|ERROR) ", re.M)
PASSED, FAILED, ERROR = "passed", "failed", "error"


def parse(text: str) -> dict[str, object]:
    """관문 출력 한 덩이 → 셈. `counted` 가 False 면 집계 줄이 없어 **진행 표시를 센 추정**이다(그 사실을 함께 돌려준다).

    셈이 없을 때 조용히 0 을 돌려주지 않는다 — 0 은 「통과 0」 과 구별이 안 되고, 그 구별이 안 되는 수치가 보고로 나간다.
    """
    text = text or ""
    out: dict[str, object] = {PASSED: 0, FAILED: 0, ERROR: 0, "counted": False, "marks": 0, "fail_lines": 0}
    out["fail_lines"] = len(_FAILED_LINE.findall(text))
    m = None
    for m in _SUMMARY.finditer(text):           # 마지막 것이 그 실행의 집계다(재실행 로그가 이어 붙어도)
        pass
    if m is not None:
        out["counted"] = True
        for n, what in _ITEM.findall(m.group("body")):
            key = ERROR if what.startswith("error") else what
            if key in (PASSED, FAILED, ERROR):
                out[key] = int(n)
        return out
    marks = "".join(_PROGRESS.findall(text))    # 집계 줄이 없다 — 진행 표시를 센다(죽은 실행의 부분 출력도 여기로 온다)
    out["marks"] = len(marks)
    out[PASSED] = marks.count(".")
    out[FAILED] = marks.count("F")
    out[ERROR] = marks.count("E")
    return out


def last_gate() -> int | None:
    """직전 회차의 관문 수 — **대장 페이지 정본에서** 읽는다(손으로 적은 수와 대조하지 않는다 · 발행자가 읽는 그 숫자와 한 자리)."""
    src = (ROOT / "scripts" / "build_ledger_page.py").read_text(encoding="utf-8")
    m = re.search(r'"gate":\s*"\s*\d+\s*→\s*(\d+)', src)
    return int(m.group(1)) if m else None


def report(text: str, rc: int | None = None, last: int | None = None, full: bool = True) -> tuple[str, bool]:
    """(사람이 읽는 한 줄, 초록인가). 초록의 조건은 **셋**이다 — rc 0 · 실패·오류 0 · 집계 줄이 있었다(셈 추정으로 초록을 말하지 않는다).

    `full` — 인자 없이 돈 전체 관문만 **증분**을 말한다. 부분 스코프의 수를 직전 회차와 견주면 「−1800」 같은 수가 보고로 나가고,
    더 나쁘게는 그 수를 믿고 회귀를 찾는다(좁은 스코프 실행이 이 트랙에서 두 번 회귀를 숨긴 그 자리다)."""
    c = parse(text)
    last = last_gate() if last is None else last
    ok = (rc in (0, None)) and not c[FAILED] and not c[ERROR] and bool(c["counted"])
    head = f"관문 {c[PASSED]} passed · {c[FAILED]} failed · {c[ERROR]} error"
    if not c["counted"]:
        head += f" — **집계 줄 없음**(진행 표시 {c['marks']}개를 센 추정 · -qq 거나 중간에 죽은 출력)"
    if rc is not None:
        head += f" · rc={rc}"
    if not full:
        head += " · **부분 스코프 — 이 수치는 전체 관문이 아니다**(증분 대조 대상 아님)"
    elif last is not None:
        d = c[PASSED] - last
        head += f" · 직전 {last} → 증분 {d:+d}(신규 검사 수와 대조하라 — 어긋난 만큼이 회귀다)"
    if c["fail_lines"] and not (c[FAILED] or c[ERROR]):
        head += f" · FAILED/ERROR 줄 {c['fail_lines']}개가 있는데 셈에는 없다 — 출력을 직접 보라"
    return head, ok


def main(argv: list[str]) -> int:
    full = "--partial" not in argv
    argv = [a for a in argv if a != "--partial"]
    if not argv:
        print("쓰는 법: python -m scripts.gate_count <관문 출력 파일> [rc] [--partial]", file=sys.stderr)
        return 2
    text = Path(argv[0]).read_text(encoding="utf-8", errors="replace")
    rc = int(argv[1]) if len(argv) > 1 else None
    line, ok = report(text, rc, full=full)
    print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
