# -*- coding: utf-8 -*-
# FILE: judge/stage_decisions.py
# ROLE: [M-10 결정 등록] 격자 칸이 선언한 결정 중 남은 8건 — sowing_window · base_fertilization · replant · pest_alert ·
#       top_dressing_1 · top_dressing_2 · drainage_alert · ship_or_store. 등록부에 규칙·축을 선언하고 판정한다.
#
#   정직성: 정본이 없는 것은 판단 불가(지식)로, 입력이 없는 것은 판단 불가(데이터)로 낸다. 값을 지어내지 않는다.
#   · base_fertilization / top_dressing 의 **양**은 처방 정본(토양검정 처방 기준)이 격자에 도착하지 않았다 → 지식 미비.
#   · pest_alert / drainage_alert 는 risk_alert 의 봉투를 그 칸으로 잘라 낸다(같은 규칙, 다른 결정 id — 두 벌 로직 금지).
#   · ship_or_store 는 D-8(이번 작기 자가) 이면 해당 없음, 납품 계획일이 없으면 데이터 미비.
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from grid import capture as grid_capture
from grid import schema as grid_schema
from judge import plan_vs_actual, registry, risk_alert, units
from judge.envelope import AxisUse, Envelope, weakest
from judge.harvest_timing import GRID_GRADE

FORB = ("humidity_air",)
SELF_USE_WORDS = ("자가", "시험")
REPLANT_WORDS = ("결주", "빈", "안 났", "안났", "드문", "듬성", "성글", "출현 불량", "안 올라")
TOP_DRESSING_EVENT = "시비"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stage(unit: dict[str, Any], decision_id: str) -> dict[str, Any] | None:
    for s in unit.get("stages", []):
        if decision_id in (s.get("decisions") or []):
            return s
    return None


def _task(stage: dict[str, Any], key: str) -> dict[str, Any] | None:
    tasks = stage.get("tasks")
    if not isinstance(tasks, list):
        return None
    return next((t for t in tasks if key in t.get("name", "")), None)


def _deadline_day(task: dict[str, Any] | None) -> int | None:
    """격자 작업의 마감(일). 없으면 None — **창 끝으로 메우지 않는다**.

    [대리값 전수 2026-09-20] B6 에서 출하 마감의 기본값 63 을 없앴는데, 같은 지식(retry.deadline_day)을 읽는
    자리가 넷이었고 처방은 한 곳에만 닿아 있었다(§7.5 지점 축). 나머지 셋은 `stage["window"]["to_day"]` 로
    메우고 있었다 — 리터럴이 아니라 **식**이라 직전 회차의 숫자 축 전수가 못 봤다. 읽는 법을 한 벌로 세운다.
    """
    d = ((task or {}).get("retry") or {}).get("deadline_day")
    return int(d) if d is not None else None


def _no_deadline(did: str, sid: str, as_of: str, task_name: str) -> Envelope:
    return Envelope("판단 불가(지식)", did, sid, as_of,
                    result={"why": f"격자 작업 '{task_name}' 에 마감(retry.deadline_day)이 없다 — 창 끝으로 지어내지 않는다",
                            "summary": f"{task_name} 마감이 기준에 없습니다 — 지어내지 않습니다"})


def _need_cert(did: str, sid: str, as_of: str) -> Envelope:
    """[코드 평가 B2] cert 는 시비 결정의 필요 축 — 없으면 판단 불가(데이터). 전에는 mats.get(None, []) 로 빈 자재를 들고 '판단함'이 나갔다."""
    return Envelope("판단 불가(데이터)", did, sid, as_of,
                    missing=[{"axis": "cert", "who_can_fill": "농가 — 인증 유형(유기 · 무농약 · 관행) 을 재배 단위에"}],
                    result={"why": "인증 유형(cert)이 없다 — 자재 갈래를 정할 수 없다", "summary": "인증 유형(유기 · 무농약 · 관행)이 없습니다 — 있어야 자재를 고릅니다"})


def _grid_grade(unit: dict[str, Any]) -> str:
    return GRID_GRADE.get(unit["unit"].get("confidence", "하"), "추정")


def _anchor_inputs(subject: dict[str, Any], anchor: str) -> list[AxisUse]:
    return [AxisUse("anchor", anchor, subject.get("source", "farmer"), "cultivation_unit", "관측")]


# ── 등록 ─────────────────────────────────────────────────────────────────────────
_R = registry.register
SOWING_WINDOW = _R(registry.Decision(
    id="sowing_window", name="파종 창", required_axes=("anchor",), optional_axes=("temp",), forbidden_axes=FORB,
    rule="기준점(파종일)이 있으면 격자 칸 1 의 창(anchor 상대)을 날짜로 낸다. 창을 지났으면 해당 없음(이미 파종). "
         "기준점이 없는 계획 목록에는 달력 기준 적기가 정본에 없으므로 판단 불가(지식).", revisit_days=None,
    params={"source": "격자 jjokpa-autumn 칸 1 window"}))
BASE_FERTILIZATION = _R(registry.Decision(
    id="base_fertilization", name="밑거름", required_axes=("anchor", "soil_chem", "cert"), optional_axes=(), forbidden_axes=FORB,
    rule="밑거름 창(칸 1, 파종 마감일까지) 안에서만 산다. 토양검정 값(soil_chem)이 없으면 판단 불가(데이터). "
         "값이 있어도 시비량 처방 정본이 격자에 없으면 판단 불가(지식) — 양을 지어내지 않는다. 자재는 인증 갈래만 인용.", revisit_days=None,
    params={"source": "격자 칸 1 tasks[밑거름] materials · 처방 정본 미도착"}))
REPLANT = _R(registry.Decision(
    id="replant", name="보식", required_axes=("anchor",), optional_axes=("soil_water", "temp"), forbidden_axes=FORB,
    rule="발아·출현 창(칸 2) 안에서, 농가 관찰(결주·출현 불량)이 있으면 마감일까지 보식을 권고한다(판단함). "
         "관찰이 없으면 판단 불가(데이터) — 출현 상태는 농가 관찰이 최종 심급. 창 밖이면 해당 없음.", revisit_days=1,
    # [두 층 불일치 2026-09-21] 이 결정은 "관찰이 없으면 판단 불가(데이터)" 라고 **이미 선언하고 있었는데**, 계획 대 실제는
    # 같은 작업을 '놓침 — 사유를 묻는다' 로 냈다. 한 작업에 두 층이 다른 답을 한 것이다. 원인은 '조건부' 라는 사실이
    # **격자 작업명의 괄호 표기**("관수(건조 시)")에만 실려 있었고 '보식' 이라는 이름에는 그 표기가 없었다는 것 — 곧 조건
    # 여부가 작업명 문자열에만 있는 **두 벌 진실**이었다. 조건을 여기 선언하면 두 층이 같은 것을 읽는다(계획 대 실제는
    # registry 만 import 하므로 순환이 없다 — import 방향은 stage_decisions → plan_vs_actual 이다).
    params={"words": REPLANT_WORDS, "source": "격자 칸 2 tasks[보식] retry.deadline_day",
            "conditional_task": "보식",                       # 이 격자 작업은 조건부다 — 안 했다고 놓친 것이 아니다
            "condition": "결주·출현 불량 관찰(농가)",            # 무엇이 채워져야 조건이 서는가
            "condition_source": "농가 — 출현 상태 한 줄(채팅 관찰: 결주 · 듬성 · 안 났다)"}))
PEST_ALERT = _R(registry.Decision(
    id="pest_alert", name="병해충 경보(칸 3)", required_axes=("anchor",), optional_axes=("pest_regional", "temp", "precip", "microclimate"),
    forbidden_axes=FORB, rule="risk_alert 와 같은 규칙(비대칭 경보)을 칸 3 의 위험에만 적용해 낸다. 칸이 horizon 밖이면 해당 없음.",
    revisit_days=1, params={"delegate": "risk_alert", "stage_order": 3}))
TOP_DRESSING_1 = _R(registry.Decision(
    id="top_dressing_1", name="웃거름 1회", required_axes=("anchor", "cert"), optional_axes=("temp", "precip"), forbidden_axes=FORB,
    rule="칸 3 작업 '웃거름 1회'의 작업일·마감일을 날짜로 내고, 창 안 시비 사건이 있으면 이행, 작업일이 지났는데 없으면 미이행, "
         "아직이면 예정. 자재는 인증 갈래만. 양은 처방 정본 미도착 — 판단 불가(지식)로 병기.", revisit_days=1,
    params={"task_key": "웃거름 1회", "stage_order": 3, "event_type": TOP_DRESSING_EVENT}))
TOP_DRESSING_2 = _R(registry.Decision(
    id="top_dressing_2", name="웃거름 2회(필요 시)", required_axes=("anchor", "cert"), optional_axes=("temp", "precip", "soil_water"), forbidden_axes=FORB,
    rule="'필요 시' 의 필요 여부 판정 규칙이 격자에 미채움 — 판단 불가(지식). 창·자재만 사실로 낸다.", revisit_days=None,
    params={"task_key": "웃거름 2회", "stage_order": 4}))
