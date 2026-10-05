# -*- coding: utf-8 -*-
# [U-17 안내 검증 2026-10-05] 세션이 발행자에게 **다섯 회차 동안** 같은 말을 했다: *"10/14 부터 매일 틀린 「수확 지연 — 회복 불가」 경보가 나갑니다"* ·
# *"아흐레 남았습니다"*. 그 말을 재지 않고 썼다. 재니 **틀렸다** — 잎 수확 기준 경보는 **10/07** 부터 나간다(이틀 뒤). 발행자가 그 줄만 믿었으면 **한 주를 놓쳤다**.
# 원인은 구조에 있었다(지어낸 숫자가 아니다): 위험 경보는 오늘이 속한 칸과 **horizon 안에 시작하는 다음 칸**을 본다(`risk_alert` params.horizon_days=7).
# 수확 칸 창이 심은 날 +50일(2026-10-14)에 열리므로 경보는 **창 − horizon = 10/07** 부터 선다.
#
# 이 검사가 고정하는 것은 **날짜가 아니라 계약**이다(날짜를 박으면 격자가 바뀔 때 거짓 실패한다):
#   ① 잎 수확 기준 위험 둘은 **창이 열리기 horizon 일 전부터** 나온다(안내가 말해야 하는 날은 그 날이다)
#   ② 용도가 「종구 생산」 이면 그 둘이 **아예 안 나온다**(수확 시기도 잎 기준으로 답하지 않는다 — 판단 불가(지식))
#   ③ 발행자에게 나가는 줄(대장 페이지 BEST)이 **그 날을 그대로** 말한다 — 안내와 측정이 어긋나면 여기서 터진다(U-17: 안내도 재고 나서 쓴다)
from __future__ import annotations

from datetime import date, timedelta

from grid import schema as grid_schema
from ingest import parcels, subjects
from judge import risk_alert, run as judge_run

SID = "p001-jjokpa-2026f"
LEAF_RISKS = ("수확 지연", "첫 서리")          # 잎 수확 기준 — 종구 재배에는 그대로 못 쓴다(기준이 재배 달력에 없다)


def _alerts(d: date) -> list[str]:
    e = next(x for x in judge_run.judgments_for(SID, today=d) if x.decision_id == "risk_alert")
    items = (e.result or {}).get("items") or (e.result or {}).get("alerts") or []
    return [str(x.get("risk") or x.get("name") or "") for x in items]


def _harvest_window_start() -> date:
    s = subjects.by_id(SID)
    unit, miss = grid_schema.load_unit(s)
    assert unit and not miss, miss
    stage = next(st for st in unit["stages"] if str(st.get("name", "")).strip() == "수확")
    return date.fromisoformat(s["anchor"]) + timedelta(days=int(stage["window"]["from_day"]))


def _horizon() -> int:
    """정본 하나에서 읽는다 — 검사에 7 을 박지 않는다(격자·결정이 바뀌면 안내가 먼저 틀린다)."""
    from judge import registry
    return int(registry.get(risk_alert.DECISION_ID).params["horizon_days"])


def test_the_leaf_harvest_alerts_start_a_horizon_before_the_window_opens():
    """안내가 말해야 하는 날은 **창이 열리는 날이 아니라 그 horizon 일 전**이다 — 그 차이가 이번에 한 주였다."""
    start, horizon = _harvest_window_start(), _horizon()
    first = start - timedelta(days=horizon)
    assert not any(any(k in a for k in LEAF_RISKS) for a in _alerts(first - timedelta(days=1))), "하루 전에는 아직 없어야 한다"
    assert all(any(k in a for a in _alerts(first)) for k in LEAF_RISKS), f"{first} 에 잎 수확 기준 경보 둘이 다 서야 한다"
    assert all(any(k in a for a in _alerts(start)) for k in LEAF_RISKS), "창이 열린 날에도 그대로"


def test_the_use_value_removes_exactly_those_alerts():
    """용도 한 줄이 무엇을 멎게 하는가 — 그 둘뿐이고, 과습(용도 무관)은 그대로다."""
    start, horizon = _harvest_window_start(), _horizon()
    day = start - timedelta(days=horizon)
    before = _alerts(day)
    assert any("과습" in a or "부패" in a for a in before)
    parcels.set_fields((subjects.by_id(SID) or {}).get("parcel"), use="종구 생산", overwrite=True)
    after = _alerts(day)
    assert not any(any(k in a for k in LEAF_RISKS) for a in after), after
    assert any("과습" in a or "부패" in a for a in after), "용도와 무관한 위험까지 사라졌다"
    ht = next(x for x in judge_run.judgments_for(SID, today=start) if x.decision_id == "harvest_timing")
    assert ht.kind == "판단 불가(지식)" and "종구" in str(ht.result or {}), "수확 시기가 잎 기준으로 답한다"


def test_the_line_we_send_the_publisher_names_the_measured_day():
    """U-17 — 발행자에게 나가는 줄이 **잰 날**을 말한다. 격자나 horizon 이 바뀌면 이 검사가 먼저 터지고, 안내를 다시 재게 만든다."""
    import importlib
    page = importlib.import_module("scripts.build_ledger_page")
    first = _harvest_window_start() - timedelta(days=_horizon())
    said = page.BEST["do"]["why_now"] + " " + page.BEST["do"]["if_not"]
    # **변별 표지**: 날짜만 찾으면 안내가 두 날짜를 다 말하므로(「창이 열리는 10/14 이 아니라」) 어느 쪽을 시작일로 말하는지 못 가른다 —
    # 주입 A(horizon 0)가 그래서 한 번 통과했다(§7.1 4번 · 검사 문자열 겹침). 「그 날 **부터**」 꼴로 본다
    assert f"{first.month}/{first.day} 부터" in said, f"안내가 잰 시작일({first})을 「부터」 로 말하지 않는다 — {said[:90]}"
