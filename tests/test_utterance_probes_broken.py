# -*- coding: utf-8 -*-
# [2026-10-04 처방 직후 전수] 문장 형태 점검의 목록 파일이 깨지면(JSON 오류 · 어휘 밖 기대 · 파일 없음) 자기 점검 화면이 **통째로 500** 이었다 — 결정 답 파일(H-후보㉣ 형태)과 같은 자리.
# 화면은 다른 점검을 그대로 돌리고 그 사실을 말한다 · /changes 「읽다 버린 것」 에도 남는다(조용한 실패 금지).
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from frontend import config, selfcheck
from ingest import dropped, probes
from tests.test_brand_home import srv  # noqa: F401
from tests.test_selfcheck import _get

TODAY = date(2026, 9, 24)


def _break(monkeypatch, tmp_path, text: str):
    p = tmp_path / "utterance_probes.json"
    p.write_text(text, encoding="utf-8")
    monkeypatch.setattr(probes, "PATH", p)


def test_a_broken_probe_file_is_said_not_a_500_and_lands_in_the_drop_ledger(srv, monkeypatch, tmp_path):
    monkeypatch.setenv(config.TODAY_ENV, TODAY.isoformat())
    _break(monkeypatch, tmp_path, "{not json")
    u = selfcheck.utterances(TODAY, selfcheck.subject())
    assert u["error"].startswith("JSONDecodeError") and u["groups"] == [] and u["with_expected"] == 0
    status, body = _get(srv, "/selfcheck")
    text = re.sub(r"<[^>]*>", " ", body)
    assert status == 200 and selfcheck.PROBES_BROKEN in text and body.count('class="card chk"') == 5          # 다른 점검은 그대로
    assert any(probes.DROP_WHERE in str(r) for r in dropped.all_drops())                                        # /changes 에 보인다


def test_an_expectation_outside_the_vocabulary_is_a_visible_error_not_a_silent_row(monkeypatch, tmp_path):
    _break(monkeypatch, tmp_path, '{"groups": [{"name": "x", "rows": [{"text": "물 줬다", "expected": "사건", "expected_route": null, "by": "발행자 2026-10-04"}]}]}')
    u = selfcheck.utterances(TODAY, selfcheck.subject())
    assert "어휘 밖" in u["error"] and "사건" in u["error"]


def test_the_shipped_file_loads_and_the_missing_file_is_also_said(monkeypatch, tmp_path):
    assert probes.load()["groups"]
    monkeypatch.setattr(probes, "PATH", tmp_path / "nope.json")
    u = selfcheck.utterances(TODAY, selfcheck.subject())
    assert u["error"].startswith("FileNotFoundError")
