# -*- coding: utf-8 -*-
# [M-13 · D-6] 내부 화면은 루프백에만 묶인다 — 거부와 통과를 둘 다 본다.
# 배선 검사: make_server 본문 안에서 assert_local 호출이 서버 생성보다 **앞**에 있다
# (형태 독립 — 인자 표현식·줄 번호·문자 창을 고정하지 않는다. 구역을 잘라 순서만 본다).
from __future__ import annotations

import ast
import inspect
import http.client
import threading
from pathlib import Path

import pytest

from frontend import config, render, serve

ROOT = Path(__file__).resolve().parent.parent


# ── 거부 ──────────────────────────────────────────────────────────────────────
def test_host_constant_is_loopback():
    assert config.HOST in {"127.0.0.1", "::1", "localhost"}


@pytest.mark.parametrize("bad", ["0.0.0.0", "", "192.168.0.10", "::"])
def test_assert_local_rejects_non_loopback(bad):
    with pytest.raises(RuntimeError):
        config.assert_local(bad)


# ── 통과 ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("ok", ["127.0.0.1", "localhost", "::1"])
def test_assert_local_accepts_loopback(ok):
    assert config.assert_local(ok) == ok


# ── 배선: 검증이 서버 생성보다 앞 ───────────────────────────────────────────────
def _calls_in_order(fn) -> list[str]:
    tree = ast.parse(inspect.getsource(fn))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            names.append(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    return names


def test_make_server_validates_host_before_binding():
    calls = _calls_in_order(serve.make_server)
    assert "assert_local" in calls, "루프백 검증 호출이 없다"
    assert "ThreadingHTTPServer" in calls, "서버 생성 호출이 없다"
    assert calls.index("assert_local") < calls.index("ThreadingHTTPServer"), "검증이 생성보다 뒤다"


# ── 화면: 모든 docs 가 렌더되고 대장이 첫 페이지다 ──────────────────────────────
def test_every_doc_renders():
    for name in serve.doc_list():
        status, body = serve.render_page(name)
        assert status == 200, name
        assert "<main>" in body


def test_root_is_ledger_with_badges():
    status, body = serve.render_page(config.LEDGER_DOC)
    assert status == 200
    # 머리의 건수 배지도 같은 class 를 쓴다 — 표 셀 안의 배지만 변별 표지다(문자열 겹침 주의).
    # 주입 실측(2026-09-18): 'class="st st-' 만 보면 치환을 지워도 통과했다.
    assert '<td><span class="st st-' in body, "표 셀 상태 배지가 없다 — 대장 렌더가 깨졌다"


def test_ledger_counts_ignore_header_vocabulary():
    text = (ROOT / "docs" / config.LEDGER_DOC).read_text(encoding="utf-8")
    counts = render.ledger_counts(text)
    assert sum(counts.values()) > 0
    # 규칙 4 의 "상태 열 값: 대기 · 진행 …" 줄은 표가 아니므로 세지 않는다
    assert counts["폐기"] == 0


def test_path_traversal_rejected():
    status, _ = serve.render_page("../CLAUDE.md")
    assert status == 404


# ── 실제 기동: 루프백에서 응답한다 ────────────────────────────────────────────
def test_server_serves_on_loopback(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)  # OS 가 빈 포트를 준다
    srv = serve.make_server()
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        # [M-13] 루트는 첫 채팅(재배 단위)으로 보낸다 — 목록이 있으면 /c/<id>, 없으면 /c/new
        assert resp.status == 302 and resp.getheader("Location", "").startswith("/c/")
        resp.read()
        conn.request("GET", resp.getheader("Location"))
        resp = conn.getresponse()
        assert resp.status == 200
        assert "agrodss" in resp.read().decode("utf-8")
    finally:
        srv.shutdown()
        srv.server_close()


# ── I-5 §5: 화면 코드는 원장을 직접 읽지 않는다 (배선 부재를 결정으로 고정) ───────
_ALLOWED_TOPLEVEL = {
    "__future__", "os", "re", "sys", "html", "subprocess", "webbrowser", "threading",
    "http", "urllib", "pathlib", "typing", "markdown", "frontend",
    "email",  # multipart/form-data 파서(표준 라이브러리) — 채팅 반입(M-13)
    "names",  # 작목 이름 사전·후보(U-14) — ingest 와 같은 규율: 원장은 모듈 함수를 통해서만, 파일을 직접 열지 않는다
    "ingest",  # 입력 화면(I-7)은 ingest 를 통해서만 1층에 쓴다 — 아래 검사가 원장 직접 접근을 막는다
    "datetime", "grid",  # 촬영 시점 알림 — 격자 지식(원장 아님)
    "judge",  # 3층 봉투만 받는다
}


def test_frontend_does_not_touch_layer1_sources_directly():
    # 4층은 판단(judge.run)을 통해서만 산출을 받는다 — 기상 원천을 직접 부르지 않는다
    src = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")
    assert "from ingest import kma" not in src and "kma." not in src


def test_judge_page_shows_kind_first(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    srv = serve.make_server()
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/judge")
        resp = conn.getresponse()
        page = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "판단함" in page and "수확 창 2026-10-14 ~ 2026-11-03" in page and "신뢰 등급" in page
        assert "위험 경보" in page and "회복 가능 위험" in page      # M-10 ② 도 같은 화면에
        assert "사실 인용" in page and "공시" in page                 # M-15 ④ 자재 인용
        assert "계획 대 실제" in page and "이행" in page              # M-10 ③
        conn.request("GET", "/events")
        resp = conn.getresponse()
        assert resp.status == 200 and "불이행 사유" in resp.read().decode("utf-8")
        body = "subject=p001-jjokpa-2026f&type=%EC%98%88%EC%B0%B0&observed_at=&note="
        conn.request("POST", "/events/add", body=body,
                     headers={"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(body))})
        resp = conn.getresponse()
        assert resp.status == 400 and "기록 안 됨" in resp.read().decode("utf-8")     # 대상 시각 없으면 거부
        assert "hourly_tmp" not in page
    finally:
        srv.shutdown()
        srv.server_close()


def test_frontend_never_opens_ledger_files_directly():
    # I-5 §5: 화면 코드가 data/ 아래 원장(index.jsonl · subjects.json)을 직접 열지 않는다
    for py in (ROOT / "frontend").glob("*.py"):
        src = py.read_text(encoding="utf-8")
        assert "index.jsonl" not in src and "subjects.json" not in src, py.name
        assert 'open("data' not in src and "/ \"data\"" not in src, py.name


def test_media_page_get_and_bad_register(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    srv = serve.make_server()
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/media")
        resp = conn.getresponse()
        page = resp.read().decode("utf-8")
        assert resp.status == 200 and "영상 반입" in page
        assert "지금 찍을 장면" in page and "기준점 후" in page   # 격자 촬영 칸이 화면에 실린다
        body = "key=inbox%3Anope.mp4&subject=p001-jjokpa-2026f&observed_at=&note="
        conn.request("POST", "/media/register", body=body,
                     headers={"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(body))})
        resp = conn.getresponse()
        assert resp.status == 400 and "등록 안 됨" in resp.read().decode("utf-8")
    finally:
        srv.shutdown()
        srv.server_close()


def test_frontend_imports_are_only_stdlib_markdown_and_frontend():
    for py in (ROOT / "frontend").glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            for m in mods:
                top = m.split(".")[0]
                assert top in _ALLOWED_TOPLEVEL, f"{py.name}: 허용되지 않은 import {m!r}"
