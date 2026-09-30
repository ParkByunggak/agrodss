# -*- coding: utf-8 -*-
# [R-8 2026-09-30] 마감 체인 스크립트 — 파이프가 rc 를 삼켜 빨간 채 커밋·푸시된 형태를 **경로**로 막는다(규율만 두면 세 번째에 또 난다 — HEREDOC-1 전례).
# 계약: set -euo pipefail · 검사·생성기 출력은 파일로 받고 rc 로 판단(파이프 뒤 tail 로 자르지 않는다) · 실패한 단계에서 멈추고 그 로그 꼬리를 보인다 ·
# 관문·주입·걷기는 이 스크립트 앞의 몫(여기서 돌리지 않는다) · 핸드오버 자리 채우기는 이 한 파일만 · 실제로 돌려 첫 단계가 붉으면 커밋 전에 멈춘다.
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "scripts" / "finish_round.sh"


def test_the_closing_chain_cannot_swallow_a_return_code():
    src = SH.read_text(encoding="utf-8")
    assert src.startswith("#!/bin/bash") and "set -euo pipefail" in src
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert re.search(r"\|\s*tail", body) is None, "파이프 뒤 tail — R-8 의 그 형태"          # 출력은 파일로, 꼬리는 파일에서
    assert "> \"$LOG\" 2>&1 || fail" in body and body.count("|| fail") >= 4               # 단계마다 rc 를 본다
    assert "/dev/null" not in body                                                        # HEREDOC-1 의 그 형태도 없다
    assert "python -B -m pytest" in body and "tests/test_build_ledger_page.py" in body and "static_overflow.cjs" in body
    assert "walk.sh" not in body and "inject" not in body                                   # 관문·주입·걷기는 이 앞의 몫 — 여기서 돌리면 마감이 관문을 대신한다고 믿게 된다
    assert "git commit -q -F \"$MSG\"" in body and "(이 커밋 X)" in body and "docs/handover_20260919.md" in body
    assert "git push -u origin main" in body and "for d in 0 2 4 8 16" in body


def test_a_red_first_step_stops_before_any_commit(tmp_path):
    """실제로 돌린다 — 검사 단계가 붉으면(존재하지 않는 검사 파일을 끼워) 커밋 없이 멈추고 로그 꼬리를 보인다. 저장소는 건드리지 않는다(임시 클론)."""
    clone = tmp_path / "c"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{ROOT}", str(clone)], check=True)
    sh = clone / "scripts" / "finish_round.sh"
    text = SH.read_text(encoding="utf-8").replace("tests/test_first_farm_literals.py", "tests/없는_검사.py")   # 작업 트리의 스크립트(아직 커밋 전일 수 있다)
    sh.write_text(text, encoding="utf-8")
    msg = tmp_path / "m.txt"
    msg.write_text("test: 안 남아야 할 커밋\n", encoding="utf-8")
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=clone, capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, NO_PUSH="1", LEDGER_OUT=str(tmp_path / "l.html"), TZ="Asia/Seoul")
    r = subprocess.run(["bash", str(sh), str(msg)], cwd=clone, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=600)
    assert r.returncode != 0 and "검사 실패" in r.stdout and "로그 꼬리" in r.stdout
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=clone, capture_output=True, text=True).stdout.strip()
    assert after == before, "붉은데 커밋이 났다"
    assert not (tmp_path / "l.html").exists()                                              # 검사 앞에서 멈췄으니 생성도 없다
