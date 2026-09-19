# -*- coding: utf-8 -*-
# [M-13] Claude 형식 채팅 — 목록 = 재배 단위 · 새 목록은 작목 추가/계획 · 발화 분류(제안만) · 확인 → 원장 · 질문 → 봉투 · 영농일지.
from __future__ import annotations

import http.client
import json
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

import pytest

from frontend import config, serve
from ingest import chat, events as ev, feedback as fb, media, subjects
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
TODAY = date(2026, 9, 19)
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


@pytest.fixture
def reg():
    """재배 단위 등록부 — conftest 가 tmp 사본으로 격리한다(R-4). 여기서는 그 사실을 검사한다."""
    p = media.subjects_path()
    assert p.resolve() != media.SUBJECTS_PATH.resolve(), "테스트가 운영 등록부를 가리키고 있다"
    return p


# ── 날짜 · 분류 ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,day", [
    ("2026-09-10에 물 줬다", "2026-09-10"), ("9월 12일 웃거름", "2026-09-12"), ("어제 풀 뽑았다", "2026-09-18"),
    ("3일 전에 약 쳤다", "2026-09-16"), ("내일 트랩 놓으려고", "2026-09-20"), ("물 줬다", None),
])
def test_parse_day(text, day):
    assert chat.parse_day(text, TODAY) == day


def test_classify_rules_are_proposals_only():
    d = chat.classify("오늘 물 줬다", TODAY)[0]
    assert d["kind"] == "event" and d["type"] == "관수" and d["observed_at"] == "2026-09-19" and d["needs"] == []
    d = chat.classify("풀 뽑았다", TODAY)[0]
    assert d["kind"] == "event" and d["type"] == "제초" and d["observed_at"] is None and d["needs"] == ["observed_at"]
    d = chat.classify("잎 끝이 누렇게 보인다", TODAY)[0]
    assert d["kind"] == "observation.note" and d["observed_at"] == "2026-09-19"
    d = chat.classify("9월 25일에 웃거름 주려고 한다", TODAY)[0]
    assert d["kind"] == "plan.farmer" and d["task"] == "시비" and d["planned_day"] == "2026-09-25"
    d = chat.classify("10월 30일 납품 예정", TODAY)[0]
    assert d["kind"] == "plan.target_date" and d["target_date"] == "2026-10-30"
    d = chat.classify("수확 창이 너무 넓다, 고쳐 달라", TODAY)[0]
    assert d["kind"] == "feedback.request"
    assert chat.classify("언제 캐면 되나?", TODAY)[0]["kind"] == "question"
    assert chat.classify("날씨가 좋다", TODAY) == []                       # 추측하지 않는다
    assert ev.list_records(SID) == [] and fb.list_records() == []         # 분류는 아무 원장에도 안 쓴다


# ── 보내기 · 확인 ───────────────────────────────────────────────────────────────────
def test_send_records_message_and_reply_and_confirm_writes_ledger():
    m, r = chat.send(SID, "오늘 물 줬다", today=TODAY, now=NOW)
    assert m["kind"] == "chat.message" and m["schema_version"] == sch.SCHEMA_VERSION and m["drafts"][0]["type"] == "관수"
    assert r["role"] == "system" and r["reply_ref"] == m["id"] and "사건" in r["text"]
    assert ev.list_records(SID) == []                                     # 확인 전엔 원장에 없다
    rec = chat.confirm(m["id"], 0, now=NOW)
    assert rec["kind"] == "event" and rec["type"] == "관수" and rec["chat_ref"] == m["id"] and rec["observed_at"] == "2026-09-19"
    assert chat.get_message(m["id"])["confirmed_refs"] == [rec["id"]]
    assert chat.pending_drafts(SID) == []


