# -*- coding: utf-8 -*-
# [U-16] 피해 사건 입력형 + 경보 ↔ 피해 대조 — 적중(창 안 같은 갈래 경보) · 빗나감(놓친 경보 / 회복 가능 과경보) ·
#        대조 불가(회복 불가 과경보 허용 H) · 채팅 분류(갈래) · 확인은 risk 없이는 거부.
from __future__ import annotations

from datetime import date, datetime, timezone
from urllib.parse import quote, urlencode

import http.client
import threading

import pytest

from frontend import config, serve
from ingest import chat, events as ev, feedback as fb
from judge import evolve

SID = "p001-jjokpa-2026f"
TODAY = date(2026, 9, 19)
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def _pred(alerts, as_of="2026-09-19", horizon=14):
    return fb.record_prediction(SID, "risk_alert", "판단함", {"alerts": alerts, "horizon_days": horizon}, as_of, grade="추정", now=NOW)


UNREC = {"level": "경보", "risk": "고자리파리 유충", "recoverable": False}
REC = {"level": "경보", "risk": "잎 곰팡이(회복 가능)", "recoverable": True}
NOTICE = {"level": "예고", "risk": "서리(늦서리)", "recoverable": False}


# ── 입력형 ────────────────────────────────────────────────────────────────────────
def test_damage_event_requires_risk_and_severity_vocab():
    with pytest.raises(ev.EventError, match="무엇의 피해"):
        ev.add_event(SID, "피해", "2026-09-25", now=NOW)
    with pytest.raises(ev.EventError, match="피해 정도"):
        ev.add_event(SID, "피해", "2026-09-25", risk="서리", severity="엄청", now=NOW)
    r = ev.add_event(SID, "피해", "2026-09-25", risk="서리", severity="보통", now=NOW)
    assert r["type"] == "피해" and r["risk"] == "서리" and r["severity"] == "보통" and r["schema_version"]
    assert "risk" not in ev.add_event(SID, "관수", "2026-09-25", now=NOW)


@pytest.mark.parametrize("a,b,ok", [
    ("얼었다", "서리(늦서리)", True), ("썩었다", "뿌리 부패(가을 장마)", True), ("벌레", "서리(늦서리)", False),
    ("고자리파리", "고자리파리 유충", True), ("해충", "고자리파리 유충", True), ("", "서리", False),
])
def test_match_risk_by_family_then_substring(a, b, ok):
    assert evolve.match_risk(a, b) is ok


# ── 대조 ─────────────────────────────────────────────────────────────────────────
def test_damage_inside_window_with_same_family_alert_is_hit():
    p = _pred([UNREC])
    d = ev.add_event(SID, "피해", "2026-09-25", risk="해충", now=NOW)
    out = evolve.measure(SID, date(2026, 9, 26))
    assert len(out) == 1 and out[0]["verdict"] == "적중" and out[0]["actual_ref"] == d["id"] and out[0]["prediction_id"] == p["id"]
    assert evolve.measure(SID, date(2026, 9, 26)) == []


def test_damage_without_prior_alert_is_missed_alert():
    _pred([UNREC])
    ev.add_event(SID, "피해", "2026-09-25", risk="서리", now=NOW)
    out = evolve.measure(SID, date(2026, 9, 26))
    assert out[0]["verdict"] == "빗나감" and "놓친 경보" in out[0]["detail"]


def test_alert_without_damage_after_window_asymmetric():
    _pred([UNREC, REC, NOTICE])
    assert evolve.measure(SID, date(2026, 9, 30)) == []                     # 창 안 — 아직 아무것도
    out = evolve.measure(SID, date(2026, 10, 10))
    by = {o["actual_ref"]: o for o in out}
    assert by["alert:고자리파리 유충"]["verdict"] == "대조 불가" and "과경보 허용" in by["alert:고자리파리 유충"]["detail"]
    assert by["alert:잎 곰팡이(회복 가능)"]["verdict"] == "빗나감" and "과경보" in by["alert:잎 곰팡이(회복 가능)"]["detail"]
    assert "alert:서리(늦서리)" not in by                                    # 예고는 세지 않는다


def test_no_prediction_or_no_damage_writes_nothing():
    assert evolve.measure(SID, date(2026, 10, 10)) == []
    ev.add_event(SID, "피해", "2026-09-25", risk="서리", now=NOW)
    assert evolve.measure(SID, date(2026, 10, 10)) == []                    # 예측이 없으면 대조도 없다


def test_risk_miss_proposes_threshold_review_not_window():
    _pred([UNREC])
    ev.add_event(SID, "피해", "2026-09-25", risk="서리", now=NOW)
    evolve.measure(SID, date(2026, 9, 26))
    made = evolve.propose(SID, date(2026, 9, 26))
    ex = [m for m in made if m["direction"] == "확장"][0]
    assert "신호 임계" in ex["proposal"] and ex["target_ref"] == "risk_alert"
    assert fb.active_caps(SID)[0]["target_ref"] == "risk_alert"


# ── 채팅 ─────────────────────────────────────────────────────────────────────────
def test_chat_classifies_damage_with_family_and_asks_when_unknown():
    d = chat.classify("어제 서리 맞아서 잎이 얼었다", TODAY)[0]
    assert d["kind"] == "event" and d["type"] == "피해" and d["risk"] == "서리" and d["observed_at"] == "2026-09-18" and d["needs"] == []
    d = chat.classify("두둑 한쪽에 피해가 있다", TODAY)[0]
    assert d["type"] == "피해" and d["risk"] is None and d["needs"] == ["risk"]
    m, _ = chat.send(SID, "두둑 한쪽에 피해가 있다", today=TODAY, now=NOW)
    with pytest.raises(chat.ChatError, match="무엇의 피해"):
        chat.confirm(m["id"], 0, now=NOW)
    rec = chat.confirm(m["id"], 0, risk="부패", now=NOW)
    assert rec["risk"] == "부패"
    assert chat.diary(SID)[0]["text"].startswith("피해(부패)")


def test_confirm_damage_through_http(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        port = s.server_address[1]
        m, _ = chat.send(SID, "고랑 쪽이 썩었다", today=TODAY, now=NOW)
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.request("POST", f"/c/{quote(SID)}/confirm", body=urlencode({"msg": m["id"], "i": "0", "day": "", "type": "피해", "risk": "부패"}),
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
        r = c.getresponse()
        body = r.read().decode("utf-8")
        assert r.status == 200 and "원장에 들어감" in body
        assert ev.list_records(SID)[0]["risk"] == "부패"
    finally:
        s.shutdown()
        s.server_close()
