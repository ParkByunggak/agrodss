# -*- coding: utf-8 -*-
# [U-14 사투리·이명 채집 통로] 모르는 이름 → 후보(자동, 중복 없음) · 사전에 있는 이름은 후보 아님 · 승인은 사람만 · 승인 → 정본 CSV 한 줄 +
#        사전 재적재 → 새 채팅이 통한다 · 정본명이 사전에 없으면 거부 · 정본 파일은 사본(격리) · 화면 경로.
from __future__ import annotations

import http.client
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest

from frontend import config, serve
from ingest import subjects
from names import candidates as nc, resolve as names
from schema import records as sch

NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def test_unknown_name_becomes_candidate_once_and_known_names_do_not():
    c = nc.add("쪽파모종", context="chat", now=NOW)
    assert c and c["status"] == "후보" and c["normalized"] == "쪽파모종" and c["schema_version"] == sch.SCHEMA_VERSION
    assert nc.add("쪽파 모종", context="chat", now=NOW) is None                     # 공백 차이는 같은 이름
    assert nc.add("쪽파", context="chat") is None and nc.add("길경", context="chat") is None
    assert [x["id"] for x in nc.open_candidates()] == [c["id"]]
    with pytest.raises(nc.CandidateError):
        nc.add("x", context="telepathy")


def test_new_chat_with_unknown_name_records_candidate_in_error_path():
    with pytest.raises(subjects.SubjectError, match="후보로 적어 두었다"):
        subjects.add("땡파", "2026 가을")
    assert nc.open_candidates()[0]["query"] == "땡파" and nc.open_candidates()[0]["context"] == "new_chat"
    with pytest.raises(subjects.SubjectError, match="이미 후보에 있다"):
        subjects.add("땡파", "2026 가을")


def test_approve_is_human_only_and_needs_known_canonical():
    c = nc.add("땡파", context="chat", now=NOW)
    with pytest.raises(nc.CandidateError, match="사람만"):
        nc.approve(c["id"], "쪽파", by="computed:evolve")
    with pytest.raises(nc.CandidateError, match="사전에 없다"):
        nc.approve(c["id"], "외계작물", by="publisher")
    with pytest.raises(nc.CandidateError, match="이명 종류"):
        nc.approve(c["id"], "쪽파", alias_kind="별명", by="publisher")


def test_approve_appends_csv_reloads_dictionary_and_new_chat_works():
    csv_path = Path(names.names_csv_path())
    assert csv_path.resolve() != names.NAMES_CSV.resolve()                        # 정본은 사본으로 격리
    before = csv_path.read_text(encoding="utf-8")
    c = nc.add("땡파", context="new_chat", now=NOW)
    r = nc.approve(c["id"], "길경", alias_kind="사투리", by="publisher", now=NOW)   # 이명으로 적어도 정본(도라지)에 잇는다
    assert r["status"] == "승인" and r["canonical"] == "도라지" and r["source"] == "publisher"
    after = csv_path.read_text(encoding="utf-8")
    assert after.startswith(before) and "도라지,땡파,동일,사투리,발행자 승인 2026-09-19" in after
    assert names.resolve("땡파").status == "alias" and names.resolve("땡파").canonical == "도라지"
    assert nc.open_candidates() == []
    s = subjects.add("땡파", "2026 가을", status="계획", now=NOW)                    # 이제 새 채팅이 통한다
    assert s["crop"] == "도라지"
    with pytest.raises(nc.CandidateError, match="열린 후보가 아니다"):
        nc.approve(c["id"], "쪽파", by="publisher")
    assert not (Path(__file__).resolve().parent.parent / "docs" / "crop_names.md").read_text(encoding="utf-8").count("땡파")   # 생성물은 안 건드림


def test_reject_closes_candidate():
    c = nc.add("땡파", context="chat", now=NOW)
    r = nc.reject(c["id"], why="오타", by="publisher", now=NOW)
    assert r["status"] == "거부" and r["note"] == "오타" and nc.open_candidates() == []
    assert nc.add("땡파", context="chat", now=NOW) is not None                   # 거부된 이름은 다시 후보가 될 수 있다


def test_improve_page_lists_and_approves_candidate(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        port = s.server_address[1]
        c = nc.add("땡파", context="new_chat", now=NOW)
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/improve")
        r = conn.getresponse()
        body = r.read().decode("utf-8")
        assert r.status == 200 and "땡파" in body and "승인 → 사전" in body
        conn.request("POST", "/improve/name", body=urlencode({"id": c["id"], "canonical": "쪽파", "kind": "사투리", "act": "approve"}),
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        r = conn.getresponse()
        body = r.read().decode("utf-8")
        assert r.status == 200 and "사전 등재" in body and names.resolve("땡파").canonical == "쪽파"
        conn.request("POST", "/improve/name", body=urlencode({"id": c["id"], "canonical": "쪽파", "act": "approve"}),
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        r = conn.getresponse()
        assert r.status == 400 and "열린 후보가 아니다" in r.read().decode("utf-8")
    finally:
        s.shutdown()
        s.server_close()
