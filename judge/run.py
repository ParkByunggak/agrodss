# -*- coding: utf-8 -*-
# FILE: judge/run.py
# ROLE: 3층 실행부 — 재배 단위마다 1층 원천을 모아 판정기에 넘기고 봉투를 돌려준다.
#       4층(frontend)은 이 함수만 부른다. 1층 원천(ingest.kma)은 여기서만 만진다.
from __future__ import annotations

from datetime import date
from typing import Any

from ingest import events as ev
from ingest import feedback as fb
from ingest import kma, media, ncpms, parcels
from judge import boundary, evolve, harvest_timing, material_citation, plan_vs_actual, risk_alert
from judge.envelope import Envelope


def gather_pest(subject: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, str]:
    """작목의 NCPMS 예찰(올해). 키·코드 없으면 (None, 이유)."""
    crop = subject.get("crop")
    if not crop:
        return None, "재배 단위에 작목이 없다"
    if not ncpms.api_key():
        return None, "예찰 키 없음(.env NCPMS_API_KEY)"
    r = ncpms.fetch_forecast(crop, year=date.today().year)
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


def harvest_for_subject(subject: dict[str, Any], today: date | None = None) -> tuple[Envelope, dict[str, str]]:
    forecast, why = gather_forecast(subject)
    env = harvest_timing.judge(subject, forecast=forecast, today=today)
    return env, {"forecast": why or "예보 사용"}


def all_harvest(today: date | None = None) -> list[tuple[dict[str, Any], Envelope, dict[str, str]]]:
    out = []
    for s in media.load_subjects():
        env, info = harvest_for_subject(s, today=today)
        out.append((s, env, info))
    return out


def all_judgments(today: date | None = None) -> list[tuple[dict[str, Any], list[Envelope], dict[str, str]]]:
    """재배 단위마다 [수확 시기, 위험 경보] 봉투 — 원천은 한 번만 모은다."""
    out = []
    for s_reg in media.load_subjects():
        # [M-6] 필지 등록부에서 3층 허용 필드만 붙인다(주소·PNU 는 안 붙는다) — 입력 병합은 게이트 앞
        s0 = parcels.enrich_subject(s_reg, parcels.by_id(s_reg.get("parcel", "")))
        forecast, why = gather_forecast(s0)
        pest, pwhy = gather_pest(s0)
        evts = ev.list_records(s0.get("id"), "event")
        reasons = ev.list_records(s0.get("id"), "decision.noncompliance")
        videos = media.list_records(s0.get("id"))
        caps = fb.active_caps(s0.get("id"))
        # [M-3 · I-5 §3-4] 경계 게이트 — 모든 입력을 모은 뒤, 판정 직전, 한 번
        s, recs = boundary.gate(s0, forecast=forecast, pest=pest, events=evts, reasons=reasons, videos=videos, caps=caps)
        envs = [harvest_timing.judge(s, forecast=recs["forecast"], today=today),
                risk_alert.judge(s, forecast=recs["forecast"], today=today, pest=recs["pest"]),
                material_citation.judge(s, today=today),
                plan_vs_actual.judge(s, today=today, evts=recs["events"], videos=recs["videos"], reasons=recs["reasons"])]
        # [M-6 · D-14] 자율진화 보수 상한 — 판정기 뒤, 돌려주기 전, 한 번. 규칙은 안 바꾸고 등급만 낮춘다
        envs = evolve.apply_caps(s["id"], envs, caps=recs["caps"])
        out.append((s, envs, {"forecast": why or "예보 사용", "pest": pwhy or "예찰 사용"}))
    return out