def test_confirm_without_day_is_refused_until_day_given():
    m, _ = chat.send(SID, "풀 뽑았다", today=TODAY, now=NOW)
    with pytest.raises(chat.ChatError, match="대상 시각"):
        chat.confirm(m["id"], 0, now=NOW)
    rec = chat.confirm(m["id"], 0, day="2026-09-17", now=NOW)
    assert rec["observed_at"] == "2026-09-17" and rec["type"] == "제초"


def test_unclassified_then_human_chooses_kind():
    m, r = chat.send(SID, "날씨가 좋다", today=TODAY, now=NOW)
    assert m["drafts"] == [] and "분류 안 됨" in r["text"]
    m2 = chat.choose_kind(m["id"], "observation.note", today=TODAY)
    assert m2["drafts"][0]["kind"] == "observation.note"
    rec = chat.confirm(m["id"], 0, now=NOW)
    assert rec["kind"] == "observation.note" and rec["text"] == "날씨가 좋다"


def test_request_from_chat_lands_in_feedback_ledger():
    m, _ = chat.send(SID, "수확 창이 너무 넓다, 고쳐 달라", today=TODAY, now=NOW)
    rec = chat.confirm(m["id"], 0, now=NOW)
    assert rec["kind"] == "feedback.request" and rec["status"] == "접수" and rec["subject"] == SID


def test_question_answered_from_envelope_kind_first():
    m, r = chat.send(SID, "언제 캐면 되나?", today=TODAY, now=NOW)
    assert r["text"].startswith("[") and ("수확 창" in r["text"] or "판단" in r["text"])
    _, r2 = chat.send(SID, "달이 왜 둥근가?", today=TODAY, now=NOW)
    assert "판단 불가(지식)" in r2["text"]                                  # 지어내지 않는다


def test_sowing_confirm_sets_anchor_on_planned_subject(reg):
    s = subjects.add("배추", "2026 가을", status="계획", now=NOW)
    assert "anchor" not in s and s["status"] == "계획"
    m, _ = chat.send(s["id"], "9월 15일에 배추 심었다", today=TODAY, now=NOW)
    rec = chat.confirm(m["id"], 0, now=NOW)
    assert rec["type"] == "파종"
    s2 = subjects.by_id(s["id"])
    assert s2["anchor"] == "2026-09-15" and s2["status"] == "재배 중"


# ── 목록 = 재배 단위 ───────────────────────────────────────────────────────────────
def test_add_subject_resolves_names_and_refuses_ambiguous_unknown_duplicate(reg):
    s = subjects.add("쪽파", "2027 봄", status="계획", now=NOW)
    assert s["crop"] == "쪽파" and s["id"] == "p001-쪽파-2027봄" and "grid_unit" not in s
    with pytest.raises(subjects.SubjectError, match="사전에 없는"):
        subjects.add("외계작물", "2026 가을")
    with pytest.raises(subjects.SubjectError, match="이미 있는"):
        subjects.add("쪽파", "2026 가을")
    with pytest.raises(subjects.SubjectError, match="기준점"):
        subjects.add("배추", "2026 가을", status="재배 중")
    s3 = subjects.add("쪽파", "2026 가을", parcel="p002", anchor="2026-08-30", status="재배 중", now=NOW)
    assert s3["grid_unit"] == "jjokpa-autumn" and s3["anchor_kind"] == "파종"
    assert len(subjects.load()) == 3


def test_registry_writes_never_touch_operating_file(reg):
    # [R-4] 경로를 기본 인자에 묶으면 격리가 안 닿는다 — 쓰기 뒤 운영 파일의 바이트가 그대로여야 한다
    before = media.SUBJECTS_PATH.read_bytes()
    subjects.add("배추", "2026 가을", status="계획", now=NOW)
    subjects.set_anchor("p001-배추-2026가을", "2026-09-15")
    assert media.SUBJECTS_PATH.read_bytes() == before
    assert json.loads(reg.read_text(encoding="utf-8"))["subjects"][-1]["status"] == "재배 중"


