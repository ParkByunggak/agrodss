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
LOOP = ROOT / "scripts" / "watch_screen.bat"
INSTALL = ROOT / "scripts" / "install_autostart.bat"
UNINSTALL = ROOT / "scripts" / "uninstall_autostart.bat"
UPDATE = ROOT / "scripts" / "update.bat"
TASKS = ("agrodss-screen-logon", "agrodss-screen-watch")
ENTRY = "agrodss-screen.cmd"        # 스케줄러가 거부당했을 때의 시작프로그램 항목 — 설치·제거가 같은 이름을 본다


@pytest.mark.parametrize("p", [WATCH, LOOP, INSTALL, UNINSTALL, UPDATE])
def test_the_batches_exist_and_are_ascii(p):
    assert p.exists(), p
    raw = p.read_bytes()
    assert all(b < 128 for b in raw), f"배치는 ASCII — cmd 가 cp949 로 읽는다: {p.name}"


def _body(p: Path) -> str:
    """주석(REM)을 걷은 **실제 실행되는 줄만**. [§7.1 4번 — 이 세션 세 번째] 첫 판은 전체에서 `start ` 를 찾았는데
    머리말 주석의 *\"start it\"* 이 먼저 걸려 '포트 검사가 뒤에 있다'는 **거짓 실패**가 났다. 검사 대상 범위를 먼저 자른다."""
    return "\n".join(ln for ln in p.read_text(encoding="ascii").splitlines() if not ln.strip().upper().startswith("REM"))


@pytest.mark.parametrize("p", [WATCH, LOOP, INSTALL, UNINSTALL, UPDATE])
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
    """관리자 권한도, 시스템 전역도 아니다 — 발행자 계정에만, **로그온해 있을 때만** 등록한다.

    [발행자 실측 2026-09-21 "오류: 액세스가 거부되었습니다"] 첫 판은 `/RU` 가 **있으면** 권한을 올리는 줄 알고
    *"`/RU` 가 없어야 현재 사용자"* 를 계약으로 박아 두었다 — 거꾸로였다. `/RU` 도 `/IT` 도 없으면 schtasks 는
    *"로그온 여부와 무관하게 실행"* 으로 등록하려 하고, 그것은 **'배치 작업으로 로그온' 권한**을 요구한다.
    표준 계정에는 그 권한이 없어 거부당한다. `/RU "%USERNAME%" /IT` 는 그 요구를 없앤다(암호도 필요 없다).

    그래서 계약은 *"`/RU` 를 쓰지 않는다"* 가 아니라 **"내 계정 · 대화형 · 암호 없음"** 이다.
    """
    ins = INSTALL.read_text(encoding="ascii")
    creates = [ln for ln in ins.splitlines() if "schtasks /Create" in ln]
    assert len(creates) == len(TASKS)
    for ln in creates:
        assert '/RU "%USERNAME%"' in ln, f"등록 대상이 내 계정이 아니다: {ln}"
        assert "/IT" in ln, f"/IT 가 없으면 '배치 작업으로 로그온' 권한을 요구한다 — 거부당한 그 형태: {ln}"
        assert "/RP" not in ln, f"암호를 배치에 적지 않는다: {ln}"
    assert "SYSTEM" not in ins
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
    """되돌릴 수 없는 일은 하지 않는다 — U-18 의 그 한 파일(값은 덮개에 있다) 말고는 아무것도 **버리지** 않는다.

    [운영 상태 파일 전수 2026-09-21] 되돌리기가 하나 늘었다 — 추적 파일에 런타임이 쓰는 자리가 `parcels.json`
    말고도 셋 더 있었고, 그것이 수정돼 있으면 pull 이 멈춰 발행자가 또 옛 코드에 묶인다. 그래서 되돌리되
    **먼저 사본을 뜬다**. 계약은 "되돌리기가 하나" 가 아니라 **"사본 없는 되돌리기는 그 한 파일뿐"** 이다.
    """
    text = _body(UPDATE)
    assert "data/parcels.json" in text
    known = text[:text.index(":preserve")]
    assert known.count("git checkout") == 1, "사본 없이 되돌리는 자리가 늘었다"
    kept = text[text.index(":preserve"):]
    assert kept.count("git checkout") == 1 and "copy " in kept
    for danger in ("reset --hard", "clean -", "push --force", "rm -rf", "rmdir"):
        assert danger not in text, danger


