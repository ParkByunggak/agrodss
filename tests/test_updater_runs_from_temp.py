# -*- coding: utf-8 -*-
# [발행자 붙임 2026-09-27] update.bat 이 pull 직후 `'/f'은(는) 내부 또는 외부 명령 … 아닙니다` 를 내고 "pulling ..." 을 **두 번** 찍었다.
#
# 형태: cmd 는 배치 파일을 **바이트 위치**로 읽어 가며 실행한다. 그 pull 이 update.bat 자체를 바꿨으므로(9줄) cmd 가 새 파일의
# 옛 위치에서 이어 읽다 `for /f` 한가운데(`/f`)를 명령으로 읽었다. 실행 중인 파일이 pull 로 바뀌는 형태 — 파일을 TEMP 로 복사해
# 그 사본을 돌리고, 사본은 저장소 폴더를 인자로 받는다(사본 안의 %~dp0 은 TEMP 다).
# 세션은 Windows 를 못 돌린다 — 여기서는 구조만 잰다. 실제 확인은 발행자 PC 의 다음 더블클릭이다.
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPDATE = ROOT / "scripts" / "update.bat"


def _split() -> tuple[str, str]:
    """(사본으로 넘어가는 머리, `:run` 라벨 뒤 본문) — 라벨 **줄**로 자른다(`goto :run` 의 글자로 자르면 머리가 비어 버린다 — 첫 판의 자기 도구 오류)."""
    text = UPDATE.read_text(encoding="ascii")
    body = "\n".join(ln for ln in text.splitlines() if not ln.strip().upper().startswith("REM"))
    parts = re.split(r"^:run\s*$", body, maxsplit=1, flags=re.M)
    assert len(parts) == 2, ":run 라벨이 없다"
    return parts[0], parts[1]


def test_the_updater_copies_itself_to_temp_before_anything_touches_the_repo():
    stub, run = _split()
    assert 'copy /y "%~f0" "%TEMP%\\' in stub and "--from-temp" in stub, "pull 이 바꾸는 파일을 그대로 실행한다"
    assert "git" not in stub, "사본으로 넘어가기 전에 저장소를 건드린다"
    assert 'if /i "%~1"=="--from-temp" goto :run' in stub                    # 사본은 곧장 본문으로
    assert "git pull" in run


def test_the_temp_copy_never_uses_its_own_folder_as_the_repo():
    """사본 안의 %~dp0 은 TEMP 다 — 저장소 폴더는 인자(%~2 → HERE)로 받고, 그 뒤로는 HERE 만 쓴다."""
    _, run = _split()
    assert 'set "HERE=%~2"' in run and 'cd /d "%HERE%.."' in run
    stray = [ln for ln in run.splitlines() if "%~dp0" in ln and 'set "HERE=%~dp0"' not in ln]
    assert stray == [], f"사본에서 자기 폴더(TEMP)를 저장소로 쓴다: {stray}"
    assert re.search(r'call "%HERE%keep_screen_up\.bat"', run) and "%~dp0keep_screen_up" not in run


def test_a_failed_copy_still_runs_in_place_rather_than_doing_nothing():
    stub, _ = _split()
    assert "if errorlevel 1 goto :run" in stub, "사본을 못 만들면 아무것도 안 하고 끝난다 — 옛 방식으로라도 돈다"