DRAINAGE_ALERT = _R(registry.Decision(
    id="drainage_alert", name="배수 경보(칸 4)", required_axes=("anchor",), optional_axes=("forecast", "precip", "soil_water"),
    forbidden_axes=FORB, rule="risk_alert 와 같은 규칙을 칸 4 의 위험(과습·부패 — 회복 불가)에만 적용해 낸다. 칸이 horizon 밖이면 해당 없음.",
    revisit_days=1, params={"delegate": "risk_alert", "stage_order": 4}))
SHIP_OR_STORE = _R(registry.Decision(
    id="ship_or_store", name="출하 또는 저장", required_axes=("anchor",), optional_axes=("forecast", "temp"), forbidden_axes=FORB,
    rule="필지 용도가 자가·시험(D-8)이면 해당 없음. 납품 계획일(plan.target_date, 농가만)이 없으면 판단 불가(데이터). "
         "있으면 수확 창 끝과 계획일의 간격을 저장 일수로 내고, 칸 5 '출하 또는 단기 저장' 마감(63일)을 넘기면 상한 제약.", revisit_days=7,
    params={"source": "격자 칸 5 tasks[출하 또는 단기 저장] retry.deadline_day"}))

# [D-18 자리 2026-09-27] 발행자 2026-09-26: *"농가가 실제로 묻는 것의 상당수가 '이거 왜 이런가'인데, 지금 결정 목록은 전부 '언제 무엇을
# 하는가'입니다."* 그리고 2026-09-27: *"어느 단계에 이르러야 질문에 답을 제대로 할 수 있는가?"* — 결정 하나(여기)와 그 결정이 읽을
# 지식 정본(격자 `symptom_rules` — 발행자 몫)이다. 결정은 지식 없이 등록한다: 지식이 비어 있으면 **어느 격자의 어느 키가 비었는지**를
# 말하는 판단 불가(지식)가 3층에서 나오고(채팅의 고정 문장이 아니라), 발행자가 결정하면 격자 한 수정으로 답이 열린다(B6 전례).
# 이 결정은 격자 칸의 decisions 목록에 **선언되지 않는다** — 칸 하나의 결정이 아니라 칸 3·4 에 걸친 '왜 이런가' 결정이고, 그 선언은
# symptom_rules 키 자체다(키가 있는 칸이 이 결정을 연 칸이다).
SYMPTOM_RULES_KEY = grid_schema.SYMPTOM_RULES_KEY      # 이름 정본은 격자 스키마 하나(검증기 · 문서 생성기 · 판정기가 같은 키를 본다)
SYMPTOM_TRIAGE = _R(registry.Decision(
    id="symptom_triage", name="증상 → 원인 좁히기", required_axes=("anchor",),      # 관찰은 축이 아니라 **기록**이다(원장) — replant 와 같다
    optional_axes=("pest_regional", "temp", "precip", "soil_water"), forbidden_axes=FORB,
    rule="[D-18 발행자 결정 대기] 격자 칸 3·4 의 symptom_rules — [{symptoms:[증상 어휘], causes:[{name, check, recoverable}], first_check}] — 가 채워지면, "
         "최근 관찰(observation.note) 중 증상 어휘가 든 것에 대해 원인 **후보**와 먼저 할 확인 하나를 낸다(단정 없음 · 회복 불가 후보 먼저 · 등급 추정). "
         "규칙이 비어 있으면 판단 불가(지식) — 어느 격자의 어느 키가 비었는지 말한다. 증상 관찰이 없으면 판단 불가(데이터). "
         "관찰에 증상은 있으나 규칙 어휘와 안 맞으면 판단 불가(지식) — 기준이 아는 말을 함께 낸다. 규칙의 증상 어휘는 1층 라우팅에도 덧붙는다(어휘 한 벌).",
    revisit_days=1,
    params={"rules_key": SYMPTOM_RULES_KEY, "stage_orders": (3, 4), "lookback_days": 14,
            "source": "D-18 — 발행자가 쓴 감별(양분 부족 · 과습/뿌리 부패 · 고자리파리 유충 · 노균병/잎마름 · 확인 하나 = 인경 밑)이 정본 후보"}))

# [D-20 자리 2026-09-28] 발행자 실사용 2026-09-28 *"가을 가뭄이 심하다. 아침에 포장을 보니 특별한 징후는 없다"* → 규칙은 본 것으로 적었고(맞다) 그런데
# **가뭄을 읽는 판단이 없었다** — 격자 칸마다 water(요구 · 결핍 민감)가 있는데 소비자 0 · 경보는 과습(배수)만. 발행자 "D-20 등재하자" → D-18 과 같은 형태로
# 결정을 **지식 없이** 먼저 세운다: 임계(무강수 며칠)는 격자 칸의 drought_rules 에 발행자가 적는다. 비어 있으면 봉투가 어느 칸의 어느 키가 비었는지 · 지금 칸의
# 수분 값이 무엇인지 말한다. 선언은 키 자체(symptom_triage 와 같은 규율 — 칸 decisions 목록에 안 적는다).
DROUGHT_RULES_KEY = grid_schema.DROUGHT_RULES_KEY
DROUGHT_ALERT = _R(registry.Decision(
    id="drought_alert", name="가뭄 · 관수 판단", required_axes=("anchor",), optional_axes=("forecast", "precip", "soil_water"), forbidden_axes=FORB,
    rule="[D-20 발행자 등재 2026-09-28] 오늘 칸(기준점 후 날수)의 water(요구 · 결핍 민감)를 읽는다. 칸의 drought_rules — {dry_days: 무강수 임계 일수, source} — 가 "
         "채워지면, 최근 비 관찰(observation.note 에 비 어휘 · 1층 정본 chat.rain_in) 또는 관수 사건(event type 관수) 뒤 지난 날수를 세어 임계 이상이면 판단함(관수 검토 · "
         "등급 추정 · 결핍 민감도 함께), 미만이면 판단함(아직 관수 판단 아님). 비·관수 기록이 하나도 없으면 판단 불가(데이터) — 마지막 비 온 날 · 관수한 날. "
         "임계가 비어 있으면 판단 불가(지식) — 어느 격자의 어느 칸이 비었는지와 지금 칸의 수분 값을 함께. 관수량·방법은 말하지 않는다(그것은 별도 지식).",
    revisit_days=1,
    params={"rules_key": DROUGHT_RULES_KEY, "lookback_days": 30, "irrigation_event": "관수",
            # [발행자 2026-09-29 "이미 기상청 현시점 이전의 무강수일을 가지고 있다 — 이를 활용해서 관수를 권고해야"] 마지막 비 온 날의 원천 하나 더: 최근접 지점의
            # 지난 일강수(kma_sfcdd). 비 온 날 = 일강수 ≥ wet_mm — 0.1mm 는 기상청 「강수일수」 통계 정의(일강수 0.1mm 이상)이지 세션의 값이 아니다.
            # 격자 칸 drought_rules.wet_mm 이 있으면 그것이 이긴다(발행자 정본).
            "wet_mm": 0.1, "wet_mm_source": "기상청 강수일수 정의 — 일강수 0.1mm 이상(기상자료개방포털 용어 해설)",
            "source": "D-20 — 발행자 실사용 2026-09-28. 임계는 발행자·농진청 정본 몫 — 세션이 정하지 않는다(대리값이 경보로 나간다)"}))

# [D-21 자리 2026-09-28] 발행자 *"KMA api 가 있는데 날씨를 안내하지 않고, 예측도 하지 않는 이유는?"* — 예보는 판단 넷의 **입력**이었지 산출이 아니었다(I-1: 등록된
# 결정만 낸다). 발행자 "D-21 등재하자" → **사실 인용** 종류로 등록: 가진 예보를 출처·발표 시각과 함께 그대로 낸다. 해석·권고는 붙이지 않는다(그것은 위험 경보 몫).
# 지식 정본이 필요 없는 결정이라 자리와 답이 같은 커밋에 선다. 격자 칸 선언은 없다(어느 칸이든 · 좌표만 있으면).
FORECAST_CITATION = _R(registry.Decision(
    id="forecast_citation", name="날씨 인용(단기·중기 예보)", required_axes=("forecast",), optional_axes=(), forbidden_axes=FORB,
    rule="[D-21 발행자 등재 2026-09-28] 판단이 아니라 사실 인용. 필지 좌표의 기상청 단기예보(forecast.weather_daily)에서 오늘부터 며칠(params.days)의 "
         "날마다 최저·최고 기온 · 강수 확률 최대 · 강수량을 출처·발표 시각과 함께 그대로 낸다. 단기 창 뒤는 권역 중기예보(forecast.weather_mid · D+3~D+10)의 "
         "최저·최고 · 강수 확률(오전·오후 최대)을 이어 붙인다 — 둘은 원천·해상도가 달라 따로 표기한다. 둘 다 없으면(좌표 없음 · 키 없음 · 권역 미해소 · 원천 오류) "
         "판단 불가(데이터), 한쪽만 없으면 사실 인용에 그쪽의 못 받은 이유를 그대로 싣는다. 해석·권고를 붙이지 않는다. 장기(1·3개월 전망)는 오픈 API 가 없어 "
         "발행자가 발표문 수치를 출처와 함께 등재한 수동 정본(reference.climate_outlook · data/kma/climate_outlook.json)만 — 오늘 뒤를 덮는 항목을 확률 3분위 그대로, "
         "없으면 '등재된 장기 전망 없음'. 셋 다 없을 때만 판단 불가(데이터).",
    revisit_days=1,
    params={"days": 3, "source": "D-21 — 발행자 2026-09-28. 값은 기상청 원천 그대로(대리값 없음) · 발표 시각 = 레코드 observed_at. 중기는 VELA 인용(D-9 · mid_regions.json)"}))

