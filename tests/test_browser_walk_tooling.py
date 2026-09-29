# -*- coding: utf-8 -*-
# [U-35 2026-09-27] 브라우저 걷기 도구(scripts/browser/) — 2026-09-26 화면 처방 셋을 확인한 도구가 스크래치패드에만 있었다.
# 저장소에 두되 세 가지를 검사로 고정한다:
#   ① 격리 완전성 — walk.sh 가 돌리는 AGRODSS_* 경로 목록이 conftest 의 격리 목록을 **전부** 덮는다(§7.5 관문의 입력 —
#      하나 빠지면 걷기가 운영 원장에 쓴다. R-4 가 그렇게 33줄을 썼다). conftest 에 격리가 늘면 여기서 깨진다.
#   ② 모든 격리 경로가 tmp($W) 아래다 — 저장소 data/ 를 가리키는 것이 없다
#   ③ 내리는 것은 띄운 PID 하나 — 이름으로 죽이지 않는다(taskkill /IM 금지와 같은 축)
# 브라우저 자체는 여기서 돌리지 않는다(pytest 는 node · Chromium 을 전제하지 않는다) — 도구의 **계약**만 잰다.
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "scripts" / "browser" / "walk.sh"


def _conftest_isolation_envs() -> set[str]:
    src = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    return set(re.findall(r'setenv\("(AGRODSS_[A-Z_]+)"', src))


def _walk_exports() -> dict[str, str]:
    src = SH.read_text(encoding="utf-8")
    return dict(re.findall(r'(AGRODSS_[A-Z_]+)="([^"]*)"', src))


def test_the_walk_isolates_every_path_conftest_isolates():
    missing = _conftest_isolation_envs() - set(_walk_exports())
    assert missing == set(), f"걷기가 운영 원장에 쓸 수 있다 — walk.sh 에 격리가 빠졌다: {sorted(missing)}"


def test_every_isolated_path_lives_under_the_temp_dir():
    bad = {k: v for k, v in _walk_exports().items() if (k.endswith("_DIR") or k.endswith("_PATH") or k.endswith("_CSV")) and not v.startswith("$W/")}
    assert bad == {}, f"저장소 쪽을 가리키는 격리 경로: {bad}"


def test_the_walk_kills_only_the_pid_it_started():
    src = SH.read_text(encoding="utf-8")
    assert 'kill "$PID"' in src and "PID=$!" in src
    assert not re.search(r"\b(pkill|killall|taskkill)\b", src), "이름으로 죽인다 — 관계없는 프로세스가 죽는다"


def test_the_scripts_exist_and_take_the_chromium_path_from_env():
    for name in ("walk.cjs", "overflow.cjs", "composer.cjs", "static_overflow.cjs", "widths.cjs"):    # static_overflow: 정적 HTML(대장 페이지) 판 · 2026-09-27 · widths: 요소별 폭(휴대폰 사이드바 260 결함을 잡은 측정) 2026-09-29
        src = (ROOT / "scripts" / "browser" / name).read_text(encoding="utf-8")
        # 코드 형태로 본다 — 주석에 변수 이름이 적혀 있으면 문자열 포함 검사가 통과한다(주입 미적발 실측 2026-09-27 · §7.1 4번)
        assert "process.env.PLAYWRIGHT_CHROMIUM" in src and 'require("playwright")' in src, name
