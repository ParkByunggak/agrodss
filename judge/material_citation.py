# -*- coding: utf-8 -*-
# FILE: judge/material_citation.py
# ROLE: [M-15 ④ · H 자재 분리] 첫 '사실 인용' 산출 — 지금 단계의 유기 자재 계열을 공시 목록에서 실제 제품으로 인용한다.
#
# I-1 §2-3: 사실 인용은 판단이 아니다. 3층을 거치는 이유는 인용 대상이 1층 3요건(관측 시각·출처·해상도)을
#   만족하는지 확인하는 것뿐이고, 인용문에는 출처·시각이 붙는다. 여기서는 봉투 result 에 인용 항목이 실린다
#   (사실 인용은 값을 전달하는 것이 목적이라 4층 격리 예외 — 봉투 자체가 인용문이다).
#
# 인증 갈래(H): cert=유기 → 공시 유기농업자재. cert=관행 → PSIS 등록약제(M-15 ⑤, 2026-09-19 — 칸의 병해충 위험마다
#   작물·병해충 등록약제 + 안전사용기준). 범주명("BT제")으로 메우지 않는다 — 목록에 없으면 no_data 로 정직하게 비운다.
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from grid import capture, schema as grid_schema
from ingest import organic_materials as om, psis
from judge import registry
from judge.envelope import AxisUse, Envelope
from judge.harvest_timing import _load_unit

DECISION_ID = "material_citation"

registry.register(registry.Decision(
    id=DECISION_ID,
    name="자재 인용(유기 공시 · 관행 PSIS)",
    required_axes=("cert", "anchor"),
    optional_axes=(),
    forbidden_axes=(),
    rule=("cert=유기이면 오늘이 속한 격자 칸의 작업 자재(유기 갈래) 계열마다 농관원 공시 목록에서 유효 제품을 인용한다. "
          "계열은 params.aliases 로 공시 자재명 검색어에 대응시킨다. 목록에 없으면 그 계열은 no_data. "
          "cert=관행이면 그 칸의 병해충 위험마다 PSIS 등록약제(작물·병해충)와 안전사용기준을 인용한다 — 키 없으면 판단 불가(데이터). "
          "인용은 판단이 아니다 — 효능 보증 아님을 함께 싣는다."),
    revisit_days=7,
    params={
        "per_alias_limit": 3,
        "aliases": {"BT제": ("비티", om.TYPE_PEST), "BT": ("비티", om.TYPE_PEST), "님": ("님", om.TYPE_PEST),
                    "유황": ("황", om.TYPE_PEST), "석회보르도액": ("보르도", om.TYPE_PEST), "페로몬": ("페로몬", om.TYPE_PEST),
                    "천적": ("천적", om.TYPE_PEST), "유기질 비료": ("유기질", om.TYPE_SOIL), "유기질": ("유기질", om.TYPE_SOIL),
                    "완숙 퇴비": ("퇴비", om.TYPE_SOIL), "퇴비": ("퇴비", om.TYPE_SOIL)},
        "aliases_source": "격자 자재 칸 문면의 계열명 ↔ 공시 자재명(MTRIL_NM) 부분일치 검색어 — 추론, 발행자 검토 대기",
    },
))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _families(stage: dict[str, Any]) -> list[str]:
    """칸의 작업 자재(유기) 문면에서 계열명 추출 — '·' 로 나누고 괄호·설명은 뗀다."""
    out: list[str] = []
    for t in (stage.get("tasks") or []) if stage.get("tasks") != grid_schema.NA else []:
        m = t.get("materials")
        if not isinstance(m, dict):
            continue
        for s in m.get("유기", []):
            for part in re.split(r"[·,]", s):
                part = re.sub(r"\(.*?\)", "", part).split("—")[0].strip()   # 괄호 설명 · '— 비고' 는 뗀다
                part = part.removeprefix("공시 ").strip()                      # '공시 유기질 비료' → '유기질 비료'
                if part and part not in out:
                    out.append(part)
    return out


CERTS = ("유기", "관행")


