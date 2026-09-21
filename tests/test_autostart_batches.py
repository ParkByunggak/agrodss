# -*- coding: utf-8 -*-
# [발행자 2026-09-21 "run_frontend.bat 이 실행을 code가 직접할 수 없는가?"]
#
# 못 한다. 세션은 원격 리눅스 컨테이너에서 돌고 화면은 발행자 PC 에서 돈다 — 세션이 그 PC 에 프로세스를 띄울 방법이 없다.
# 대신 **그 PC 가 스스로 지키게** 할 수는 있다: 포트가 안 열려 있으면 배치가 화면을 다시 띄우고, 그 배치를 Windows 스케줄러가
# 로그온 때와 5분마다 부른다. 발행자는 **한 번 더블클릭**하면 된다.
#
# 세션은 Windows 에서 이것을 **돌려 보지 못한다**(R-5 — 안내는 걷거나 재고 나서 쓴다. 못 걸었으면 못 걸었다고 적는다).
# 그래서 여기서 재는 것은 *돌아가는가* 가 아니라 **형태가 이 저장소의 배치 규율을 지키는가**다.
#
#   ASCII 만            cmd 는 콘솔 코드페이지(한글 Windows = cp949)로 배치를 읽는다 — UTF-8 한글은 깨진 바이트로 온다
#   블록 안 괄호 금지    live_check.bat 가 실제로 그것으로 죽었다(")" 가 블록을 일찍 닫아 아무것도 안 돌았다)
#   먼저 보고 나중에 띄운다  포트 검사가 start 보다 앞 — 아니면 켤 때마다 서버가 겹친다
#   되돌릴 수 있다       설치와 같은 이름을 지우는 uninstall 이 짝으로 있다
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WATCH = ROOT / "scripts" / "keep_screen_up.bat"
INSTALL = ROOT / "scripts" / "install_autostart.bat"
UNINSTALL = ROOT / "scripts" / "uninstall_autostart.bat"
UPDATE = ROOT / "scripts" / "update.bat"
TASKS = ("agrodss-screen-logon", "agrodss-screen-watch")


@pytest.mark.parametrize("p", [WATCH, INSTALL, UNINSTALL, UPDATE])
def test_the_batches_exist_and_are_ascii(p):
    assert p.exists(), p
    raw = p.read_bytes()
    assert all(b < 128 for b in raw), f"배치는 ASCII — cmd 가 cp949 로 읽는다: {p.name}"


def _body(p: Path) -> str:
    """주석(REM)을 걷은 **실제 실행되는 줄만**. [§7.1 4번 — 이 세션 세 번째] 첫 판은 전체에서 `start ` 를 찾았는데
    머리말 주석의 *\"start it\"* 이 먼저 걸려 '포트 검사가 뒤에 있다'는 **거짓 실패**가 났다. 검사 대상 범위를 먼저 자른다."""
    return "\n".join(ln for ln in p.read_text(encoding="ascii").splitlines() if not ln.strip().upper().startswith("REM"))


@pytest.mark.parametrize("p", [WATCH, INSTALL, UNINSTALL, UPDATE])
def test_no_multi_line_blocks_in_the_batches(p):
    """live_check.bat 실측: **여러 줄 블록** 안의 ')' 가 블록을 일찍 닫아 아무것도 안 돌고 빈 로그만 남았다.

    [규칙을 좁힘 2026-09-21] 첫 판은 괄호를 **하나도** 못 쓰게 했는데, `for /f %%h in ('git rev-parse …') do` 는
    괄호가 **문법상 필수**라 새 업데이터가 걸렸다. 위험한 것은 괄호 자체가 아니라 **줄 끝에서 열리는 블록**이다
    (그 안의 echo 에 ')' 가 있으면 일찍 닫힌다). 한 줄 안에서 열고 닫는 `('…')` 는 그 위험이 없다.
    과잉 차단은 다음 사람이 규칙을 통째로 끄게 만든다 — 급을 가른다.
    """
    for n, line in enumerate(_body(p).splitlines(), 1):
        s = line.strip()
        assert not s.endswith("("), f"{p.name}:{n} 줄 끝에서 블록이 열린다 — goto 로 가른다"
        assert s != ")" and not s.startswith(")"), f"{p.name}:{n} 블록 닫기 — 여러 줄 블록을 쓰지 않는다"
        assert s.count("(") == s.count(")"), f"{p.name}:{n} 한 줄 안에서 괄호가 안 맞는다"


def test_the_watchdog_looks_before_it_starts():
    """포트를 **먼저** 본다 — 아니면 5분마다 서버가 하나씩 더 뜬다(VELA 의 supervisor 4겹 경합과 같은 형태)."""
    text = _body(WATCH)
    i_check, i_start = text.index("netstat"), text.index("start ")
    assert i_check < i_start, "포트 검사가 start 뒤에 있다 — 켤 때마다 겹친다"
    assert "LISTENING" in text and "run_frontend.bat" in text
    assert "taskkill" not in text, "이 배치는 아무것도 죽이지 않는다 — 없는 것만 띄운다"


