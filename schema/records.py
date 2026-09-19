# -*- coding: utf-8 -*-
# FILE: schema/records.py
# ROLE: [M-6] 스키마 원본 = 마이그레이션. 모든 레코드 종류(kind)의 필드·출처·층을 **한 정의**로 둔다.
#
#   · 원장 셋(영상 · 사건 · 사유)과 외부 원천 레코드, 등록부(재배 단위 · 필지), 계획, 되먹임(J) 전부 여기.
#   · 허용 목록 방식 — 선언되지 않은 필드는 거부한다(I-5 §3-1: 이름 매칭만 하면 우회 이름을 못 잡는다).
#     경계(judge.boundary)의 허용 목록은 여기서 파생된다. 두 벌을 두지 않는다.
#   · 공통 필드 5(I-3 §0): source · recorded_at · observed_at · resolution · subject. source 없는 레코드는 1층에 못 들어간다.
#   · 되먹임(J): feedback.request(사용자 개선 요구) · feedback.prediction(예측 원장) · feedback.outcome(대조 결과) ·
#     improvement.item(개선 항목 — 자기개선 업무의 단위). 자율진화 규칙은 judge/evolve.py, 여기서는 **자리**만.
#   · 값을 메우지 않는다 — 없는 값은 키 부재(격자 빈칸 3종과 같은 규율). 대리값 금지.
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

# 공통 필드(I-3 §0) — 농가·몰이 쓰는 입력형은 다섯을 다 가진다. 외부 원천 레코드는 subject 가 없다(원천은 필지를 모른다).
COMMON_INPUT_FIELDS: tuple[str, ...] = ("source", "recorded_at", "observed_at", "resolution", "subject")

# 문서용 금지 목록(I-5 §1-1) — 검사는 허용 목록으로 한다. 어떤 kind 의 어느 필드에도 이 이름이 없어야 한다.
FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "stock", "inventory", "inventory_qty", "order_qty", "orders_pending", "sales_velocity", "views", "settlement_amount",
    "unit_price", "price", "revenue", "review_score", "rating", "demand_forecast", "demand",
    "재고", "주문", "주문잔량", "판매속도", "조회수", "정산액", "단가", "리뷰", "평점", "수요예측", "수요",
})
# 화면·봉투·몰에 나가지 않는 필드(I-5 §1-2 필지 상세 = PII). 3층은 받을 수 있다(좌표는 예보 조회에 필요).
PII_FIELDS: frozenset[str] = frozenset({"address", "pnu", "lat", "lon", "address_label", "gps"})

# 되먹임 상태·방향 어휘 — 판정과 처방이 같은 목록을 쓴다(어휘 두 벌 금지)
REQUEST_STATUS: tuple[str, ...] = ("접수", "검토", "채택", "반영", "거부", "보류")
ITEM_STATUS: tuple[str, ...] = ("제안", "검토", "채택", "반영", "검증", "거부", "보류")
DIRECTIONS: tuple[str, ...] = ("보수", "확장")          # 보수 = 등급 하향·판단 불가 전환·범위 축소 / 확장 = 임계·규칙·칸 변경
TARGETS: tuple[str, ...] = ("grid", "decision", "dictionary", "screen", "schema", "input", "other")
VERDICTS: tuple[str, ...] = ("적중", "빗나감", "대조 불가")
HUMAN_SOURCES: frozenset[str] = frozenset({"farmer", "publisher"})


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class Kind:
    name: str
    layer: str                                   # 등록부 | 1층 사실 | 1층 계획 | 되먹임
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    sources: frozenset[str] = frozenset()        # 정확 일치 또는 "external:" 같은 접두(끝이 ':' 이면 접두)
    layer3_input: bool = False                   # 3층 판정기가 받아도 되는가(경계 허용 목록의 원천)
    subject_bound: bool = True                   # subject 를 가지는가
    pii: tuple[str, ...] = ()

    @property
    def fields(self) -> frozenset[str]:
        return frozenset(self.required) | frozenset(self.optional) | {"kind", "schema_version"}