IDS = ("sowing_window", "base_fertilization", "replant", "pest_alert", "top_dressing_1", "top_dressing_2", "drainage_alert", "ship_or_store",
       "forecast_citation", "drought_alert", "symptom_triage")
UNDECLARED = ("forecast_citation", "drought_alert", "symptom_triage")   # 격자 칸 decisions 목록에 안 적는 결정 — 선언은 규칙 키 자체(drought_rules · symptom_rules) 또는 없음(날씨 인용)


# ── 판정 ─────────────────────────────────────────────────────────────────────────
def _base(subject: dict[str, Any], did: str, today: date):
    """공통 앞부분 — (unit, stage, anchor_date, day) 또는 즉시 돌려줄 봉투."""
    sid = subject.get("id", "?")
    as_of = _now()
    unit, miss = grid_schema.load_unit(subject)
    if miss is not None:
        # [U-23] 격자를 **못 읽은 것**과 격자가 이 결정을 **선언하지 않은 것**은 다른 사실이다. 전에는 둘 다
        # '해당 없음' 이라 격자 파일 이름 한 글자가 어긋나면 카드 여덟 장이 조용히 "할 일 없음" 이 됐다.
        return None, units.envelope_for(miss, did, sid, as_of)
    stage = _stage(unit, did)
    if stage is None:
        return None, Envelope("해당 없음", did, sid, as_of, result={"why": "이 결정을 선언한 격자 칸이 없다"})
    d = registry.get(did)
    errs = registry.check_against_grid(d, stage)
    if errs:
        return None, Envelope("판단 불가(지식)", did, sid, as_of, result={"why": "결정과 칸의 축 선언이 어긋난다", "detail": errs})
    return (unit, stage, sid, as_of), None


def _dates(anchor_d: date, stage: dict[str, Any]) -> tuple[date, date]:
    w = stage["window"]
    return anchor_d + timedelta(days=w["from_day"]), anchor_d + timedelta(days=w["to_day"])


def judge_sowing_window(subject, today: date) -> Envelope:
    ctx, env = _base(subject, "sowing_window", today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(지식)", "sowing_window", sid, as_of,
                        result={"why": "격자 파종 창은 기준점 상대(anchor -7~0일)라 파종 전 목록에는 달력 기준 적기가 정본에 없다",
                                "summary": "파종 적기 기준이 아직 없습니다 — 심은 날이 정해지면 그날 기준으로 냅니다"})   # [사유 문면 전수 2026-09-29] 농가 말로 — 정확한 사유는 why
    a = date.fromisoformat(anchor)
    day = (today - a).days
    s, e = _dates(a, stage)
    if day > stage["window"]["to_day"]:
        return Envelope("해당 없음", "sowing_window", sid, as_of, result={"why": f"이미 파종됨(기준점 {anchor}, {day}일 경과)", "summary": f"이미 심었습니다 — 심은 날 {anchor}, 오늘 {day}일째"})
    return Envelope("판단함", "sowing_window", sid, as_of, inputs=_anchor_inputs(subject, anchor), grade=weakest(["관측", _grid_grade(unit)]),
                    result={"window_start": s.isoformat(), "window_end": e.isoformat(), "summary": f"파종 때 {s} ~ {e}"},
                    notes=[grid_schema.source_note(unit)])      # [2026-10-01 전수] 격자 출처(추론 초안 · 검토 대기)가 답까지


def _prescription(prescriptions: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """필지 처방 레코드 중 success 인 최신 것. 표준 시비량(national)은 여기 안 온다 — 필지값이 아니라서 처방으로 안 쓴다."""
    ok = [p for p in (prescriptions or []) if p.get("kind") == "reference.fertilizer_prescription" and p.get("status") == "success" and p.get("values")]
    return sorted(ok, key=lambda p: p.get("fetched_at") or "")[-1] if ok else None


def _unreadable_envelope(did: str, sid: str, as_of: str, bad: list[str], extra: dict[str, Any]) -> Envelope:
    """[U-21 2026-09-21] 처방 정본이 **있는데 못 읽은** 경우 — '없다' 와 다른 사실이고, **고치면 바뀐다**.

    전에는 둘 다 `판단 불가(지식) — 정본 미도착` 이었다. 그러면 농가는 이미 받은 것을 **다시 받으러 간다**.
    I-1 §2-6: 채우면 바뀌는 것은 지식 미비가 아니라 **데이터 미비**다(그래서 `missing` 을 채울 수 있다).
    """
    return Envelope("판단 불가(데이터)", did, sid, as_of,
                    missing=[{"axis": "soil_chem",
                              "who_can_fill": f"저장된 처방 파일이 깨졌다({' · '.join(bad)}) — python -m ingest.fertilizer <주소> 로 다시 받으면 된다"}],
                    result={"why": f"시비량 처방 정본이 **있는데 읽지 못했다**(파일 {len(bad)}건) — 없는 것이 아니다. "
                                   f"/changes 의 '읽다 버린 것' 에 사유가 있다",
                            "unreadable": list(bad), **extra})


def _prescription_input(p: dict[str, Any]) -> AxisUse:
    return AxisUse("soil_chem", p.get("observed_at"), p["source"], p["resolution"], "관측")


def _amounts(p: dict[str, Any], prefix: str) -> str:
    v, u = p.get("values", {}), p.get("units", {})
    parts = [f"{lab} {v[k]}{u.get(k, '')}" for k, lab in ((f"{prefix}_n", "N"), (f"{prefix}_p2o5", "P₂O₅"), (f"{prefix}_k2o", "K₂O")) if k in v]
    return " · ".join(parts)


def judge_base_fertilization(subject, today: date, prescriptions: list[dict[str, Any]] | None = None,
                             unreadable: list[str] | None = None) -> Envelope:
    ctx, env = _base(subject, "base_fertilization", today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", "base_fertilization", sid, as_of, missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일"}], result={"why": "기준점이 없다"})
    a = date.fromisoformat(anchor)
    day = (today - a).days
    t = _task(stage, "밑거름")
    deadline = _deadline_day(t)
    if deadline is None:
        return _no_deadline("base_fertilization", sid, as_of, "밑거름")
    if day > deadline:
        return Envelope("해당 없음", "base_fertilization", sid, as_of,
                        result={"why": f"밑거름 창(파종 마감 {deadline}일)을 지났다 — 이후는 웃거름", "summary": f"밑거름 때(파종 뒤 {deadline}일까지)는 지났습니다 — 이제는 웃거름으로 봅니다"})
    if not subject.get("soil_chem"):
        return Envelope("판단 불가(데이터)", "base_fertilization", sid, as_of,
                        missing=[{"axis": "soil_chem", "who_can_fill": "농가 — 토양검정(python -m ingest.fertilizer <주소>, 키 투입) 또는 성적서 값"}],
                        result={"why": "토양검정 값이 없다", "summary": "토양검정 값이 없습니다 — 검정 결과가 오면 양을 냅니다"})
    cert = subject.get("cert")
    if not cert:
        return _need_cert("base_fertilization", sid, as_of)
    mats = (t or {}).get("materials")
    m = mats.get(cert, []) if isinstance(mats, dict) else []
    p = _prescription(prescriptions)
    if p is None and unreadable:
        return _unreadable_envelope("base_fertilization", sid, as_of, list(unreadable),
                                    {"materials": m, "summary": f"자재({cert}): {', '.join(m) or '없음'} · 양은 저장된 처방을 못 읽어 못 냅니다"})
    if p is None:
        return Envelope("판단 불가(지식)", "base_fertilization", sid, as_of,
                        result={"why": "시비량 처방 정본(흙토람 FrtlzrUse — 검정값 기반)이 아직 이 필지에 없다 — 양을 지어내지 않는다. python -m ingest.fertilizer <주소> 로 받는다",
                                "materials": m, "summary": f"자재({cert}): {', '.join(m) or '없음'} · 양은 검정 처방이 오면 냅니다"})
    # [M-15 ⑥] 처방 정본 도착 — 기비 N·P·K 와 퇴비(kg/10a). 유기 갈래는 화학비료가 아니라 **목표 양분량**으로 읽는다(자재 환산 규칙은 정본 없음)
    v = p.get("values", {})
    compost = {k: v[k] for k in ("compost_cattle", "compost_pig", "compost_chicken", "compost_mixed") if k in v}
    notes = [grid_schema.source_note(unit), f"출처: {p['source']} · 조회 {str(p.get('fetched_at', ''))[:10]} · 작물코드 {p.get('crop_code')}"]
    if cert == "유기":
        notes.append("유기 갈래: N·P·K 는 목표 양분량 — 공시 유기질 비료·퇴비로 환산하는 규칙은 정본 없음(지식 미비, 자재 성분표로 사람이 환산)")
    return Envelope("판단함", "base_fertilization", sid, as_of, inputs=_anchor_inputs(subject, anchor) + [_prescription_input(p)],
                    grade=weakest(["관측", _grid_grade(unit)]),
                    result={"pre": _amounts(p, "pre"), "compost_kg_10a": compost, "materials": m, "values": v, "units": p.get("units", {}),
                            "summary": f"기비 {_amounts(p, 'pre') or '값 없음'} · 퇴비 {', '.join(f'{k} {val}' for k, val in compost.items()) or '없음'} (kg/10a) · 자재({cert}) {', '.join(m) or '없음'}"},
                    notes=notes)


