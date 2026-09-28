# -*- coding: utf-8 -*-
# [U-19 · D-13 · 2026-09-27] 작업대장 페이지 생성기가 저장소에 있다(스크래치패드에서 옮김 — U-35 형태). 본다: 대장 정본에서 페이지가 나온다 ·
# 머리에 커밋 해시는 하나까지 · 페이지에 모델 식별자 0 · 지번 주소 패턴 0(도구·파일 이름은 통과) · 회차마다 다시 쓰는 두 목록이 비지 않는다 ·
# CLI 는 준 경로 하나에만 쓴다(저장소 바이트 불변).
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

from scripts import build_ledger_page as blp

ROOT = Path(__file__).resolve().parent.parent


def test_the_page_comes_from_the_backlog_and_names_the_running_head():
    assert "정본 docs/agrodss_backlog.md" in blp.page and blp.head and blp.head in blp.page
    assert "최선의 다음 한 수" in blp.page and "발행자 몫 — 지금" in blp.page and "세션 몫" in blp.page
    assert len(blp.ids) >= 80 and str(len(blp.ids)) in blp.page                   # 대장 항목 수가 머리에 실린다
    assert blp.check_page(blp.page) == []                                            # 지금 페이지는 래칫을 지난다


def test_the_head_carries_at_most_one_commit_hash():
    assert len(set(re.findall(r"\b[0-9a-f]{7}\b", blp.BEST[0]))) <= 1                # U-19 — 지금의 한 수 하나
    assert blp.BEST[0].startswith("<b>") and blp.BEST[1]                             # 머리(굵게) · 이유


def test_the_guard_catches_model_names_and_addresses_but_passes_tool_names():
    assert blp.check_page("CLAUDE.md · .claude/settings.json · Claude 형식 · 하면 3건 자리 3곳 칸 3·4 3~4월 12-3 2026-09-27") == []
    assert blp.check_page("Fable 5.1") and blp.check_page("claude-fable-5-1") and blp.check_page("Opus") and blp.check_page("anthropic")
    assert blp.check_page("괴산군 연풍면 원풍리 123-4") == ["지번 주소 · PNU 패턴"]
    assert blp.check_page("12번지") and blp.check_page("x 1234567890123456789 y") and blp.check_page("x 123456789012345678 y") == []


def test_the_two_todo_lists_are_rewritten_each_round_and_not_empty():
    for lst in (blp.NEXT_PUBLISHER, blp.NEXT_SESSION):
        assert lst and all(isinstance(t, tuple) and len(t) == 2 and t[0] and t[1] for t in lst)
    joined = " ".join(a + b for a, b in blp.NEXT_PUBLISHER)
    assert "update.bat" in joined and "D-18" in joined                              # 발행자 몫의 첫 줄은 언제나 라이브 반영 · 열린 결정


def test_the_publisher_list_never_tells_them_to_hand_edit_a_tracked_data_file():
    """[순서 함정 전수 2026-09-28] ②·②b 가 "직접 하시면 data/grid/… 에 넣으라" 고 안내했다 — 추적 파일의 손 수정은 다음 update.bat 이 되돌린다
    (장기 전망에서 같은 함정을 잡은 날 같은 형태를 세니 둘 더). 발행자 몫 목록은 추적 파일을 손으로 고치라고 말하지 않는다 — 덮개(*_local)는 된다."""
    joined = " ".join(a + b for a, b in blp.NEXT_PUBLISHER)
    assert "직접 하시면" not in joined and "직접 넣" not in joined
    for tracked in ("data/grid/", "climate_outlook.json</code> 을 열어", "crop_names.csv 에"):
        for verb in ("에 넣", "을 열어", "더하고"):
            assert f"{tracked}{verb}" not in joined, (tracked, verb)
    assert "climate_outlook_local.json" in joined                                   # 손 수정의 자리는 덮개


def test_the_todo_lists_render_their_own_html_and_are_not_numbered_twice():
    """[발행자 붙임 2026-09-28] 머리(k)만 escape 해 <span style=…>·<code> 가 글자 그대로 나갔고, <ol> 번호 위에 ⓪①② 표지가 또 있어 "1. ⓪" 로 두 번 셌다.
    두 목록 구역 안에 escape 된 태그가 없고, 목록은 번호 없는 <ul> 이다."""
    for head in ("발행자 몫 — 지금", "세션 몫 — 지시하면 이 순서로"):
        i = blp.page.index(f"<h2>{head}</h2>")
        block = blp.page[i:blp.page.index("</section>", i)]
        assert block.startswith(f"<h2>{head}</h2><ul>") and "&lt;span" not in block and "&lt;code" not in block and "&lt;b&gt;" not in block, head
        assert "<ol>" not in block
    src = (ROOT / "scripts" / "build_ledger_page.py").read_text(encoding="utf-8")
    li_src = src[src.index("def li("):src.index("\n\n", src.index("def li("))]
    assert "html.escape" not in li_src                                              # 머리도 본문도 저자 HTML — 어느 쪽도 escape 하지 않는다


def test_the_cli_writes_only_the_given_file(tmp_path):
    watched = sorted(p for p in (ROOT / "docs").glob("*.md")) + [ROOT / "scripts" / "build_ledger_page.py"]
    before = hashlib.sha1(b"".join(p.read_bytes() for p in watched)).hexdigest()
    out = tmp_path / "ledger.html"
    r = subprocess.run([sys.executable, "-B", "scripts/build_ledger_page.py", str(out)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and out.exists() and "written" in r.stdout, r.stdout + r.stderr
    assert hashlib.sha1(b"".join(p.read_bytes() for p in watched)).hexdigest() == before
    r2 = subprocess.run([sys.executable, "-B", "scripts/build_ledger_page.py"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r2.returncode == 2 and "쓰는 법" in r2.stdout                            # 경로 없이는 아무것도 안 쓴다
    src = (ROOT / "scripts" / "build_ledger_page.py").read_text(encoding="utf-8")
    assert src.count("write_text(") == 1 and "_UNUSED_BEST" not in src               # 쓰는 곳 하나 · 옛 회차 서술은 싣지 않는다
