# -*- coding: utf-8 -*-
# [발행자 환경 2026-09-21] 자동 재기동 루프가 **래퍼(run_frontend.bat)에만** 있었다. 서버는 코드가 바뀌면 종료 코드 3으로
#   내려가고, 다시 띄우는 것은 배치의 `goto again` 이었다. 발행자는 PowerShell 을 쓰고 "bat 이 없다"고 했다 —
#   배치를 건너뛰고 `python frontend\serve.py` 로 켜는 길을 알려 준 참이었는데, 그러면 코드가 바뀌어도 서버가 **그냥 멈춘다**.
#   멈춘 것을 아무도 안 알려 주므로 사람은 옛 코드가 도는 줄 안다 — **이번 27커밋 드리프트를 만든 바로 그 구멍**이다.
# 처방: 래퍼가 없으면 스스로 새 코드로 갈아탄다(os.execv). 래퍼가 있으면 옛 방식(종료 3) 그대로 — 배치 루프가 검증돼 있다.
from __future__ import annotations

import re
from pathlib import Path

from frontend import config, serve

ROOT = Path(__file__).resolve().parent.parent


def _main_body() -> str:
    src = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")
    src = re.sub(r'\"{3}.*?\"{3}', "", src, flags=re.S)
    i = src.index("def main(")
    j = src.index('\nif __name__', i)
    return "\n".join(ln.split("#", 1)[0] for ln in src[i:j].splitlines())


def test_wrapper_flag_comes_from_the_environment():
    assert config.WRAPPED is (__import__("os").environ.get("AGRODSS_WRAPPED", "") == "1")


def test_the_batch_sets_the_wrapper_flag_and_stays_ascii():
    raw = (ROOT / "run_frontend.bat").read_bytes()
    assert all(b < 128 for b in raw), "배치는 ASCII — cmd 가 cp949 로 읽는다"
    text = raw.decode("ascii")
    assert "AGRODSS_WRAPPED=1" in text
    assert text.index("AGRODSS_WRAPPED=1") < text.index(":again"), "표지는 루프보다 먼저 서야 한다"


def test_without_a_wrapper_the_server_re_execs_instead_of_just_stopping():
    """배선 — 래퍼가 없을 때 새 코드로 갈아타는 호출이 main 안에 있다(없으면 서버가 멈추고 사람은 모른다)."""
    body = _main_body()
    assert "config.WRAPPED" in body, "래퍼 여부를 안 본다"
    assert "os.execv(" in body, "래퍼가 없을 때 새 코드로 갈아타지 않는다"
    i_flag, i_exec = body.index("config.WRAPPED"), body.index("os.execv(")
    assert i_flag < i_exec, "래퍼가 있어도 갈아타면 배치 루프와 겹친다"
    assert "RESTART_EXIT_CODE" in body[:i_exec], "래퍼가 있을 때의 옛 방식(종료 3)이 사라졌다"


def test_the_re_exec_does_not_open_another_browser_window():
    body = _main_body()
    seg = body[body.index("os.execv(") - 300:body.index("os.execv(") + 200]
    assert "--no-browser" in seg, "갈아탈 때마다 브라우저 새 창이 뜬다"


def test_restart_exit_code_is_still_three_for_the_batch():
    # 경계 — 배치 루프가 기대하는 계약을 깨지 않는다(게이트가 막던 것을 남긴다)
    assert config.RESTART_EXIT_CODE == 3
    text = (ROOT / "run_frontend.bat").read_text(encoding="ascii")
    assert '"%RC%"=="3"' in text


def test_the_batch_also_restarts_on_the_silent_death_shape():
    """[R-6 2026-09-21] 종료 코드 3 만 보면 **옛 빌드의 조용한 종료**(exit 0)를 못 살린다.

    고친 코드가 도착하는 그 순간 돌고 있는 것은 **옛 빌드**다 — 제 재기동을 스스로 못 구한다(발행자 화면이
    두 번 죽은 이유). 그래서 래퍼가 **죽음의 형태**로 판단한다: 도는 동안 HEAD 가 바뀌었는데 재기동을
    요청하지 않았으면 그것이 조용한 종료다. Ctrl+C 도 0 으로 끝나지만 그때는 HEAD 가 안 바뀌므로 조용히 멈춘다.
    """
    text = (ROOT / "run_frontend.bat").read_text(encoding="ascii")
    assert all(ord(c) < 128 for c in text), "배치는 ASCII — cmd 가 cp949 로 읽는다"
    assert text.count("rev-parse --short HEAD") == 2, "돌기 전과 돌고 난 뒤 두 번 재야 바뀜을 안다"
    assert 'if not "%H0%"=="%H1%" goto restart' in text
    i_rc, i_shape = text.index('if "%RC%"=="3" goto restart'), text.index('if not "%H0%"=="%H1%"')
    assert i_rc < i_shape, "종료 코드 3 이 먼저다 — 형태 판단은 그것이 아닐 때만"
    assert text.index(":again") < text.index("rev-parse"), "첫 측정은 루프 안에서(재기동마다 새로 잰다)"
    assert text.index(":restart") > i_shape and text.count("goto again") == 1
