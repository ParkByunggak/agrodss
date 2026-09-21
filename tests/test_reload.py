# -*- coding: utf-8 -*-
# [발행자 2026-09-19 21:40 "수정된 것들은 리프레시하면 반영이 되어야 한다"] git pull 이 내려앉으면 서버가 스스로 내려가고(종료 코드 3)
#   run_frontend.bat 가 새 코드로 다시 띄운다. 데이터는 원래 요청마다 새로 읽는다 — 그것도 여기서 한 번 고정한다.
from __future__ import annotations

import threading
import time
from pathlib import Path

from frontend import config, serve

ROOT = Path(__file__).resolve().parent.parent


class _Srv:
    def __init__(self) -> None:
        self.down = threading.Event()

    def shutdown(self) -> None:
        self.down.set()


def test_watch_head_shuts_down_only_on_a_real_head_change():
    heads = iter(["abc1234", "?", "", "abc1234", "def5678"])
    srv = _Srv()
    stop = threading.Event()
    assert serve.watch_head(srv, "abc1234", 0.001, stop, head_fn=lambda: next(heads)) is True
    assert srv.down.is_set()                                       # '?'·''·같은 값은 지나가고 다른 해시에서만 내린다


def test_watch_head_returns_false_when_stopped():
    srv = _Srv()
    stop = threading.Event()
    t = threading.Thread(target=lambda: setattr(srv, "ret", serve.watch_head(srv, "abc", 0.01, stop, head_fn=lambda: "abc")))
    t.start()
    time.sleep(0.05)
    stop.set()
    t.join(timeout=2)
    assert srv.ret is False and not srv.down.is_set()               # Ctrl+C 경로 — 재시작 코드가 아니다


def test_reload_is_on_by_default_and_launcher_restarts_on_code_3():
    assert config.RELOAD_ON_HEAD_CHANGE is True and config.RESTART_EXIT_CODE == 3 and config.RELOAD_POLL_SEC > 0
    bat = (ROOT / "run_frontend.bat").read_text(encoding="utf-8")
    assert ":again" in bat and '"%RC%"=="3"' in bat and "--no-browser" in bat and "goto again" in bat
    src = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")
    assert "sys.exit(main(" in src                                  # 종료 코드가 배치에 닿는다


# ── [발행자 화면 ERR_CONNECTION_REFUSED 2026-09-21] 서버가 pull 뒤 조용히 사라졌다 ──────────────────────
# 원인은 **경쟁 조건**이었다. `srv.shutdown()` 이 main 의 `serve_forever` 를 즉시 깨우는데, 재기동 표시는 watch_head 가
# **반환한 뒤에야** 대입됐다. main 이 먼저 도착하면 표시가 False 라 `return 0` — 서버는 사라지고, 래퍼는 `RC==3` 이
# 아니므로 다시 띄우지 않고 pause 에 멈춘다(발행자가 본 화면). 위의 검사들은 **함수**만 봤지 main 의 종료 경로를
# 안 봤다(§7.1 2번 — 검사가 배선을 보는가). 실측: 고치기 전 3/3 이 종료 코드 0 · 프로세스 0 · 연결 거부, 고친 뒤 5/5 가 3.


class _OrderSrv:
    """shutdown 이 불릴 때 표시가 **이미** 서 있었는지 기록한다 — 순서 자체가 계약이다."""

    def __init__(self, mark) -> None:
        self.mark = mark
        self.marked_at_shutdown = None

    def shutdown(self) -> None:
        self.marked_at_shutdown = self.mark.is_set()


def test_the_restart_flag_is_set_before_the_server_is_told_to_stop():
    """순서 고정 — 표시가 shutdown **뒤**로 가면 main 이 그것을 못 보고 조용히 0 으로 나간다(원 결함)."""
    mark = threading.Event()
    srv = _OrderSrv(mark)
    heads = iter(["abc1234", "def5678"])
    assert serve.watch_head(srv, "abc1234", 0.001, threading.Event(),
                            head_fn=lambda: next(heads), on_change=mark.set) is True
    assert srv.marked_at_shutdown is True, "내리기 전에 표시가 서 있어야 한다 — 늦으면 main 이 return 0 으로 나간다"


def test_main_exits_with_the_restart_code_when_the_head_changes(monkeypatch):
    """[배선] 함수가 아니라 **main 의 종료 코드**를 본다 — 배치가 다시 띄우는 근거가 그 값이다.
    래퍼 있음으로 고정한다: 래퍼 없음 경로는 `os.execv` 라 검사 프로세스 자체를 갈아치운다(그쪽은 임시 클론 프로브로 쟀다)."""
    monkeypatch.setattr(config, "PORT", 0)
    monkeypatch.setattr(config, "WRAPPED", True)
    monkeypatch.setattr(config, "RELOAD_POLL_SEC", 0.01)
    heads = iter(["aaaaaaa"] + ["bbbbbbb"] * 200)
    monkeypatch.setattr(serve, "git_head_short", lambda: next(heads))
    assert serve.main(open_browser=False) == config.RESTART_EXIT_CODE


def test_data_is_read_per_request_not_cached(monkeypatch):
    # 데이터 반영은 재시작이 아니라 새로고침 — judge_page 가 매 호출마다 all_judgments 를 새로 돈다
    calls = {"n": 0}
    real = serve.judge_run.all_judgments

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)
    monkeypatch.setattr(serve.judge_run, "all_judgments", counting)
    serve.judge_page()
    serve.judge_page()
    assert calls["n"] == 2
