# -*- coding: utf-8 -*-
# FILE: judge/boundary.py
# ROLE: [M-3 · I-5 · H G1] 몰↔DSS 경계 — 3층 진입 직전 한 번 서는 게이트(산출 레벨 말미 1회, 경로마다 아님).
#
# 1겹(스키마): 3층 입력에는 재고·주문·판매 속도·정산액·리뷰·수요 예측이 들어갈 **자리가 없다** — 허용 목록 방식.
#             금지 목록은 문서용, 허용 목록이 검사용(I-5 §3-1: 이름 매칭만 하면 우회 이름을 못 잡는다).
# 2겹(검사):  tests/test_boundary.py — 거부·통과·출처·위치 네 검사 + 주입.
#
# 위반은 조용히 걷어 내지 않고 BoundaryError 로 올린다 — 걷어 내면 "경계가 있다"고 믿은 채 샌다(fail-open 금지).
from __future__ import annotations

from typing import Any

# 재배 단위(subject) — 3층이 받아도 되는 필드 전부. 여기 없으면 거부.
ALLOWED_SUBJECT_FIELDS: frozenset[str] = frozenset({
    "id", "parcel", "label", "crop", "season", "anchor", "anchor_kind", "grid_unit", "cert", "source",
    "lat", "lon", "area_m2", "use", "irrigation", "drainage", "slope", "microclimate", "night_light", "environment",
})
# 1층 레코드 종류 — 3층이 받아도 되는 kind
ALLOWED_RECORD_KINDS: frozenset[str] = frozenset({
    "observation.video", "observation.weather_daily", "observation.pest_forecast", "reference.climate_normal",
    "reference.organic_material_notice", "forecast.weather_daily", "event", "decision.noncompliance",
    "plan.task", "plan.capture", "plan.target_date",
})
# 문서용 금지 목록(I-5 §1-1) — 검사는 허용 목록으로 한다. 이 이름들이 어디에도 없어야 함을 별도 검사가 본다.
FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "stock", "inventory", "inventory_qty", "order_qty", "orders_pending", "sales_velocity", "views", "settlement_amount",
    "unit_price", "price", "revenue", "review_score", "rating", "demand_forecast", "demand",
    "재고", "주문", "주문잔량", "판매속도", "조회수", "정산액", "단가", "리뷰", "평점", "수요예측", "수요",
})
# 사건 레코드의 허용 출처
ALLOWED_EVENT_SOURCES: frozenset[str] = frozenset({"farmer", "mall:settlement", "computed:grid"})
# 계획(납품 계획일)은 농가가 정한 것만 — 몰 수요가 정한 것은 조언 입력이 된다
ALLOWED_PLAN_SOURCES: frozenset[str] = frozenset({"farmer"})
RETURN_KIND_QUALITY = "품질"


class BoundaryError(ValueError):
    pass


def gate_subject(subject: dict[str, Any]) -> dict[str, Any]:
    extra = set(subject) - ALLOWED_SUBJECT_FIELDS
    if extra:
        raise BoundaryError(f"[G1] 재배 단위에 3층이 받을 수 없는 필드: {sorted(extra)} — 허용 목록 밖")
    return dict(subject)


def gate_records(records: list[dict[str, Any]] | None, what: str = "records") -> list[dict[str, Any]] | None:
    if records is None:
        return None
    for r in records:
        kind = r.get("kind")
        if kind not in ALLOWED_RECORD_KINDS:
            raise BoundaryError(f"[G1] {what}: 3층이 받을 수 없는 레코드 종류 {kind!r}")
        if kind == "event" and r.get("source") not in ALLOWED_EVENT_SOURCES:
            raise BoundaryError(f"[G1] {what}: 사건 출처 {r.get('source')!r} 는 허용되지 않는다")
        if kind == "plan.target_date" and r.get("source") not in ALLOWED_PLAN_SOURCES:
            raise BoundaryError(f"[G1] {what}: 납품 계획일의 출처 {r.get('source')!r} — 농가가 정한 것만 들어온다(몰 수요는 조언 입력)")
        hit = FORBIDDEN_FIELDS & set(r.get("values", {}) or {})
        if hit:
            raise BoundaryError(f"[G1] {what}: 레코드 값에 금지 필드 {sorted(hit)}")
    return list(records)


def gate(subject: dict[str, Any], **record_sets: list[dict[str, Any]] | None) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]] | None]]:
    """3층 진입 직전 1회. (subject, {이름: 레코드들}) 를 검증해 돌려준다. 위반이면 BoundaryError."""
    s = gate_subject(subject)
    out = {name: gate_records(recs, name) for name, recs in record_sets.items()}
    return s, out


# ── 몰 → DSS 허용 흐름: 정산 → 결과 기록(사건) ───────────────────────────────────────
def settlement_to_events(settlement: dict[str, Any]) -> list[dict[str, Any]]:
    """몰 정산 레코드 → 사건(수확·납품) 결과 기록. 허용 필드만 옮긴다 — 정산액·재고·단가는 여기서 떨어진다.
    반품 사유는 품질 갈래만 넘어온다(배송·변심은 몰 내부).
    입력 예: {subject, harvested_at, delivered_at, quantity, quality_grade, return_reason, return_kind, amount, stock}"""
    sid = settlement.get("subject")
    if not sid:
        raise BoundaryError("정산 레코드에 재배 단위가 없다")
    out: list[dict[str, Any]] = []
    if settlement.get("harvested_at"):
        out.append({"kind": "event", "type": "수확", "subject": sid, "observed_at": settlement["harvested_at"],
                    "source": "mall:settlement", "resolution": "cultivation_unit",
                    "quantity": settlement.get("quantity"), "materials": [], "note": "몰 정산에서"})
    if settlement.get("delivered_at"):
        reason = settlement.get("return_reason") if settlement.get("return_kind") == RETURN_KIND_QUALITY else None
        out.append({"kind": "event", "type": "납품", "subject": sid, "observed_at": settlement["delivered_at"],
                    "source": "mall:settlement", "resolution": "cultivation_unit",
                    "quality_grade": settlement.get("quality_grade"), "return_reason": reason, "materials": [], "note": "몰 정산에서"})
    for e in out:
        assert not (FORBIDDEN_FIELDS & set(e)), "변환 결과에 금지 필드가 남았다"
    return out


def accept_plan_target(plan: dict[str, Any]) -> dict[str, Any]:
    """납품 계획일(F 역산 입력). source=farmer 만 진입."""
    if plan.get("source") not in ALLOWED_PLAN_SOURCES:
        raise BoundaryError(f"[G1] 납품 계획일 출처 {plan.get('source')!r} — 농가가 정한 것만 들어온다")
    if not plan.get("target_date"):
        raise BoundaryError("납품 계획일이 없다")
    return {"kind": "plan.target_date", "subject": plan.get("subject"), "target_date": plan["target_date"],
            "source": "farmer", "resolution": "cultivation_unit"}
