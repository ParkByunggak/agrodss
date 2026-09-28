# -*- coding: utf-8 -*-
# [U-39 자동 갱신 · 발행자 등재 2026-09-28 "⓪ 자동 pull 등재하자"] 화면 프로세스가 스스로 저장소를 따라간다 — 재기동은 이미 스스로 했고 pull 만 사람 몫이었다.
# 계약(임시 git 저장소 셋 — 원격 bare · 이 PC · 세션): 뒤처지면 fast-forward 로 따라간다 · 최신이면 아무것도 안 한다 · 추적 파일 수정이 있으면 **보류**하고
# 아무것도 버리지 않는다(덮개는 안 걸린다) · 갈라졌으면 보류 · fetch 가 안 되면 실패 — 넷 다 이유가 꼬리·/changes·/running 에 남는다 · 0 이면 꺼짐.
from __future__ import annotations

import http.client
import subprocess
import threading
from pathlib import Path

import pytest

from frontend import autopull, config, serve
from tests.test_brand_home import srv  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


def _git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True, env={"GIT_TERMINAL_PROMPT": "0", "PATH": "/usr/bin:/bin", "HOME": "/root"}).stdout.strip()


@pytest.fixture
def repos(tmp_path):
    """원격 bare + 이 PC(pc) + 세션(dev). dev 가 커밋을 밀면 pc 가 뒤처진다."""
    remote = tmp_path / "remote.git"
    _git("init", "-q", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    dev, pc = tmp_path / "dev", tmp_path / "pc"
    _git("clone", "-q", str(remote), str(dev), cwd=tmp_path)
    for d in (dev,):
        _git("config", "user.email", "t@example.invalid", cwd=d)
        _git("config", "user.name", "t", cwd=d)
    (dev / "a.txt").write_text("1\n", encoding="utf-8")
    (dev / ".gitignore").write_text("*_local.json\n", encoding="utf-8")
    _git("add", "-A", cwd=dev)
    _git("commit", "-qm", "init", cwd=dev)
    _git("push", "-q", "origin", "HEAD:main", cwd=dev)
    _git("clone", "-q", str(remote), str(pc), cwd=tmp_path)
    _git("config", "user.email", "t@example.invalid", cwd=pc)
    _git("config", "user.name", "t", cwd=pc)
    return remote, dev, pc


def _push_change(dev, text="2\n"):
    (dev / "a.txt").write_text(text, encoding="utf-8")
    _git("commit", "-qam", "change", cwd=dev)
    _git("push", "-q", "origin", "HEAD:main", cwd=dev)
    return _git("rev-parse", "--short", "HEAD", cwd=dev)


def test_behind_pulls_fast_forward_and_records_it(repos):
    remote, dev, pc = repos
    before = _git("rev-parse", "--short", "HEAD", cwd=pc)
    new = _push_change(dev)
    r = autopull.pull_once(pc)
    assert r["result"] == "갱신" and r["head_before"] == before and r["head_after"] == new and r["at"]
    assert _git("rev-parse", "--short", "HEAD", cwd=pc) == new and (pc / "a.txt").read_text(encoding="utf-8") == "2\n"
    assert autopull.STATE["result"] == "갱신" and autopull.STATE["head_after"] == new                       # 마지막 시도가 남는다
    assert autopull.pull_once(pc)["result"] == "최신"                                                          # 다시 돌리면 최신


def test_a_modified_tracked_file_holds_the_pull_and_loses_nothing(repos):
    remote, dev, pc = repos
    _push_change(dev)
    (pc / "a.txt").write_text("mine\n", encoding="utf-8")                                                      # 추적 파일 손 수정
    (pc / "climate_outlook_local.json").write_text("{}", encoding="utf-8")                                    # 덮개(gitignore) — 걸리면 안 된다
    (pc / "note.txt").write_text("untracked\n", encoding="utf-8")                                              # 추적 안 된 새 파일 — 걸리면 안 된다
    r = autopull.pull_once(pc)
    assert r["result"] == "보류" and "추적 파일 수정 1: a.txt" in r["reason"] and "버리지 않는다" in r["reason"]
    assert (pc / "a.txt").read_text(encoding="utf-8") == "mine\n" and r["head_after"] == r["head_before"]      # 아무것도 안 건드렸다
    (pc / "a.txt").write_text("1\n", encoding="utf-8")                                                         # 손 수정을 되돌리면(원문과 같아지면) 간다
    r = autopull.pull_once(pc)
    assert r["result"] == "갱신" and (pc / "climate_outlook_local.json").exists() and (pc / "note.txt").exists()


def test_a_diverged_local_commit_holds_and_a_dead_remote_fails_with_the_reason(repos):
    remote, dev, pc = repos
    _push_change(dev)
    (pc / "b.txt").write_text("local\n", encoding="utf-8")
    _git("add", "b.txt", cwd=pc)
    _git("commit", "-qm", "local only", cwd=pc)
    r = autopull.pull_once(pc)
    assert r["result"] == "보류" and "갈라짐" in r["reason"]
    _git("remote", "set-url", "origin", str(remote.parent / "no_such.git"), cwd=pc)
    r = autopull.pull_once(pc)
    assert r["result"] == "실패" and r["reason"].startswith("fetch:") and len(r["reason"]) > 8
    assert autopull.pull_once(pc, remote="origin", branch="no_such_branch")["result"] == "실패"


def test_status_lines_say_off_pending_and_each_result():
    assert autopull.status_line(0) == "자동 갱신 꺼짐(AGRODSS_AUTO_PULL_SEC=0)"
    assert autopull.status_line(600, {"result": None}) == "자동 갱신 대기(600초마다 저장소를 본다)"
    st = {"at": "2026-09-28T14:05:00+09:00", "result": "갱신", "head_before": "aaaaaaa", "head_after": "bbbbbbb", "reason": ""}
    assert autopull.status_line(600, st) == "자동 갱신 14:05 aaaaaaa → bbbbbbb — 새 코드로 다시 뜬다"
    assert autopull.status_line(600, dict(st, result="최신")) == "자동 갱신 14:05 최신"
    assert autopull.status_line(600, dict(st, result="보류", reason="갈라짐")) == "자동 갱신 14:05 보류: 갈라짐"
    assert autopull.status_line(600, dict(st, result="실패", reason="fetch: x")) == "자동 갱신 14:05 실패: fetch: x"
    assert autopull.running_lines(0) == "autopull=off\nautopull_at=\n"
    assert autopull.running_lines(600, st) == "autopull=updated\nautopull_at=2026-09-28T14:05:00\n"
    assert autopull.running_lines(600, {"result": "보류", "at": None}) == "autopull=held\nautopull_at=\n"
    for k in autopull.RESULTS:
        assert autopull.ASCII[k].isascii()


def test_the_loop_runs_once_soon_then_every_period_and_is_off_at_zero():
    calls = []
    stop = threading.Event()

    def once(root, remote, branch):
        calls.append((root, remote, branch))
        if len(calls) >= 3:
            stop.set()
        return {"result": "최신"}

    n = autopull.loop(stop, 0.01, Path("/r"), "origin", "main", once=once, first_wait=0.0)
    assert n == 3 and calls[0] == (Path("/r"), "origin", "main")
    stop0 = threading.Event()

    def once0(root, remote, branch):                      # 0 인데 불리면 스스로 멈추고(무한 회전 방지 — 주입 H 가 매달렸다) 아래 단언이 잡는다
        calls.append("zero")
        stop0.set()
        return {"result": "최신"}

    assert autopull.loop(stop0, 0, Path("/r"), once=once0) == 0 and "zero" not in calls                        # 0 = 끔 · 한 번도 안 부른다

    def boom(root, remote, branch):
        calls.append("boom")
        stop2.set()
        raise RuntimeError("git 없음")

    stop2 = threading.Event()
    autopull.loop(stop2, 0.01, Path("/r"), once=boom, first_wait=0.0)
    assert autopull.STATE["result"] == "실패" and "git 없음" in autopull.STATE["reason"]                          # 예외도 침묵이 아니다


def test_the_screen_shows_the_last_attempt_in_footer_changes_and_running(srv, monkeypatch):
    monkeypatch.setattr(config, "AUTO_PULL_SEC", 600.0)
    monkeypatch.setitem(autopull.STATE, "result", "보류")
    monkeypatch.setitem(autopull.STATE, "reason", "추적 파일 수정 1: data/grid/x.json")
    monkeypatch.setitem(autopull.STATE, "at", "2026-09-28T14:05:00+09:00")
    assert "자동 갱신 14:05 보류: 추적 파일 수정 1: data/grid/x.json" in serve.footer_text()
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", "/changes")
    body = c.getresponse().read().decode("utf-8", "replace")
    assert "자동 갱신 14:05 보류: 추적 파일 수정 1: data/grid/x.json" in body
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", "/running")
    raw = c.getresponse().read().decode("ascii")                                                                # 배치가 읽는다 — ASCII 여야 한다
    assert "autopull=held\n" in raw and "autopull_at=2026-09-28T14:05:00\n" in raw and raw.startswith("head=")
    monkeypatch.setattr(config, "AUTO_PULL_SEC", 0.0)
    assert "자동 갱신 꺼짐" in serve.footer_text()


def test_main_starts_the_pull_thread_next_to_the_head_watch_and_tests_keep_it_off():
    src = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")
    body = src[src.index("def main("):]
    body = body[:body.index("\ndef ", 10)] if "\ndef " in body[10:] else body
    assert "if config.AUTO_PULL_SEC > 0:" in body and 'name="agrodss-auto-pull"' in body and "autopull.loop(stop, config.AUTO_PULL_SEC, config.ROOT" in body
    assert body.index('name="agrodss-head-watch"') < body.index('name="agrodss-auto-pull"')                    # 재기동 감시가 먼저 선다 — pull 이 먼저 내려앉으면 아무도 안 본다
    assert config.AUTO_PULL_SEC == 0                                                                           # 검사 프로세스는 꺼져 있다(conftest)
    cf = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert 'setenv("AGRODSS_AUTO_PULL_SEC", "0")' in cf and 'setattr(_cfg, "AUTO_PULL_SEC", 0.0)' in cf
    assert 'AGRODSS_AUTO_PULL_SEC="0"' in (ROOT / "scripts" / "browser" / "walk.sh").read_text(encoding="utf-8")
    assert "GIT_TERMINAL_PROMPT" in (ROOT / "frontend" / "autopull.py").read_text(encoding="utf-8")            # 자격 증명 프롬프트에 매달리지 않는다
    assert "--ff-only" in (ROOT / "frontend" / "autopull.py").read_text(encoding="utf-8")