def judge_replant(subject, today: date, observations: list[dict[str, Any]] | None = None) -> Envelope:
    ctx, env = _base(subject, "replant", today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", "replant", sid, as_of, missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일"}], result={"why": "기준점이 없다"})
    a = date.fromisoformat(anchor)
    day = (today - a).days
    t = _task(stage, "보식")
    deadline = _deadline_day(t)
    if deadline is None:
        return _no_deadline("replant", sid, as_of, "보식")
    w0 = stage["window"]["from_day"]
    if day < w0 or day > deadline:
        return Envelope("해당 없음", "replant", sid, as_of, result={"why": f"보식 창({w0}~{deadline}일) 밖 — 오늘 {day}일",
                                                                       "summary": f"보식할 때가 아닙니다 — 보식은 파종 뒤 {w0}~{deadline}일, 오늘은 {day}일째"})   # "창 밖" 은 낱말 표를 거쳐 "기간이 아닙니다" 가 됐다(SURF-1 전수 2026-09-29)
    obs = observations or []
    words = REPLANT_WORDS
    seen = [o for o in obs if (o.get("observed_at") or "") >= (a + timedelta(days=w0)).isoformat() and any(k in (o.get("text") or "") for k in words)]
    if not seen:
        return Envelope("판단 불가(데이터)", "replant", sid, as_of,
                        missing=[{"axis": "observation", "who_can_fill": "농가 — 출현 상태 한 줄(채팅 관찰: 결주 · 듬성 · 안 났다)"}],
                        result={"why": "출현 관찰이 없다 — 최종 심급은 농가 관찰", "summary": "난 상태를 한 줄 적어 주시면 판단합니다(결주 · 듬성 · 안 났다)"})
    dl = (a + timedelta(days=deadline)).isoformat()
    return Envelope("판단함", "replant", sid, as_of, inputs=_anchor_inputs(subject, anchor), grade=weakest(["관측", _grid_grade(unit)]),
                    revisit_at=(today + timedelta(days=1)).isoformat(), notes=[grid_schema.source_note(unit)],
                    result={"deadline": dl, "observations": [o.get("id") for o in seen],
                            "summary": f"결주 관찰 {len(seen)}건 — {dl} 까지 보식(2단계 다시 심기)"})


def _delegate_risk(subject, did: str, today: date, forecast, pest) -> Envelope:
    ctx, env = _base(subject, did, today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    r = risk_alert.judge(subject, forecast=forecast, today=today, pest=pest)
    if r.kind != "판단함":
        return Envelope(r.kind, did, sid, as_of, missing=list(r.missing), result=dict(r.result), notes=list(r.notes))
    tag = f"{stage['order']}. {stage['name']}"
    if tag not in (r.result.get("stages") or []):
        # [발행자 2026-09-29 "답이 틀렸습니다 — '칸이 기간이 아닙니다' 는 농가에게 하는 말이 아니다"] 안쪽 사유("칸이 창 밖")가 낱말 표를 거쳐 뜻 없는 말이 됐다
        # (SURF-1 내부 표현 노출). 사람에게는 **오늘이 어느 칸이고 무엇을 보면 되는지**를 말한다 — 정확한 사유는 why 에 남긴다.
        now_cells = " · ".join(r.result.get("stages") or []) or "없음"
        day = r.result.get("days_since_anchor")
        return Envelope("해당 없음", did, sid, as_of,
                        result={"why": f"칸 '{tag}' 가 horizon 밖 — 오늘 {day}일째, 보는 칸 {now_cells}",
                                "summary": f"{tag} 칸의 경보는 지금 볼 때가 아닙니다 — 오늘은 파종 {day}일째라 {now_cells} 칸을 봅니다. 그 칸의 위험은 「위험 경보」 에 전부 있습니다"})
    alerts = [a for a in r.result.get("alerts", []) if a.get("stage") == tag]
    body = " / ".join(f"{a['level']} {a['risk']}" for a in alerts) or "이 칸에 경보 없음"
    return Envelope("판단함", did, sid, as_of, inputs=list(r.inputs), grade=r.grade, revisit_at=r.revisit_at,
                    result={"stage": tag, "alerts": alerts, "signals": r.result.get("signals"), "summary": body}, notes=list(r.notes))


def judge_pest_alert(subject, today: date, forecast=None, pest=None) -> Envelope:
    return _delegate_risk(subject, "pest_alert", today, forecast, pest)


def judge_drainage_alert(subject, today: date, forecast=None, pest=None) -> Envelope:
    return _delegate_risk(subject, "drainage_alert", today, forecast, pest)


def judge_top_dressing(subject, did: str, today: date, evts: list[dict[str, Any]] | None = None,
                       prescriptions: list[dict[str, Any]] | None = None,
                       unreadable: list[str] | None = None) -> Envelope:
    ctx, env = _base(subject, did, today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    d = registry.get(did)
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", did, sid, as_of, missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일"}], result={"why": "기준점이 없다"})
    a = date.fromisoformat(anchor)
    day = (today - a).days
    t = _task(stage, d.params["task_key"])
    if t is None:
        return Envelope("판단 불가(지식)", did, sid, as_of, result={"why": "격자에 그 작업 칸이 없다"})
    wd = int(t["work_day"])
    deadline = _deadline_day(t)
    if deadline is None:
        return _no_deadline(did, sid, as_of, str(t.get("name", d.params["task_key"])))
    cert = subject.get("cert")
    if not cert:
        return _need_cert(did, sid, as_of)                                   # [B2] 필요 축 부재는 데이터 미비 — 빈 자재로 판단하지 않는다
    mats = t.get("materials")
    m = mats.get(cert, []) if isinstance(mats, dict) else []
    work_date, dl = (a + timedelta(days=wd)).isoformat(), (a + timedelta(days=deadline)).isoformat()
    # [B5] 판별 순서(I-1 §3): 해당하는가 → 지식 → 데이터. 창 지남을 먼저 본다 — 전에는 지식 미비가 먼저라 시즌 내내 그 상태로 남았다
    if day > deadline:
        return Envelope("해당 없음", did, sid, as_of, result={"why": f"마감({dl})을 지났다", "summary": f"웃거름 때가 지났습니다 — 마감 {dl}"})
    if did == "top_dressing_2":
        return Envelope("판단 불가(지식)", did, sid, as_of,
                        result={"why": "'필요 시' 의 필요 여부 판정 규칙이 격자에 미채움(생육 관찰 기준 없음)", "work_date": work_date, "deadline": dl,
                                "materials": m, "summary": f"줄지 말지 가르는 기준이 아직 없습니다 — 때 {work_date}~{dl} · 자재({cert}) {', '.join(m) or '없음'}"})
    # [B3] 이행 판정은 계획 대 실제와 **한 벌** — 같은 매처 · 같은 허용 폭(registry params). 전에는 wd-7 하드코딩 · 예정 경계가 달라
    # 같은 사건이 한쪽은 이행, 다른 쪽은 미이행이었다
    pva = registry.get(plan_vs_actual.DECISION_ID)
    row = {"task": t.get("name", d.params["task_key"]), "work_date": work_date, "deadline_date": dl}
    hit = plan_vs_actual._matched_event(row, list(evts or []), int(pva.params["tolerance_days"]), pva.params)
    done = [hit] if hit else []
    reason = plan_vs_actual.reason_for(list(evts or []), row["task"], work_date)   # 불이행 사유도 계획 대 실제와 같은 키 — 한 벌
    status = "이행" if done else ("사유 기록됨" if reason else ("예정" if day < wd else "미이행"))
    p = _prescription(prescriptions)
    inputs = _anchor_inputs(subject, anchor)
    if p is not None:
        amount = _amounts(p, "post") or "처방에 추비 값 없음"
        amount_note = f"추비 {amount} (kg/10a, {p['source']})" + (" — 유기 갈래는 목표 양분량(자재 환산 규칙 정본 없음)" if cert == "유기" else "")
        inputs = inputs + [_prescription_input(p)]
    elif unreadable:
        # [U-21] 웃거름은 창·자재를 여전히 '판단함' 으로 낸다(양만 못 낸다) — 그래서 등급 대신 **문면**으로 가른다.
        amount_note = (f"판단 불가(데이터) — 처방 정본이 **있는데 읽지 못했다**(파일 {len(unreadable)}건: {' · '.join(unreadable)}). "
                       "없는 것이 아니다 — 다시 받으면 된다(python -m ingest.fertilizer <주소>) · /changes 에 사유")
    else:
        amount_note = "판단 불가(지식) — 처방 정본 미도착(python -m ingest.fertilizer <주소>)"
    return Envelope("판단함", did, sid, as_of, inputs=inputs, grade=weakest(["관측", _grid_grade(unit)]),
                    revisit_at=(today + timedelta(days=1)).isoformat(),
                    result={"status": status, "work_date": work_date, "deadline": dl, "materials": m, "done_refs": [e.get("id") for e in done],
                            "amount": amount_note, "reason": (reason or {}).get("reason"), "reason_ref": (reason or {}).get("id"),
                            # [U-21] 요약이 카드에서 읽히는 줄이다 — 여기서도 '없다' 와 '있는데 못 읽었다' 를 가른다.
                            # 안 가르면 판정 종류만 고치고 **사람이 보는 문장은 그대로**인 표현 층 결함이 된다(G1 세 번째 형태).
                            "summary": f"{status} — 작업일 {work_date} · 마감 {dl} · 자재({cert}) {', '.join(m) or '없음'} · "
                                       + ("양 " + amount_note if p else ("양은 저장된 처방을 못 읽어 못 냅니다(다시 받으면 됩니다)" if unreadable else "양은 검정 처방이 오면 냅니다"))   # 농가 말(2026-09-29 전수)
                                       + (f" · 사유: {reason['reason'][:120]}" if reason else "")},
                    notes=[grid_schema.source_note(unit), "양(kg/10a)은 지어내지 않는다 — 처방 정본이 없으면 비운다"])


