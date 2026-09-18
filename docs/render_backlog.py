# -*- coding: utf-8 -*-
# 읽기 전용 렌더 CLI — docs/agrodss_backlog.md → 단일 HTML 파일.
# 정본 렌더는 frontend/render.py 다(여기서는 부르기만 한다). 세션 패널에 띄우는 임시 수단이며
# M-13 관문(별도 앱 화면)을 채우지 않는다.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from frontend import render  # noqa: E402

src = Path(sys.argv[1])
out = Path(sys.argv[2])
text = src.read_text(encoding="utf-8")
counts = render.ledger_counts(text)
meta = "정본: docs/agrodss_backlog.md · 렌더 사본 · " + " ".join(f"{s} {n}" for s, n in counts.items())
out.write_text(render.page("agrodss 작업대장", "", render.md_to_html(text), meta, ""), encoding="utf-8")
print("written", out)
