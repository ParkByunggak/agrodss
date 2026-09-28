# -*- coding: utf-8 -*-
# FILE: frontend/autopull.py
# ROLE: [U-39 자동 갱신 · 발행자 등재 2026-09-28 "⓪ 자동 pull 등재하자"] 화면 프로세스가 스스로 저장소를 따라간다.
#   드리프트(커밋 완료 ≠ 반영 완료)가 이 트랙 최다 사고다 — 27커밋·하루 넘게 옛 코드가 돌았고, 매번 사람이 update.bat 을 눌러야 했다.
#   재기동은 이미 스스로 한다(watch_head · execv). 빠진 것은 **pull 자체**였다. 스케줄러는 발행자 PC 에서 거부당했으므로(2026-09-21
#   "액세스가 거부되었습니다") 서버 안 스레드로 한다.
#
#   규율(update.bat :preserve 와 같은 선 · 더 보수적):
#     · fast-forward 만(`--ff-only`) — 병합·리베이스·되돌리기 없음. 갈라졌으면 **보류**하고 이유를 말한다.
#     · 추적 파일에 로컬 수정이 있으면 **보류** — 치우지도 되돌리지도 않는다(update.bat 은 _local_backup 으로 치우지만 이것은 사람이 누른 것이고,
#       자동은 아무것도 버리지 않는다). 덮개(*_local · gitignore)는 추적이 아니라 걸리지 않는다.
#     · 실패는 조용히 넘기지 않는다 — 마지막 시도의 결과·이유가 꼬리 · /changes · /running 에 남는다(침묵이 가장 나쁜 실패).
#     · 자격 증명 프롬프트에 매달리지 않는다(GIT_TERMINAL_PROMPT=0) — 비공개로 바뀌면 "실패: fetch …" 로 보인다.
#     · 원천을 부르는 일이라 검사·걷기는 AGRODSS_AUTO_PULL_SEC=0 으로 끈다(격리 짝).
from __future__ import annotations

import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

RESULTS = ("갱신", "최신", "보류", "실패")                          # 한 번의 시도가 낼 수 있는 결과 — 이 넷뿐
ASCII = {"갱신": "updated", "최신": "fresh", "보류": "held", "실패": "failed", None: "pending"}   # /running 용(배치가 읽는다 · cp949)
STATE: dict[str, Any] = {"at": None, "result": None, "reason": "", "head_before": None, "head_after": None, "enabled": True}
_lock = threading.Lock()


def _git(args: list[str], cwd: Path, timeout: float = 60) -> tuple[int, str]:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, f"{type(e).__name__}: {e}"
    return r.returncode, (r.stdout + r.stderr).strip()


def pull_once(root: Path, remote: str = "origin", branch: str = "main", git: Callable[..., tuple[int, str]] = _git) -> dict[str, Any]:
    """한 번의 시도. 돌려주는 것: {result, reason, head_before, head_after, at}. 결과는 RESULTS 중 하나 — 침묵은 없다."""
    at = datetime.now().astimezone().isoformat(timespec="seconds")
    rc, head = git(["rev-parse", "HEAD"], root, 10)
    head = head.strip() if rc == 0 else "?"
    out: dict[str, Any] = {"at": at, "head_before": head[:7], "head_after": head[:7], "result": None, "reason": ""}

    def done(result: str, reason: str = "") -> dict[str, Any]:
        out["result"], out["reason"] = result, reason
        with _lock:
            STATE.update(out)
        return out

    rc, log = git(["fetch", "--quiet", remote, branch], root, 60)
    if rc != 0:
        return done("실패", f"fetch: {log[-160:] or '이유 없음'}")
    rc, target = git(["rev-parse", "FETCH_HEAD"], root, 10)
    if rc != 0:
        return done("실패", f"FETCH_HEAD: {target[-160:]}")
    target = target.strip()
    if target == head:
        return done("최신")
    rc, _ = git(["merge-base", "--is-ancestor", head, target], root, 10)
    if rc != 0:
        return done("보류", "갈라짐 — 이 PC 의 커밋이 원격에 없다(세션 커밋으로만 · update.bat 도 같은 자리에서 멈춘다)")
    rc, st = git(["status", "--porcelain", "--untracked-files=no"], root, 20)
    dirty = [(ln.strip().split(None, 1) + [""])[1] or ln.strip() for ln in st.splitlines() if ln.strip()] if rc == 0 else []   # "XY path" — 앞 두 글자가 상태
    if rc != 0:
        return done("실패", f"status: {st[-160:]}")
    if dirty:
        return done("보류", f"추적 파일 수정 {len(dirty)}: {' · '.join(dirty[:3])}{' …' if len(dirty) > 3 else ''} — 자동은 아무것도 버리지 않는다(덮개 *_local 은 안 걸린다 · 추적 파일은 세션 커밋으로만)")
    rc, log = git(["pull", "--ff-only", "--quiet", remote, branch], root, 120)
    if rc != 0:
        return done("실패", f"pull: {log[-160:] or '이유 없음'}")
    rc, after = git(["rev-parse", "HEAD"], root, 10)
    out["head_after"] = (after.strip() if rc == 0 else "?")[:7]
    return done("갱신")                                          # HEAD 가 바뀌었다 — watch_head 가 보고 새 코드로 다시 뜬다


def status_line(sec: float, state: dict[str, Any] | None = None) -> str:
    """꼬리 · /changes 용 한 줄(사람 말). 꺼짐 · 아직 · 결과 넷."""
    s = state if state is not None else STATE
    if not sec or sec <= 0:
        return "자동 갱신 꺼짐(AGRODSS_AUTO_PULL_SEC=0)"
    if not s.get("result"):
        return f"자동 갱신 대기({int(sec)}초마다 저장소를 본다)"
    when = str(s.get("at") or "")[11:16]
    r = s["result"]
    if r == "갱신":
        return f"자동 갱신 {when} {s.get('head_before')} → {s.get('head_after')} — 새 코드로 다시 뜬다"
    if r == "최신":
        return f"자동 갱신 {when} 최신"
    return f"자동 갱신 {when} {r}: {s.get('reason', '')}"


def running_lines(sec: float, state: dict[str, Any] | None = None) -> str:
    """/running 용 ASCII 키=값 — 배치가 읽는다."""
    s = state if state is not None else STATE
    if not sec or sec <= 0:
        return "autopull=off\nautopull_at=\n"
    r = ASCII.get(s.get("result"), "pending")
    at = str(s.get("at") or "")[:19].replace(" ", "T")
    return f"autopull={r}\nautopull_at={at}\n"


def loop(stop: threading.Event, sec: float, root: Path, remote: str = "origin", branch: str = "main",
         once: Callable[..., dict[str, Any]] = pull_once, first_wait: float | None = None) -> int:
    """sec 마다 pull_once. 첫 시도는 기동 뒤 곧(기본 30초 · sec 보다 길지 않게) — PC 를 켠 뒤 오래 옛 코드로 있지 않게. 돌린 횟수를 돌려준다."""
    if not sec or sec <= 0:
        return 0
    n = 0
    wait = min(sec, 30.0) if first_wait is None else first_wait
    while not stop.wait(wait):
        try:
            once(root, remote, branch)
        except Exception as e:                                   # noqa: BLE001 — 스레드가 죽으면 침묵이 된다. 실패로 남기고 계속 본다
            with _lock:
                STATE.update({"at": datetime.now().astimezone().isoformat(timespec="seconds"), "result": "실패", "reason": f"{type(e).__name__}: {e}"})
        n += 1
        wait = sec
    return n