def test_the_install_says_it_was_not_tested_on_windows():
    """[R-5] 세션은 이것을 Windows 에서 못 돌려 봤다 — **못 걸었으면 못 걸었다고 적는다**.
    이 문장이 사라지면 다음 사람이 검증된 절차로 읽는다(안내가 틀리는 형태는 이 트랙에서 세 번 났다)."""
    ins = INSTALL.read_text(encoding="ascii")
    assert "not verified on Windows" in ins
    assert "paste this whole window into the session" in ins.lower()  # 틀리면 고치는 길을 같이 준다


# ── 스케줄러가 거부당한 뒤 (발행자 실측 2026-09-21 "오류: 액세스가 거부되었습니다") ────────────────
#
# 옛 판은 schtasks 가 실패하면 `:failed` 로 가서 **멈췄다** — 발행자에게 남는 것은 오류 한 줄뿐이었다.
# R-5 의 그 형태다: 세션은 Windows 를 못 걷고, 그래서 **한 방법에 걸면 걷지 못한 추측 하나에 전부를 건다**.
# 처방은 추측을 맞히는 것이 아니라 **권한이 필요 없는 두 번째 길**을 붙이는 것이다.

def test_every_scheduler_call_has_a_way_out():
    """schtasks 줄이 늘면 그 줄에도 탈출구가 있어야 한다 — 하나가 가드 없이 들어오면 거기서 다시 멈춘다."""
    lines = [ln.strip() for ln in _body(INSTALL).splitlines()]
    creates = [i for i, ln in enumerate(lines) if "schtasks /Create" in ln]
    assert creates, "설치가 스케줄러를 아예 안 부른다"
    for i in creates:
        nxt = next((ln for ln in lines[i + 1:] if ln), "")
        assert nxt == "if errorlevel 1 goto fallback", f"거부당했을 때 갈 곳이 없다: {lines[i]}"
    assert ":failed" not in _body(INSTALL), "거부 = 끝 인 옛 갈래가 되돌아왔다"


def test_the_fallback_writes_a_startup_entry_that_needs_no_permission():
    """두 번째 길은 **스케줄러를 다시 부르지 않는다** — 거부한 그것에 또 기대면 길이 하나인 것과 같다.

    시작프로그램 항목은 내 프로필 안에 파일 하나를 쓰는 것이라 권한 문제로 거부될 수 없다.
    (한글 Windows 에서도 이 경로는 영문이다 — 표시 이름만 번역된다.)
    """
    body = _body(INSTALL)
    fb = body[body.index(":fallback"):body.index(":started")]
    assert "schtasks" not in fb, "거부한 그 도구를 두 번째 길에서 또 부른다"
    assert '> "%ENTRY%"' in fb and '>> "%ENTRY%"' in fb, "항목을 만드는 두 줄 중 하나가 없다 — 반쪽 파일이 남는다"
    assert "%LOOP%" in fb, "항목이 감시자를 안 가리킨다"
    assert 'if not exist "%ENTRY%" goto nostartup' in fb, "썼다고 믿고 넘어간다 — 쓰였는지 보고 넘어간다"
    assert "Start Menu\\Programs\\Startup" in body


def test_the_watch_loop_checks_before_it_sleeps_and_never_stops():
    """감시자는 **먼저 보고 그 다음 잔다** — 순서가 반대면 로그온 직후 5분 동안 화면이 없다."""
    text = _body(LOOP)
    i_call, i_sleep = text.index("keep_screen_up.bat"), text.index("timeout /t")
    assert i_call < i_sleep, "잠부터 자면 첫 5분이 빈다"
    assert text.index(":loop") < i_call, "돌아올 표가 호출보다 뒤에 있다"
    assert text.rindex("goto loop") > i_sleep, "한 번 자고 끝난다 — 감시가 아니다"
    assert "taskkill" not in text, "감시자는 아무것도 죽이지 않는다"
    assert "AGRODSS_WATCH_SECONDS" in text                            # 주기도 하드코딩하지 않는다


