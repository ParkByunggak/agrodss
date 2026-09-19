# -*- coding: utf-8 -*-
# [2026-09-19 발행자 PC] markdown 모듈이 없으면 채팅 화면까지 못 떴다 — 문서 렌더만 원문으로 대체하고 나머지는 산다.
from __future__ import annotations

from frontend import config, render, serve


def test_md_to_html_falls_back_to_pre_without_markdown(monkeypatch):
    monkeypatch.setattr(render, "markdown", None)
    out = render.md_to_html("# 제목\n\n| a | b |\n|---|---|\n| 완료 | x |\n")
    assert out.startswith(render.MISSING_MARKDOWN_NOTE) and "<pre>" in out and "완료" in out
    assert "<table>" not in out


def test_chat_and_ledger_pages_survive_without_markdown(monkeypatch):
    monkeypatch.setattr(render, "markdown", None)
    status, body = serve.chat_page("p001-jjokpa-2026f")
    assert status == 200 and 'class="thread"' in body
    status, body = serve.render_page(config.LEDGER_DOC)
    assert status == 200 and "pip install markdown" in body