def judge_ship_or_store(subject, today: date, targets: list[dict[str, Any]] | None = None, harvest: Envelope | None = None) -> Envelope:
    ctx, env = _base(subject, "ship_or_store", today)
    if env:
        return env
    unit, stage, sid, as_of = ctx
    use = str(subject.get("use") or "")
    if subject.get("mall_supply") is False or any(w in use for w in SELF_USE_WORDS):
        return Envelope("해당 없음", "ship_or_store", sid, as_of, result={"why": f"이번 작기 용도 '{use or '자가'}'(D-8) — 출하 결정 대상 아님", "summary": f"이번 작기는 {use or '자가'} 용도라 출하·저장 판단이 없습니다"})
    tg = sorted((t for t in (targets or []) if t.get("target_date")), key=lambda t: t["target_date"])
    if not tg:
        return Envelope("판단 불가(데이터)", "ship_or_store", sid, as_of,
                        missing=[{"axis": "plan.target_date", "who_can_fill": "농가 — 납품 계획일(채팅: '10월 30일 납품 예정')"}],
                        result={"why": "납품 계획일이 없다", "summary": "납품 계획일이 없습니다 — 채팅에 '10월 30일 납품 예정' 처럼 한 줄"})
    if harvest is None or harvest.kind != "판단함":
        return Envelope("판단 불가(데이터)", "ship_or_store", sid, as_of, missing=[{"axis": "anchor", "who_can_fill": "수확 시기 판정이 먼저"}],
                        result={"why": "수확 창이 없다"})
    target = date.fromisoformat(tg[0]["target_date"])
    h_end = date.fromisoformat(harvest.result["window_end"])
    store_days = (target - h_end).days
    t = _task(stage, "출하")
    deadline = _deadline_day(t)   # 마감을 읽는 법은 한 벌 — 네 결정이 같은 함수를 쓴다
    if deadline is None:
        # [B6 코드 쪽 2026-09-20] 전에는 63 을 기본값으로 메웠다(하드코딩 · 대리값 금지 위반) — 격자에 마감이 없으면 지식 미비다
        return Envelope("판단 불가(지식)", "ship_or_store", sid, as_of,
                        result={"why": "격자 칸 5 '출하 또는 단기 저장' 작업에 마감(retry.deadline_day)이 없다 — 값을 지어내지 않는다", "summary": "출하 마감이 기준에 없습니다 — 지어내지 않습니다"})
    a = date.fromisoformat(subject["anchor"])
    caps = []
    if target > a + timedelta(days=deadline):
        caps.append({"name": "단기 저장 한계", "basis": f"칸 5 '출하 또는 단기 저장' 마감 {deadline}일({(a + timedelta(days=deadline)).isoformat()})을 계획일이 넘는다"})
    notes = [grid_schema.source_note(unit)]
    h_to = int(stage["window"]["to_day"])
    if deadline < h_to:
        # 격자 자체 모순(코드 평가 B6): 출하 마감이 수확 창 끝보다 앞이면 창 끝에 수확한 것은 출하 마감을 이미 넘긴다. 지식 결함이라 여기서
        # 고치지 않고(검토지 ⓓ B6 발행자 답), 봉투에 그 사실을 남긴다 — 상한 제약이 그 모순에서 나온 것임을 읽는 쪽이 알게
        notes.append(f"격자 자체 모순(B6): 출하 마감 {deadline}일 < 수확 창 끝 {h_to}일 — 창 끝 수확분은 마감을 넘긴다. 검토지 ⓓ B6 답 대기")
    verdict = "출하(저장 없이)" if store_days <= 0 else f"단기 저장 {store_days}일 뒤 출하"
    return Envelope("판단함", "ship_or_store", sid, as_of, inputs=list(harvest.inputs), grade=weakest([str(harvest.grade), _grid_grade(unit)]), caps=caps,
                    result={"target_date": target.isoformat(), "harvest_window_end": h_end.isoformat(), "store_days": store_days, "ship_deadline_day": deadline,
                            "summary": f"{verdict} — 계획일 {target}"}, notes=notes)


def _symptom_rules(unit: dict[str, Any], key: str, orders: tuple[int, ...]) -> list[dict[str, Any]]:
    return [r for s in unit.get("stages", []) if s.get("order") in orders and isinstance(s.get(key), list) for r in s[key] if isinstance(r, dict)]


def _rule_words(rules: list[dict[str, Any]]) -> tuple[str, ...]:
    out: list[str] = []
    for r in rules:
        sy = r.get("symptoms")
        if not isinstance(sy, list):          # 문자열 하나면 글자 단위로 돌아 '노'·'랗' 이 어휘가 된다 — 목록만 읽는다(검증기가 먼저 거부한다)
            continue
        for w in sy:
            if isinstance(w, str) and w and w not in out:
                out.append(w)
    return tuple(out)


def _unit_id(subject: dict[str, Any], unit: dict[str, Any]) -> str:
    return str(subject.get("grid_unit") or (unit.get("unit") or {}).get("id") or "")     # 격자 id 는 unit.unit.id


def symptom_words_for(subject: dict[str, Any]) -> tuple[str, ...]:
    """이 재배 단위의 격자 규칙(symptom_rules)이 아는 증상 어휘. 규칙이 없거나 격자를 못 읽으면 ().

    [어휘 한 벌 2026-09-27] 채팅의 라우팅 목록(1층 정본)과 격자 규칙의 어휘가 **두 벌**이었다 — 발행자가 규칙에 라우팅 목록
    밖의 말(예: "하얗")을 쓰면 규칙은 맞는데 채팅이 증상 물음으로 보지 않아 문이 안 열린다(직렬 게이트의 앞 문). 1층은 이 목록을
    **덧붙여** 쓴다 — 규칙이 아는 말은 정본이 하나(격자)다.
    """
    unit, miss = grid_schema.load_unit(subject)
    if miss is not None:
        return ()
    d = registry.get("symptom_triage")
    return _rule_words(_symptom_rules(unit, d.params["rules_key"], tuple(d.params["stage_orders"])))


