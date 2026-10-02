# -*- coding: utf-8 -*-
# FILE: judge/run.py
# ROLE: 3층 실행부 — 재배 단위마다 1층 원천을 모아 판정기에 넘기고 봉투를 돌려준다.
#       4층(frontend)은 이 함수만 부른다. 1층 원천(ingest.kma)은 여기서만 만진다.
from __future__ import annotations

from datetime import date
from typing import Any

from ingest import events as ev
from ingest import feedback as fb
from ingest import kma, media, ncpms, outlook, parcels, soil_store
from grid import capture as grid_capture
from grid import schema as grid_schema
from judge import boundary, evolve, harvest_timing, material_citation, plan_vs_actual, registry, risk_alert, stage_decisions
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
        return None, "예찰 조회 열쇠가 발행자 PC 설정에 없다 [설정: .env NCPMS_API_KEY]"     # [WO-ASK-01 §2] 열쇠 이름은 설정 꼬리에만 — 농가 줄은 judge.need.plain_reason 이 뗀다
    r = ncpms.fetch_forecast(crop, year=today.year)
    if r.get("status") != "success":
        return None, f"예찰 원천 {r.get('status')}: {r.get('message', '')}"
    return r["records"], ("대리 작물 " + r["proxy"] if r.get("proxy") else "")


def gather_forecast(subject: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, str]:
    """좌표와 키가 있을 때만 단기예보를 가져온다. 없으면 (None, 이유)."""
    lat, lon = subject.get("lat"), subject.get("lon")
    if lat is None or lon is None:
        return None, "밭 좌표가 없다 — 밭 주소가 등록되면 좌표가 잡힌다 [설정: 주소→좌표는 ingest.soil_exam 지오코딩(I-6)]"
    if not kma.fcst_key():
        return None, "예보 조회 열쇠가 발행자 PC 설정에 없다 [설정: .env KMA_FORECAST_API_KEY 또는 DATA_GO_KR_API_KEY]"
    r = kma.fetch_vilage(float(lat), float(lon))
    if r.get("status") != "success":
        return None, f"예보 원천 {r.get('status')}: {r.get('message', '')}"
    return r["records"], ""


def gather_mid(subject: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, str]:
    """[D-21 중기] 좌표·키·권역이 있을 때만 중기예보(D+3~D+10)를 가져온다. 없으면 (None, 이유) — 단기와 같은 꼴, 같은 키."""
    lat, lon = subject.get("lat"), subject.get("lon")
    if lat is None or lon is None:
        return None, "밭 좌표가 없다 — 밭 주소가 등록되면 좌표가 잡힌다 [설정: 주소→좌표는 ingest.soil_exam 지오코딩(I-6)]"
    if not kma.fcst_key():
        return None, "예보 조회 열쇠가 발행자 PC 설정에 없다 [설정: .env KMA_FORECAST_API_KEY 또는 DATA_GO_KR_API_KEY]"
    r = kma.fetch_mid(float(lat), float(lon))
    if r.get("status") != "success":
        return None, f"중기예보 원천 {r.get('status')}: {r.get('message', '')}"
    return r["records"], (f"일부만 — {r['partial']}" if r.get("partial") else "")


def drought_days_needed(subject: dict[str, Any], today: date) -> int:
    """관측을 며칠 뒤로 볼지 — 임계(오늘 칸 drought_rules.dry_days)가 있으면 **그 날수**: 그 안에 비가 없었으면 무강수는 이미 임계 이상이고
    (정확한 날수는 몰라도 판단은 선다), 있었으면 그 날이 마지막 비 온 날이다. [2026-09-29 구조적 위험 처방 — 첫 답이 최대 30번 부르던 것]
    [산출물 검토 2026-09-30] ① 임계가 30보다 커도 그만큼 본다 — min(30, N) 이면 창이 임계를 못 덮어 관측으로는 **영영** 판단이 안 섰다(「30일만 받음」).
    ② 임계가 없으면 0 — 판정기가 관측을 읽기 전에 판단 불가(지식)로 돌아가므로 부르는 것은 낭비였다(임계 없는 지금 답마다 30번)."""
    unit, miss = grid_schema.load_unit(subject)
    anchor = subject.get("anchor")
    if miss is not None or not anchor:
        return 0
    stage = grid_capture.stage_for_day(unit, (today - date.fromisoformat(anchor)).days)
    rules = (stage or {}).get(grid_schema.DROUGHT_RULES_KEY)
    dd = rules.get("dry_days") if isinstance(rules, dict) else None
    return int(dd) if isinstance(dd, int) and not isinstance(dd, bool) and dd >= 1 else 0


