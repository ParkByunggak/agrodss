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
import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Any

SCHEMA_VERSION = 1

# [칸 3 재측정 2026-09-20 · C17] 화면 서버는 ThreadingHTTPServer — 요청마다 스레드가 선다. 원장 가드는 대부분
# **읽고 → 검사하고 → 덧붙이는** 꼴(재확인 방지 · sha 중복 · 예측 payload 대조 · 개선 항목 중복)이라 두 요청이 겹치면
# 둘 다 "없다"를 보고 둘 다 쓴다. 실측(2026-09-20): 확인 단추를 동시에 두 번 누르면 같은 예찰 사건이 원장에 **두 줄**.
# 그 한 벌이 계획 대 실제와 되먹임 대조에서 두 번 세어진다. 검사·덧붙이기를 한 덩이로 묶는다.
#   재진입(RLock)인 이유: 가드가 다시 원장 함수를 부른다(confirm → add_event → _append) — 같은 스레드가 두 번 잡는다.
#   범위: 한 프로세스 안의 스레드. 프로세스끼리(서버 + CLI)는 파일 잠금이 필요하고 발행자 PC(Windows)에서 재야 한다 — 등재.
ledger_lock = threading.RLock()

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
       ("anchor", "anchor_kind", "grid_unit", "cert", "status", "recorded_at", "note", "ended_at"),   # ended_at: 종료일(작기 종료 — 시점 걷기 2026-09-20)
       sources=("farmer", "publisher", "d1_first_farm.md (발행자 2026-09-18)"), layer3_input=True),
    _k("user", "등록부",     # 사용자 정보 탭(M-13) — 표시명 · 역할 · 필지 id 목록. 연락처·주소는 두지 않는다(PII)
       ("id", "name", "role", "parcels", "source", "recorded_at"), ("note",),
       sources=("farmer", "publisher"), subject_bound=False),
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
    _k("observation.image", "1층 사실",   # 사진 — 영상과 같은 3요건. 촬영 시각은 EXIF 또는 입력(M-13 채팅 반입)
       ("id", "subject", "observed_at", "observed_at_source", "recorded_at", "source", "resolution", "origin", "file", "sha256", "bytes"),
       ("width", "height", "duration_sec", "gps", "note"), sources=("farmer",), layer3_input=True, pii=("gps",)),
    _k("event", "1층 사실",
       ("id", "type", "subject", "observed_at", "recorded_at", "source", "resolution"),
       ("advice_ref", "materials", "quantity", "quality_grade", "return_reason", "note", "chat_ref", "risk", "severity"),
       sources=("farmer", "mall:settlement"), layer3_input=True),
    _k("observation.note", "1층 사실",   # I-3 §3 직접 관찰값 — 농가가 본 것(최종 심급). 채팅에서 분류돼 확인 뒤 들어온다
       ("id", "subject", "text", "observed_at", "recorded_at", "source", "resolution"),
       ("tags", "chat_ref"), sources=("farmer",), layer3_input=True),
    _k("plan.farmer", "1층 계획",         # 농가가 스스로 세운 계획(격자 계획과 다르다) — 영농일지의 '할 일'
       ("id", "subject", "task", "planned_day", "recorded_at", "observed_at", "source", "resolution"),
       ("note", "chat_ref", "done_ref"), sources=("farmer",), layer3_input=True),
    _k("decision.noncompliance", "1층 사실",
       ("id", "subject", "planned_task", "planned_day", "reason", "observed_at", "recorded_at", "source", "resolution"),
       sources=("farmer",), layer3_input=True),
    # ── 1층 사실(외부 원천, D-9 인용) ───────────────────────────────────────────────────
    _k("observation.weather_daily", "1층 사실", _EXT_OBS + ("station",), sources=("external:",), layer3_input=True, subject_bound=False),
    _k("reference.climate_normal", "1층 사실", _EXT_OBS + ("station", "for_day"), sources=("external:",), layer3_input=True, subject_bound=False),
    _k("forecast.weather_daily", "1층 사실", _EXT_OBS + ("for_day",), ("hourly_tmp", "sky", "pty", "hours"),   # hours: [발행자 2026-09-29] 3시간 줄(t · tmp · sky · pty · pop · pcp · wsd)
       sources=("external:",), layer3_input=True, subject_bound=False),
    # [D-21 중기 2026-09-28] 중기예보(D+3~D+10 · 권역 단위 — getMidLandFcst 육상 + getMidTa 기온). 단기와 **다른 kind** 다 — 판단 넷이 단기 줄을
    # 날짜별로 읽으므로 같은 kind 에 섞으면 해상도가 다른 값이 그 판단에 들어간다. 오전·오후 원문은 am/pm(8일 뒤는 allday)에 그대로.
    _k("forecast.weather_mid", "1층 사실", _EXT_OBS + ("for_day", "region"), ("am", "pm", "allday", "ta_region"),
       sources=("external:",), layer3_input=True, subject_bound=False),
    # [D-21 장기 2026-09-28 · 발행자 ⓐ] 1·3개월 전망 수동 정본 — 오픈 API 가 없어(VELA 실측 2026-08-05) 발행자가 발표문 수치를 출처와 함께 등재한 것.
    # 출처는 publisher: 뿐(external: 이 아니다 — 원천을 부른 적이 없다는 사실을 source 가 말한다). citation{title,url} 필수.
    _k("reference.climate_outlook", "1층 사실", _EXT_OBS + ("period_type", "period_from", "period_to", "region", "citation"), ("note",),
       sources=("publisher:",), layer3_input=True, subject_bound=False),
    _k("observation.pest_forecast", "1층 사실",
       _EXT_OBS + ("region", "crop_requested", "crop_code_crop", "raw", "schema_confirmed"), ("proxy_reason",),
       sources=("external:",), layer3_input=True, subject_bound=False),
    _k("reference.organic_material_notice", "1층 사실", ("axis", "observed_at", "source", "resolution", "values"),
       sources=("external:",), layer3_input=True, subject_bound=False),
    _k("observation.soil_exam", "1층 사실",
       ("status", "pnu", "axis", "source", "resolution", "observed_at", "fetched_at"),
       ("exam_year", "address_label", "values", "units", "message"),
       sources=("external:",), layer3_input=True, subject_bound=False, pii=("pnu", "address_label")),
    _k("reference.fertilizer_prescription", "1층 사실",   # 흙토람 FrtlzrUse — 필지 검정값 기반 N·P·K·퇴비(kg/10a). PII: pnu
       ("axis", "status", "pnu", "crop_code", "observed_at", "fetched_at", "source", "resolution", "values", "units"),
       ("crop_name", "raw", "message"), sources=("external:",), layer3_input=True, subject_bound=False, pii=("pnu",)),
    _k("reference.pesticide_registration", "1층 사실",    # PSIS SVC01 — 작물·병해충별 현행 등록약제 + 안전사용기준(전국). 관행 갈래
       ("axis", "status", "crop", "pest", "observed_at", "fetched_at", "source", "resolution", "total", "items"),
       ("queried_as", "message"), sources=("external:",), layer3_input=True, subject_bound=False),
    _k("reference.fertilizer_standard", "1층 사실",       # 흙토람 FrtlzrStdUse — 작물 표준 시비량(전국). 필지값이 아니다
       ("axis", "status", "crop_code", "observed_at", "fetched_at", "source", "resolution", "values", "units"),
       ("crop_name", "raw", "message"), sources=("external:",), layer3_input=True, subject_bound=False),
    # ── 1층 계획 ─────────────────────────────────────────────────────────────────────
    _k("plan.task", "1층 계획",
       ("source", "resolution", "stage", "task", "work_day", "work_date", "prep_date_own", "prep_date_rental", "tools",
        "materials", "retry_possible", "deadline_day", "deadline_date", "source_note"),
       ("fixable_by",),            # [WO-ASK-01 §10 2026-10-03] 격자 작업이 추론값이면 누가 고칠 수 있는가(grid.schema.FIXABLE_BY) — 계획 행이 그 표지를 든다
       sources=("computed:grid",), layer3_input=True, subject_bound=False),
    _k("plan.capture", "1층 계획",
       ("source", "resolution", "stage", "task", "work_day", "work_date", "prep_date_own", "prep_date_rental", "tools",
        "materials", "retry_possible", "deadline_day", "deadline_date", "source_note"),
       sources=("computed:grid",), layer3_input=True, subject_bound=False),
    _k("plan.target_date", "1층 계획",   # I-3 §4 — 농가가 정한 것만(몰 수요가 정하면 조언 입력이 된다)
       ("subject", "target_date", "source", "resolution"), ("id", "recorded_at", "observed_at", "note", "chat_ref"),
       sources=("farmer",), layer3_input=True),
    # ── 1층 사실(농가 발화 — I-3 §3 "질의 자체가 관찰", M-13 채팅) ─────────────────────────
    _k("chat.message", "1층 사실",   # 채팅 한 줄. 분류(2층)는 drafts 에 제안으로만 — 확인(confirm)해야 원장에 들어간다
       ("id", "subject", "role", "text", "observed_at", "recorded_at", "source", "resolution"),
       ("drafts", "confirmed_refs", "reply_ref", "retry_of", "edit_of", "request_ref", "input_mode", "media_refs",
        "after_ask"),      # [WO-ASK-01 §9 2026-10-03] 직전 물음 뒤 처음 온 말 — {axes, msg}(어느 물음 뒤인지 · 답이 맞았는지는 다음 단계)
       sources=("farmer", "publisher", "computed:chat")),
    # ── 되먹임(J) ─────────────────────────────────────────────────────────────────────
    _k("feedback.request", "되먹임",     # 사용자 개선 요구 — 농가·발행자가 직접 말한 것(오탐일 수 없다, 다리 B)
       ("id", "text", "target", "status", "observed_at", "recorded_at", "source", "resolution"),
       ("subject", "target_ref", "response", "item_ref"), sources=("farmer", "publisher")),
    _k("feedback.prediction", "되먹임",   # 예측 원장 — 3층이 낸 판단함의 대조 가능한 주장. 바뀔 때만 한 줄.
       # [코드 평가 A2] last_seen_at — 같은 주장이 마지막으로 확인된 판정일. 바뀌지 않아도 이것은 갱신된다(같은 id 로 덧붙임 · latest 우선).
       #   없으면 창이 첫 발행일+horizon 에서 끝나 그 뒤 피해가 "앞선 경보 없음"으로 잘못 적혔다.
       ("id", "subject", "decision_id", "envelope_kind", "payload", "payload_hash", "observed_at", "recorded_at", "source", "resolution"),
       ("grade", "code_head", "last_seen_at"), sources=("computed:judge",)),
    _k("feedback.outcome", "되먹임",      # 대조 결과 — 예측 ↔ 사건 원장. 사건이 없으면 '대조 불가'(값을 메우지 않는다)
       ("id", "subject", "decision_id", "prediction_id", "verdict", "detail", "observed_at", "recorded_at", "source", "resolution"),
       ("actual_ref",), sources=("computed:evolve",)),
    _k("names.candidate", "되먹임",       # U-14 사투리·이명 후보 — 사전에 없는 이름. 보이게까지 자동, 승인(정본 CSV 등재)은 사람
       ("id", "query", "normalized", "context", "status", "observed_at", "recorded_at", "source", "resolution"),
       ("subject", "canonical", "alias_kind", "note"), sources=("farmer", "publisher")),
    _k("verification.live", "되먹임",     # 라이브 3/3 재현 기록(scripts/live_reproduce.py) — 독립 프로세스 회차 · 대조 · 판정. 완료의 증거
       ("id", "subject", "subjects", "code_head", "runs", "verdict", "live", "agree", "total", "diffs", "cache_suspect",
        "observed_at", "recorded_at", "source", "resolution"), (), sources=("computed:verify",)),
    _k("improvement.item", "되먹임",      # 개선 항목 — 자기개선 업무의 단위. 보이게까지 자동, 확장 방향의 채택은 사람.
       ("id", "origin", "target", "proposal", "direction", "status", "auto_applied", "observed_at", "recorded_at", "source", "resolution"),
       ("subject", "target_ref", "applied_ref", "verify", "note", "history"),
       sources=("farmer", "publisher", "computed:evolve"), layer3_input=True),
)}