def judge_symptom_triage(subject, today: date, observations: list[dict[str, Any]] | None = None) -> Envelope:
    """[D-18 자리] 증상 → 원인 후보. 지식(격자 symptom_rules)이 없으면 어디가 비었는지 말하고, 있으면 후보 + 확인 하나(단정 없음)."""
    did, sid, as_of = "symptom_triage", subject.get("id", "?"), _now()
    unit, miss = grid_schema.load_unit(subject)
    if miss is not None:
        return units.envelope_for(miss, did, sid, as_of)
    d = registry.get(did)
    key, orders, lookback = d.params["rules_key"], tuple(d.params["stage_orders"]), int(d.params["lookback_days"])
    rules = _symptom_rules(unit, key, orders)
    uid = _unit_id(subject, unit)                                          # 문면에 격자 이름과 고칠 파일을 함께
    where = f"격자 {uid} 칸 {'·'.join(str(o) for o in orders)} 의 {key}"
    if not rules:
        return Envelope("판단 불가(지식)", did, sid, as_of,
                        result={"why": f"{where}(증상 → 원인 후보 · 확인) 미채움 — D-18 발행자 결정 대기 · 고칠 파일 {grid_schema.unit_file_name(uid)}",
                                "summary": "증상에서 원인을 좁히는 기준이 아직 없습니다 — 기준이 서면 원인 후보와 먼저 할 확인 하나를 냅니다"})
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", did, sid, as_of, missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일"}], result={"why": "기준점이 없다"})
    since = (today - timedelta(days=lookback)).isoformat()
    obs = [o for o in (observations or []) if (o.get("observed_at") or "")[:10] >= since]
    # 어휘는 _rule_words 와 같은 규율로 읽는다(str 목록만) — `symptoms: "노랗"` 이 글자 단위로 매칭되는 형태를 판정기에서도 막는다(검증기와 짝)
    hits = [(r, [o for o in obs if any(w in (o.get("text") or "") for w in _rule_words([r]))]) for r in rules]
    hits = [(r, m) for r, m in hits if m]
    if not hits:
        # [어휘 한 벌 2026-09-27] 관찰에 증상은 있는데 규칙 어휘와 안 맞는 것은 **지식**의 빈자리다 — "관찰이 없다" 로 내면 농가가 본 것을
        # 부정하는 문면이 된다(조건 탈락과 같은 급). 증상인지의 판정은 1층 정본 하나(chat.symptom_in)로 — 여기 목록을 두 벌째 두지 않는다.
        from ingest.chat import symptom_in                                 # 함수 안에서 — 3층이 1층 어휘를 판정에 쓰는 유일한 자리
        known = " · ".join(_rule_words(rules))
        if any(symptom_in(o.get("text") or "") for o in obs):
            return Envelope("판단 불가(지식)", did, sid, as_of,
                            result={"why": f"최근 {lookback}일 관찰 {len(obs)}건에 증상이 있으나 {where} 어휘({known})와 안 맞는다 — D-18 · "
                                           f"고칠 파일 {grid_schema.unit_file_name(uid)}",
                                    "summary": f"본 것이 기준이 아는 증상 말과 안 맞습니다 — 기준이 아는 말: {known}. 기준을 넓히면 원인 후보를 냅니다"})
        return Envelope("판단 불가(데이터)", did, sid, as_of,
                        missing=[{"axis": "observation", "who_can_fill": "농가 — 밭에서 본 것 한 줄(잎 색 · 시듦 · 무름 · 반점 …)"}],
                        result={"why": f"최근 {lookback}일 관찰에 증상 어휘가 없다 — 최종 심급은 농가 관찰", "summary": "본 것을 한 줄 적어 주시면 원인을 좁힙니다"})
    causes: list[dict[str, Any]] = []
    for r, _ in hits:
        for c in r.get("causes") or []:
            if isinstance(c, dict) and c.get("name") and c["name"] not in {x["name"] for x in causes}:
                causes.append({"name": c["name"], "check": c.get("check", ""), "recoverable": bool(c.get("recoverable", True))})
    causes.sort(key=lambda c: c["recoverable"])                      # 회복 불가 후보가 앞 — 확인이 급한 순
    first = next((r.get("first_check") for r, _ in hits if r.get("first_check")), None)
    seen_ids = [o.get("id") for _, m in hits for o in m]
    summary = "원인 후보: " + " · ".join(c["name"] for c in causes) + (f" — 먼저 {first}" if first else "") + " (좁히기이지 진단이 아니다)"
    return Envelope("판단함", did, sid, as_of, inputs=_anchor_inputs(subject, anchor), grade="추정", revisit_at=(today + timedelta(days=1)).isoformat(),
                    result={"candidates": causes, "first_check": first, "observations": seen_ids, "summary": summary},
                    notes=[grid_schema.source_note(unit), "원인 후보는 좁히기이지 진단이 아니다 — 확인 하나로 갈린다(격자 symptom_rules · D-18)"])


def _issued(iso: Any) -> str:
    """발표 시각을 농가 말로 — "09-28 05시". 기상청 발표 시각은 KST 로 정의된 사실이라(레코드에 +09:00 이 실려 있다) 변환 없이 글자만 다듬는다.
    화면의 기록 시각은 4층 `render.local_time` 몫이고 3층은 그 모듈을 부르지 않는다(층 규율)."""
    s = str(iso or "")
    if len(s) >= 16 and s[4] == "-" and s[10] == "T":
        return f"{s[5:10]} {s[11:13]}시"
    return s[:10]


def _fmt_forecast_hour(h: dict[str, Any]) -> str:
    """3시간 한 줄 — "· 06시 16℃ 흐림 비 60% 1.0mm 바람 2m/s". 없는 값은 비운다(대리값 없음).
    [발행자 2026-09-29 17시 *"단기예보는 격자형예보로 3시간 단위로 예보를 사용자에게 알려 줘야 한다"*]"""
    t = str(h.get("t") or "")
    parts = [f"{t[:2]}시" if len(t) >= 2 else t]
    if h.get("tmp") is not None:
        parts.append(f"{round(h['tmp'])}℃")
    sky = " ".join(w for w in (h.get("sky"), h.get("pty")) if w)
    if sky:
        parts.append(sky)
    if h.get("pop") is not None:
        parts.append(f"비 {int(h['pop'])}%")
    if h.get("pcp"):
        parts.append(f"{h['pcp']}mm")
    if h.get("wsd") is not None:
        parts.append(f"바람 {h['wsd']:g}m/s")
    return "· " + " ".join(parts)


def _fmt_forecast_day(x: dict[str, Any]) -> str:
    t = "" if x["tmin"] is None and x["tmax"] is None else f"{'' if x['tmin'] is None else round(x['tmin'])}~{'' if x['tmax'] is None else round(x['tmax'])}℃{'(시간대 값)' if x.get('approx') else ''}"
    p = "" if x["pop_max"] is None else f" 비 {int(x['pop_max'])}%"
    m = "" if not x.get("rain_mm") else f" {x['rain_mm']}mm"
    return f"{x['day'][5:]} {t}{p}{m}".strip()


def _fmt_tercile(t: dict[str, Any] | None, words: tuple[str, str, str]) -> str:
    if not t:
        return ""
    return " · ".join(f"{w} {t[k]:g}%" for w, k in zip(words, ("above", "normal", "below")))


def _fmt_outlook_period(x: dict[str, Any]) -> str:
    parts = [p for p in (("기온 " + _fmt_tercile(x.get("temp"), ("높음", "비슷", "낮음"))) if x.get("temp") else "",
                         ("강수 " + _fmt_tercile(x.get("precip"), ("많음", "비슷", "적음"))) if x.get("precip") else "") if p]
    return f"{x['from'][5:]}~{x['to'][5:]} {x['region']} " + " / ".join(parts)