def _conventional(subject: dict[str, Any], stage: dict[str, Any], today: date, as_of: str, sid: str, anchor: str,
                  psis_search=None) -> Envelope:
    """[M-15 ⑤] 관행 갈래 — 칸의 병해충 위험마다 PSIS 등록약제. 위험이 병해충이 아니면(서리 · 부패 · 지연) 인용 대상이 없다."""
    d = registry.get(DECISION_ID)
    risks = stage.get("risks") if isinstance(stage.get("risks"), list) else []
    terms = [(r["name"], t) for r in risks if isinstance(r, dict) for t in psis.pest_terms(r["name"])]
    if not terms:
        return Envelope("해당 없음", DECISION_ID, sid, as_of, result={"why": f"칸 '{stage['name']}' 에 병해충 위험이 없다 — PSIS 인용 대상 없음"})
    if psis_search is None and not psis.key():
        return Envelope("판단 불가(데이터)", DECISION_ID, sid, as_of,
                        missing=[{"axis": "cert", "who_can_fill": "발행자 — .env PSIS_API_KEY(psis.rda.go.kr 전용 활용신청)"}],
                        result={"why": "PSIS 키가 없어 등록약제를 인용할 수 없다 — 범주명으로 메우지 않는다"})
    crop = subject.get("crop", "")
    groups: list[dict[str, Any]] = []
    for risk, term in terms:
        rec = (psis_search or psis.search)(crop, term, today=today)
        groups.append({"risk": risk, "pest": term, "status": rec.get("status"), "total": rec.get("total", 0),
                       "items": rec.get("items", []), "queried_as": rec.get("queried_as"), "note": rec.get("message")})
    seen = [g for g in groups if g["status"] == "success"]
    inputs = [AxisUse("cert", None, subject.get("source", "farmer"), "cultivation_unit", "관측"),
              AxisUse("anchor", anchor, subject.get("source", "farmer"), "cultivation_unit", "관측")]
    return Envelope(
        "사실 인용", DECISION_ID, sid, as_of, inputs=inputs,
        revisit_at=(today + __import__("datetime").timedelta(days=d.revisit_days)).isoformat(),
        result={"stage": f"{stage['order']}. {stage['name']}", "groups": groups, "cited_families": len(seen),
                "citation": {"source": "농촌진흥청 농약안전정보시스템(PSIS) 농약등록정보 검색 SVC01",
                             "observed_at": today.isoformat(), "resolution": "national",
                             "note": "등록 = 그 작물·병해충에 쓸 수 있음(PLS). 희석배수 · 안전사용시기 · 사용횟수를 지킨다. 효능 보증 아님. "
                                     "유기·무농약 인증 필지에는 쓸 수 없다(H 자재 분리)"}},
        notes=["작용기작(indictSymbl)이 다른 약제를 앞세운다(VELA W-20 — 같은 기작만 나열되던 실사례)", "0건은 0건으로 둔다 — 범주명으로 메우지 않는다"],
    )


def judge(subject: dict[str, Any], today: date | None = None, psis_search=None) -> Envelope:
    today = today or date.today()
    as_of = _now()
    sid = subject.get("id", "?")
    d = registry.get(DECISION_ID)
    cert = subject.get("cert")
    if not cert:
        return Envelope("판단 불가(데이터)", DECISION_ID, sid, as_of,
                        missing=[{"axis": "cert", "who_can_fill": "농가 — 인증 유형(필지 고정 정보)"}],
                        result={"why": "인증 유형이 없어 어느 자재 목록을 볼지 정할 수 없다"})
    if cert not in CERTS:
        return Envelope("해당 없음", DECISION_ID, sid, as_of,
                        result={"why": f"인증 유형 {cert!r} — 유기(공시) · 관행(PSIS) 갈래만 인용한다. 무농약은 갈래 규칙 미정"})
    unit = _load_unit(subject)
    anchor = subject.get("anchor")
    if unit is None:
        return Envelope("해당 없음", DECISION_ID, sid, as_of, result={"why": "격자 단위가 없다"})
    if not anchor:
        return Envelope("판단 불가(데이터)", DECISION_ID, sid, as_of,
                        missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일"}], result={"why": "기준점이 없다"})
    day = (today - date.fromisoformat(anchor)).days
    stage = capture.stage_for_day(unit, day)
    if stage is None:
        return Envelope("해당 없음", DECISION_ID, sid, as_of, result={"why": f"기준점 후 {day}일 — 격자 창 밖"})
    if cert == "관행":
        return _conventional(subject, stage, today, as_of, sid, anchor, psis_search)
    fams = _families(stage)
    if not fams:
        return Envelope("해당 없음", DECISION_ID, sid, as_of, result={"why": f"칸 '{stage['name']}' 에 유기 자재 계열이 없다"})
    canon = om.load()
    groups: list[dict[str, Any]] = []
    for fam in fams:
        alias = next((v for k, v in d.params["aliases"].items() if k in fam), None)
        if alias is None:
            groups.append({"family": fam, "status": "no_alias", "items": [], "note": "검색어 대응 없음 — params.aliases 보강 대상"})
            continue
        kw, mtype = alias
        res = om.search(mtype, kw, limit=int(d.params["per_alias_limit"]), today=today)
        groups.append({"family": fam, "keyword": kw, "type": mtype, "status": res["status"], "total": res["total"],
                       "items": [i["values"] for i in res["items"]]})
    fetched = canon.get("fetched_at")
    fetched_iso = f"{fetched[:4]}-{fetched[4:6]}-{fetched[6:]}" if fetched and len(fetched) == 8 else fetched
    inputs = [AxisUse("cert", None, subject.get("source", "farmer"), "cultivation_unit", "관측"),
              AxisUse("anchor", anchor, subject.get("source", "farmer"), "cultivation_unit", "관측")]
    cited = sum(1 for g in groups if g["status"] == "success")
    return Envelope(
        "사실 인용", DECISION_ID, sid, as_of, inputs=inputs,
        revisit_at=(today + __import__("datetime").timedelta(days=d.revisit_days)).isoformat(),
        result={"stage": f"{stage['order']}. {stage['name']}", "groups": groups, "cited_families": cited,
                "citation": {"source": "국립농산물품질관리원 유기농업자재 공시현황(공공데이터포털 15080748)",
                             "observed_at": fetched_iso, "resolution": "national",
                             "note": "공시 = 유기재배에 쓸 수 있음(인정). 효능·방제 성능 보증이 아니다 — 대상 병해충·작물 적용 범위는 제품 라벨에서"}},
        notes=[f"계열↔검색어 대응: {d.params['aliases_source']}"],
    )
