# -*- coding: utf-8 -*-
# [발행자 2026-10-05 "여기서 완료된 것을 확인하자"] 보고의 「세션이 한 것」 은 회차마다 길어지는 **누적 문장**이고, 관문 초록은 *"모순 미발견"* 이지 검증이 아니다.
# 그래서 주장을 **실제 경로로 다시 걷는** 경로를 만들었다(`scripts/verify_claims.py`). 이 검사는 그 경로가 **살아 있게** 한다 —
# 안 그러면 다음 회차에 아무도 안 돌리고, 돌아가지 않는 검증기는 없는 것보다 나쁘다(가드 창 전례와 같은 축).
#   ① 돌아간다 · 틀린 주장 0 · 줄 수는 **줄지 않는다**(말뭉치 하한과 같은 꼴 — 주장이 늘면 하한도 올린다)
#   ② 격리 — 이 스크립트도 conftest 가 격리하는 `AGRODSS_*` 를 **전부** 덮는다(하나 빠지면 검증기가 운영 원장에 쓴다 · walk.sh 와 같은 계약)
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "verify_claims.py"
CLAIMS_MIN = 46          # 2026-10-05 첫 판 46줄 — **위로만** 간다


def _run() -> tuple[int, str]:
    p = subprocess.run([sys.executable, "-B", str(SCRIPT)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900, cwd=str(ROOT))
    return p.returncode, p.stdout + p.stderr


def test_the_verifier_runs_and_every_claim_holds():
    rc, out = _run()
    head = re.search(r"줄 (\d+) — 확인 (\d+) · 틀림 (\d+) · 못 잼 (\d+)", out)
    assert head, out[-1500:]
    total, ok, wrong, na = (int(head.group(i)) for i in (1, 2, 3, 4))
    assert wrong == 0, [ln for ln in out.splitlines() if ln.startswith("!!")]
    assert total >= CLAIMS_MIN and ok + na == total, (total, ok, wrong, na, CLAIMS_MIN)
    assert rc == 0, out[-800:]


def test_the_verifier_isolates_every_path_conftest_isolates():
    conftest = set(re.findall(r'setenv\("(AGRODSS_[A-Z_]+)"', (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")))
    mine = set(re.findall(r'"(AGRODSS_[A-Z_]+)":', SCRIPT.read_text(encoding="utf-8")))
    assert conftest, "conftest 격리 목록을 못 읽었다 — 이 검사가 눈을 감는다"
    assert conftest - mine == set(), f"검증기가 운영 원장에 쓸 수 있다 — 격리가 빠졌다: {sorted(conftest - mine)}"


def test_it_says_what_it_could_not_measure_instead_of_guessing():
    """못 세운 조건은 「못 잼」 으로 적는다 — 틀림으로도 확인으로도 적지 않는다(판정 셋뿐)."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert 'OK, NO, NA = "확인", "틀림", "못 잼"' in src
    body = src[src.index("    def say("):]
    body = body[:body.index("\n    def ", 10)]
    assert "assert verdict in (OK, NO, NA)" in body          # 네 번째 판정이 생기지 않는다
