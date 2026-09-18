# -*- coding: utf-8 -*-
# FILE: frontend/render.py
# ROLE: docs/*.md → HTML 조각. 대장 상태 셀에 배지를 붙인다. 정본 렌더는 이 파일 하나다 —
#       docs/render_backlog.py(CLI)도 여기를 부른다(어휘·규칙 두 벌 금지).
from __future__ import annotations

import re
from pathlib import Path

import markdown

STATES: tuple[str, ...] = ("대기", "진행", "완료", "보류", "폐기")
_STATE_CELL = re.compile(r"<td>(대기|진행|완료|보류|폐기)([^<]*)</td>")


def md_to_html(text: str) -> str:
    body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    return _STATE_CELL.sub(
        lambda m: f'<td><span class="st st-{m.group(1)}">{m.group(1)}{m.group(2)}</span></td>',
        body,
    )


def render_doc(path: Path) -> str:
    return md_to_html(path.read_text(encoding="utf-8"))


def ledger_counts(text: str) -> dict[str, int]:
    """대장 본문에서 상태별 건수 — 표 행의 상태 셀만 센다(머리글의 상태 어휘는 제외)."""
    counts = {s: 0 for s in STATES}
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| ID") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        # 상태 열은 표마다 위치가 다르다(D/I/M/U 는 4번째, R 은 3번째) — 셀 전체를 훑는다
        for c in cells:
            base = c.split("(")[0]
            if base in counts:
                counts[base] += 1
                break
    return counts


CSS = """
:root { --bg:#fff; --fg:#1a1a1a; --muted:#6b6b6b; --line:#e3e3e3; --head:#f5f5f5; --nav:#fafafa;
  --wait:#e8eef8; --wait-fg:#2b4c8c; --run:#fff3d6; --run-fg:#8a5a00; --done:#e3f4e6; --done-fg:#1f6b35;
  --hold:#f0f0f0; --hold-fg:#555; --drop:#f8e3e3; --drop-fg:#8c2b2b; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#161616; --fg:#e8e8e8; --muted:#a0a0a0; --line:#333; --head:#222; --nav:#1c1c1c;
  --wait:#1f2a40; --wait-fg:#9db7ea; --run:#3a2e12; --run-fg:#f0c060; --done:#16301c; --done-fg:#7fd095;
  --hold:#2a2a2a; --hold-fg:#bbb; --drop:#3a1a1a; --drop-fg:#f09090; } }
:root[data-theme="dark"] {
  --bg:#161616; --fg:#e8e8e8; --muted:#a0a0a0; --line:#333; --head:#222; --nav:#1c1c1c;
  --wait:#1f2a40; --wait-fg:#9db7ea; --run:#3a2e12; --run-fg:#f0c060; --done:#16301c; --done-fg:#7fd095;
  --hold:#2a2a2a; --hold-fg:#bbb; --drop:#3a1a1a; --drop-fg:#f09090; }
html,body { background:var(--bg); color:var(--fg); margin:0; }
body { font:14px/1.55 -apple-system,"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif; }
.wrap { display:flex; min-height:100vh; }
nav { width:240px; flex:none; background:var(--nav); border-right:1px solid var(--line); padding:16px 12px; box-sizing:border-box; }
nav a { display:block; padding:4px 8px; color:var(--fg); text-decoration:none; border-radius:4px; font-size:13px; }
nav a.on { background:var(--head); font-weight:600; }
nav .grp { color:var(--muted); font-size:11px; margin:12px 8px 4px; text-transform:uppercase; }
main { flex:1; padding:16px 24px; max-width:1100px; box-sizing:border-box; min-width:0; }
h1 { font-size:20px; margin:0 0 4px; } h2 { font-size:16px; margin:28px 0 8px; padding-top:12px; border-top:1px solid var(--line); }
h3 { font-size:14px; margin:20px 0 6px; }
code { font-size:12.5px; background:var(--head); padding:1px 4px; border-radius:3px; }
pre { background:var(--head); padding:10px; overflow-x:auto; border-radius:4px; }
table { border-collapse:collapse; width:100%; margin:8px 0 12px; font-size:13px; display:block; overflow-x:auto; }
th,td { border:1px solid var(--line); padding:5px 8px; text-align:left; vertical-align:top; }
th { background:var(--head); position:sticky; top:0; }
.st { display:inline-block; padding:1px 8px; border-radius:10px; font-size:12px; white-space:nowrap; }
.st-대기 { background:var(--wait); color:var(--wait-fg); } .st-진행 { background:var(--run); color:var(--run-fg); }
.st-완료 { background:var(--done); color:var(--done-fg); } .st-보류 { background:var(--hold); color:var(--hold-fg); }
.st-폐기 { background:var(--drop); color:var(--drop-fg); }
.meta { color:var(--muted); font-size:12px; margin-bottom:12px; }
.counts span { margin-right:10px; }
footer { color:var(--muted); font-size:12px; border-top:1px solid var(--line); margin-top:32px; padding-top:8px; }
@media (max-width: 720px) { .wrap { display:block; } nav { width:auto; border-right:0; border-bottom:1px solid var(--line); } main { padding:16px; } }
"""


def page(title: str, nav_html: str, body_html: str, meta_html: str, footer_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{CSS}</style></head>
<body><div class="wrap"><nav>{nav_html}</nav><main><div class="meta">{meta_html}</div>{body_html}<footer>{footer_html}</footer></main></div></body></html>"""
