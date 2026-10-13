# -*- coding: utf-8 -*-
# [2026-10-14 · 앞날 걷기 목록을 잃었다] 10-13 의 앞날 걷기는 스크래치패드의 측정 스크립트로 쟀고 결과 표도 거기 있었다 — 세션 컨테이너가 회수되며
# 둘 다 사라져 대장 페이지 · 핸드오버에는 풀 수 없는 번호(F8 · F10 …)만 남았다. 답을 날짜로 걷는 도구를 저장소에 둔다(scripts/answer_walk.py).
# 이 검사가 지키는 것: ① 돌아간다(날짜 · 물음 · 답이 나온다) ② **운영 data 를 건드리지 않는다**(전후 해시) ③ 격리 목록은 하나(verify_claims.isolate —
# 자기 목록을 두면 conftest · walk.sh 와 갈린다) ④ --use 가 정말 그 밭의 용도로 걷는다(용도를 넣은 뒤의 답이 다르다 — 넣기 전후를 가르는 도구다).
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"


def _data_hash() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "data").rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(ROOT)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _call(*args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("AGRODSS_")}      # 부르는 쪽 격리에 기대지 않는다 — 도구가 스스로 격리해야 한다
    env.update({"TZ": "Asia/Seoul", "PYTHONIOENCODING": "utf-8"})
    return subprocess.run([sys.executable, "-B", "-m", "scripts.answer_walk", *args], cwd=ROOT, capture_output=True,
                          encoding="utf-8", errors="replace", env=env, timeout=600)


def _run(*args: str) -> str:
    r = _call(*args)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    return r.stdout


def test_the_walk_answers_by_date_and_leaves_data_alone():
    before = _data_hash()
    out = _run("2026-10-14", "--only", SID, "--ask", "수확 언제 해요")
    assert f"===== 2026-10-14 · {SID} · 심은 뒤 50일 =====" in out and "-- 수확 언제 해요" in out
    answer = out.split("-- 수확 언제 해요", 1)[1].strip()
    assert len(answer) > 20, out                                                     # 빈 답이 아니다
    assert _data_hash() == before                                                    # 운영 data 그대로


def test_use_walks_the_field_with_that_use():
    plain = _run("2026-10-14", "--only", SID, "--ask", "수확 언제 해요").split("-- 수확 언제 해요", 1)[1]
    before = _data_hash()
    seed = _run("2026-10-14", "--only", SID, "--use", "종구 생산", "--ask", "수확 언제 해요")
    assert _data_hash() == before                                                    # [재검토 F7] 쓰는 유일한 길(--use · 덮개 쓰기)도 운영 data 를 안 건드린다
    assert "· 용도 종구 생산 =====" in seed
    assert seed.split("-- 수확 언제 해요", 1)[1] != plain and "종구" in seed.split("-- 수확 언제 해요", 1)[1]   # 넣은 뒤의 답이 다르다


def test_add_walks_a_second_crop_and_an_unknown_only_is_refused():
    """[재검토 WF-2] 씨앗 등록부에는 쪽파 하나뿐이라 대파 행(W-08 …)을 그 「어디서」 로 다시 잴 수 없었다 — --add 로 격리 사본에 세운다.
    없는 --only 는 빈 출력 · rc 0 이었다(측정이 아무것도 안 했는데 초록) — 이유와 rc 2 다."""
    before = _data_hash()
    out = _run("2026-10-14", "--add", "대파:2026 가을:2026-09-01", "--only", "p001-대파-2026가을", "--ask", "웃거름 언제 줘요")
    assert _data_hash() == before
    assert "===== 2026-10-14 · p001-대파-2026가을 · 심은 뒤 43일 =====" in out and "-- 웃거름 언제 줘요" in out
    # [재재검토] 화면 행(W-12 · W-29)도 같은 차림으로 — --screen 이 그 격리 사본에 화면을 띄워 보이는 글을 낸다(물음 없이 화면만)
    before = _data_hash()
    out = _run("2026-10-14", "--add", "대파:2026 가을:2026-10-11", "--only", "p001-대파-2026가을", "--screen", "/c/p001-대파-2026가을")
    assert _data_hash() == before
    assert "===== 2026-10-14 · 화면 /c/p001-대파-2026가을 =====" in out and "-- HTTP 200" in out and "대파 · 2026 가을" in out and "<" not in out
    assert "-- 수확 언제 해요" not in out                                              # 화면만 볼 때는 물음을 안 돌린다
    r = _call("2026-10-14", "--only", "p001-없는-작목", "--ask", "수확 언제 해요")
    assert r.returncode == 2 and "걸을 재배 단위가 없다" in r.stderr and SID in r.stderr and "=====" not in r.stdout
    r = _call("2026-10-14", "--add", "대파", "--ask", "수확 언제 해요")
    assert r.returncode == 2 and "작목:작기" in r.stderr


def test_the_isolated_copy_answers_materials_like_the_farm_does():
    """[재검토 F6] 격리가 유기 자재 정본을 **없는 경로**로 가리켜 자재 답이 농가가 받는 답과 달랐다 — 격리 사본에도 정본이 있어야 같은 답이다."""
    out = _run("2026-10-14", "--only", SID, "--ask", "약 뭐 쳐요")
    m = __import__("re").search(r"유기질 비료\((\d+)건\)", out)
    assert m and int(m.group(1)) > 0, out[-400:]


def test_one_isolation_list():
    src = (ROOT / "scripts" / "answer_walk.py").read_text(encoding="utf-8")
    assert "verify_claims.isolate()" in src
    own = {w for w in __import__("re").findall(r"AGRODSS_[A-Z_]+", src)}
    assert own <= {"AGRODSS_TODAY"}, own                                               # 날짜 말고는 제 목록을 두지 않는다