def judge_forecast_citation(subject, today: date, forecast: list[dict[str, Any]] | None = None, why: str | None = None,
                            mid: list[dict[str, Any]] | None = None, mid_why: str | None = None,
                            outlook: list[dict[str, Any]] | None = None, outlook_why: str | None = None) -> Envelope:
    """[D-21] 사실 인용 — 가진 단기예보(오늘부터 params.days)를 그대로, 그 뒤는 중기예보(권역 · D+3~D+10)를 이어서, 그 뒤는 발행자가 등재한
    1·3개월 전망(수동 정본 — 확률 3분위)을 그대로. 없는 쪽은 못 받은 이유(why · mid_why · outlook_why — gather_* 가 준 문장)를 그대로 싣는다.
    셋 다 없으면 판단 불가(데이터)."""
    did, sid, as_of = "forecast_citation", subject.get("id", "?"), _now()
    d = registry.get(did)
    n = int(d.params["days"])
    last = (today + timedelta(days=n - 1)).isoformat()
    rows = sorted((r for r in (forecast or []) if r.get("kind") == "forecast.weather_daily" and r.get("for_day")), key=lambda r: r["for_day"])
    all_short = [r for r in rows if r["for_day"] >= today.isoformat()]
    rows = [r for r in all_short if r["for_day"] <= last]
    # [D-21 중기] 단기 창 **뒤**의 날만 — 발표일에 따라 D+3 이 단기 창과 겹치면 단기(격자 5km)가 이긴다. 오늘 이전 줄(어제 저녁 발표)도 버린다
    mrows = sorted((r for r in (mid or []) if r.get("kind") == "forecast.weather_mid" and r.get("for_day")), key=lambda r: r["for_day"])
    mrows = [r for r in mrows if r["for_day"] > last]
    # [발행자 실사용 2026-09-29 14시] 단기 09-29~10-01 · 중기 10-03~ — **10-02 가 어느 줄에도 없었다**(06시 발표 중기의 D+3 이 원천에 비어 줄이 안 섰고,
    # 단기는 창 3일에서 잘렸다). 두 지평 사이의 빈 날은 단기 원천에 더 있는 날(창 뒤 · 중기 시작 전)로 메우고, 그래도 없는 날은 **없다고 말한다**.
    gap_days: list[str] = []
    if mrows:
        first_mid = mrows[0]["for_day"]
        spill = [r for r in all_short if last < r["for_day"] < first_mid]
        rows += spill
        covered = {r["for_day"] for r in rows}
        d0, d1 = date.fromisoformat(last) + timedelta(days=1), date.fromisoformat(first_mid)
        gap_days = [x.isoformat() for x in (d0 + timedelta(days=i) for i in range((d1 - d0).days)) if x.isoformat() not in covered]
    # [D-21 장기] 발행자 등재분 — 오늘 뒤를 덮는 항목만(끝난 기간은 전망이 아니다). 원천을 부른 적 없는 값이라 source 가 publisher: 다
    lrows = sorted((r for r in (outlook or []) if r.get("kind") == "reference.climate_outlook" and r.get("period_to")), key=lambda r: (r["period_from"], r["period_to"]))
    lrows = [r for r in lrows if r["period_to"] >= today.isoformat()]
    short_reason = None if rows else ((why or "").strip() or f"오늘부터 {n}일 안의 예보 줄이 없다")
    mid_reason = None if mrows else ((mid_why or "").strip() or f"{last} 뒤의 중기예보 줄이 없다")
    long_reason = None if lrows else ((outlook_why or "").strip() or "오늘 뒤를 덮는 장기 전망 등재 없음")
    if not rows and not mrows and not lrows:
        reason = f"단기: {short_reason} · 중기: {mid_reason} · 장기: {long_reason}"
        return Envelope("판단 불가(데이터)", did, sid, as_of,
                        missing=[{"axis": "forecast", "who_can_fill": f"예보를 못 받았다 — {reason}"}],
                        result={"why": reason, "short_why": short_reason, "mid_why": mid_reason, "long_why": long_reason,
                                # [발행자 2026-09-29 "가독성"] 지평마다 한 줄 — 이유 셋을 한 줄로 이으면 휴대폰에서 못 읽는다
                                "summary": "\n".join(["예보를 받지 못해 날씨를 말할 수 없습니다", f"단기 — {short_reason}", f"중기 — {mid_reason}", f"장기 — {long_reason}"])})
    days: list[dict[str, Any]] = []
    for r in rows:
        v = r.get("values") or {}
        tmin, tmax = v.get("tmin"), v.get("tmax")
        approx = tmin is None or tmax is None                      # 발표 시각 뒤의 날은 TMN/TMX 가 없어 시간대 값으로 — 표기에 남긴다(대리값을 숨기지 않는다)
        days.append({"day": r["for_day"], "tmin": tmin if tmin is not None else v.get("tmin_from_tmp"), "tmax": tmax if tmax is not None else v.get("tmax_from_tmp"),
                     "pop_max": v.get("pop_max"), "rain_mm": v.get("rain_mm"), "approx": approx,
                     "hours": [h for h in (r.get("hours") or []) if isinstance(h, dict)]})      # 3시간 줄 — 원천 그대로(발행자 2026-09-29 17시)
    mdays: list[dict[str, Any]] = []
    for r in mrows:
        v = r.get("values") or {}
        sky = [str(h.get("sky")) for h in (r.get("am"), r.get("pm"), r.get("allday")) if isinstance(h, dict) and h.get("sky")]
        mdays.append({"day": r["for_day"], "tmin": v.get("tmin"), "tmax": v.get("tmax"), "pop_max": v.get("pop_max"),
                      "sky": " / ".join(dict.fromkeys(sky)) or None, "region": r.get("region"), "ta_region": r.get("ta_region")})

    inputs, parts, notes, cit = [], [], ["값은 원천 그대로다. 최저·최고가 없는 날은 시간대 값으로 표기했다(대리값을 숨기지 않는다)"], {}
    if rows:
        src, issued, res = rows[0].get("source") or "기상청 단기예보", rows[0].get("observed_at") or "", rows[0].get("resolution") or ""
        inputs.append(AxisUse("forecast", str(issued), str(src), str(res), "관측"))
        cit = {"source": src, "observed_at": issued, "resolution": res, "note": "기상청 단기예보 그대로 — 해석·권고 없음(경보는 위험 경보 몫 · D-21)"}
        # [발행자 2026-09-29 "이 날씨는 어느 지점을 말하는가"] 어느 자리의 예보인지를 줄에 싣는다 — 단기는 필지 좌표가 든 기상청 5km 격자 칸
        # [발행자 2026-09-29 "가독성이 떨어진다 — 시간과 날짜 단위로 줄바꿈"] 지평 머리 한 줄 + 날마다 한 줄. ' · ' 로 잇던 줄은 휴대폰에서 못 읽었다
        parts.append(f"단기 — 기상청 단기예보 · 필지 자리 5km 예보 구역 · 3시간 단위 · 발표 {_issued(issued)}")   # '격자' 는 화면 낱말 표가 재배 달력으로 바꾼다 — 농가 말로
        for x in days:                                                   # 날 한 줄 + 그 아래 3시간마다 한 줄(원천이 3시간 단위다 — 하루로 접지 않는다)
            parts.append(_fmt_forecast_day(x))
            parts += [_fmt_forecast_hour(h) for h in x["hours"]]
    else:
        notes.append(f"단기예보는 못 받았다 — {short_reason}")
        parts.append(f"단기 — 못 받음: {short_reason}")
    for g in gap_days:
        notes.append(f"{g} 는 단기 창 뒤 · 중기 시작 전인데 두 원천 어느 쪽에도 값이 없다")
        parts.append(f"{g[5:]} 값 없음 — 단기 창 뒤 · 중기 시작 전(두 원천 어느 쪽에도 없음)")
    mcit = None
    if mrows:
        msrc, missued, mres = mrows[0].get("source") or "기상청 중기예보", mrows[0].get("observed_at") or "", mrows[0].get("resolution") or ""
        inputs.append(AxisUse("forecast", str(missued), str(msrc), str(mres), "관측"))
        ta_from = mrows[0].get("ta_region")
        mcit = {"source": msrc, "observed_at": missued, "resolution": mres, "region": mrows[0].get("region"), "ta_region": ta_from,
                "note": "기상청 중기예보(권역) 그대로 — 강수 확률은 오전·오후 중 큰 값 · 강수량은 중기에 없다"}
        where = str(mrows[0].get("region") or "권역") + (f" 권역 · 기온은 {ta_from} 기준" if ta_from else " 권역")   # 어느 자리인지(권역 · 빌린 기온 코드)
        parts.append(f"중기 — {where} · 기상청 중기예보 · 발표 {_issued(missued)}")
        parts += [_fmt_forecast_day(x) for x in mdays]
    else:
        notes.append(f"중기예보는 못 받았다 — {mid_reason}")
        parts.append(f"중기 — 못 받음: {mid_reason}")
    periods: list[dict[str, Any]] = []
    for r in lrows:
        v, c = r.get("values") or {}, r.get("citation") or {}
        periods.append({"from": r["period_from"], "to": r["period_to"], "type": r.get("period_type"), "region": r.get("region"),
                        "temp": v.get("temp"), "precip": v.get("precip"), "title": c.get("title"), "url": c.get("url"), "issued": r.get("observed_at")})
    lcit = None
    if lrows:
        lsrc, lissued = lrows[0].get("source") or "publisher:kma_outlook", lrows[0].get("observed_at") or ""
        inputs.append(AxisUse("forecast", str(lissued), str(lsrc), "region:" + " · ".join(dict.fromkeys(str(p["region"]) for p in periods)), "관측"))
        lcit = {"source": lsrc, "observed_at": lissued, "note": "기상청 1·3개월 전망 — 발행자가 발표문 수치를 출처와 함께 등재한 것(확률 3분위) · 시스템이 원천을 부른 적 없다 · 해석·권고 없음"}
        parts.append("장기 — " + " · ".join(dict.fromkeys(str(p["type"]) + " 전망" for p in periods)) + f" · 등재 정본 · 발표 {str(lissued)[:10]}")
        parts += [_fmt_outlook_period(p) for p in periods]
    else:
        notes.append(f"장기 전망은 없다 — {long_reason}")
        parts.append(f"장기 — 없음: {long_reason}")
    return Envelope("사실 인용", did, sid, as_of, inputs=inputs, revisit_at=(today + timedelta(days=1)).isoformat(),
                    result={"citation": cit or {"source": None, "observed_at": None, "resolution": None, "note": f"단기예보 없음 — {short_reason}"},
                            "days": days, "short_why": short_reason, "gap_days": gap_days,
                            "mid": {"citation": mcit, "days": mdays, "why": mid_reason},
                            "long": {"citation": lcit, "periods": periods, "why": long_reason},
                            # [표현 2026-09-28] 단기 · 중기 · 장기는 줄을 나눈다 — 한 줄로 이으면 380자가 넘어 휴대폰에서 못 읽는다(채팅 말풍선은 pre-wrap · 줄이 산다)
                            "summary": "\n".join(parts)},
                    notes=notes)