LAYER3_INPUT_KINDS: frozenset[str] = frozenset(k.name for k in KINDS.values() if k.layer3_input)
# 3층이 받는 재배 단위 = 등록부 필드 + 필지에서 붙는 비PII·좌표 필드(경계 허용 목록의 원천)
PARCEL_FIELDS_TO_LAYER3: tuple[str, ...] = ("lat", "lon", "area_m2", "use", "irrigation", "drainage", "slope",
                                            "microclimate", "night_light", "environment",
                                            "mall_supply")   # [코드 평가 B7] 출하 결정(D-8)이 읽는 불리언 — 없어서 라이브 경로에서 도달 불가였다
# 실행부(judge.run)가 원천 저장소에서 붙이는 파생 필드 — 토양검정 값(soil_chem)과 검정일. 봉투에는 이름만 실린다(4층 격리)
SUBJECT_DERIVED_FIELDS: tuple[str, ...] = ("soil_chem", "soil_exam_at")
LAYER3_SUBJECT_FIELDS: frozenset[str] = (frozenset(KINDS["subject"].required) | frozenset(KINDS["subject"].optional)
                                         | frozenset(PARCEL_FIELDS_TO_LAYER3) | frozenset(SUBJECT_DERIVED_FIELDS))
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
    elif name == "subject":
        # [코드 평가 D3 · A12 · 2026-09-19] 기준점은 YYYY-MM-DD 여야 한다 — 화면 사이드바가 매 페이지 date.fromisoformat 으로 읽어,
        # 비ISO 값 하나가 모든 셸 화면을 죽였다. 상태 어휘(SUBJECT_STATUS)도 등록부 편집 경로(subjects.add)만이 아니라 여기서 본다.
        if rec.get("status") is not None and rec["status"] not in SUBJECT_STATUS:
            raise SchemaError(f"재배 단위 상태가 어휘 밖: {rec['status']!r} — {' · '.join(SUBJECT_STATUS)}")
        a = rec.get("anchor")
        if a is not None:
            try:
                date.fromisoformat(str(a))
                ok = len(str(a)) == 10
            except ValueError:
                ok = False
            if not ok:
                raise SchemaError(f"기준점(anchor)은 YYYY-MM-DD 여야 한다: {a!r}")


