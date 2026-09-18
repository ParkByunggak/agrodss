# 읽기 전용 렌더 스크립트 — docs/agrodss_backlog.md → HTML (측정·표시용, 소스 수정 없음)
import re
import sys
from pathlib import Path

import markdown

src = Path(sys.argv[1]).read_text(encoding="utf-8")
out = Path(sys.argv[2])

body = markdown.markdown(src, extensions=["tables", "fenced_code"])

# 상태 셀에 색 배지 — 텍스트는 그대로 두고 class 만 붙인다
STATES = ["대기", "진행", "완료(초안)", "완료", "보류", "폐기"]
for s in STATES:
    body = body.replace(f"<td>{s}</td>", f'<td><span class="st st-{s.split("(")[0]}">{s}</span></td>')

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agrodss 작업대장</title>
<style>
:root {{
  --bg: #ffffff; --fg: #1a1a1a; --muted: #6b6b6b; --line: #e3e3e3; --head: #f5f5f5;
  --wait: #e8eef8; --wait-fg: #2b4c8c; --run: #fff3d6; --run-fg: #8a5a00;
  --done: #e3f4e6; --done-fg: #1f6b35; --hold: #f0f0f0; --hold-fg: #555; --drop: #f8e3e3; --drop-fg: #8c2b2b;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #161616; --fg: #e8e8e8; --muted: #a0a0a0; --line: #333; --head: #222;
    --wait: #1f2a40; --wait-fg: #9db7ea; --run: #3a2e12; --run-fg: #f0c060;
    --done: #16301c; --done-fg: #7fd095; --hold: #2a2a2a; --hold-fg: #bbb; --drop: #3a1a1a; --drop-fg: #f09090;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #161616; --fg: #e8e8e8; --muted: #a0a0a0; --line: #333; --head: #222;
  --wait: #1f2a40; --wait-fg: #9db7ea; --run: #3a2e12; --run-fg: #f0c060;
  --done: #16301c; --done-fg: #7fd095; --hold: #2a2a2a; --hold-fg: #bbb; --drop: #3a1a1a; --drop-fg: #f09090;
}}
html, body {{ background: var(--bg); color: var(--fg); }}
body {{ margin: 0; padding: 16px; font: 14px/1.55 -apple-system, "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; }}
main {{ max-width: 1100px; margin: 0 auto; }}
h1 {{ font-size: 20px; margin: 0 0 4px; }}
h2 {{ font-size: 16px; margin: 28px 0 8px; padding-top: 12px; border-top: 1px solid var(--line); }}
p, li {{ color: var(--fg); }}
code {{ font-size: 12.5px; background: var(--head); padding: 1px 4px; border-radius: 3px; }}
table {{ border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 13px; display: block; overflow-x: auto; }}
th, td {{ border: 1px solid var(--line); padding: 5px 8px; text-align: left; vertical-align: top; }}
th {{ background: var(--head); position: sticky; top: 0; }}
td:first-child {{ white-space: nowrap; font-weight: 600; }}
.st {{ display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; white-space: nowrap; }}
.st-대기 {{ background: var(--wait); color: var(--wait-fg); }}
.st-진행 {{ background: var(--run); color: var(--run-fg); }}
.st-완료 {{ background: var(--done); color: var(--done-fg); }}
.st-보류 {{ background: var(--hold); color: var(--hold-fg); }}
.st-폐기 {{ background: var(--drop); color: var(--drop-fg); }}
.meta {{ color: var(--muted); font-size: 12px; margin-bottom: 12px; }}
</style>
</head>
<body>
<main>
<div class="meta">정본: docs/agrodss_backlog.md · 이 화면은 렌더 사본이다 — 갱신은 파일에서</div>
{body}
</main>
</body>
</html>
"""
out.write_text(html, encoding="utf-8")
print("written", out, len(html), "bytes")