def _k(name: str, layer: str, required: tuple[str, ...], optional: tuple[str, ...] = (), sources: tuple[str, ...] = (),
       layer3_input: bool = False, subject_bound: bool = True, pii: tuple[str, ...] = ()) -> Kind:
    return Kind(name, layer, required, optional, frozenset(sources), layer3_input, subject_bound, pii)


_EXT_OBS = ("axis", "observed_at", "fetched_at", "source", "resolution", "values")

KINDS: dict[str, Kind] = {k.name: k for k in (
    # ── 등록부 ──────────────────────────────────────────────────────────────────────
    _k("subject", "등록부",   # 채팅 목록의 단위(M-13) — 작목을 추가하거나 계획이 생길 때 만들어진다. 파종 전이면 anchor 없음.
       ("id", "parcel", "label", "crop", "season", "source"),
       ("anchor", "anchor_kind", "grid_unit", "cert", "status", "recorded_at", "note"),
       sources=("farmer", "publisher", "d1_first_farm.md (발행자 2026-09-18)"), layer3_input=True),
    _k("parcel", "등록부",   # I-3 §1 필지 고정 정보 — I-6 값의 자리. 값이 없으면 키를 두지 않는다.
       ("id", "source", "recorded_at", "observed_at", "resolution"),
       ("address", "pnu", "lat", "lon", "area_m2", "area_source", "use", "mall_supply", "environment", "soil_texture",
        "slope", "drainage", "irrigation", "microclimate", "night_light", "cert_claimed", "cert_legal", "cert_since",
        "seed_source", "variety", "soil_exam_ref", "note"),
       sources=("farmer", "publisher"), subject_bound=False, pii=("address", "pnu", "lat", "lon")),
    # ── 1층 사실(농가) ──────────────────────────────────────────────────────────────
    _k("observation.video", "1층 사실",
       ("id", "subject", "observed_at", "observed_at_source", "recorded_at", "source", "resolution", "origin", "file", "sha256", "bytes"),
       ("width", "height", "duration_sec", "gps", "note"), sources=("farmer",), layer3_input=True, pii=("gps",)),
    _k("event", "1층 사실",
       ("id", "type", "subject", "observed_at", "recorded_at", "source", "resolution"),
       ("advice_ref", "materials", "quantity", "quality_grade", "return_reason", "note"),
       sources=("farmer", "mall:settlement"), layer3_input=True),
    _k("decision.noncompliance", "1층 사실",
       ("id", "subject", "planned_task", "planned_day", "reason", "observed_at", "recorded_at", "source", "resolution"),
       sources=("farmer",), layer3_input=True),
    # ── 1층 사실(외부 원천, D-9 인용) ───────────────────────────────────────────────────
    _k("observation.weather_daily", "1층 사실", _EXT_OBS + ("station",), sources=("external:",), layer3_input=True, subject_bound=False),
    _k("reference.climate_normal", "1층 사실", _EXT_OBS + ("station", "for_day"), sources=("external:",), layer3_input=True, subject_bound=False),
    _k("forecast.weather_daily", "1층 사실", _EXT_OBS + ("for_day",), ("hourly_tmp", "sky", "pty"),
       sources=("external:",), layer3_input=True, subject_bound=False),
    _k("observation.pest_forecast", "1층 사실",
       _EXT_OBS + ("region", "crop_requested", "crop_code_crop", "raw", "schema_confirmed"), ("proxy_reason",),
       sources=("external:",), layer3_input=True, subject_bound=False),
    _k("reference.organic_material_notice", "1층 사실", ("axis", "observed_at", "source", "resolution", "values"),
       sources=("external:",), layer3_input=True, subject_bound=False),
    _k("observation.soil_exam", "1층 사실",
       ("status", "pnu", "axis", "source", "resolution", "observed_at", "fetched_at"),
       ("exam_year", "address_label", "values", "units", "message"),
       sources=("external:",), layer3_input=True, subject_bound=False, pii=("pnu", "address_label")),
    # ── 1층 계획 ─────────────────────────────────────────────────────────────────────
    _k("plan.task", "1층 계획",
       ("source", "resolution", "stage", "task", "work_day", "work_date", "prep_date_own", "prep_date_rental", "tools",
        "materials", "retry_possible", "deadline_day", "deadline_date", "source_note"),
       sources=("computed:grid",), layer3_input=True, subject_bound=False),
    _k("plan.capture", "1층 계획",
       ("source", "resolution", "stage", "task", "work_day", "work_date", "prep_date_own", "prep_date_rental", "tools",
        "materials", "retry_possible", "deadline_day", "deadline_date", "source_note"),
       sources=("computed:grid",), layer3_input=True, subject_bound=False),
    _k("plan.target_date", "1층 계획",   # I-3 §4 — 농가가 정한 것만(몰 수요가 정하면 조언 입력이 된다)
       ("subject", "target_date", "source", "resolution"), ("id", "recorded_at", "observed_at", "note"),
       sources=("farmer",), layer3_input=True),
    # ── 1층 사실(농가 발화 — I-3 §3 "질의 자체가 관찰", M-13 채팅) ─────────────────────────
    _k("chat.message", "1층 사실",   # 채팅 한 줄. 분류(2층)는 drafts 에 제안으로만 — 확인(confirm)해야 원장에 들어간다
       ("id", "subject", "role", "text", "observed_at", "recorded_at", "source", "resolution"),
       ("drafts", "confirmed_refs", "reply_ref"), sources=("farmer", "publisher", "computed:chat")),
    # ── 되먹임(J) ─────────────────────────────────────────────────────────────────────
    _k("feedback.request", "되먹임",     # 사용자 개선 요구 — 농가·발행자가 직접 말한 것(오탐일 수 없다, 다리 B)
       ("id", "text", "target", "status", "observed_at", "recorded_at", "source", "resolution"),
       ("subject", "target_ref", "response", "item_ref"), sources=("farmer", "publisher")),
    _k("feedback.prediction", "되먹임",   # 예측 원장 — 3층이 낸 판단함의 대조 가능한 주장. 바뀔 때만 한 줄.
       ("id", "subject", "decision_id", "envelope_kind", "payload", "payload_hash", "observed_at", "recorded_at", "source", "resolution"),
       ("grade", "code_head"), sources=("computed:judge",)),
    _k("feedback.outcome", "되먹임",      # 대조 결과 — 예측 ↔ 사건 원장. 사건이 없으면 '대조 불가'(값을 메우지 않는다)
       ("id", "subject", "decision_id", "prediction_id", "verdict", "detail", "observed_at", "recorded_at", "source", "resolution"),
       ("actual_ref",), sources=("computed:evolve",)),
    _k("improvement.item", "되먹임",      # 개선 항목 — 자기개선 업무의 단위. 보이게까지 자동, 확장 방향의 채택은 사람.
       ("id", "origin", "target", "proposal", "direction", "status", "auto_applied", "observed_at", "recorded_at", "source", "resolution"),
       ("subject", "target_ref", "applied_ref", "verify", "note", "history"),
       sources=("farmer", "publisher", "computed:evolve"), layer3_input=True),
)}

