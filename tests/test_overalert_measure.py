# -*- coding: utf-8 -*-
# [칸 3 재측정 · 2026-09-20 / 코드 평가 A10] 과경보 판정이 `preds[-1]` 하나만 봤다.
#
# 예측 원장은 payload 가 **바뀔 때만** 한 줄이고, 같은 주장이 서 있는 동안은 `last_seen_at` 만 나아간다(A2).
# 그래서 창은 주장이 살아 있는 내내 늘어나고, 경보가 사라진 날 새 줄이 생겨 그것이 `preds[-1]` 이 된다.
# 곧 **창이 지난 예측은 언제나 마지막 줄이 아니다** — 과경보(회복 가능 위험의 빗나감)는 정상 운영에서 한 번도 안 재진다.
# 되먹임의 한 축이 죽어 있던 것이라 산출 오염(즉시 급): 자율진화가 "내가 과하게 경보한다"를 배울 통로가 그것뿐이다.
from __future__ import annotations

from datetime import date, datetime, timezone

from ingest import feedback as fb
from ingest import media
from judge import evolve

SID = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]["id"]
NOW = datetime(2026, 9, 19, tzinfo=timezone.utc)


def _alerts(*risks, level="경보", recoverable=True):
    return {"horizon_days": 7, "alerts": [{"level": level, "risk": r, "recoverable": recoverable} for r in risks]}


def _standing_then_gone():
    """경보가 며칠 서 있다가(같은 payload — last_seen_at 만 나아감) 사라진다(새 줄). 피해는 없다."""
    fb.record_prediction(SID, "risk_alert", "판단함", _alerts("과습 부패"), "2026-09-01", grade="추정", now=NOW)
    fb.record_prediction(SID, "risk_alert", "판단함", _alerts("과습 부패"), "2026-09-05", grade="추정", now=NOW)   # 같은 주장 — 창이 9/12 까지
    fb.record_prediction(SID, "risk_alert", "판단함", {"horizon_days": 7, "alerts": []}, "2026-09-06", grade="추정", now=NOW)


def test_overalert_is_measured_on_expired_claims_not_only_the_last_line():
    _standing_then_gone()
    out = evolve._measure_risk(SID, date(2026, 9, 19), events=[])
    misses = [o for o in out if o["verdict"] == "빗나감"]
    assert misses, "창이 지난 경보에 피해가 없는데 과경보 판정이 없다 — 마지막 줄만 보고 있다"
    assert any("과습 부패" in o["detail"] for o in misses)


def test_unrecoverable_overalert_stays_uncomparable_on_expired_claims():
    # 비대칭(H)은 넓힌 뒤에도 그대로 — 회복 불가 위험의 과경보는 빗나감이 아니다
    fb.record_prediction(SID, "risk_alert", "판단함", _alerts("첫 서리", recoverable=False), "2026-09-01", grade="추정", now=NOW)
    fb.record_prediction(SID, "risk_alert", "판단함", {"horizon_days": 7, "alerts": []}, "2026-09-06", grade="추정", now=NOW)
    out = evolve._measure_risk(SID, date(2026, 9, 19), events=[])
    assert any(o["verdict"] == "대조 불가" and "첫 서리" in o["detail"] for o in out)
    assert not any(o["verdict"] == "빗나감" and "첫 서리" in o["detail"] for o in out)


def test_a_claim_still_standing_is_not_judged_early():
    # 반대편 — 창이 안 지난 주장에는 아무것도 적지 않는다(막는 것을 검사하면 통과하는 것도 검사한다)
    fb.record_prediction(SID, "risk_alert", "판단함", _alerts("과습 부패"), "2026-09-18", grade="추정", now=NOW)
    out = evolve._measure_risk(SID, date(2026, 9, 19), events=[])
    assert not out, "창이 아직 안 지났는데 판정했다"


def test_measuring_twice_does_not_write_twice():
    _standing_then_gone()
    first = evolve._measure_risk(SID, date(2026, 9, 19), events=[])
    again = evolve._measure_risk(SID, date(2026, 9, 19), events=[])
    assert first and not again, "같은 판정을 두 번 적었다 — 개선 항목이 중복으로 붇는다"
