# -*- coding: utf-8 -*-
# [B4 · 2026-09-20] '오늘 칸'의 정본은 grid.capture 하나다. 격자 창은 양끝 포함이라 경계일(10 · 30 · 50 · 70)은 두 칸에 걸친다 — 어느 칸이 맞는지는
# 검토지 ⓓ B4(지식)이고, 답이 오기 전의 약속은 "경계일은 앞 칸(첫 매치)". 판정기마다 창을 따로 비교하면 약속이 갈린다(실측: stage_for_day 는
# 칸 3, risk_alert 는 칸 3·4 — 같은 날 '오늘 칸'이 달랐다). 여기서는 약속이 한 곳에만 있고 소비자가 그것을 쓰는지를 고정한다.
from __future__ import annotations

import re
from pathlib import Path

from grid import capture, schema as grid_schema
from judge import risk_alert

ROOT = Path(__file__).resolve().parent.parent
UNIT = grid_schema.load(grid_schema.GRID_DIR / "jjokpa_autumn.json")
INCLUSIVE = re.compile(r'\["from_day"\]\s*<=\s*\w+\s*<=\s*\w+\["to_day"\]')


def test_the_promise_when_two_stages_overlap_is_the_earlier_one():
    """**계약**만 본다 — 겹치는 창 둘이면 앞 칸이 이긴다. 합성 격자로 재므로 **B4 답이 무엇이든 이 검사는 남는다**.

    [미리 걷기 2026-09-20] 전에는 계약과 **지금 격자의 상태**(경계일이 10·30·50·70 이고 칸 이름이 이것이다)를 한 검사에
    섞어 두었다. B4 답이 와서 겹침을 없애면 깨지는데, 깨진 이유가 '계약이 무너져서'가 아니라 '전제가 사라져서'다 —
    다음 사람이 계약을 약화하기 쉬운 형태다. 계약과 상태를 가른다.
    """
    synth = {"stages": [{"order": 1, "name": "앞 칸", "window": {"basis": "anchor", "from_day": 0, "to_day": 10}},
                        {"order": 2, "name": "뒤 칸", "window": {"basis": "anchor", "from_day": 10, "to_day": 20}}]}
    assert [s["name"] for s in capture.stages_open(synth, 10)] == ["앞 칸", "뒤 칸"]      # 양끝 포함이라 둘 다 열린다
    assert capture.stage_for_day(synth, 10)["name"] == "앞 칸"                            # 약속: 앞 칸
    assert capture.stage_for_day(synth, 11)["name"] == "뒤 칸"
    assert capture.stages_open(synth, 21) == [] and capture.stage_for_day(synth, 21) is None


def test_the_real_grid_today_still_has_overlapping_boundaries():
    """**상태**를 적어 둔다 — 지금 격자는 겹친다(검토지 ⓓ B4 미회신). 답이 와서 겹침이 사라지면 **이 검사만** 고친다.
    위 계약 검사는 그대로 선다 — 어느 쪽이 깨졌는지로 '지식이 바뀐 것'과 '계약이 무너진 것'을 가른다."""
    for day, earlier, later in ((10, "발아 · 출현", "생육 초기 (잎 2~4매)"), (30, "생육 초기 (잎 2~4매)", "생육 중기 · 비대"),
                                (50, "생육 중기 · 비대", "수확"), (70, "수확", "수확 후 · 후작")):
        open_ = [s["name"] for s in capture.stages_open(UNIT, day)]
        assert open_ == [earlier, later], (day, open_)                                   # 경계일은 두 칸이 열려 있다(격자 데이터 그대로)
        assert capture.stage_for_day(UNIT, day)["name"] == earlier                       # 약속: 앞 칸
    assert [s["name"] for s in capture.stages_open(UNIT, 25)] == ["생육 초기 (잎 2~4매)"]
    assert capture.stages_open(UNIT, 91) == [] and capture.stage_for_day(UNIT, 91) is None


def test_risk_alert_scopes_stages_through_the_same_canon():
    in_scope = risk_alert._stages_in_scope(UNIT, 30, 0)
    assert [s["name"] for s in in_scope] == [s["name"] for s in capture.stages_open(UNIT, 30)]   # 지평 0 이면 열린 칸과 같다
    assert capture.is_open({"from_day": 10, "to_day": 30}, 30) and not capture.is_open({"from_day": 10, "to_day": 30}, 31)
    assert not capture.is_open("N/A", 5)


def test_only_capture_compares_windows_inclusively():
    """소비자 전수 래칫 — 양끝 포함 창 비교(from_day <= day <= to_day)는 grid/capture.py 에만 있다(정본 세운 회차의 소비자 배선 전수)."""
    hits = []
    for rel in ("judge", "grid", "ingest", "frontend"):
        for py in (ROOT / rel).glob("*.py"):
            code = "\n".join(ln.split("#", 1)[0] for ln in py.read_text(encoding="utf-8").splitlines())
            if INCLUSIVE.search(code):
                hits.append(py.name)
    assert hits == ["capture.py"], hits