def test_ambiguous_name_asks(reg):
    d = subjects.names.load()
    amb = next((k for k in d.ambiguous), None)
    if amb is None:
        pytest.skip("사전에 모호 이름 없음")
    with pytest.raises(subjects.SubjectError, match="여러 작목"):
        subjects.add(amb, "2026 가을")


# ── 영농일지 ─────────────────────────────────────────────────────────────────────
def test_diary_is_ledgers_by_day_not_a_new_ledger():
    m, _ = chat.send(SID, "9월 10일에 트랩 놓았다", today=TODAY, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)
    ev.add_noncompliance(SID, "예찰(트랩 · 육안)", "비가 왔다", "2026-09-08", now=NOW)
    items = chat.diary(SID)
    assert [i["day"] for i in items] == ["2026-09-10", "2026-09-08"]
    assert items[0]["label"] == "사건" and items[0]["from_chat"] and items[1]["label"] == "불이행 사유"
    assert not (Path(chat.chat_dir()) / "diary.jsonl").exists()


# ── 화면 ───────────────────────────────────────────────────────────────────────────
@pytest.fixture
def srv(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    s = serve.make_server()
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield s.server_address[1]
    s.shutdown()
    s.server_close()


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.getheader("Location"), r.read().decode("utf-8")


def _post(port, path, form):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("POST", path, body=urlencode(form), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.getheader("Location"), r.read().decode("utf-8")


def test_root_redirects_to_first_chat_and_layout_has_three_columns(srv):
    st, loc, _ = _get(srv, "/")
    assert st == 302 and loc == f"/c/{quote(SID)}"
    st, _, body = _get(srv, loc)
    assert st == 200
    assert 'class="side"' in body and 'class="thread"' in body and 'class="panel"' in body
    assert "새 채팅" in body and "쪽파" in body and "영농일지" in body and "종류가 먼저" in body


def test_send_confirm_through_http(srv):
    st, loc, _ = _post(srv, f"/c/{quote(SID)}/send", {"text": "오늘 물 줬다"})
    assert st == 302
    st, _, body = _get(srv, loc)
    assert "초안" in body and "확인 → 원장" in body
    m = chat.list_messages(SID)[0]
    st, _, body = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m["id"], "i": "0", "day": "", "type": "관수"})
    assert st == 200 and "원장에 들어감" in body
    assert ev.list_records(SID)[0]["type"] == "관수"


def test_new_chat_form_and_bad_name(srv, reg):
    st, _, body = _get(srv, "/c/new")
    assert st == 200 and "작목" in body
    st, _, body = _post(srv, "/c/new", {"crop": "외계작물", "season": "2026 가을", "status": "계획"})
    assert st == 400 and "사전에 없는" in body
    st, loc, _ = _post(srv, "/c/new", {"crop": "배추", "season": "2026 가을", "status": "계획"})
    assert st == 302 and loc.startswith("/c/")
    st, _, body = _get(srv, loc)
    assert st == 200 and "배추" in body


def test_diary_and_improve_pages(srv):
    st, _, body = _get(srv, f"/diary/{quote(SID)}")
    assert st == 200 and "영농일지" in body
    st, _, body = _get(srv, "/improve")
    assert st == 200 and "자율진화" in body
    st, _, body = _post(srv, "/improve/cycle", {})
    assert st == 200 and "한 바퀴" in body
    st, _, body = _post(srv, "/improve/request", {"text": "화면이 느리다", "target": "screen", "subject": ""})
    assert st == 200 and "접수" in body


def test_ledger_doc_still_served_under_doc(srv):
    st, _, body = _get(srv, f"/doc/{config.LEDGER_DOC}")
    assert st == 200 and '<td><span class="st st-' in body


def test_chat_pages_never_touch_ledger_files():
    src = (ROOT / "frontend" / "chat_pages.py").read_text(encoding="utf-8")
    assert "index.jsonl" not in src and "subjects.json" not in src and "json.load" not in src
