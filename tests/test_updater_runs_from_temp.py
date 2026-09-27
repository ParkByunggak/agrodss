# -*- coding: utf-8 -*-
# [발행자 붙임 2026-09-27] update.bat 이 pull 직후 `'/f'은(는) 내부 또는 외부 명령 … 아닙니다` 를 내고 "pulling ..." 을 **두 번** 찍었다.
#
# 형태: cmd 는 배치 파일을 **바이트 위치**로 읽어 가며 실행한다. 그 pull 이 update.bat 자체를 바꿨으므로(9줄) cmd 가 새 파일의
# 옛 위치에서 이어 읽다 `for /f` 한가운데(`/f`)를 명령으로 읽었다. 실행 중인 파일이 pull 로 바뀌는 형태 — 파일을 TEMP 로 복사해
# 그 사본을 돌리고, 사본은 저장소 폴더를 인자로 받는다(사본 안의 %~dp0 은 TEMP 다).
#
# [처방 직후 전수 §7.5] 같은 형태가 **오래 도는 배치 둘**에 더 있었다 — run_frontend.bat(서버를 기다렸다가 새 코드로 다시 띄우는
# 감독 루프 · 며칠을 돈다) · watch_screen.bat(5분 루프 · 영원히). 둘은 pull 이 그 파일을 바꾸는 순간이 아니라 **그 뒤 처음 이어 읽는
# 순간**(서버 종료 · 다음 5분)에 깨진다. 셋 다 같은 처방. 넘겨주기는 `call` 없이 — call 이면 사본이 끝난 뒤 이 파일로 돌아오는데
# 그때는 이미 pull 이 이 파일을 바꿔 놓았다(같은 함정).
# 세션은 Windows 를 못 돌린다 — 여기서는 구조만 잰다. 실제 확인은 발행자 PC 의 다음 더블클릭이다.
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BATCHES = {
    "scripts/update.bat": {"temp": "agrodss_update.bat", "cd": 'cd /d "%HERE%.."', "keep": True},
    "run_frontend.bat": {"temp": "agrodss_run_frontend.bat", "cd": 'cd /d "%HERE%"', "keep": False},
    "scripts/watch_screen.bat": {"temp": "agrodss_watch_screen.bat", "cd": 'cd /d "%HERE%"', "keep": True},
}


def _split(rel: str) -> tuple[str, str]:
    """(사본으로 넘어가는 머리, `:run` 라벨 뒤 본문) — 라벨 **줄**로 자른다(`goto :run` 의 글자로 자르면 머리가 비어 버린다 — 첫 판의 자기 도구 오류)."""
    text = (ROOT / rel).read_text(encoding="ascii")
    body = "\n".join(ln for ln in text.splitlines() if not ln.strip().upper().startswith("REM"))
    parts = re.split(r"^:run\s*$", body, maxsplit=1, flags=re.M)
    assert len(parts) == 2, f"{rel}: :run 라벨이 없다"
    return parts[0], parts[1]


@pytest.mark.parametrize("rel", sorted(BATCHES))
def test_the_batch_copies_itself_to_temp_and_hands_off_without_call(rel):
    spec = BATCHES[rel]
    stub, run = _split(rel)
    assert 'copy /y "%~f0" "%TEMP%\\' + spec["temp"] + '"' in stub, f"{rel}: pull 이 바꾸는 파일을 그대로 실행한다"
    assert 'if /i "%~1"=="--from-temp" goto :run' in stub                    # 사본은 곧장 본문으로
    assert re.search(r'^"%TEMP%\\' + re.escape(spec["temp"]) + r'" --from-temp "%~dp0"\s*$', stub, re.M), f"{rel}: 사본으로 넘겨주지 않는다"
    assert 'call "%TEMP%' not in stub and "exit /b" not in stub, f"{rel}: call 로 넘기면 사본이 끝난 뒤 바뀐 이 파일로 돌아온다 — 같은 함정"
    assert "git" not in stub, f"{rel}: 사본으로 넘어가기 전에 저장소를 건드린다"
    assert "if errorlevel 1 goto :run" in stub, f"{rel}: 사본을 못 만들면 아무것도 안 하고 끝난다 — 옛 방식으로라도 돈다"


@pytest.mark.parametrize("rel", sorted(BATCHES))
def test_the_temp_copy_never_uses_its_own_folder_as_the_repo(rel):
    """사본 안의 %~dp0 은 TEMP 다 — 저장소 폴더는 인자(%~2 → HERE)로 받고, 그 뒤로는 HERE 만 쓴다."""
    spec = BATCHES[rel]
    _, run = _split(rel)
    assert 'set "HERE=%~2"' in run and spec["cd"] in run, rel
    stray = [ln for ln in run.splitlines() if "%~dp0" in ln and 'set "HERE=%~dp0"' not in ln]
    assert stray == [], f"{rel}: 사본에서 자기 폴더(TEMP)를 저장소로 쓴다: {stray}"
    if spec["keep"]:
        assert re.search(r'call "%HERE%keep_screen_up\.bat"', run) and "%~dp0keep_screen_up" not in run, rel


def test_every_long_running_or_pulling_batch_is_covered():
    """전수 — pull 을 부르거나 오래 도는 배치는 전부 위 표에 있다(새로 생기면 여기서 깨진다)."""
    bats = list(ROOT.glob("*.bat")) + list((ROOT / "scripts").glob("*.bat"))
    risky = set()
    for p in bats:
        body = "\n".join(ln for ln in p.read_text(encoding="ascii", errors="replace").splitlines() if not ln.strip().upper().startswith("REM"))
        if "git pull" in body or re.search(r"^goto (loop|again)\s*$", body, re.M):
            risky.add(p.relative_to(ROOT).as_posix())
    assert risky <= set(BATCHES), f"pull 하거나 오래 도는데 사본으로 안 도는 배치: {sorted(risky - set(BATCHES))}"