def test_the_watchdog_honours_the_port_setting_instead_of_hardcoding_it():
    """포트는 설정에서 온다(하드코딩 금지) — 기본만 적고 환경변수가 있으면 그것을 쓴다."""
    text = WATCH.read_text(encoding="ascii")
    assert "AGRODSS_FRONTEND_PORT" in text
    i_default, i_env = text.index('set "PORT=8765"'), text.index("AGRODSS_FRONTEND_PORT")
    assert i_default < i_env, "환경변수가 기본값을 덮어야 한다(순서가 반대면 설정이 무시된다)"


def test_install_and_uninstall_name_exactly_the_same_tasks():
    """되돌릴 수 있는가 — 설치가 만든 것만 지운다(이름이 갈리면 지울 수 없는 것이 남는다)."""
    ins, uns = INSTALL.read_text(encoding="ascii"), UNINSTALL.read_text(encoding="ascii")
    for t in TASKS:
        assert f'/TN "{t}"' in ins, t
        assert f'/TN "{t}"' in uns, t
    assert uns.count("/Delete") == len(TASKS)
    assert "/Delete" not in ins and "/Create" not in uns


def test_install_registers_for_the_current_user_only():
    """관리자 권한도, 시스템 전역도 아니다 — 발행자 계정에만 등록한다(되돌리기 쉽고 범위가 좁다)."""
    ins = INSTALL.read_text(encoding="ascii")
    assert "/RU" not in ins and "SYSTEM" not in ins
    assert "/SC ONLOGON" in ins and "/SC MINUTE" in ins and "/MO 5" in ins


def test_the_updater_does_not_repeat_the_claim_that_r6_disproved():
    """[R-6] 옛 `update.bat` 의 마지막 줄은 *"HEAD 가 바뀌면 서버가 스스로 재시작한다"* 였다 — **사실이 아니다**.
    경쟁 조건으로 조용히 종료했고, 그 경쟁 조건을 고친 뒤에도 **고친 코드가 도착하는 순간 돌고 있는 것은 옛 빌드**라
    제 재기동을 스스로 못 구한다. 그래서 업데이트가 **직접** 화면을 되살린다."""
    text = _body(UPDATE)
    assert "restarts itself" not in text, "R-6 이 반증한 주장이 되돌아왔다"
    assert "keep_screen_up.bat" in text, "받기만 하고 화면을 안 되살린다 — 그것이 지금까지의 마찰이다"
    i_pull, i_start = text.index("git pull"), text.index("keep_screen_up.bat")
    assert i_pull < i_start, "받기 전에 띄우면 옛 코드로 뜬다"


def test_the_updater_keeps_the_window_open_and_stops_on_failure():
    """더블클릭하면 창이 번쩍 사라지던 것이 옛 판이다 — 출력이 안 읽히면 안내가 없는 것과 같다.
    그리고 pull 이 실패하면 **거기서 멈춘다**(실패를 지나쳐 옛 코드로 띄우지 않는다)."""
    text = _body(UPDATE)
    # [주입이 드러낸 허점 2026-09-21] 첫 판은 `"pause" in text` 만 봤다 — 실패 갈래의 pause 가 남아 있어
    # **성공 갈래에서 pause 를 빼는 주입(N7)이 통과**했다. 성공 갈래에 있는지를 본다(있음을 세면 뚫린다).
    ok_branch = text[text.index("keep_screen_up.bat"):text.index("exit /b 0")]
    assert "pause" in ok_branch, "성공했을 때 창이 닫혀 버린다 — 무엇이 일어났는지 못 본다"
    assert "pause" in text[text.index(":pullfailed"):], "실패했을 때도 창은 열려 있어야 한다"
    assert "if errorlevel 1 goto pullfailed" in text
    assert text.index("if errorlevel 1 goto pullfailed") < text.index("keep_screen_up.bat")
    assert "NOTHING was changed or discarded" in UPDATE.read_text(encoding="ascii")


def test_the_updater_discards_nothing_but_the_one_known_file():
    """되돌릴 수 없는 일은 하지 않는다 — U-18 의 그 한 파일(값은 덮개에 있다) 말고는 아무것도 버리지 않는다."""
    text = _body(UPDATE)
    assert text.count("git checkout") == 1 and "data/parcels.json" in text
    for danger in ("reset --hard", "clean -", "push --force", "rm -rf", "rmdir"):
        assert danger not in text, danger


def test_the_install_says_it_was_not_tested_on_windows():
    """[R-5] 세션은 이것을 Windows 에서 못 돌려 봤다 — **못 걸었으면 못 걸었다고 적는다**.
    이 문장이 사라지면 다음 사람이 검증된 절차로 읽는다(안내가 틀리는 형태는 이 트랙에서 세 번 났다)."""
    ins = INSTALL.read_text(encoding="ascii")
    assert "not verified on Windows" in ins
    assert "paste it into the session" in ins.lower()                 # 틀리면 고치는 길을 같이 준다