def test_install_and_uninstall_name_the_same_startup_entry():
    """되돌릴 수 있는가 — 두 번째 길로 만든 것도 지운다(이름이 갈리면 지울 수 없는 것이 남는다)."""
    ins, uns = INSTALL.read_text(encoding="ascii"), UNINSTALL.read_text(encoding="ascii")
    assert ENTRY in ins and ENTRY in uns
    body = _body(UNINSTALL)
    assert body.count("del ") == 1, "지우는 줄이 하나가 아니다 — 범위가 넓어진 것이다"
    assert body.index('if exist "%ENTRY%"') < body.index("del "), "없는 파일을 지우려다 오류만 찍는다"
    for danger in ("rmdir", " /s", "rd "):
        assert danger not in body, danger


# ── 업데이터가 주장이 아니라 측정을 한다 (발행자 실측 2026-09-23) ────────────────────────
#
# 발행자가 붙여 준 창: "[agrodss] done. The screen SHOULD now be running ed45339". **주장**이다 — 재지 않았다.
# pull 이 닿아도 이미 떠 있는 프로세스는 옛 빌드를 계속 낸다(R-6). 그것을 아무도 말해 주지 않아 며칠을 잃었다.
# 이제 화면에게 `/running` 을 **묻고** 저장소 HEAD 와 비교한다 — 다르면 그 포트의 프로세스만 멈추고 다시 띄운다.

def test_the_updater_asks_the_screen_before_it_says_what_is_running():
    """'should now be running' 이 되돌아오면 안 된다 — 성공 문면은 **측정 뒤** 갈래에만 있다."""
    text = _body(UPDATE)
    assert "should now be running" not in text.lower(), "주장이 되돌아왔다 — 재고 말한다"
    assert "/running" in text and "findstr /B /C:\"head=\"" in text, "화면에게 묻지 않는다"
    ok = text[text.index(":isnew"):text.index(":cannotask")]
    assert "measured" in ok and 'if "%RUNNING%"=="%NEW%" goto isnew' in text[:text.index(":isnew")]


def test_the_updater_restarts_only_the_process_on_our_port_and_only_when_stale():
    """죽이는 것은 **그 포트의 PID 하나**뿐이고, **측정이 어긋났을 때**뿐이다 — 이름으로 죽이면 남의 파이썬이 죽는다."""
    text = _body(UPDATE)
    kill = text[text.index(":killpid"):]
    assert "taskkill /PID" in kill and "/IM" not in text, "이름(/IM)으로 죽이면 관계없는 프로세스가 죽는다"
    assert text.count("taskkill") == 1, "죽이는 자리는 하나 — 늘면 범위가 넓어진 것"
    restart = text[text.index(":restart"):text.index(":killpid")]
    assert ":%PORT% .*LISTENING" in restart, "포트로 고르지 않는다"
    before = text[:text.index("call :restart")]
    assert "call :measure" in before and 'if "%RUNNING%"=="" goto cannotask' in before, "재지도 않고 다시 띄운다"


def test_a_refusal_does_not_leave_the_publisher_without_a_screen():
    """둘 다 막혔을 때 **화면이 멈추는 것이 아니다** — 자동 재시작만 없는 것이다. 그 구별을 화면이 말한다.

    [§7.1 4번] 판정 어휘가 빠지면 정직한 고지가 아니라 막다른 길이 된다 — 옛 `:failed` 가 그랬다.
    """
    body = _body(INSTALL)
    end = body[body.index(":nostartup"):]
    assert "does NOT stop the screen" in end
    assert "update.bat" in end, "지금 당장 화면을 띄우는 길을 안 알려 준다"
    assert "shell:startup" in end, "손으로 하는 길을 안 알려 준다"
    assert "paste this whole window into the session" in end.lower()  # 막히면 고치는 길이 이어진다
