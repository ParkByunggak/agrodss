# -*- coding: utf-8 -*-
# FILE: mall/product.py
# ROLE: [M-11 몰 MVP 목업 · 몰-B/C/F/G/H] 상품 상세 = **현장 영상의 시계열**(대원칙). 상품 키 = 재배 단위(몰-B).
#
#   DSS → 몰 허용(몰-H): 영상 공개 뷰(위치는 있음/없음만) · 촬영 시점 칸(격자) · consumer_visible=True 인 봉투(판정+관측일+기준, 판단함만)
#   DSS → 몰 금지: 필지 상세(주소 · PNU · 좌표 · 검정값) · 1·2층 원본 값 · 영상 판독(2층)
#   인증 표기(몰-F): 법정 인증은 **인증서 확인 없이 표기 금지** — cert_legal 이 참일 때만 '유기' 등을 쓴다. 아니면 '인증 표기 없음'.
#   노출 판정(몰-G): 첫 시즌 비노출 권고(D-2 대기) — consumer_visible 이 전부 False 라 실질 0건. 규칙은 코드에 서 있다.
#   예약 판매(몰-B · D-3 대기) · 수량 예측(몰-N 입력 고아) — 자리만 두고 값을 지어내지 않는다.
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from grid import schema as grid_schema
from ingest import media, parcels, subjects
from judge import run as judge_run
from schema import records as sch

STATUS_BY_SUBJECT = {"계획": "생육 준비", "재배 중": "생육 중(예약 없음 — D-3 대기)", "종료": "판매 종료"}
NO_CERT_LABEL = "인증 표기 없음 — 인증서 확인 전(몰-F)"
# 상품 뷰에 절대 나타나면 안 되는 키(몰-H · I-5 §1-2). 검사가 재귀로 전수를 센다.
FORBIDDEN_KEYS: frozenset[str] = sch.PII_FIELDS | frozenset({"soil_chem", "soil_exam_at", "values", "raw", "sha256", "file", "origin"})


class MallBoundaryError(ValueError):
    pass


def cert_label(parcel: dict[str, Any] | None, subject: dict[str, Any]) -> str:
    """법정 인증 표기는 인증서 확인(cert_legal=True)이 있을 때만. 주장(cert_claimed)만으로는 안 쓴다."""
    if parcel and parcel.get("cert_legal") is True and (parcel.get("cert_claimed") or subject.get("cert")):
        return f"{parcel.get('cert_claimed') or subject.get('cert')} 인증(인증서 확인)"
    return NO_CERT_LABEL


def capture_timeline(subject: dict[str, Any], videos: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """격자 촬영 칸(shoot=True)마다 — 그 창에 찍힌 영상들 · 없으면 '촬영 예정/미촬영'. 소비자가 보는 것은 시계열 목록(몰-C)."""
    # [U-23] 몰 화면은 봉투를 내지 않는다 — 사유는 `load_unit` 이 이미 '읽다 버린 것' 에 남겼고(/changes),
    # 소비자에게는 시계열이 비는 것으로 족하다. 읽는 자리는 그래도 정본 하나다.
    unit, _miss = grid_schema.load_unit(subject)
    anchor = subject.get("anchor")
    if unit is None or not anchor:
        return []
    a = date.fromisoformat(anchor)
    out = []
    for s in unit.get("stages", []):
        cap = s.get("capture")
        if not isinstance(cap, dict) or not cap.get("shoot"):
            continue
        w = s["window"]
        start, end = a + timedelta(days=w["from_day"]), a + timedelta(days=w["to_day"])
        clips = [v for v in videos if start.isoformat() <= (v.get("observed_at") or "")[:10] <= end.isoformat()]
        if clips:
            state = "촬영됨"
        elif today < start:
            state = "촬영 예정"
        elif today <= end:
            state = "촬영 창 열림"
        else:
            state = "미촬영(창 지남)"
        out.append({"stage": f"{s['order']}. {s['name']}", "scene": cap.get("scene", ""), "window": f"{start} ~ {end}", "state": state,
                    "clips": [{"id": v.get("id"), "kind": "사진" if v.get("kind") == "observation.image" else "영상",
                               "observed_at": v.get("observed_at"), "duration_sec": v.get("duration_sec"),
                               "width": v.get("width"), "height": v.get("height"), "note": v.get("note", "")} for v in clips]})
    return out


def visible_judgments(envs: list[Any]) -> list[dict[str, Any]]:
    """몰-G: consumer_visible 이고 '판단함'인 봉투만 — 판정 + 관측일(as_of) + 기준(rule)이 같이 간다. 값 원본은 안 간다."""
    from judge import registry
    out = []
    for e in envs:
        if not getattr(e, "consumer_visible", False) or e.kind != "판단함":
            continue
        d = registry.get(e.decision_id)
        out.append({"decision": d.name if d else e.decision_id, "kind": e.kind, "grade": e.grade, "as_of": e.as_of[:10],
                    "basis": (d.rule if d else ""), "summary": (e.result or {}).get("summary") or ""})
    return out


def assert_public(obj: Any, path: str = "view") -> None:
    """몰-H 게이트 — 뷰 어디에도 금지 키가 없어야 한다(재귀). 있으면 조용히 빼지 않고 올린다."""
    if isinstance(obj, dict):
        bad = FORBIDDEN_KEYS & set(obj)
        if bad:
            raise MallBoundaryError(f"[몰-H] {path}: 몰 뷰에 금지 키 {sorted(bad)}")
        for k, v in obj.items():
            assert_public(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            assert_public(v, f"{path}[{i}]")


def product_view(subject_id: str, today: date | None = None, envs: list[Any] | None = None) -> dict[str, Any]:
    today = today or date.today()
    s = subjects.by_id(subject_id)
    if not s:
        raise MallBoundaryError(f"없는 상품(재배 단위): {subject_id}")
    parcel = parcels.by_id(s.get("parcel", ""))
    videos = [media.public_view(v) for v in media.list_records(subject_id)]
    videos.sort(key=lambda v: v.get("observed_at") or "")
    envs = envs if envs is not None else judge_run.judgments_for(subject_id, today=today)
    view = {
        "product_id": s["id"], "title": f"{s.get('crop')} · {s.get('season')}", "label": s.get("label"),
        "status": STATUS_BY_SUBJECT.get(s.get("status") or ("재배 중" if s.get("anchor") else "계획"), "생육 중"),
        "anchor_kind": s.get("anchor_kind"), "days_since_anchor": (today - date.fromisoformat(s["anchor"])).days if s.get("anchor") else None,
        "cert_label": cert_label(parcel, s),
        "use": (parcel or {}).get("use"), "mall_supply": (parcel or {}).get("mall_supply"),
        "timeline": capture_timeline(s, videos, today),
        "clips_total": len(videos),
        "judgments": visible_judgments(envs),
        "reservation": "예약 판매 없음 — D-3 대기(수량 예측 · 환불 규칙 선행)",
        "quantity": "수량 예측 없음 — 몰-N 입력 고아",
        "editing_rule": "무편집 또는 자르기만 — 연출·보정은 현장 영상이 아니다(몰-C)",
        "as_of": today.isoformat(),
    }
    assert_public(view)
    return view
