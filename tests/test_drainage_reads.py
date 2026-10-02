# -*- coding: utf-8 -*-
# [WO-ASK-01 결정 ① 「가」 · 발행자 2026-10-03 "결정은 필지 필드(parcel.drainage)로 받는 쪽이 맞습니다 … 속성이 주, 관측이 보조입니다"]
#
# 검토(docs/wo_ask01_review_20261002.md §2-①)가 잰 것: 위험 경보의 과습 근거는 **예보 강수 합만** 봤고 soil_water 축은 이름만 있었다 —
# 배수 답이 돌아갈 축이 없었다. 처방: 필지의 배수 등급(parcel.drainage → 재배 단위에 붙는 PARCEL_FIELDS_TO_LAYER3)을 과습 위험의
# **근거**에 싣는다. 등급(주의/경보)은 **안 바꾼다** — "나쁨이면 경보로 올린다" 는 임계 규칙이고 그것은 발행자 몫이다(대리 규칙 금지).
# 그래서 drainage 는 STORED_ONLY 에서 READ_BY_JUDGMENT 로 옮겨 갔고(test_input_has_a_consumer 가 그 이동을 요구한다 — 소비자가 생긴 증거),
# 값이 없으면 그 사실을 메모에 말한다(§3 질문 생성이 출발할 자리 — 배선 뒤 질문 문면).
from __future__ import annotations

from datetime import date

from ingest import media, parcels
from judge import risk_alert as A
from judge import stage_decisions as SD

SID = "p001-jjokpa-2026f"
SUBJ = next(s for s in media.load_subjects() if s["id"] == SID)
T34 = date(2026, 9, 28)        # 기준점 후 34일 — 칸 4(30~50) 열림 · 과습 위험은 회복 불가라 신호 없이도 '주의'


def _fc(day: str, rain: float) -> dict:
    return {"for_day": day, "observed_at": "2026-09-28T05:00:00+09:00", "source": "external:kma_vilagefcst",
            "resolution": "grid5km:69,107", "values": {"tmin": 10.0, "rain_mm": rain, "pop_max": 0}}


def _wet(env) -> dict:
    return next(a for a in env.result["alerts"] if "과습" in a["risk"])


def test_without_a_drainage_grade_the_wet_risk_says_what_it_needs():
    env = A.judge(dict(SUBJ), today=T34)
    w = _wet(env)
    assert w["level"] == "주의" and "needs" in w and "배수" in w["needs"] and "drainage" not in w
    assert any(n.startswith(A.DRAINAGE_NOTE_PREFIX) and "밭 정보" in n for n in env.notes)
    assert not any(i.axis == "soil_water" for i in env.inputs)


def test_the_drainage_grade_rides_the_basis_and_the_inputs_but_never_the_level():
    env = A.judge(dict(SUBJ, drainage="나쁨"), today=T34)
    w = _wet(env)
    assert w["level"] == "주의" and w["drainage"] == "나쁨" and "배수 나쁨" in w["basis"] and "needs" not in w
    assert any(i.axis == "soil_water" and i.resolution == "parcel" and i.source == "farmer" for i in env.inputs)
    assert any("발행자 규칙 대기" in n for n in env.notes)                 # 등급 규칙은 지어내지 않았다 — 그 사실을 답이 말한다
    # 신호가 있으면 경보 — 배수와 무관하게 같은 등급(배수 '좋음' 이 경보를 눌러 내리지도 않는다)
    fc = [_fc("2026-09-29", 60.0)]
    assert _wet(A.judge(dict(SUBJ, drainage="나쁨"), fc, today=T34))["level"] == "경보"
    assert _wet(A.judge(dict(SUBJ, drainage="좋음"), fc, today=T34))["level"] == "경보"
    assert _wet(A.judge(dict(SUBJ), fc, today=T34))["level"] == "경보"


def test_other_risks_do_not_carry_the_drainage_grade():
    env = A.judge(dict(SUBJ, drainage="나쁨"), today=T34)
    for a in env.result["alerts"]:
        if "과습" not in a["risk"]:
            assert "drainage" not in a and "needs" not in a and "배수" not in a["basis"], a


def test_the_drainage_note_stays_on_the_drainage_card_not_the_pest_card():
    """칸 카드는 위험 경보를 칸으로 자른다 — 배수 메모는 과습 위험이 있는 칸(4)에만 남고 병해충 칸(3)에는 안 붙는다."""
    s = dict(SUBJ, drainage="나쁨")
    d = SD.judge_drainage_alert(s, T34)
    assert d.kind == "판단함" and any(n.startswith(A.DRAINAGE_NOTE_PREFIX) for n in d.notes) and "drainage" in _wet(d)
    p = SD.judge_pest_alert(s, date(2026, 9, 18))           # 칸 3 열림(10~30일)
    assert p.kind == "판단함" and not any(n.startswith(A.DRAINAGE_NOTE_PREFIX) for n in p.notes)


def test_the_parcel_field_really_changes_a_judgment_now():
    """선언(FIELDS_READ_BY_JUDGMENT)이 사실인지 **동작으로** — 등록부에 배수를 적으면 배수 카드 봉투가 달라지고, 다른 결정은 그대로다."""
    def _bodies():
        raw = next(s for s in media.load_subjects() if s["id"] == SID)
        out = []
        for e in SD.judge_all(parcels.enrich_subject(raw, parcels.by_id("p001")), date(2026, 9, 21)):
            d = e.to_dict()
            d.pop("as_of")
            out.append((e.decision_id, repr(d)))
        return out
    before = _bodies()
    parcels.set_fields("p001", drainage="나쁨", overwrite=True)
    changed = [a for (a, b), (_, c) in zip(before, _bodies()) if b != c]
    assert changed == ["drainage_alert"], changed
    assert "drainage" in parcels.FIELDS_READ_BY_JUDGMENT and "drainage" not in parcels.FIELDS_STORED_ONLY
