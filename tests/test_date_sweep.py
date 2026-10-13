# -*- coding: utf-8 -*-
# [달력 걷기 2026-10-14] 날이 바뀌어 붉어지는 검사를 미리 세는 경로(scripts/date_sweep.sh)가 살아 있게 — 전체 검사를 안에서 다시 돌리면 관문이 두 배라
# 배선만 본다: 날짜마다 AGRODSS_TODAY 를 바꾸고 · 출력을 파일로 받아 rc 를 지키고(파이프가 rc 를 삼키지 않게 — R-8) · 날짜가 없으면 거부한다.
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "scripts" / "date_sweep.sh"


def test_the_sweep_moves_today_per_date_and_keeps_the_rc():
    # [재검토 F8 · 2026-10-14] 첫 판은 검사 줄을 글자 그대로 박아 무해한 「-rf」 하나에 빨갛고, 같은 줄을 주석으로 바꿔도 초록이었다 — 주석을 걷고 구조로 본다
    body = SH.read_text(encoding="utf-8")
    code = [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    loop = code[code.index('for d in "$@"; do') + 1:code.index("done")]
    i = next(i for i, ln in enumerate(loop) if ln.startswith('AGRODSS_TODAY="$d" '))                # 날짜를 바꾸는 자리가 검사 줄 그 자체(앞에 붙인 환경)
    run = loop[i]
    assert "-m pytest" in run and re.search(r'>\s*"\$out"\s+2>&1\s*$', run) and "|" not in run       # 출력은 파일로 · 파이프가 rc 를 삼키지 않게
    assert loop[i + 1] == "rc=$?"                                                                  # 바로 다음 문장이 그 rc
    # [재재검토] 이 둘도 주석을 걷은 줄에서 꼴로 본다 — 원문에서 찾으면 주석 처리해도 초록이었다
    assert any(re.match(r"set -\w*o pipefail\b", ln) for ln in code) and any(re.match(r"export TZ=", ln) for ln in code)


LEAKED = "1999-01-01"


@pytest.fixture(scope="module")
def _today_between_tests():
    """검사 **몸 밖**의 오늘 — 모듈 범위 픽스처는 앞 검사의 뒷정리가 끝난 뒤, 다음 검사의 픽스처보다 먼저 선다."""
    return os.environ.get("AGRODSS_TODAY")


def test_a_test_that_sets_today_directly_and_forgets_it():
    """[재검토 F4] 검사 하나가 os.environ 에 날짜를 바로 넣고 안 되돌려 알파벳 뒤의 쉰두 파일이 그 날로 돌았다 — 날짜 쓸기가 그 범위를 못 봤다. 그 꼴을 일부러 낸다."""
    os.environ["AGRODSS_TODAY"] = LEAKED


def test_the_next_test_starts_from_the_session_today_again(_today_between_tests):
    assert os.environ.get("AGRODSS_TODAY") != LEAKED                                # conftest 가 검사마다 시작 값으로 되돌린다(바로 위 검사의 새는 날짜가 안 넘어온다)
    assert _today_between_tests != LEAKED                                           # [재재검토] 검사 사이(몸 밖)에도 — 없던 날짜는 지워져야 한다(delenv 만으로는 안 적힌다)


def test_without_a_date_it_refuses_instead_of_sweeping_nothing():
    r = subprocess.run(["bash", str(SH)], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 2 and "날짜를 하나 이상" in r.stdout
