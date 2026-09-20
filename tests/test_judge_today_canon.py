# -*- coding: utf-8 -*-
# [칸 3 재측정 · 2026-09-20 / 코드 평가 A11] 화면의 오늘 정본(config.today())은 닫았는데, **판정 층에 같은 형태가 그대로** 있었다.
#   `gather_pest` 가 연도를 `date.today().year` 로 스스로 정했고, `judge_all` 호출이 `today or date.today()` 로 한 번 더 메웠다.
#   고정(AGRODSS_TODAY) · 재현 · 과거 판정에서 같은 회차 안의 연도가 둘이 된다 — §7.5 '관문의 입력' 이 한 층 아래에 있던 것.
# 규율(발행자 2026-09-20): 정본을 세운 회차에 **소비자 배선을 전수로 센다**. 여기서는 judge 패키지가 대상이다.
from __future__ import annotations

import inspect
import re
from datetime import date
from pathlib import Path

from judge import run as judge_run

ROOT = Path(__file__).resolve().parent.parent


def _code(path: Path) -> str:
    """주석과 독스트링을 걷은 실행 코드. 둘 다 옛 꼴을 설명해 두므로 안 걷으면 자기 문면에 걸린다(§7.1 4번 — 이 세션에서 네 번)."""
    src = re.sub(r'\"{3}.*?\"{3}', "", path.read_text(encoding="utf-8"), flags=re.S)
    return "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())


def test_pest_source_takes_the_year_from_the_round_not_the_wall_clock(monkeypatch):
    seen = {}
    monkeypatch.setattr(judge_run.ncpms, "api_key", lambda: "k")
    monkeypatch.setattr(judge_run.ncpms, "fetch_forecast",
                        lambda crop, year: seen.update(year=year) or {"status": "no_data", "message": ""})
    judge_run.gather_pest({"crop": "쪽파"}, date(2024, 3, 1))
    assert seen["year"] == 2024, "예찰이 회차의 해가 아니라 실제 해를 물었다"


def test_judge_layer_decides_today_once():
    code = _code(ROOT / "judge" / "run.py")
    assert code.count("date.today()") == 1, "판정 층의 '오늘'은 한 자리에서만 정한다"
    body = code[code.index("def all_judgments"):]
    assert "date.today()" in body.split("\n out", 1)[0][:400], "정본 자리는 all_judgments 머리"
    # 소비자 전수 — 오늘을 받아야 하는 호출에 실제로 넘어가는가(인자를 안 넘기면 아래가 실제 날짜로 메운다)
    for call in ("gather_pest(", "judge_all(", "harvest_timing.judge(", "risk_alert.judge(", "plan_vs_actual.judge(", "material_citation.judge("):
        for m in re.finditer(re.escape(call), body):
            seg = body[m.end():m.end() + 260]
            assert re.search(r"\btoday\b", seg.split("\n\n", 1)[0]), f"{call} 에 오늘이 안 넘어간다"


def test_gather_pest_signature_requires_today():
    # 계약형 — 기본값을 두면 호출부가 안 넘겨도 조용히 통과한다(그 형태로 났던 결함이다)
    p = inspect.signature(judge_run.gather_pest).parameters
    assert "today" in p and p["today"].default is inspect.Parameter.empty