def stamp(rec: dict[str, Any]) -> dict[str, Any]:
    """검증 뒤 schema_version 을 찍어 돌려준다 — 원장에 쓰는 직전 한 번."""
    validate(rec)
    out = dict(rec)
    out["schema_version"] = SCHEMA_VERSION
    return out


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def strip_pii(rec: dict[str, Any]) -> dict[str, Any]:
    """[코드 평가 §1-1 · 2026-09-19] 화면·몰용 PII 제거의 **정본 하나**. kind 를 알면 그 kind 가 선언한 pii 를, 모르면 전역 PII_FIELDS 를 뺀다.
    전에는 kind 별 pii 선언의 소비자가 문서 생성기뿐이었고 실제 제거는 parcels/media 의 손코딩 두 벌이었다(세 진실)."""
    k = KINDS.get(str(rec.get("kind") or ""))
    drop = frozenset(k.pii) | PII_FIELDS if k else PII_FIELDS
    return {key: v for key, v in rec.items() if key not in drop}


# ── 사람이 쓴 글을 인용할 때 ────────────────────────────────────────────────────────
# [전수 2026-10-05] 사람이 쓴 글을 **잘라서** 다른 문장에 싣는 자리가 여섯인데 **잘렸다고 말하는 곳은 한 곳**뿐이었다(채팅 인용 꼬리만 「…」 를 붙였다).
# 나머지 다섯은 말없이 자른다. 그중 일지 인용은 **30자**라 거의 매번 걸린다 — 「고랑 물 빠짐이 잘 되고 있고, 잎 끝 황화 현상은」 까지만 보인 채
# 시스템이 그것을 **그 사람의 말로** 되묻는다. 앞 회차 결함과 같은 축이다(그쪽은 낱말이 바뀌었고 이쪽은 뒤가 사라진다 — 둘 다 쓴 글이 달라져 돌아온다).
# 꼬리는 **자른 자리에만** 붙인다: 안 자른 글에 붙이면 그것도 거짓이다(양방향 검사가 둘 다 본다).
QUOTE_TAIL = "…"


