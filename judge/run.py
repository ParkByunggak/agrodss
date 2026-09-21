# -*- coding: utf-8 -*-
# FILE: judge/run.py
# ROLE: 3층 실행부 — 재배 단위마다 1층 원천을 모아 판정기에 넘기고 봉투를 돌려준다.
#       4층(frontend)은 이 함수만 부른다. 1층 원천(ingest.kma)은 여기서만 만진다.
from __future__ import annotations

from datetime import date
from typing import Any

from ingest import events as ev
from ingest import feedback as fb
from ingest import kma, media, ncpms, parcels, soil_store
from judge import boundary, evolve, harvest_timing, material_citation, plan_vs_actual, risk_alert, stage_decisions
from judge.envelope import Envelope


def gather_pest(subject: dict[str, Any], today: date) -> tuple[list[dict[str, Any]] | None, str]:
    """작목의 NCPMS 예찰(판정하는 해). 키·코드 없으면 (None, 이유).

    [칸 3 재측정 2026-09-20 · A11] 전에는 연도를 `date.today().year` 로 스스로 정했다 — 판정의 '오늘'이
    고정돼도(AGRODSS_TODAY · 재현 · 과거 판정) 예찰만 실제 연도를 물어 같은 회차 안에 **연도가 둘**이었다.
    오늘은 위에서 정해 내려온다(§7.5 관문의 입력 — frontend 에서 닫은 형태가 한 층 아래에 그대로 있었다).
    """
    crop = subject.get("crop")
    if not crop:
        return None, "재배 단위에 작목이 없다"
    if not ncpms.api_key():
        return None, "예찰 키 없음(.env NCPMS_API_KEY)"
    r = ncpms.fetch_forecast(crop, year=today.year)
    if r.get("status") != "success":
        return None, f"예찰 원천 {r.get('status')}: {r.get('message', '')}"
    return r["records"], ("대리 작물 " + r["proxy"] if r.get("proxy") else "")


def gather_forecast(subject: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, str]:
    """좌표와 키가 있을 때만 단기예보를 가져온다. 없으면 (None, 이유)."""
    lat, lon = subject.get("lat"), subject.get("lon")
    if lat is None or lon is None:
        return None, "재배 단위에 좌표가 없다(I-6 — 주소→좌표는 ingest.soil_exam 지오코딩)"
    if not kma.fcst_key():
        return None, "단기예보 키 없음(.env KMA_FORECAST_API_KEY 또는 DATA_GO_KR_API_KEY)"
    r = kma.fetch_vilage(float(lat), float(lon))
    if r.get("status") != "success":
        return None, f"예보 원천 {r.get('status')}: {r.get('message', '')}"
    return r["records"], ""


# [코드 평가 §1-1 · 2026-09-19] 옛 진입점 harvest_for_subject / all_harvest 를 지웠다 — 호출자 0 이면서 필지 병합·boundary.gate·apply_caps 를
# 전부 우회하는 경로였다. 3층 진입점은 all_judgments 하나다(게이트 위치 래칫이 그것만 보는 이유).


def judgments_for(subject_id: str, today: date | None = None) -> list[Envelope]:
    """한 재배 단위의 봉투들(채팅 답변용). 없으면 []."""
    for s, envs, _ in all_judgments(today=today, only=subject_id):
        if s["id"] == subject_id:
            return envs
    return []


def all_judgments(today: date | None = None, only: str | None = None) -> list[tuple[dict[str, Any], list[Envelope], dict[str, str]]]:
    """재배 단위마다 [수확 시기, 위험 경보, 자재 인용, 계획 대 실제] 봉투 — 원천은 한 번만 모은다."""
    today = today or date.today()   # [A11] 이 회차의 '오늘'은 여기서 한 번 정하고 아래로만 내려간다 — 판정기·원천이 따로 묻지 않는다
    out = []
    for s_reg in media.load_subjects():
        if only and s_reg.get("id") != only:
            continue
        # [M-6] 필지 등록부에서 3층 허용 필드만 붙인다(주소·PNU 는 안 붙는다) — 입력 병합은 게이트 앞
        s0 = parcels.enrich_subject(s_reg, parcels.by_id(s_reg.get("parcel", "")))
        # [M-15 ⑥] 필지 토양 원천 저장소 — 검정값은 soil_chem 으로 붙고(값은 봉투에 안 실린다), 처방 레코드는 게이트를 지나 결정으로
        soil = soil_store.latest("observation.soil_exam", s_reg.get("parcel", ""))
        if soil and soil.get("status") == "success" and soil.get("values"):
            s0["soil_chem"], s0["soil_exam_at"] = dict(soil["values"]), soil.get("observed_at")
        prescriptions = soil_store.prescriptions_for(s_reg.get("parcel", ""))
        forecast, why = gather_forecast(s0)
        pest, pwhy = gather_pest(s0, today)
        evts = ev.list_records(s0.get("id"), "event")
        ledger = ev.list_records(s0.get("id"))                 # 관찰 · 농가 계획 · 납품 계획일까지(M-10 결정 등록이 쓴다)
        reasons = ev.list_records(s0.get("id"), "decision.noncompliance")
        videos = media.list_records(s0.get("id"))
        caps = fb.active_caps(s0.get("id"))
        # [M-3 · I-5 §3-4] 경계 게이트 — 모든 입력을 모은 뒤, 판정 직전, 한 번
        s, recs = boundary.gate(s0, forecast=forecast, pest=pest, events=evts, ledger=ledger, reasons=reasons, videos=videos, caps=caps,
                                prescriptions=prescriptions)
        envs = [harvest_timing.judge(s, forecast=recs["forecast"], today=today),
                risk_alert.judge(s, forecast=recs["forecast"], today=today, pest=recs["pest"], evts=recs["events"]),   # [B1] 수확 사건
                material_citation.judge(s, today=today),
                # [§7.5 관문의 입력 2026-09-21] notes 를 안 넘기면 조건부 갈래가 관찰을 못 보고 **게이트를 안 거친 원장**을 직접 읽는다 —
                # 관문은 멀쩡히 서 있고 아무것도 안 거르는 형태. 게이트를 지난 원장에서 관찰만 골라 넘긴다
                plan_vs_actual.judge(s, today=today, evts=recs["events"], videos=recs["videos"], reasons=recs["reasons"],
                                     notes=[r for r in (recs["ledger"] or []) if r.get("kind") == "observation.note"])]
        # [M-10 결정 등록] 격자 칸이 선언한 나머지 8 결정 — 같은 입력, 같은 게이트 뒤
        envs += stage_decisions.judge_all(s, today, evts=recs["ledger"], forecast=recs["forecast"], pest=recs["pest"], harvest=envs[0],
                                          prescriptions=recs["prescriptions"])
        # [M-6 · D-14] 자율진화 보수 상한 — 판정기 뒤, 돌려주기 전, 한 번. 규칙은 안 바꾸고 등급만 낮춘다
        envs = evolve.apply_caps(s["id"], envs, caps=recs["caps"])
        out.append((s, envs, {"forecast": why or "예보 사용", "pest": pwhy or "예찰 사용"}))
    return out
