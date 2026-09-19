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