def quote(text: Any, limit: int) -> str:
    """사람이 쓴 글을 limit 자까지 인용 — 자르면 꼬리를 붙여 **자른 것이 보이게** 한다. 저장이 아니라 인용(표시 · 이름 · 요구 문장)의 정본이다."""
    if limit < 1:
        raise ValueError(f"인용 한도는 1자 이상이어야 한다 — {limit}")
    s = "" if text is None else str(text)
    return s if len(s) <= limit else s[:limit] + QUOTE_TAIL


# ── 조사는 **앞말의 받침**이 고른다 ───────────────────────────────────────────────────
# [전수 2026-10-06] 사람에게 보이는 문장이 조사를 **손으로** 적어 어긋난 자리를 셌다. 값이 들어오는 자리라 **고정 조사는 반드시 언젠가 틀린다**:
#     「칸 '수확' 가 7일 뒤 열린다」(받침 ㄱ → 「이」)   「배수 나쁨 는 밭 정보의 고정값」(「은」)   「인증 유형 '유기' 은」(「는」)
#     「오늘이 2026-10-06 로 고정돼 있다」(육 → 「으로」)   「'수확 시기' 은 검토 전 추론」(「는」)   「어휘 '무농약' 를 읽었다」(「을」)
# 안쪽 낱말 표가 「재배 달력가」 를 고친 그 축의 **템플릿 판**이고, 고치는 길은 하나다 — 받침으로 고르는 정본.
# 한계는 적어 둔다: 끝이 한글도 숫자도 아니면(영문·기호) **받침 없음** 쪽을 쓴다(지어내지 않는다 · 검사가 그 한계를 문서화한다).
_JOSA_PAIRS: dict[str, tuple[str, str]] = {      # (받침 있음, 받침 없음)
    "이": ("이", "가"), "가": ("이", "가"), "은": ("은", "는"), "는": ("은", "는"),
    "을": ("을", "를"), "를": ("을", "를"), "과": ("과", "와"), "와": ("과", "와"),
    "으로": ("으로", "로"), "로": ("으로", "로"),
}
# 숫자로 끝나는 말은 **읽는 소리**로 센다(영 ㅇ · 일 ㄹ · 삼 ㅁ · 육 ㄱ · 칠 ㄹ · 팔 ㄹ) — 2 · 4 · 5 · 9 는 받침이 없다.
_DIGIT_FINAL: dict[str, int] = {"0": 21, "1": 8, "2": 0, "3": 16, "4": 0, "5": 0, "6": 1, "7": 8, "8": 8, "9": 0}
_RIEUL = 8      # 받침 ㄹ — 「으로」 가 아니라 「로」(종구로 · 7일로)


