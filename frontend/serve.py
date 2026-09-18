# -*- coding: utf-8 -*-
# FILE: frontend/serve.py
# ROLE: [M-13] 내부 화면 — 별도 앱, localhost 전용, 브라우저 새 창. 매 요청마다 docs/ 를
#       다시 읽으므로 문서를 고치면 새로고침에 그대로 보인다(진행하는 대로 화면).
#
# 층 구조: 이 앱은 4층(전달)이다. 지금은 docs/ 만 읽는다. 앞으로 DSS 산출 봉투·몰 화면
# 데이터를 받되, 1·2층 원장을 직접 읽는 import 는 두지 않는다(I-5 §5 — 검사로 고정).
from __future__ import annotations

import html
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

if __package__ in (None, ""):
    # `python frontend/serve.py` 로 직접 실행될 때 저장소 루트를 경로에 넣는다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frontend import config, render  # noqa: E402


def git_head_short() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT,
            capture_output=True, encoding="utf-8", errors="replace", timeout=5,
        )
        return r.stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def doc_list() -> list[str]:
    present = sorted(p.name for p in config.DOCS_DIR.glob("*.md"))
    ordered = [n for n in config.NAV_ORDER if n in present]
    return ordered + [n for n in present if n not in ordered]


def nav_html(current: str) -> str:
    parts = ['<div class="grp">agrodss</div>']
    for name in doc_list():
        cls = ' class="on"' if name == current else ""
        label = html.escape(name.removesuffix(".md"))
        parts.append(f'<a href="/doc/{html.escape(name)}"{cls}>{label}</a>')
    return "".join(parts)


def render_page(name: str) -> tuple[int, str]:
    path = config.DOCS_DIR / name
    if not name.endswith(".md") or "/" in name or "\\" in name or not path.is_file():
        return 404, render.page("없음", nav_html(""), "<h1>없는 문서</h1>", "", "")
    text = path.read_text(encoding="utf-8")
    body = render.md_to_html(text)
    meta = f"정본 <code>docs/{html.escape(name)}</code> · 화면은 렌더 사본 — 갱신은 파일에서"
    if name == config.LEDGER_DOC:
        counts = render.ledger_counts(text)
        meta += ' · <span class="counts">' + "".join(
            f'<span class="st st-{s}">{s} {n}</span>' for s, n in counts.items()
        ) + "</span>"
    footer = f"HEAD {git_head_short()} · {config.HOST}:{config.PORT} · 외부 배포 없음(D-6)"
    return 200, render.page(f"agrodss — {name}", nav_html(name), body, meta, footer)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        p = urlparse(self.path).path
        if p == "/":
            status, body = render_page(config.LEDGER_DOC)
        elif p.startswith("/doc/"):
            status, body = render_page(unquote(p[len("/doc/"):]))
        else:
            status, body = 404, render.page("없음", nav_html(""), "<h1>없는 경로</h1>", "", "")
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:  # 조용히
        pass


def make_server() -> ThreadingHTTPServer:
    host = config.assert_local(config.HOST)  # [D-6] 루프백 검증이 서버 생성보다 앞에 있다
    return ThreadingHTTPServer((host, config.PORT), Handler)


def main(open_browser: bool = True) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    srv = make_server()
    url = f"http://{config.HOST}:{config.PORT}/"
    print(f"[agrodss 내부 화면] {url}  (Ctrl+C 로 종료)")
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main(open_browser="--no-browser" not in sys.argv)
