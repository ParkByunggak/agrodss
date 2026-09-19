# -*- coding: utf-8 -*-
# [M-3 · I-5 §3] 몰↔DSS 경계 — 거부(3-1) · 통과(3-2) · 출처(3-3) · 위치(3-4). 막는 것을 검사하면 통과하는 것도 검사한다.
from __future__ import annotations

import ast
import inspect

import pytest

from ingest import media
from judge import boundary as B
from judge import run as R

SUBJ = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]


# ── 3-1 거부: 허용 목록 밖 필드는 자리가 없다 ─────────────────────────────────────
def test_subject_allowed_list_has_no_forbidden_name():
    assert not (B.ALLOWED_SUBJECT_FIELDS & B.FORBIDDEN_FIELDS)
    assert set(SUBJ) <= B.ALLOWED_SUBJECT_FIELDS                       # 실제 등록부가 허용 목록 안이다


@pytest.mark.parametrize("bad", ["stock", "inventory_qty", "재고", "review_score", "demand_forecast", "totally_new_field"])
def test_subject_with_extra_field_rejected(bad):
    with pytest.raises(B.BoundaryError, match="허용 목록 밖"):
        B.gate_subject({**SUBJ, bad: 1})


def test_records_with_unknown_kind_or_forbidden_value_rejected():
    with pytest.raises(B.BoundaryError, match="레코드 종류"):
        B.gate_records([{"kind": "mall.order", "values": {}}], "x")
    with pytest.raises(B.BoundaryError, match="금지 필드"):
        B.gate_records([{"kind": "forecast.weather_daily", "values": {"tmin": 1.0, "demand": 3}}], "x")


def test_event_source_allowed_list():
    with pytest.raises(B.BoundaryError, match="출처"):
        B.gate_records([{"kind": "event", "source": "mall:orders", "values": {}}], "x")
    assert B.gate_records([{"kind": "event", "source": "farmer", "values": {}}], "x")


# ── 3-2 통과: 허용 필드는 흐른다 ─────────────────────────────────────────────────────
def test_settlement_flows_quantity_grade_and_quality_return_only():
    st = {"subject": SUBJ["id"], "harvested_at": "2026-10-20", "delivered_at": "2026-10-21", "quantity": "12kg",
          "quality_grade": "상", "return_reason": "잎끝 마름", "return_kind": "품질",
          "amount": 48000, "stock": 3, "unit_price": 4000, "rating": 4.5}
    evs = B.settlement_to_events(st)
    assert [e["type"] for e in evs] == ["수확", "납품"]
    h, d = evs
    assert h["quantity"] == "12kg" and h["source"] == "mall:settlement" and h["observed_at"] == "2026-10-20"
    assert d["quality_grade"] == "상" and d["return_reason"] == "잎끝 마름"                 # 세 값이 도착한다
    for e in evs:
        assert not ({"amount", "stock", "unit_price", "rating"} & set(e))                    # 금지 값은 떨어진다
    assert B.gate_records(evs, "settlement") == evs                                          # 게이트도 통과시킨다


def test_settlement_non_quality_return_does_not_flow():
    st = {"subject": SUBJ["id"], "delivered_at": "2026-10-21", "return_reason": "배송 지연", "return_kind": "배송"}
    assert B.settlement_to_events(st)[0]["return_reason"] is None


def test_settlement_without_subject_rejected():
    with pytest.raises(B.BoundaryError):
        B.settlement_to_events({"harvested_at": "2026-10-20"})


# ── 3-3 출처: 납품 계획일은 농가가 정한 것만 ──────────────────────────────────────────
def test_plan_target_source_rule():
    ok = B.accept_plan_target({"subject": SUBJ["id"], "target_date": "2026-10-25", "source": "farmer"})
    assert ok["kind"] == "plan.target_date"
    with pytest.raises(B.BoundaryError, match="농가가 정한 것만"):
        B.accept_plan_target({"subject": SUBJ["id"], "target_date": "2026-10-25", "source": "mall:demand"})
    with pytest.raises(B.BoundaryError):
        B.gate_records([{"kind": "plan.target_date", "source": "mall:demand", "values": {}}], "x")


# ── 3-4 위치: 게이트는 입력을 다 모은 뒤 · 판정 직전 · 한 번 ─────────────────────────
def _calls_in_order(fn) -> list[str]:
    tree = ast.parse(inspect.getsource(fn))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            names.append(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    return names


def test_gate_position_in_all_judgments():
    calls = _calls_in_order(R.all_judgments)
    assert calls.count("gate") == 1, "게이트는 한 번이어야 한다(경로마다 아님)"
    g = calls.index("gate")
    gathers = [i for i, c in enumerate(calls) if c in ("gather_forecast", "gather_pest", "list_records")]
    judges = [i for i, c in enumerate(calls) if c == "judge"]
    assert gathers and max(gathers) < g, "게이트가 입력 수집보다 앞이면 무효(차단 지점이 주입 지점보다 앞)"
    assert judges and g < min(judges), "게이트가 판정보다 뒤면 무효"


def test_all_judgments_runs_through_gate_on_real_registry():
    out = R.all_judgments()
    assert out and all(len(envs) == 4 for _, envs, _ in out)