def _final(word: Any) -> int | None:
    """끝의 받침 코드(0 = 없음) — 뒤에서부터 한글이나 숫자를 찾는다(따옴표·괄호로 끝나는 말이 흔하다). 둘 다 없으면 None."""
    for ch in reversed(str("" if word is None else word).strip()):
        if "가" <= ch <= "힣":
            return (ord(ch) - 0xAC00) % 28
        if ch in _DIGIT_FINAL:
            return _DIGIT_FINAL[ch]
    return None


def josa(word: Any, pair: str) -> str:
    """앞말에 맞는 조사 하나 — `pair` 는 짝 중 아무 꼴로나 준다(「가」 든 「이」 든 (이, 가) 짝을 뜻한다)."""
    try:
        with_final, without = _JOSA_PAIRS[pair]
    except KeyError:
        raise ValueError(f"짝을 모르는 조사: {pair!r} — {sorted(set(_JOSA_PAIRS))}") from None
    f = _final(word)
    if not f:                                   # 받침 없음 · 또는 한글·숫자가 아예 없음(위에 적은 한계)
        return without
    if with_final == "으로" and f == _RIEUL:     # ㄹ 받침만 예외
        return without
    return with_final


def describe() -> list[dict[str, Any]]:
    """문서 생성용(scripts/build_schema_doc.py)."""
    return [{"kind": k.name, "layer": k.layer, "required": list(k.required), "optional": list(k.optional),
             "sources": sorted(k.sources), "layer3_input": k.layer3_input, "subject_bound": k.subject_bound, "pii": list(k.pii)}
            for k in KINDS.values()]
