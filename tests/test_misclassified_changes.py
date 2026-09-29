# -*- coding: utf-8 -*-
# [검토표 ③ 2026-09-29 · 발행자 승인 "제안 순서대로"] 오분류 상시 측정 — 발행자가 PC 에서 손으로 재던 WO-LLM-01 두 줄을 /changes 가 열 때마다 낸다.
# 계약: 건수만(발화 원문 0 · 안쪽 종류 이름 0) · 읽기 전용(원장 바이트 그대로) · 문턱을 넘으면 발행자 결정을 부른다 · 정본은 ingest 하나(스크립트는 껍데기).
from __future__ import annotations

import hashlib
import http.client
import re
from datetime import date, datetime, timezone

from frontend import config
from ingest import chat, media, misclassified
from scripts import measure_misclassified as mm
from tests.test_brand_home import srv  # noqa: F401
from tests.test_measure_misclassified import _statement_sentence

T = date(2026, 9, 24)
NOW = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.read().decode("utf-8", "replace")


def _visible(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html))


def test_the_script_is_a_shell_over_the_ingest_canon():
    assert mm.measure is misclassified.measure and mm.report is misclassified.report and mm.MIN_SET == misclassified.MIN_SET == 30


def test_changes_shows_counts_only_and_writes_nothing(srv, monkeypatch):
    monkeypatch.setenv(config.TODAY_ENV, T.isoformat())
    sid = media.load_subjects()[0]["id"]
    stmt = _statement_sentence()
    m1, _ = chat.send(sid, stmt, today=T, now=NOW)
    chat.choose_kind(m1["id"], "event", today=T)                                     # 규칙 본 것 → 사람이 한 일: 고침 1
    m3, _ = chat.send(sid, "어제 웃거름 줬다 검사용", today=T, now=NOW)
    chat.send(sid, "쪽파는 언제 캐면 되나 검사용", today=T, now=NOW, edit_of=m3["id"])   # 편집 1
    d = chat.chat_dir()
    before = {p.name: hashlib.sha1(p.read_bytes()).hexdigest() for p in d.rglob("*") if p.is_file()}
    status, body = _get(srv, "/changes")
    after = {p.name: hashlib.sha1(p.read_bytes()).hexdigest() for p in d.rglob("*") if p.is_file()}
    assert status == 200 and before == after and before                              # 읽기 전용
    seen = _visible(body)
    assert "종류 고침 재료 2건 (손으로 고친 종류 1 · 편집 1) — 문턱 30: 미달" in seen and "농가 발화 3" in seen and "잰 때" in seen
    for secret in (stmt, "어제 웃거름 줬다 검사용", "쪽파는 언제 캐면 되나 검사용"):
        assert secret not in seen, secret                                             # 원문은 화면 어디에도 없다(PII)
    line = re.search(r"종류 고침 재료.*?잰 때 \S+", seen).group(0)
    assert "observation.note" not in line and "event" not in line                     # 그 줄에 안쪽 종류 이름이 없다(커밋 제목 표는 인용이라 범위 밖)
    assert "그 자체가 결과" in seen and "발행자 결정" not in seen


def test_over_the_threshold_it_calls_for_the_publishers_decision(srv, monkeypatch):
    monkeypatch.setattr(misclassified, "MIN_SET", 1)
    sid = media.load_subjects()[0]["id"]
    m1, _ = chat.send(sid, _statement_sentence(), today=T, now=NOW)
    chat.choose_kind(m1["id"], "event", today=T)
    line = misclassified.status_line(misclassified.measure())
    assert line.startswith("종류 고침 재료 1건") and "문턱 1: 충족 — 발행자 결정" in line and "트리거 D" in line
    status, body = _get(srv, "/changes")
    assert status == 200 and "발행자 결정" in _visible(body) and 'st-진행">종류 고침' in body      # 넘으면 색이 바뀐다


def test_an_empty_ledger_is_zero_not_an_error(srv):
    line = misclassified.status_line(misclassified.measure())
    assert line.startswith("종류 고침 재료 0건 (손으로 고친 종류 0 · 편집 0) — 문턱 30: 미달")
    status, body = _get(srv, "/changes")
    assert status == 200 and "종류 고침 재료 0건" in _visible(body)
