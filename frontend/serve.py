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
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

if __package__ in (None, ""):
    # `python frontend/serve.py` 로 직접 실행될 때 저장소 루트를 경로에 넣는다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frontend import config, render  # noqa: E402
from ingest import media  # noqa: E402  — 입력 화면은 ingest 를 통해서만 1층에 쓴다(원장 파일을 직접 열지 않는다)
from grid import capture as grid_capture  # noqa: E402  — 촬영 시점 알림(격자 지식, 원장 아님)


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
    parts = ['<div class="grp">입력</div>']
    cls = ' class="on"' if current == "/media" else ""
    parts.append(f'<a href="/media"{cls}>영상 반입 (I-7)</a>')
    parts.append('<div class="grp">문서</div>')
    for name in doc_list():
        cls = ' class="on"' if name == current else ""
        label = html.escape(name.removesuffix(".md"))
        parts.append(f'<a href="/doc/{html.escape(name)}"{cls}>{label}</a>')
    return "".join(parts)


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def media_page(message: str = "", error: str = "") -> tuple[int, str]:
    subjects = media.load_subjects()
    items = media.list_inbox()
    records = [media.public_view(r) for r in media.list_records()]
    watch = media.watch_dirs()
    out = ["<h1>영상 반입 — 관찰(영상) 1층 등록</h1>"]
    if error:
        out.append(f'<p class="err"><b>등록 안 됨</b> — {_e(error)}</p>')
    if message:
        out.append(f'<p class="ok">{_e(message)}</p>')
    out.append("<h2>지금 찍을 장면 (격자 촬영 칸)</h2><ul>")
    for s in subjects:
        h = grid_capture.hint_for(s, date.today())
        if h is None:
            out.append(f"<li><b>{_e(s['label'])}</b> — 격자 또는 기준점 없음</li>")
        elif h["stage"] is None:
            out.append(f"<li><b>{_e(s['label'])}</b> — 기준점 후 {h['day']}일: 격자 창 밖(단계 없음)</li>")
        else:
            what = f"<b>찍는다</b> — {_e(h['scene'])}" if h["shoot"] else "이 단계는 촬영 칸이 아니다"
            out.append(f"<li><b>{_e(s['label'])}</b> — 기준점 후 <b>{h['day']}일</b> · 단계 {_e(h['stage'])} "
                       f"({h['window'][0]}~{h['window'][1]}일) · {what}</li>")
    out.append("</ul>")
    out.append("<h2>어디서 들어오나</h2><ul>")
    out.append(f"<li>기본 inbox: <code>{_e(media.inbox_dir())}</code> — 여기 넣은 파일은 등록 시 <b>옮겨진다</b></li>")
    if watch:
        for w in watch:
            state = "" if w.is_dir() else " <b>(폴더 없음)</b>"
            out.append(f"<li>동기화 폴더(감시): <code>{_e(w)}</code>{state} — 읽기만, 등록 시 <b>복사</b>. 원본은 그대로</li>")
    else:
        out.append("<li>동기화 폴더: <b>미설정</b> — <code>.env</code> 에 <code>AGRODSS_WATCH_DIRS=…</code> "
                   "(휴대폰 카메라가 PC 로 동기화되는 폴더. OneDrive · 구글 드라이브 · iCloud 사진 · Syncthing)</li>")
    out.append("</ul>")
    out.append(f"<h2>등록 대기 ({len(items)})</h2>")
    if not items:
        out.append("<p>대기 중인 영상이 없다. 폴더에 영상이 들어오면 새로고침.</p>")
    for it in items:
        pr = it["probe"]
        auto = pr.get("creation_time")
        out.append('<form method="post" action="/media/register" class="reg">')
        out.append(f'<input type="hidden" name="key" value="{_e(it["key"])}">')
        out.append(f'<div><b>{_e(it["name"])}</b> <span class="meta">{it["bytes"] // (1 << 20)} MB · '
                   f'{_e(it["origin"])} · {_e(pr.get("width"))}×{_e(pr.get("height"))} · '
                   f'{_e(pr.get("duration_sec"))}s · 위치 {"있음" if pr.get("gps") else "없음"}</span></div>')
        if pr.get("error"):
            out.append(f'<div class="meta">메타 판독: {_e(pr["error"])}</div>')
        out.append('<label>재배 단위 <select name="subject">')
        for s in subjects:
            out.append(f'<option value="{_e(s["id"])}">{_e(s["label"])}</option>')
        out.append("</select></label>")
        if auto:
            out.append(f'<label>촬영 시각(메타, UTC) <input name="observed_at" value="{_e(auto)}" size="28"></label>')
        else:
            out.append('<label>촬영 시각 <input name="observed_at" placeholder="2026-09-18T15:30:00+09:00" size="28"> '
                       '<span class="meta">메타에 없음 — 직접 입력. 없으면 등록 안 됨</span></label>')
        out.append('<label>메모 <input name="note" size="40" placeholder="예: 파종 24일차, 잎 길이 15cm"></label>')
        out.append('<button type="submit">등록</button></form>')
    out.append(f"<h2>등록된 영상 ({len(records)})</h2>")
    if records:
        out.append("<table><tr><th>관측 시각</th><th>재배 단위</th><th>파일</th><th>해상도</th><th>길이</th>"
                   "<th>위치</th><th>시각 출처</th><th>메모</th></tr>")
        for r in sorted(records, key=lambda r: r["observed_at"], reverse=True):
            out.append(f'<tr><td>{_e(r["observed_at"])}</td><td>{_e(r["subject"])}</td><td><code>{_e(r["file"])}</code></td>'
                       f'<td>{_e(r.get("width"))}×{_e(r.get("height"))}</td><td>{_e(r.get("duration_sec"))}s</td>'
                       f'<td>{_e(r["gps"])}</td><td>{_e(r.get("observed_at_source"))}</td><td>{_e(r.get("note"))}</td></tr>')
        out.append("</table>")
    else:
        out.append("<p>아직 없다.</p>")
    style = ("<style>.reg{border:1px solid var(--line);border-radius:6px;padding:10px;margin:8px 0;display:grid;gap:6px}"
             ".reg label{display:block}.err{color:var(--drop-fg);background:var(--drop);padding:6px 10px;border-radius:4px}"
             ".ok{color:var(--done-fg);background:var(--done);padding:6px 10px;border-radius:4px}</style>")
    meta = "1층 관찰(영상) — 촬영 시각 · 출처 · 해상도가 붙어야 등록된다. 좌표는 화면에 내지 않는다"
    footer = f"HEAD {git_head_short()} · {config.HOST}:{config.PORT} · 외부 배포 없음(D-6)"
    return (400 if error else 200), render.page("agrodss — 영상 반입", nav_html("/media"), style + "".join(out), meta, footer)


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
        elif p == "/media":
            status, body = media_page()
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

    def do_POST(self) -> None:  # noqa: N802
        p = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(length, 1 << 20)).decode("utf-8", errors="replace")
        form = {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}
        if p == "/media/register":
            try:
                rec = media.register(form.get("key", ""), form.get("subject", ""),
                                     form.get("observed_at") or None, form.get("note", ""))
                status, body = media_page(message=f"등록됨 {rec['id']} · 관측 {rec['observed_at']} · {rec['file']}")
            except media.RegisterError as e:
                status, body = media_page(error=str(e))
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