def judge_drought_alert(subject, today: date, evts: list[dict[str, Any]] | None = None, observations: list[dict[str, Any]] | None = None,
                        obs_rain: list[dict[str, Any]] | None = None, obs_rain_why: str | None = None) -> Envelope:
    """[D-20 자리] 가뭄 · 관수 판단. 임계(격자 칸 drought_rules)가 없으면 어디가 비었는지와 지금 칸의 수분 값을 말하고, 있으면 마지막 비·관수 뒤 날수로 낸다.
    마지막 비 온 날의 원천은 셋 — 농가의 비 관찰(chat.rain_in) · 관수 사건 · **기상청 지난 일강수**(obs_rain · 발행자 2026-09-29). 셋 중 가장 최근 날."""
    did, sid, as_of = "drought_alert", subject.get("id", "?"), _now()
    unit, miss = grid_schema.load_unit(subject)
    if miss is not None:
        return units.envelope_for(miss, did, sid, as_of)
    anchor = subject.get("anchor")
    if not anchor:
        return Envelope("판단 불가(데이터)", did, sid, as_of, missing=[{"axis": "anchor", "who_can_fill": "농가 — 파종일"}], result={"why": "기준점이 없다"})
    a = date.fromisoformat(anchor)
    day = (today - a).days
    stage = grid_capture.stage_for_day(unit, day)
    if stage is None:
        return Envelope("해당 없음", did, sid, as_of, result={"why": f"기준점 후 {day}일에 열린 격자 칸이 없다"})
    d = registry.get(did)
    key, lookback = d.params["rules_key"], int(d.params["lookback_days"])
    uid = _unit_id(subject, unit)
    water = stage.get("water")
    if not isinstance(water, dict):
        return Envelope("판단 불가(지식)", did, sid, as_of, result={"why": f"격자 {uid} 칸 {stage.get('order')} 의 water 미채움 · 고칠 파일 {grid_schema.unit_file_name(uid)}",
                                                                     "summary": "이 칸의 수분 요구가 기준에 없어 가뭄을 판단할 수 없습니다"})
    water_txt = f"수분 요구 {water.get('demand')} · 결핍 민감 {water.get('deficit_sensitivity')} · 과습 민감 {water.get('excess_sensitivity')}"   # [2026-09-30] 과습도 함께 — 4단계는 과습이 회복 불가라 관수 검토 줄에 그 경계가 보여야 한다
    rules = stage.get(key)
    if not (isinstance(rules, dict) and isinstance(rules.get("dry_days"), int)):
        return Envelope("판단 불가(지식)", did, sid, as_of,
                        result={"why": f"격자 {uid} 칸 {stage.get('order')} 의 {key}(무강수 임계 일수) 미채움 — D-20 · 고칠 파일 {grid_schema.unit_file_name(uid)} · 지금 칸 {water_txt}",
                                "summary": f"가뭄을 판단할 기준(무강수 며칠)이 아직 없습니다 — 지금 칸은 {water_txt}. 기준이 서면 관수 검토 여부를 냅니다"})
    threshold = int(rules["dry_days"])
    wet_mm = float(rules.get("wet_mm", d.params["wet_mm"]))                # 비 온 날의 기준 — 격자(발행자)가 있으면 그것, 없으면 기상청 강수일 정의
    window = max(lookback, threshold)                                      # [2026-09-30] 임계가 30보다 크면 창도 그만큼 — 창이 임계보다 짧으면 그 사이의 비 온 날이 버려진다
    since = (today - timedelta(days=window)).isoformat()
    from ingest.chat import rain_in                                        # 비 어휘 정본은 1층 하나(증상 어휘와 같은 규율)
    wet: list[tuple[str, str]] = [(str(o.get("observed_at") or "")[:10], "농가 관찰") for o in (observations or []) if rain_in(o.get("text") or "")]
    irr = str(d.params["irrigation_event"])
    wet += [(str(e.get("observed_at") or "")[:10], "관수") for e in (evts or []) if e.get("kind") == "event" and e.get("type") == irr]
    obs_rows = [r for r in (obs_rain or []) if r.get("kind") == "observation.weather_daily"]
    stn = next((r.get("station") for r in obs_rows if r.get("station") is not None), None)
    wet += [(str(r.get("observed_at") or "")[:10], f"기상청 관측 지점 {stn}") for r in obs_rows
            if (r.get("values") or {}).get("rn_day_mm") is not None and float(r["values"]["rn_day_mm"]) >= wet_mm]
    wet = [(w, src) for w, src in wet if w and since <= w <= today.isoformat()]
    inputs = _anchor_inputs(subject, anchor)
    notes = [grid_schema.source_note(unit), "관수 검토는 권고이지 양·방법이 아니다 — 임계는 격자 drought_rules(D-20 · 발행자 정본)",
             f"임계 {threshold}일 — 출처: {rules.get('source') or '적히지 않음'}"]      # [2026-09-30] 출처가 추론이면 그 표시가 답까지 간다(맞다가 눌려도 추론이 정본으로 승격되지 않게)
    if obs_rows:
        inputs.append(AxisUse("precip", str(obs_rows[0].get("fetched_at") or ""), str(obs_rows[0].get("source") or ""), str(obs_rows[0].get("resolution") or ""), "관측"))
        notes.append(f"기상청 지난 일강수 {len(obs_rows)}일 읽음(지점 {stn}) · 비 온 날 = 일강수 {wet_mm:g}mm 이상")
    else:
        notes.append(f"기상청 지난 일강수 없음 — {obs_rain_why or '이유 없음'}")
    if not wet:
        # 기상청 관측이 뒤돌아본 날에 비가 없었고 그 날수가 임계 이상이면 그것도 사실이다 — 무강수 N일 이상(원천이 있는데 묻지 않는다).
        # [2026-09-29] 관측은 임계 날수만 보면 된다(run.drought_days_needed) — 30일을 다 불러야 판정하던 것을 임계 이상이면 판정으로
        obs_days = {str(r.get("observed_at") or "")[:10] for r in obs_rows}
        covered = len(obs_days)
        if obs_days and covered >= threshold:
            last_wet, dry, src = None, covered, f"기상청 관측 지점 {stn}"
            summary = f"최근 {covered}일 동안 비도 관수 기록도 없습니다({src}) — 무강수 {covered}일 이상, 임계 {threshold}일 이상: 관수 검토 · {water_txt}"
            return Envelope("판단함", did, sid, as_of, inputs=inputs, grade="추정", revisit_at=(today + timedelta(days=1)).isoformat(),
                            result={"dry_days": dry, "threshold": threshold, "last_wet": None, "wet_source": src, "due": True, "water": dict(water), "summary": summary}, notes=notes)
        return Envelope("판단 불가(데이터)", did, sid, as_of,
                        missing=[{"axis": "precip", "who_can_fill": "농가 — 마지막으로 비 온 날 또는 관수한 날 한 줄"}],
                        result={"why": f"최근 {window}일에 비 관찰도 관수 사건도 없고 기상청 관측도 {'비 온 날이 없다(' + str(len(obs_days)) + '일만 받음)' if obs_days else '없다 — ' + (obs_rain_why or '')} — 무강수 일수를 셀 수 없다",
                                "summary": f"마지막으로 비 온 날이나 관수한 날을 알면 판단합니다 — 지금 칸은 {water_txt}"}, notes=notes)
    last_wet, src = max(wet)
    dry = (today - date.fromisoformat(last_wet)).days
    due = dry >= threshold
    summary = (f"마지막 비·관수 {last_wet}({src}) 뒤 무강수 {dry}일 — 임계 {threshold}일 {'이상: 관수 검토' if due else '미만: 아직 관수 판단 아님'} · {water_txt}")
    return Envelope("판단함", did, sid, as_of, inputs=inputs, grade="추정", revisit_at=(today + timedelta(days=1)).isoformat(),
                    result={"dry_days": dry, "threshold": threshold, "last_wet": last_wet, "wet_source": src, "due": due, "water": dict(water), "summary": summary},
                    notes=notes)


def judge_all(subject: dict[str, Any], today: date, evts=None, forecast=None, pest=None, harvest: Envelope | None = None,
              prescriptions: list[dict[str, Any]] | None = None, unreadable: list[str] | None = None,
              said: list[dict[str, Any]] | None = None, forecast_why: str | None = None,
              mid: list[dict[str, Any]] | None = None, mid_why: str | None = None,
              outlook: list[dict[str, Any]] | None = None, outlook_why: str | None = None,
              obs_rain: list[dict[str, Any]] | None = None, obs_rain_why: str | None = None) -> list[Envelope]:
    evts = evts or []
    obs = [e for e in evts if e.get("kind") == "observation.note"]
    targets = [e for e in evts if e.get("kind") == "plan.target_date"]
    # [D-18 직렬 게이트 2026-09-27] 방금 물으신 말(said · 원장에 없다)은 **증상 결정만** 읽는다 — 재파종 판단은 저장된 관찰만
    said_obs = [e for e in (said or []) if e.get("kind") == "observation.note"]
    return [judge_sowing_window(subject, today), judge_base_fertilization(subject, today, prescriptions, unreadable), judge_replant(subject, today, obs),
            judge_pest_alert(subject, today, forecast, pest), judge_top_dressing(subject, "top_dressing_1", today, evts, prescriptions, unreadable),
            judge_top_dressing(subject, "top_dressing_2", today, evts, prescriptions, unreadable), judge_drainage_alert(subject, today, forecast, pest),
            judge_ship_or_store(subject, today, targets, harvest), judge_forecast_citation(subject, today, forecast, forecast_why, mid, mid_why, outlook, outlook_why),
            judge_drought_alert(subject, today, evts, obs, obs_rain, obs_rain_why),
            judge_symptom_triage(subject, today, obs + said_obs)]
