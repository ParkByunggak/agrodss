# -*- coding: utf-8 -*-
# [U-17 처방 직후 전수 2026-10-05] 앞 묶음에서 안내의 **손으로 적은 날짜**가 다섯 회차를 흘렀다(「10/14 부터」 — 실제는 10/07). 그 자리만 고치고 닫으면 같은 결함이
# 다른 줄에서 또 흐른다(§7.5 지점 축) → 발행자 몫 줄 전부를 **흐르는 숫자** 꼴로 셌다. 하나 더 있었다: 가뭄 예시의 「무강수 4일」(2026-09-29 측정)이 열흘 낡아,
# 안내는 「아직 관수 판단 아님」 을 기다리라고 하는데 화면은 그 사이 「관수 검토」 로 바뀌어 있었다. 둘 다 같은 형태다 — **날마다 변하는 값을 안내에 박았다**.
#
# 이 검사가 고정하는 것: 발행자에게 나가는 줄에 ① 날마다 변하는 날수·건수를 박지 않는다(모양으로 쓴다 — 「무강수 N일」) ② 임계·상한처럼 **코드에 정본이 있는 값**은
# 그 정본과 같다(가뭄 임계는 격자에서 · 되묻기 상한은 질문 생성에서 읽는다). 날짜 하나(첫 경보일)는 `test_leaf_harvest_alert_lead` 가 따로 본다.
#
# [자기 도구 오류 — 같은 날 두 번] 고친 문면이 **옛 틀린 값을 인용**하면 이 검사가 눈먼다(§7.1 4번). 앞 묶음에서 한 번, 이 묶음을 쓰며 또 한 번 그렇게 썼다 —
# 그래서 아래 DRIFTING 은 "안내가 그 값을 **말하는가**" 를 보고, 인용이 필요하면 숫자 없이 쓴다(「이 줄의 날수가 열흘 낡아 있었다」).
from __future__ import annotations

import importlib
import re

import pytest

page = importlib.import_module("scripts.build_ledger_page")

# 날마다/회차마다 변하는 값 — 안내에 박으면 하루 뒤 거짓이 된다
DRIFTING = {
    "무강수 날수": r"무강수\s*\d+\s*일",
    "남은 날수": r"(아흐레|열흘|여드레|이레)\s*(남|뒤)",
    "결정 답 수": r"답\s*\d+\s*/\s*\d+",
    "경보 건수": r"경보\s*\d+\s*건",
    "관문 건수": r"관문\s*\d{3,4}",
}


def _publisher_text() -> str:
    rows = list(page.NEXT_PUBLISHER)
    return " ".join(h + " " + b for h, b in rows) + " " + " ".join(str(v) for v in page.BEST["do"].values())


@pytest.mark.parametrize("name,pat", sorted(DRIFTING.items()))
def test_the_publisher_rows_carry_no_number_that_drifts_with_the_calendar(name, pat):
    hits = re.findall(pat, _publisher_text())
    assert hits == [], f"{name}: 안내가 날마다 변하는 값을 박았다 — {hits} (모양으로 쓴다: 「무강수 N일」)"


def test_the_thresholds_in_the_guidance_match_their_canon():
    """임계·상한은 **코드에 정본이 있다** — 안내가 다른 숫자를 말하면 발행자가 다른 동작을 기다린다."""
    from grid import schema as grid_schema
    from ingest import questions, subjects
    said = _publisher_text()
    s = subjects.by_id("p001-jjokpa-2026f")
    unit, miss = grid_schema.load_unit(s)
    assert unit and not miss, miss
    dry = {int((st.get("drought_rules") or {}).get("dry_days")) for st in unit["stages"]
           if isinstance((st.get("drought_rules") or {}).get("dry_days"), int)}
    assert len(dry) == 1, f"칸마다 가뭄 임계가 다르다 — 안내가 한 숫자로 말할 수 없다: {dry}"
    days = dry.pop()
    assert f"임계 <b>{days}일</b>" in said or f"임계 {days}일" in said, f"안내의 가뭄 임계가 정본({days}일)과 다르다"
    assert f"반복 상한 {questions.REPEAT_CAP}" in said, "되묻기 상한이 정본과 다르다"


def test_the_counts_that_do_not_drift_are_still_right():
    """흐르지 않는 수치는 **맞아야** 한다 — 추론값 표(격자에서 셈) · 문장 목록의 기대 없는 줄(목록에서 셈)."""
    from datetime import date
    from grid import schema as grid_schema
    from frontend import selfcheck
    from ingest import subjects
    said = _publisher_text()
    unit, _ = grid_schema.load_unit(subjects.by_id("p001-jjokpa-2026f"))
    inf = [v for v in grid_schema.sourced_values(unit) if v.get("inference")]
    farmer = sum(1 for v in inf if v.get("fixable_by") == "농가")
    canon = sum(1 for v in inf if v.get("fixable_by") == "정본")
    assert f"{len(inf)}행" in said and f"농가 {farmer}" in said and f"기준 자료 {canon}" in said, (len(inf), farmer, canon)
    # [주입 E] 「열넷 in said」 만 보면 **다른 자리에 같은 말이 또 있어** 한쪽이 틀려도 통과한다(안내에 두 번 적혀 있다 · §7.1 4번).
    # [2026-10-06] 그 수를 이제 **생성기가 센다**(`probe_count`) — 셈말(열넷)이 아니라 숫자로 나간다. 그래서 축을 옮긴다(약화가 아니라 이동):
    #   ① 두 자리가 다 **센 값**을 말하는가(손으로 적었으면 정본을 움직여도 안 따라온다 — 그 축은 test_page_counts_are_measured 가 본다)
    #   ② 옛 셈말이 **다른 수**로 남아 있지 않은가(한 자리만 고치고 닫으면 두 수치가 어긋난다 — 이 검사가 원래 잡던 것)
    blank = selfcheck.utterances(date(2026, 10, 5), selfcheck.subject())["without_expected"]
    assert page.probe_count()["left"] == blank, (page.probe_count(), blank)
    assert said.count(f"{blank}줄") >= 2, f"기대 없는 줄({blank})을 말하는 자리가 둘이어야 한다 — 센 값이 두 자리에 다 실린다"
    TEENS = {"열하나": 11, "열둘": 12, "열셋": 13, "열넷": 14, "열다섯": 15, "열여섯": 16,
             "열일곱": 17, "열여덟": 18, "열아홉": 19, "스물": 20}
    stale = {w: n for w, n in TEENS.items() if w in said and n != blank}
    assert not stale, f"옛 셈말이 다른 수로 남아 있다 — {stale}(센 값은 {blank})"