def gather_obs_rain(subject: dict[str, Any], today: date) -> tuple[list[dict[str, Any]] | None, str]:
    """[D-20 · 발행자 2026-09-29 "기상청 현시점 이전의 무강수일을 활용해서 관수를 권고해야"] 최근접 관측 지점의 지난 일강수(kma_sfcdd) — 마지막 비 온 날의
    원천. 좌표·apihub 키가 있을 때만. 없으면 (None, 이유) — 가뭄 판단은 그때 농가의 비·관수 기록으로만 센다."""
    need = drought_days_needed(subject, today)
    if need <= 0:
        return None, "임계(격자 drought_rules.dry_days)가 없어 관측을 부르지 않는다 — 임계가 서면 그 날수만 부른다"   # [2026-09-30] 임계 없이는 판정기가 관측을 안 읽는다
    lat, lon = subject.get("lat"), subject.get("lon")
    if lat is None or lon is None:
        return None, "밭 좌표가 없다 — 밭 주소가 등록되면 좌표가 잡힌다 [설정: 주소→좌표는 ingest.soil_exam 지오코딩(I-6)]"
    if not kma.hub_key():
        return None, "기상청 관측 조회 열쇠가 발행자 PC 설정에 없다 [설정: .env KMA_API_HUB_KEY — 지상 일자료]"
    stn = kma.nearest_station(float(lat), float(lon))
    if not stn:
        return None, "가까운 관측 지점을 못 찾았다"
    d = registry.get("drought_alert")
    r = kma.fetch_recent_obs(int(stn["id"]), today, need, float(d.params["wet_mm"]))
    if r["status"] != "success":
        return (r["records"] or None), f"관측 원천 {r['status']}: {r.get('message', '')}(지점 {stn['name']} · {r.get('days_seen', 0)}일까지 받음)"
    return r["records"], ""


def gather_outlook(today: date) -> tuple[list[dict[str, Any]] | None, str]:
    """[D-21 장기 · ⓐ] 발행자가 등재한 1·3개월 전망(수동 정본)에서 오늘 뒤를 덮는 항목. 없으면 (None, 이유) — 좌표·키와 무관(원천을 부르지 않는다)."""
    recs, bad = outlook.load()
    live = outlook.covering(recs, today)
    tail = f" · 못 읽은 항목 {len(bad)} — {bad[0]}" if bad else ""
    if live:
        return live, tail.lstrip(" ·")
    if not recs:
        # [발행자 2026-09-29 "기상청에 장기예보가 없다는 것인가?"] 아니다 — 1·3개월 전망은 발표되지만 자동으로 받는 길(오픈 API)이 없다(VELA 실측 2026-08-05). 문장이 그것을 말해야 한다
        # [WO-ASK-01 §2 2026-10-03] 농가 줄에 '오픈 API' · 파일 이름이 가고 있었다(래칫이 잡음) — 받는 길 · 파일은 설정 꼬리로(need.plain_reason 이 뗀다)
        return None, (f"등재된 장기 전망 없음 — 기상청 1·3개월 전망은 발표되지만 자동으로 받는 길이 없어, 발표문 수치를 설정 → 장기 전망 등재에 출처와 함께 넣어야 합니다(값은 발행자 몫)"
                      f" [설정: 오픈 API 없음(VELA 실측 2026-08-05) · /me/outlook 또는 {outlook.local_path().name}]" + tail)
    return None, f"등재된 장기 전망 {len(recs)}건이 모두 지난 기간(마지막 {recs[-1]['period_to']})" + tail


# [코드 평가 §1-1 · 2026-09-19] 옛 진입점 harvest_for_subject / all_harvest 를 지웠다 — 호출자 0 이면서 필지 병합·boundary.gate·apply_caps 를
# 전부 우회하는 경로였다. 3층 진입점은 all_judgments 하나다(게이트 위치 래칫이 그것만 보는 이유).


def judgments_for(subject_id: str, today: date | None = None, said: list[dict[str, Any]] | None = None) -> list[Envelope]:
    """한 재배 단위의 봉투들(채팅 답변용). 없으면 [].

    `said` — 방금 물으신 말을 관찰 레코드로 만든 것(원장에 없다 · `events.said_observation`). 증상 결정만 읽는다.
    """
    for s, envs, _ in all_judgments(today=today, only=subject_id, said=said):
        if s["id"] == subject_id:
            return envs
    return []