LAYER3_INPUT_KINDS: frozenset[str] = frozenset(k.name for k in KINDS.values() if k.layer3_input)
# 3층이 받는 재배 단위 = 등록부 필드 + 필지에서 붙는 비PII·좌표 필드(경계 허용 목록의 원천)
PARCEL_FIELDS_TO_LAYER3: tuple[str, ...] = ("lat", "lon", "area_m2", "use", "irrigation", "drainage", "slope",
                                            "microclimate", "night_light", "environment")
LAYER3_SUBJECT_FIELDS: frozenset[str] = (frozenset(KINDS["subject"].required) | frozenset(KINDS["subject"].optional)
                                         | frozenset(PARCEL_FIELDS_TO_LAYER3))
SUBJECT_STATUS: tuple[str, ...] = ("계획", "재배 중", "종료")


def _source_ok(kind: Kind, source: Any) -> bool:
    if not isinstance(source, str) or not source:
        return False
    for s in kind.sources:
        if s.endswith(":") and source.startswith(s):
            return True
        if s == source:
            return True
    return not kind.sources


def validate(rec: dict[str, Any], kind: str | None = None) -> dict[str, Any]:
    """레코드 1건 검증. 위반은 SchemaError(걷어 내지 않는다 — fail-open 금지). 통과하면 그대로 돌려준다."""
    if not isinstance(rec, dict):
        raise SchemaError("레코드가 dict 가 아니다")
    name = kind or rec.get("kind")
    if name not in KINDS:
        raise SchemaError(f"스키마에 없는 레코드 종류: {name!r}")
    k = KINDS[name]
    if kind is None and rec.get("kind") != name:
        raise SchemaError("kind 불일치")
    missing = [f for f in k.required if f not in rec]
    if missing:
        raise SchemaError(f"{name}: 필수 필드 없음 {missing}")
    extra = set(rec) - k.fields
    if extra:
        raise SchemaError(f"{name}: 스키마에 자리가 없는 필드 {sorted(extra)} — 허용 목록 밖")
    if not _source_ok(k, rec.get("source")):
        raise SchemaError(f"{name}: source {rec.get('source')!r} 는 이 종류의 허용 출처가 아니다 {sorted(k.sources)}")
    if "resolution" in k.required and not rec.get("resolution"):
        raise SchemaError(f"{name}: resolution(해상도)이 비어 있다 — 1층 3요건")
    if rec.get("source") in HUMAN_SOURCES or str(rec.get("source", "")).startswith("mall:"):
        if "observed_at" in k.required and not rec.get("observed_at"):
            raise SchemaError(f"{name}: 대상 시각(observed_at)이 없다 — 입력 시각으로 메우지 않는다")
    hit = FORBIDDEN_FIELDS & set(rec)
    vals = rec.get("values")
    if isinstance(vals, dict):
        hit |= FORBIDDEN_FIELDS & set(vals)
    if hit:
        raise SchemaError(f"{name}: 금지 필드 {sorted(hit)}")
    _validate_vocab(name, rec)
    return rec