def all_judgments(today: date | None = None, only: str | None = None,
                  said: list[dict[str, Any]] | None = None) -> list[tuple[dict[str, Any], list[Envelope], dict[str, str]]]:
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
        prescriptions, unreadable = soil_store._scan_prescriptions(s_reg.get("parcel", ""))   # [U-21] 읽힌 것과 **못 읽은 것**을 함께
        forecast, why = gather_forecast(s0)
        mid, mwhy = gather_mid(s0)                              # [D-21 중기] 단기와 별개 원천 · 별개 이유 — 한쪽이 없어도 다른 쪽은 낸다
        lng, lwhy = gather_outlook(today)                       # [D-21 장기] 수동 정본 — 좌표·키 없이도 등재만 있으면 낸다
        pest, pwhy = gather_pest(s0, today)
        obs_rain, orwhy = gather_obs_rain(s0, today)            # [D-20] 기상청 지난 일강수 — 마지막 비 온 날의 원천(농가 기록과 함께 센다)
        evts = ev.list_records(s0.get("id"), "event")
        ledger = ev.list_records(s0.get("id"))                 # 관찰 · 농가 계획 · 납품 계획일까지(M-10 결정 등록이 쓴다)
        reasons = ev.list_records(s0.get("id"), "decision.noncompliance")
        videos = media.list_records(s0.get("id"))
        caps = fb.active_caps(s0.get("id"))
        # [M-3 · I-5 §3-4] 경계 게이트 — 모든 입력을 모은 뒤, 판정 직전, 한 번
        # [D-18 직렬 게이트 2026-09-27] 물으신 말(said)도 같은 문으로 — 원장에 없는 입력이라고 게이트를 비켜 가면 관문의 입력이 새는 형태
        s, recs = boundary.gate(s0, forecast=forecast, mid=mid, outlook=lng, pest=pest, obs_rain=obs_rain, events=evts, ledger=ledger, reasons=reasons, videos=videos, caps=caps,
                                prescriptions=prescriptions, said=said)
        envs = [harvest_timing.judge(s, forecast=recs["forecast"], today=today),
                risk_alert.judge(s, forecast=recs["forecast"], today=today, pest=recs["pest"], evts=recs["events"]),   # [B1] 수확 사건
                material_citation.judge(s, today=today),
                # [§7.5 관문의 입력 2026-09-21] notes 를 안 넘기면 조건부 갈래가 관찰을 못 보고 **게이트를 안 거친 원장**을 직접 읽는다 —
                # 관문은 멀쩡히 서 있고 아무것도 안 거르는 형태. 게이트를 지난 원장에서 관찰만 골라 넘긴다
                plan_vs_actual.judge(s, today=today, evts=recs["events"], videos=recs["videos"], reasons=recs["reasons"],
                                     notes=[r for r in (recs["ledger"] or []) if r.get("kind") == "observation.note"])]
        # [M-10 결정 등록] 격자 칸이 선언한 나머지 8 결정 — 같은 입력, 같은 게이트 뒤
        envs += stage_decisions.judge_all(s, today, evts=recs["ledger"], forecast=recs["forecast"], pest=recs["pest"], harvest=envs[0],
                                          prescriptions=recs["prescriptions"], unreadable=unreadable, said=recs["said"],
                                          forecast_why=why,     # [D-21] 예보를 못 받은 이유를 날씨 인용이 그대로 싣는다(관문의 입력 — 빈 채 넘기면 이유 없는 미비)
                                          mid=recs["mid"], mid_why=mwhy,   # [D-21 중기] 게이트를 지난 중기 줄 + 못 받은 이유 — 둘 다 넘긴다(입력 도착 래칫의 대상)
                                          outlook=recs["outlook"], outlook_why=lwhy,   # [D-21 장기] 같은 형태 — 셋째 입력 쌍
                                          obs_rain=recs["obs_rain"], obs_rain_why=orwhy)   # [D-20] 넷째 입력 쌍 — 지난 일강수 + 못 받은 이유
        # [M-6 · D-14] 자율진화 보수 상한 — 판정기 뒤, 돌려주기 전, 한 번. 규칙은 안 바꾸고 등급만 낮춘다
        envs = evolve.apply_caps(s["id"], envs, caps=recs["caps"])
        out.append((s, envs, {"forecast": why or "예보 사용", "mid": mwhy or "중기예보 사용", "outlook": lwhy or "장기 전망(등재분) 사용", "pest": pwhy or "예찰 사용",
                              "obs_rain": orwhy or "지난 일강수(기상청 관측) 사용"}))
    return out