def _validate_vocab(name: str, rec: dict[str, Any]) -> None:
    if name == "feedback.request":
        if rec["status"] not in REQUEST_STATUS:
            raise SchemaError(f"요구 상태가 어휘 밖: {rec['status']!r}")
        if rec["target"] not in TARGETS:
            raise SchemaError(f"요구 대상이 어휘 밖: {rec['target']!r}")
    elif name == "improvement.item":
        if rec["status"] not in ITEM_STATUS:
            raise SchemaError(f"개선 항목 상태가 어휘 밖: {rec['status']!r}")
        if rec["direction"] not in DIRECTIONS:
            raise SchemaError(f"개선 방향이 어휘 밖: {rec['direction']!r}")
        if rec["target"] not in TARGETS:
            raise SchemaError(f"개선 대상이 어휘 밖: {rec['target']!r}")
        if rec["auto_applied"] and rec["direction"] != "보수":
            raise SchemaError("확장 방향은 자동 적용될 수 없다 — 사람이 채택한다(D-14)")
        if not isinstance(rec["origin"], dict) or not rec["origin"].get("kind"):
            raise SchemaError("개선 항목은 출처(origin.kind · origin.ref)가 있어야 한다 — 근거 없는 개선은 없다")
    elif name == "feedback.outcome":
        if rec["verdict"] not in VERDICTS:
            raise SchemaError(f"대조 판정이 어휘 밖: {rec['verdict']!r}")


def stamp(rec: dict[str, Any]) -> dict[str, Any]:
    """검증 뒤 schema_version 을 찍어 돌려준다 — 원장에 쓰는 직전 한 번."""
    validate(rec)
    out = dict(rec)
    out["schema_version"] = SCHEMA_VERSION
    return out


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def public_fields(kind: str) -> frozenset[str]:
    """화면·봉투에 내도 되는 필드 — PII 를 뺀 것."""
    k = KINDS[kind]
    return k.fields - frozenset(k.pii)


def describe() -> list[dict[str, Any]]:
    """문서 생성용(scripts/build_schema_doc.py)."""
    return [{"kind": k.name, "layer": k.layer, "required": list(k.required), "optional": list(k.optional),
             "sources": sorted(k.sources), "layer3_input": k.layer3_input, "subject_bound": k.subject_bound, "pii": list(k.pii)}
            for k in KINDS.values()]
